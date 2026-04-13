param(
    [int]$BackendPort = 8140,
    [int]$FrontendPort = 3460,
    [ValidateSet('Auto', 'Start', 'Dev')]
    [string]$FrontendMode = 'Auto',
    [switch]$DemoMode,
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

function Write-Step([string]$Message) {
    Write-Host "==> $Message"
}

function Write-CommandOutput([object[]]$Output) {
    foreach ($entry in $Output) {
        if ($entry -is [System.Management.Automation.ErrorRecord]) {
            $message = $entry.Exception.Message
            if ([string]::IsNullOrWhiteSpace($message)) {
                $message = $entry.ToString()
            }
            if ($message -eq 'System.Management.Automation.RemoteException') {
                continue
            }
            Write-Host $message
        } else {
            Write-Host $entry
        }
    }
}

function Invoke-ExternalCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$Label,
        [string]$WorkingDirectory = $null
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($WorkingDirectory) {
            Push-Location $WorkingDirectory
        }

        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        if ($WorkingDirectory) {
            Pop-Location
        }
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($null -ne $output) {
        Write-CommandOutput -Output $output
    }

    if ($exitCode -ne 0) {
        throw "$Label failed with exit code $exitCode"
    }
}

function Get-FileTail([string]$Path, [int]$LineCount = 40) {
    if (!(Test-Path $Path)) {
        return $null
    }

    $lines = Get-Content -Path $Path -Tail $LineCount -ErrorAction SilentlyContinue
    if (!$lines) {
        return $null
    }

    return ($lines -join [Environment]::NewLine)
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

function Wait-ComponentReady {
    param(
        [string]$Name,
        [string]$Url,
        [string]$StdoutLog,
        [string]$StderrLog,
        [int]$Attempts = 30,
        [int]$DelaySeconds = 2,
        [scriptblock]$Validator = $null
    )

    try {
        Wait-HttpOk -Url $Url -Attempts $Attempts -DelaySeconds $DelaySeconds -Validator $Validator | Out-Null
    } catch {
        $details = @()
        $stderrTail = Get-FileTail -Path $StderrLog
        $stdoutTail = Get-FileTail -Path $StdoutLog

        if ($stderrTail) {
            $details += "$Name stderr:`n$stderrTail"
        }

        if ($stdoutTail) {
            $details += "$Name stdout:`n$stdoutTail"
        }

        $message = "Timed out waiting for $Name at $Url"
        if ($details.Count -gt 0) {
            $message += "`n`n" + ($details -join "`n`n")
        }

        throw $message
    }
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
    Write-Step 'Stopping stale local processes'
    & $stopScript -BackendPort $BackendPort -FrontendPort $FrontendPort -IncludeLegacy -Quiet
}

Push-Location $backendDir
try {
    Write-Step 'Running backend migrations'
    Invoke-ExternalCommand -FilePath $backendPython -Arguments @('-m', 'alembic', 'upgrade', 'head') -Label 'alembic upgrade head'
    Invoke-ExternalCommand -FilePath $backendPython -Arguments @('-m', 'alembic', 'stamp', 'head') -Label 'alembic stamp head'
} finally {
    Pop-Location
}

$frontendLaunchMode = 'start'
$frontendBuildIdPath = Join-Path $frontendDir '.next\BUILD_ID'
Push-Location $frontendDir
try {
    if ($FrontendMode -eq 'Dev') {
        Write-Step 'Frontend mode forced to dev'
        $frontendLaunchMode = 'dev'
    } elseif (-not $SkipBuild) {
        Write-Step 'Building frontend'
        try {
            Invoke-ExternalCommand -FilePath $npmPath -Arguments @('run', 'build') -Label 'npm run build' -WorkingDirectory $frontendDir
        } catch {
            if ($FrontendMode -eq 'Start') {
                throw
            }

            if (Test-Path $frontendBuildIdPath) {
                Write-Host 'Frontend build exited non-zero, but BUILD_ID exists; attempting production start.'
                Write-Host $_
                $frontendLaunchMode = 'start'
            } else {
                Write-Host 'Frontend production build failed; falling back to dev mode.'
                Write-Host $_
                $frontendLaunchMode = 'dev'
            }
        }
    } elseif ($FrontendMode -eq 'Auto' -and !(Test-Path $frontendBuildIdPath)) {
        Write-Step 'No existing production build found; falling back to dev mode'
        $frontendLaunchMode = 'dev'
    }
} finally {
    Pop-Location
}

$backendOut = Join-Path $logDir "backend-$BackendPort.out.log"
$backendErr = Join-Path $logDir "backend-$BackendPort.err.log"
$backendCommand = ('"{0}" -m uvicorn app.main:app --host 127.0.0.1 --port {1} 1>"{2}" 2>"{3}"' -f $backendPython, $BackendPort, $backendOut, $backendErr)
Write-Step 'Starting backend'
Start-DetachedCmd -WorkingDirectory $backendDir -InnerCommand $backendCommand -Environment @{ HOTCLAW_AUTO_CREATE_TABLES = '0'; HOTCLAW_ENABLE_SCHEDULER = '0'; HOTCLAW_E2E_TEST_MODE = $(if ($DemoMode) { '1' } else { '0' }) }
Wait-ComponentReady -Name 'backend' -Url "$apiOrigin/api/v1/health" -StdoutLog $backendOut -StderrLog $backendErr
$backendPid = Resolve-ListenerPid -Port $BackendPort
Write-PidFile -Path (Join-Path $pidDir 'backend.pid.json') -Payload @{ name = 'backend'; pid = $backendPid; port = $BackendPort; started_at = (Get-Date).ToString('s'); log_out = $backendOut; log_err = $backendErr; scheduler_enabled = $false; demo_mode = [bool]$DemoMode }

$frontendOut = Join-Path $logDir "frontend-$FrontendPort.out.log"
$frontendErr = Join-Path $logDir "frontend-$FrontendPort.err.log"
$frontendCommand = if ($frontendLaunchMode -eq 'dev') {
    ('"{0}" run dev -- --hostname 127.0.0.1 --port {1} 1>"{2}" 2>"{3}"' -f $npmPath, $FrontendPort, $frontendOut, $frontendErr)
} else {
    ('"{0}" run start -- --hostname 127.0.0.1 --port {1} 1>"{2}" 2>"{3}"' -f $npmPath, $FrontendPort, $frontendOut, $frontendErr)
}
Write-Step ("Starting frontend ({0})" -f $frontendLaunchMode)
Start-DetachedCmd -WorkingDirectory $frontendDir -InnerCommand $frontendCommand -Environment @{ HOTCLAW_API_ORIGIN = $apiOrigin; NEXT_PUBLIC_HOTCLAW_API_ORIGIN = $apiOrigin }
Wait-ComponentReady -Name 'frontend' -Url "http://127.0.0.1:$FrontendPort/accounts" -StdoutLog $frontendOut -StderrLog $frontendErr -Attempts 45 -DelaySeconds 2 -Validator { param($resp) $resp.Content -match [regex]::Escape($apiOrigin) }
$frontendPid = Resolve-ListenerPid -Port $FrontendPort
Write-PidFile -Path (Join-Path $pidDir 'frontend.pid.json') -Payload @{ name = 'frontend'; pid = $frontendPid; port = $FrontendPort; started_at = (Get-Date).ToString('s'); log_out = $frontendOut; log_err = $frontendErr; api_origin = $apiOrigin; mode = $frontendLaunchMode }

Write-Host 'HotClaw local runtime is ready.'
Write-Host "Frontend: http://127.0.0.1:$FrontendPort/accounts"
Write-Host "Backend:  $apiOrigin/api/v1/health"
Write-Host "Mode:     frontend=$frontendLaunchMode scheduler=disabled demo=$([bool]$DemoMode)"
Write-Host "Logs:     $logDir"
