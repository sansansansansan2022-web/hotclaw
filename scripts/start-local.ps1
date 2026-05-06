param(
    [int]$BackendPort = 8140,
    [int]$FrontendPort = 3460,
    [switch]$SkipBuild,
    [switch]$SkipStop
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot 'backend'
$frontendDir = Join-Path $repoRoot 'frontend'
$runtimeDir = Join-Path $repoRoot 'tmp\local-runtime'
$pidDir = Join-Path $runtimeDir 'pids'
$logDir = Join-Path $repoRoot 'output\local-runtime'
$backendPython = Join-Path $backendDir '.venv\Scripts\python.exe'
$apiOrigin = "http://127.0.0.1:$BackendPort"

function Ensure-Directory([string]$Path) {
    if (!(Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Resolve-NpmPath {
    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($npmCommand) { return $npmCommand.Source }
    $npmCommand = Get-Command npm -ErrorAction Stop
    return $npmCommand.Source
}

function Invoke-Checked([scriptblock]$Action, [string]$Label) {
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Start-DetachedCmd {
    param(
        [string]$WorkingDirectory,
        [string]$InnerCommand,
        [hashtable]$Environment
    )

    $environmentPrefix = ""
    if ($Environment) {
        $commands = @()
        foreach ($entry in $Environment.GetEnumerator()) {
            $commands += ('set "{0}={1}"' -f $entry.Key, [string]$entry.Value)
        }
        if ($commands.Count -gt 0) {
            $environmentPrefix = ($commands -join ' && ') + ' && '
        }
    }

    $launcher = ('start "" /min cmd.exe /c "cd /d {0} && {1}{2}"' -f $WorkingDirectory, $environmentPrefix, $InnerCommand)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'cmd.exe'
    $psi.Arguments = "/d /c $launcher"
    $psi.WorkingDirectory = $repoRoot
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $process = [System.Diagnostics.Process]::Start($psi)
    if (-not $process) {
        throw 'Failed to launch detached process'
    }
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$Attempts = 30,
        [int]$DelaySeconds = 2,
        [scriptblock]$Validator = $null
    )

    for ($index = 0; $index -lt $Attempts; $index++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                if (-not $Validator -or (& $Validator $response)) {
                    return $response
                }
            }
        } catch {
        }
        Start-Sleep -Seconds $DelaySeconds
    }

    throw "Timed out waiting for $Url"
}

function Resolve-ListenerPid([int]$Port, [int]$Attempts = 10) {
    for ($index = 0; $index -lt $Attempts; $index++) {
        $lines = cmd.exe /c "netstat -ano | findstr LISTENING | findstr :$Port" 2>$null
        foreach ($line in $lines) {
            if ($line -match ('^\s*TCP\s+\S+:{0}\s+\S+\s+LISTENING\s+(\d+)\s*$' -f $Port)) {
                return [int]$matches[1]
            }
        }
        Start-Sleep -Seconds 1
    }

    throw "Could not resolve listener PID for port $Port"
}

function Write-PidFile([string]$Path, [hashtable]$Payload) {
    ($Payload | ConvertTo-Json -Depth 4) | Set-Content -Path $Path
}

Ensure-Directory $runtimeDir
Ensure-Directory $pidDir
Ensure-Directory $logDir

if (!(Test-Path $backendPython)) {
    throw "Backend virtualenv python not found at $backendPython"
}

$npmPath = Resolve-NpmPath
$stopScript = Join-Path $PSScriptRoot 'stop-local.ps1'
if (-not $SkipStop -and (Test-Path $stopScript)) {
    & $stopScript -BackendPort $BackendPort -FrontendPort $FrontendPort -IncludeLegacy -Quiet
}

Push-Location $backendDir
try {
    Invoke-Checked { & $backendPython -m alembic upgrade head } 'alembic upgrade head'
    Invoke-Checked { & $backendPython -m alembic stamp head } 'alembic stamp head'
} finally {
    Pop-Location
}

$backendOut = Join-Path $logDir "backend-$BackendPort.out.log"
$backendErr = Join-Path $logDir "backend-$BackendPort.err.log"
$backendCommand = ('"{0}" -m uvicorn app.main:app --host 127.0.0.1 --port {1} 1>"{2}" 2>"{3}"' -f $backendPython, $BackendPort, $backendOut, $backendErr)
Start-DetachedCmd -WorkingDirectory $backendDir -InnerCommand $backendCommand -Environment @{ HOTCLAW_AUTO_CREATE_TABLES = '0' }
Wait-HttpOk -Url "$apiOrigin/api/v1/health" | Out-Null
$backendPid = Resolve-ListenerPid -Port $BackendPort
Write-PidFile -Path (Join-Path $pidDir 'backend.pid.json') -Payload @{ name = 'backend'; pid = $backendPid; port = $BackendPort; started_at = (Get-Date).ToString('s'); log_out = $backendOut; log_err = $backendErr }

Push-Location $frontendDir
try {
    if (-not $SkipBuild) {
        Invoke-Checked { & $npmPath run build } 'npm run build'
    }
} finally {
    Pop-Location
}

$frontendOut = Join-Path $logDir "frontend-$FrontendPort.out.log"
$frontendErr = Join-Path $logDir "frontend-$FrontendPort.err.log"
$frontendCommand = ('"{0}" run start -- --hostname 127.0.0.1 --port {1} 1>"{2}" 2>"{3}"' -f $npmPath, $FrontendPort, $frontendOut, $frontendErr)
Start-DetachedCmd -WorkingDirectory $frontendDir -InnerCommand $frontendCommand -Environment @{ HOTCLAW_API_ORIGIN = $apiOrigin; NEXT_PUBLIC_HOTCLAW_API_ORIGIN = $apiOrigin }
Wait-HttpOk -Url "http://127.0.0.1:$FrontendPort/accounts" -Validator { param($resp) $resp.Content -match [regex]::Escape($apiOrigin) } | Out-Null
$frontendPid = Resolve-ListenerPid -Port $FrontendPort
Write-PidFile -Path (Join-Path $pidDir 'frontend.pid.json') -Payload @{ name = 'frontend'; pid = $frontendPid; port = $FrontendPort; started_at = (Get-Date).ToString('s'); log_out = $frontendOut; log_err = $frontendErr; api_origin = $apiOrigin }

Write-Host "HotClaw local runtime is ready."
Write-Host "Frontend: http://127.0.0.1:$FrontendPort/accounts"
Write-Host "Backend:  $apiOrigin/api/v1/health"
Write-Host "Logs:     $logDir"
