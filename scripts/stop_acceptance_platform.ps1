$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PidFile = Join-Path $Root "data\runtime\platform_pids.json"

function Test-WorkspaceProcess($Process) {
    if (-not $Process.CommandLine) { return $false }
    $normalizedCommand = $Process.CommandLine.Replace("/", "\").ToLowerInvariant()
    $normalizedRoot = $Root.Replace("/", "\").ToLowerInvariant()
    return $normalizedCommand.Contains($normalizedRoot)
}

if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host "No acceptance platform process registry was found"
    exit 0
}

$Registry = Get-Content -Raw -Encoding utf8 -LiteralPath $PidFile | ConvertFrom-Json
foreach ($Entry in @($Registry.processes)) {
    $Port = [int]$Entry.port
    $ProcessId = [int]$Entry.process_id
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if (-not $process) { continue }

    $ownsPort = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -eq $ProcessId }
    if ((Test-WorkspaceProcess $process) -and $ownsPort) {
        Stop-Process -Id $ProcessId -Force
        Write-Host "Stopped port $Port (PID $ProcessId)"
    } else {
        Write-Warning "Skipped PID $ProcessId on port $Port because ownership could not be verified"
    }
}

Remove-Item -LiteralPath $PidFile -Force
