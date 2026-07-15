param(
    [string]$AdminPassword = $(if ($env:ADMIN_PASSWORD) { $env:ADMIN_PASSWORD } else { "admin" })
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = "F:\panda\miniconda\conda\envs\task1-semiconductor-ui\python.exe"
$RuntimeDir = Join-Path $Root "data\runtime"
$LogDir = Join-Path $RuntimeDir "logs"
$PidFile = Join-Path $RuntimeDir "platform_pids.json"
$SessionSecretFile = Join-Path $RuntimeDir ".session_secret"
$ApiLauncher = Join-Path $Root "scripts\run_acceptance_api.py"
$ComposeDir = Join-Path $Root "graphiti-main\graphiti-main"
if (-not (Test-Path -LiteralPath $ComposeDir)) {
    $BaseDirectory = Split-Path (Split-Path $Root -Parent) -Parent
    $OriginalRoot = Get-ChildItem -LiteralPath $BaseDirectory -Directory | Where-Object {
        (Test-Path (Join-Path $_.FullName ".git")) -and
        (Test-Path (Join-Path $_.FullName "graphiti-main"))
    } | Select-Object -First 1 -ExpandProperty FullName
    if (-not $OriginalRoot) { throw "Original project root was not found" }
    $ComposeDir = Join-Path $OriginalRoot "graphiti-main\graphiti-main"
}

function Test-Port([int]$Port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Test-WorkspaceProcess($Process) {
    if (-not $Process.CommandLine) { return $false }
    $normalizedCommand = $Process.CommandLine.Replace("/", "\").ToLowerInvariant()
    $normalizedRoot = $Root.Replace("/", "\").ToLowerInvariant()
    return $normalizedCommand.Contains($normalizedRoot)
}

function Stop-WorkspacePort([int]$Port) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
        if (-not $process) { continue }
        if (-not (Test-WorkspaceProcess $process)) {
            throw "Port $Port is occupied by a process outside this worktree: PID $($process.ProcessId)"
        }
        Stop-Process -Id $process.ProcessId -Force
    }
}

function Get-WorkspaceListener([int]$Port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $listener) { throw "No listener was found on port $Port" }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
    if (-not $process -or -not (Test-WorkspaceProcess $process)) {
        throw "Listener on port $Port does not belong to this worktree"
    }
    return [PSCustomObject]@{
        port = $Port
        process_id = [int]$process.ProcessId
    }
}

function Stop-StartedProcessTree(
    [int]$StartedProcessId,
    [datetime]$LaunchStartedAt,
    [Nullable[datetime]]$ExpectedRootStartTime = $null
) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $StartedProcessId" -ErrorAction SilentlyContinue
    if (-not $process) { return }
    $runningProcess = Get-Process -Id $StartedProcessId -ErrorAction SilentlyContinue
    if (-not $runningProcess) { return }

    if ($ExpectedRootStartTime.HasValue) {
        $difference = [math]::Abs(($runningProcess.StartTime - $ExpectedRootStartTime.Value).TotalSeconds)
        if ($difference -gt 1) {
            Write-Warning "Skipped reused launcher PID $StartedProcessId"
            return
        }
    } elseif ($runningProcess.StartTime -lt $LaunchStartedAt.AddSeconds(-2)) {
        Write-Warning "Skipped stale descendant PID $StartedProcessId"
        return
    }

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $StartedProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-StartedProcessTree ([int]$child.ProcessId) $LaunchStartedAt
    }
    if ($ExpectedRootStartTime.HasValue -or (Test-WorkspaceProcess $process)) {
        Stop-Process -Id $StartedProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Wait-Url([string]$Url, [int]$Seconds = 45) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return }
        } catch {
            Start-Sleep -Milliseconds 700
        }
    }
    throw "Service startup timed out: $Url"
}

if (-not (Test-Path $Python)) { throw "task1 Python does not exist: $Python" }
if (-not (Test-Path $ApiLauncher)) { throw "API launcher was not found: $ApiLauncher" }
if (-not (Get-Command pnpm.cmd -ErrorAction SilentlyContinue)) { throw "pnpm.cmd was not found" }

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
if (-not (Test-Path $SessionSecretFile)) {
    $bytes = New-Object byte[] 48
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    } finally {
        $generator.Dispose()
    }
    [Convert]::ToBase64String($bytes) | Set-Content -Encoding ascii $SessionSecretFile
}
$SessionSecret = (Get-Content -Raw $SessionSecretFile).Trim()

if (-not (Test-Port 7687)) {
    Push-Location $ComposeDir
    try {
        docker compose up -d neo4j
    } finally {
        Pop-Location
    }
}
Wait-Url "http://127.0.0.1:7474" 60

8001, 7870, 7871 | ForEach-Object { Stop-WorkspacePort $_ }
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 600

$env:APP_ENV = "development"
$env:ADMIN_PASSWORD = $AdminPassword
$env:SESSION_SECRET = $SessionSecret
$env:COOKIE_SECURE = "false"
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "password"
$env:GROUP_ID = "semiconductor_dc_kg"
$env:SQLITE_PATH = (Join-Path $RuntimeDir "qa_observability.db")
$env:GRAPHITI_LLM_BASE_URL = "https://api.siliconflow.cn/v1"
$env:GRAPHITI_LLM_MODEL = "deepseek-ai/DeepSeek-V3.2"
$env:GRAPHITI_EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"
$env:GRAPHITI_EMBEDDING_MODEL = "BAAI/bge-m3"
$env:GRAPHITI_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

$LaunchStartedAt = Get-Date
$StartedProcesses = @()
try {
    $ApiArguments = '-X utf8 "' + $ApiLauncher + '"'
    $StartedProcesses += Start-Process -FilePath $Python -ArgumentList $ApiArguments `
        -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir "api.out.log") `
        -RedirectStandardError (Join-Path $LogDir "api.err.log")

    $StartedProcesses += Start-Process -FilePath "pnpm.cmd" -ArgumentList @("dev") `
        -WorkingDirectory (Join-Path $Root "apps\user-portal") -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir "user.out.log") `
        -RedirectStandardError (Join-Path $LogDir "user.err.log")

    $StartedProcesses += Start-Process -FilePath "pnpm.cmd" -ArgumentList @("dev") `
        -WorkingDirectory (Join-Path $Root "apps\admin-portal") -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogDir "admin.out.log") `
        -RedirectStandardError (Join-Path $LogDir "admin.err.log")

    Wait-Url "http://127.0.0.1:8001/health" 60
    Wait-Url "http://127.0.0.1:7870" 45
    Wait-Url "http://127.0.0.1:7871" 45

    $ProcessRegistry = [PSCustomObject]@{
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        processes = @(8001, 7870, 7871 | ForEach-Object { Get-WorkspaceListener $_ })
    }
    $ProcessRegistry | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $PidFile
} catch {
    foreach ($Port in 8001, 7870, 7871) {
        try { Stop-WorkspacePort $Port } catch { Write-Warning $_.Exception.Message }
    }
    foreach ($StartedProcess in $StartedProcesses) {
        Stop-StartedProcessTree ([int]$StartedProcess.Id) $LaunchStartedAt $StartedProcess.StartTime
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    throw
}

Write-Host "Acceptance platform started"
Write-Host "User portal: http://127.0.0.1:7870"
Write-Host "Admin portal: http://127.0.0.1:7871"
Write-Host "API: http://127.0.0.1:8001"
Write-Host "Neo4j: http://127.0.0.1:7474"
Write-Host "Admin password is configured"
