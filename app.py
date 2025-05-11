from flask import Flask, render_template, jsonify, request
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.identity import DefaultAzureCredential
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# ADX connection configuration
KUSTO_CLUSTER = "https://binance-monitor-adx.japaneast.kusto.windows.net"
KUSTO_DATABASE = "market_data"

def get_kusto_client():
    """Get a Kusto client using managed identity."""
    kcsb = KustoConnectionStringBuilder.with_aad_managed_identity(KUSTO_CLUSTER)
    return KustoClient(kcsb)

@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html')

@app.route('/api/symbols')
def get_symbols():
    """Get available symbols from ADX."""
    client = get_kusto_client()
    query = """
    tick_data
    | summarize by symbol
    | order by symbol asc
    """
    
    try:
        response = client.execute(KUSTO_DATABASE, query)
        symbols = [row['symbol'] for row in response.primary_results[0]]
        return jsonify(symbols)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/market-data')
def get_market_data():
    """Get market data for a specific symbol."""
    symbol = request.args.get('symbol', 'BTCUSDT')
    hours = int(request.args.get('hours', '1'))
    
    client = get_kusto_client()
    query = f"""
    tick_data
    | where symbol == '{symbol}'
    | where ['time'] > ago({hours}h)
    | project ['time'], price, quantity, is_buyer_maker, trade_id
    | order by ['time'] asc
    """
    
    try:
        response = client.execute(KUSTO_DATABASE, query)
        data = response.primary_results[0]
        
        # Format data for charting
        result = {
            "times": [],
            "prices": [],
            "volumes": [],
            "trades": []
        }
        
        for row in data:
            time_str = row['time'].strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            result["times"].append(time_str)
            result["prices"].append(row['price'])
            result["volumes"].append(row['quantity'])
            
        # Get latest trades
        latest_trades = data[-10:] if len(data) >= 10 else data
        result["latest_trades"] = [
            {
                "time": row['time'].strftime('%H:%M:%S'),
                "price": row['price'],
                "quantity": row['quantity'],
                "side": "Sell" if row['is_buyer_maker'] else "Buy"
            }
            for row in reversed(latest_trades)
        ]
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/system-status')
def get_system_status():
    """Get system status metrics."""
    client = get_kusto_client()
    query = """
    tick_data
    | where ['time'] > ago(1h)
    | summarize 
        count_1h = count(),
        symbols_1h = dcount(symbol),
        last_record = max(['time'])
    """
    
    try:
        response = client.execute(KUSTO_DATABASE, query)
        status = response.primary_results[0][0]
        
        # Calculate time since last record
        last_record_time = status['last_record']
        now = datetime.utcnow()
        time_diff = now - last_record_time
        
        return jsonify({
            "trades_last_hour": status['count_1h'],
            "symbols_last_hour": status['symbols_1h'],
            "last_record_time": last_record_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "minutes_since_last_record": time_diff.total_seconds() / 60
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)