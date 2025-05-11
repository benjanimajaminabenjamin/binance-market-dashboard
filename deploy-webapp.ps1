# Binance Market Dashboard - Direct Deployment
Write-Host "Binance Market Dashboard - Direct Deployment" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green

# Configuration
$RESOURCE_GROUP = "BinanceMonitor"
$WEBAPP_NAME = "binance-market-dashboard"
$SUBSCRIPTION_ID = "31a76efe-7f5f-4a0d-8871-155506657a50"  # Your subscription ID from the logs

# Make sure you're logged in and using the right subscription
Write-Host "Setting Azure subscription..." -ForegroundColor Yellow
az account set --subscription $SUBSCRIPTION_ID

# Package your application
Write-Host "Creating deployment package..." -ForegroundColor Yellow
if (Test-Path deploy.zip) {
    Remove-Item deploy.zip -Force
}

# Find files to include
$filesToZip = @()
foreach ($file in @("app.py", "requirements.txt")) {
    if (Test-Path $file) {
        $filesToZip += $file
    } else {
        Write-Host "Warning: $file does not exist, skipping" -ForegroundColor Yellow
    }
}

# Add directories
foreach ($dir in @("static")) {
    if (Test-Path $dir -PathType Container) {
        $filesToZip += $dir
    } else {
        Write-Host "Warning: $dir directory does not exist, skipping" -ForegroundColor Yellow
    }
}

# Create the zip file
Write-Host "Zipping files: $($filesToZip -join ', ')" -ForegroundColor Yellow
Compress-Archive -Path $filesToZip -DestinationPath deploy.zip -Force

# Deploy using the newer command
Write-Host "Deploying application..." -ForegroundColor Yellow
az webapp deploy --resource-group $RESOURCE_GROUP --name $WEBAPP_NAME --src-path deploy.zip --type zip

# Configure the runtime if needed
Write-Host "Configuring Python runtime..." -ForegroundColor Yellow
az webapp config set --resource-group $RESOURCE_GROUP --name $WEBAPP_NAME --linux-fx-version "PYTHON|3.9"

# Set the startup command
Write-Host "Setting startup command..." -ForegroundColor Yellow
az webapp config set --resource-group $RESOURCE_GROUP --name $WEBAPP_NAME --startup-file "python app.py"

# Configure environment variables
Write-Host "Setting environment variables..." -ForegroundColor Yellow
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $WEBAPP_NAME --settings `
    WEBSITES_PORT=8000 `
    KUSTO_CLUSTER="https://binance-monitor-adx.japaneast.kusto.windows.net" `
    KUSTO_DATABASE="market_data" `
    PYTHONPATH="/home/site/wwwroot" `
    SCM_DO_BUILD_DURING_DEPLOYMENT=true

Write-Host "Deployment process completed!" -ForegroundColor Green
Write-Host "Your application should be available at: https://$WEBAPP_NAME.azurewebsites.net" -ForegroundColor Cyan
Write-Host "Check the logs if you encounter any issues: https://$WEBAPP_NAME.scm.azurewebsites.net/api/logstream" -ForegroundColor Cyan