param(
    [int]$BackendPort = 8140,
    [int]$FrontendPort = 3460,
    [switch]$IncludeLegacy,
    [switch]$Quiet
)

$ErrorActionPreference = 'Continue'

$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $repoRoot 'tmp\local-runtime'
$pidDir = Join-Path $runtimeDir 'pids'
$frontendDevLock = Join-Path $repoRoot 'frontend\.next\dev\lock'

function Write-Info([string]$Message) {
    if (-not $Quiet) {
        Write-Host $Message
    }
}

function Stop-ProcessTree([int]$ProcessId, [string]$Label) {
    if ($ProcessId -le 0) { return }
    $null = taskkill /PID $ProcessId /F /T 2>$null
    $processStillRunning = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($processStillRunning) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        $processStillRunning = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    }

    if (-not $processStillRunning) {
        Write-Info "Stopped $Label (PID $ProcessId)"
    }
}

function Stop-FromPidFile([string]$Path, [string]$Label) {
    if (!(Test-Path $Path)) { return }
    try {
        $payload = Get-Content -Path $Path -Raw | ConvertFrom-Json
        if ($payload.pid) {
            Stop-ProcessTree -ProcessId ([int]$payload.pid) -Label $Label
        }
    } catch {
    }
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

function Get-WmicProcesses([string]$Name) {
    $query = ('wmic process where "name=''''{0}''''" get ProcessId,CommandLine /format:list' -f $Name)
    $lines = cmd.exe /c $query 2>$null
    $entries = @()
    $current = @{}
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            if ($current.ContainsKey('ProcessId')) {
                $entries += [pscustomobject]@{
                    ProcessId = [int]$current.ProcessId
                    CommandLine = [string]$current.CommandLine
                }
            }
            $current = @{}
            continue
        }

        $parts = $line -split '=', 2
        if ($parts.Count -eq 2) {
            $current[$parts[0]] = $parts[1]
        }
    }

    if ($current.ContainsKey('ProcessId')) {
        $entries += [pscustomobject]@{
            ProcessId = [int]$current.ProcessId
            CommandLine = [string]$current.CommandLine
        }
    }

    return $entries
}

function Stop-LegacyListeners([int[]]$Ports) {
    $lines = cmd.exe /c "netstat -ano | findstr LISTENING" 2>$null
    $pids = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($line in $lines) {
        if ($line -match '^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$') {
            $port = [int]$matches[1]
            $listenerPid = [int]$matches[2]
            if ($Ports -contains $port) {
                $null = $pids.Add($listenerPid)
            }
        }
    }

    foreach ($listenerPid in $pids) {
        Stop-ProcessTree -ProcessId $listenerPid -Label 'listener'
    }
}

if (Test-Path $pidDir) {
    Stop-FromPidFile -Path (Join-Path $pidDir 'frontend.pid.json') -Label 'frontend'
    Stop-FromPidFile -Path (Join-Path $pidDir 'backend.pid.json') -Label 'backend'
}

if ($IncludeLegacy) {
    Stop-LegacyListeners -Ports @(3410, 3420, 3440, 3450, $FrontendPort, 8000, 8002, 8110, 8120, 8130, $BackendPort)

    $frontendPortPattern = "--port\s+{0}\b" -f [regex]::Escape([string]$FrontendPort)
    $backendPortPattern = "--port\s+{0}\b" -f [regex]::Escape([string]$BackendPort)

    $nodeProcesses = Get-WmicProcesses -Name 'node.exe' | Where-Object {
        $_.CommandLine -like '*D:\project\hotclaw\frontend*next*'
    }
    foreach ($proc in $nodeProcesses) {
        if ($proc.CommandLine -notmatch $frontendPortPattern) {
            Stop-ProcessTree -ProcessId $proc.ProcessId -Label 'legacy frontend process'
        }
    }

    $pythonProcesses = Get-WmicProcesses -Name 'python.exe' | Where-Object {
        $_.CommandLine -match 'uvicorn\s+app\.main:app'
    }
    foreach ($proc in $pythonProcesses) {
        if ($proc.CommandLine -notmatch $backendPortPattern) {
            Stop-ProcessTree -ProcessId $proc.ProcessId -Label 'legacy backend process'
        }
    }
}

if (Test-Path $frontendDevLock) {
    Remove-Item -LiteralPath $frontendDevLock -Force -ErrorAction SilentlyContinue
    Write-Info 'Removed stale frontend dev lock'
}

if (Test-Path $pidDir) {
    Get-ChildItem -Path $pidDir -Filter '*.pid.json' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}


