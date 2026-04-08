param(
    [int]$BackendPort = 8140,
    [int]$FrontendPort = 3460
)

$ErrorActionPreference = 'Stop'
$apiOrigin = "http://127.0.0.1:$BackendPort"
$frontendUrl = "http://127.0.0.1:$FrontendPort/accounts"

$health = Invoke-WebRequest -UseBasicParsing "$apiOrigin/api/v1/health" -TimeoutSec 5
if ($health.StatusCode -ne 200) {
    throw "Backend health check failed with status $($health.StatusCode)"
}

$accounts = Invoke-WebRequest -UseBasicParsing $frontendUrl -TimeoutSec 5
if ($accounts.StatusCode -ne 200) {
    throw "Frontend /accounts failed with status $($accounts.StatusCode)"
}

if ($accounts.Content -notmatch [regex]::Escape($apiOrigin)) {
    throw "Frontend HTML does not inject expected API origin: $apiOrigin"
}

Write-Host "Backend health: $($health.Content)"
Write-Host "Frontend status: $($accounts.StatusCode)"
Write-Host "Injected API origin: $apiOrigin"
