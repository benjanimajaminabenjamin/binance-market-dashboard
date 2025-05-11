from flask import Flask, render_template, jsonify, request
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.identity import DefaultAzureCredential
import os
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ADX connection configuration
KUSTO_CLUSTER = "https://binance-monitor-adx.japaneast.kusto.windows.net"
KUSTO_DATABASE = "market_data"

def get_kusto_client():
    """Get a Kusto client using managed identity."""
    try:
        logger.info("Attempting to connect to ADX with managed identity")
        kcsb = KustoConnectionStringBuilder.with_aad_managed_identity(KUSTO_CLUSTER)
        client = KustoClient(kcsb)
        logger.info("Successfully connected to ADX")
        return client
    except Exception as e:
        logger.error(f"Error connecting to ADX with managed identity: {str(e)}")
        
        # Fallback to DefaultAzureCredential
        try:
            logger.info("Attempting to connect with DefaultAzureCredential")
            credential = DefaultAzureCredential()
            kcsb = KustoConnectionStringBuilder.with_azure_token_credential(KUSTO_CLUSTER, credential)
            client = KustoClient(kcsb)
            logger.info("Successfully connected to ADX with DefaultAzureCredential")
            return client
        except Exception as e2:
            logger.error(f"Error with DefaultAzureCredential: {str(e2)}")
            raise

@app.route('/')
def index():
    """Render the main dashboard page."""
    logger.info("Rendering index page")
    return render_template('index.html')

@app.route('/api/symbols')
def get_symbols():
    """Get available symbols from ADX."""
    logger.info("Fetching available symbols")
    try:
        client = get_kusto_client()
        query = """
        tick_data
        | summarize by symbol
        | order by symbol asc
        """
        
        logger.info("Executing symbol query")
        response = client.execute(KUSTO_DATABASE, query)
        symbols = [row['symbol'] for row in response.primary_results[0]]
        logger.info(f"Found {len(symbols)} symbols")
        return jsonify(symbols)
    except Exception as e:
        logger.error(f"Error fetching symbols: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/market-data')
def get_market_data():
    """Get market data for a specific symbol."""
    symbol = request.args.get('symbol', 'BTCUSDT')
    hours = int(request.args.get('hours', '1'))
    
    logger.info(f"Fetching market data for {symbol} over past {hours} hours")
    
    try:
        client = get_kusto_client()
        query = f"""
        tick_data
        | where symbol == '{symbol}'
        | where ['time'] > ago({hours}h)
        | project ['time'], price, quantity, is_buyer_maker, trade_id
        | order by ['time'] asc
        """
        
        logger.info("Executing market data query")
        response = client.execute(KUSTO_DATABASE, query)
        data = response.primary_results[0]
        logger.info(f"Retrieved {len(data)} data points")
        
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
        logger.error(f"Error fetching market data: {str(e)}")
        return jsonify({"error": str(e), "message": "Failed to retrieve market data"}), 500

@app.route('/api/system-status')
def get_system_status():
    """Get system status metrics."""
    logger.info("Fetching system status")
    
    try:
        client = get_kusto_client()
        query = """
        tick_data
        | where ['time'] > ago(1h)
        | summarize 
            count_1h = count(),
            symbols_1h = dcount(symbol),
            last_record = max(['time'])
        """
        
        logger.info("Executing system status query")
        response = client.execute(KUSTO_DATABASE, query)
        
        if len(response.primary_results[0]) == 0:
            logger.warning("No status data returned from ADX")
            return jsonify({
                "trades_last_hour": 0,
                "symbols_last_hour": 0,
                "last_record_time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                "minutes_since_last_record": 999,
                "status": "No data available"
            })
            
        status = response.primary_results[0][0]
        
        # Calculate time since last record
        last_record_time = status['last_record']
        now = datetime.utcnow()
        time_diff = now - last_record_time
        
        status_data = {
            "trades_last_hour": status['count_1h'],
            "symbols_last_hour": status['symbols_1h'],
            "last_record_time": last_record_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "minutes_since_last_record": time_diff.total_seconds() / 60
        }
        
        logger.info(f"System status: {status_data}")
        return jsonify(status_data)
    except Exception as e:
        logger.error(f"Error fetching system status: {str(e)}")
        return jsonify({
            "error": str(e),
            "message": "Failed to retrieve system status"
        }), 500

@app.route('/health')
def health_check():
    """Simple health check endpoint."""
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})

@app.errorhandler(404)
def page_not_found(e):
    logger.warning(f"404 error: {request.path}")
    return jsonify({"error": "Page not found", "path": request.path}), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"500 error: {str(e)}")
    return jsonify({"error": "Internal server error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')