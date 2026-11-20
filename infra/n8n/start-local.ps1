<#
.SYNOPSIS
    Runs a local n8n wired to this repo's FastAPI backend (no Docker needed).

.DESCRIPTION
    Loads the repo .env, exports the variables the workflows read, imports
    the workflow JSON files in this folder (with -Import) and starts n8n on
    http://localhost:5678.

    Variables the workflows depend on:
      FINSIGHT_API_BASE_URL   backend URL reachable from n8n
      FINSIGHT_SERVICE_TOKEN  long-lived JWT minted by
                              backend/scripts/mint_service_token.py
      N8N_SHARED_SECRET       shared secret for POST /api/v1/alerts/webhook

    N8N_BLOCK_ENV_ACCESS_IN_NODE=false is required: n8n blocks $env.*
    access inside expressions by default, and the workflow HTTP nodes
    read their URL, token and secret from $env.

.EXAMPLE
    # first run: import + publish the three workflow files, then start
    .\infra\n8n\start-local.ps1 -Import

.EXAMPLE
    # later runs
    .\infra\n8n\start-local.ps1

.EXAMPLE
    # start over: delete the local n8n database (workflows, executions,
    # credentials) and re-import the workflow files. Stop n8n first.
    .\infra\n8n\start-local.ps1 -Reset
#>
param(
    [switch]$Import,
    [switch]$Reset,
    [int]$Port = 5678
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$envFile = Join-Path $repoRoot ".env"
if (-not (Test-Path $envFile)) {
    throw "Missing $envFile. Copy .env.example to .env first."
}

# Load KEY=VALUE pairs from .env into this process (comments/blanks skipped).
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
        $name = $matches[1]
        $value = $matches[2].Trim()
        if ($value -match '^"(.*)"$' -or $value -match "^'(.*)'$") { $value = $matches[1] }
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

if (-not $env:N8N_SHARED_SECRET) {
    throw "N8N_SHARED_SECRET is empty in .env - the alerts webhook would reject n8n."
}
if (-not $env:FINSIGHT_SERVICE_TOKEN) {
    throw "FINSIGHT_SERVICE_TOKEN missing in .env. Run: cd backend; .\.venv\Scripts\python scripts\mint_service_token.py --days 90 --write-env"
}
if (-not $env:FINSIGHT_API_BASE_URL) {
    $env:FINSIGHT_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
}

# 127.0.0.1 rather than localhost: Node resolves localhost to ::1 first,
# which misses a backend bound to IPv4 only.
if ($env:FINSIGHT_API_BASE_URL -match '//localhost(:|/)') {
    $env:FINSIGHT_API_BASE_URL = $env:FINSIGHT_API_BASE_URL -replace '//localhost', '//127.0.0.1'
}

$env:N8N_PORT = "$Port"
$env:N8N_PROTOCOL = "http"
$env:N8N_WEBHOOK_URL = "http://localhost:$Port/"
$env:N8N_EDITOR_BASE_URL = "http://localhost:$Port"
$env:N8N_SECURE_COOKIE = "false"
$env:N8N_BLOCK_ENV_ACCESS_IN_NODE = "false"
$env:GENERIC_TIMEZONE = "UTC"

$n8nCmd = (Get-Command n8n -ErrorAction SilentlyContinue).Source
if (-not $n8nCmd) {
    $n8nCmd = Join-Path (npm prefix -g) "n8n.cmd"
}
if (-not (Test-Path $n8nCmd)) {
    throw "n8n not found. Install it once with: npm install -g n8n"
}

if ($Reset) {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        throw "n8n is still running on port $Port. Stop it before using -Reset."
    }
    $n8nHome = if ($env:N8N_USER_FOLDER) { $env:N8N_USER_FOLDER } else { Join-Path $HOME ".n8n" }
    $dbFile = Join-Path $n8nHome "database.sqlite"
    if (Test-Path $dbFile) {
        Remove-Item "$dbFile*" -Force
        Write-Host "Removed $dbFile - rebuilding a fresh n8n database."
    }
    $Import = $true
}

if ($Import) {
    # Workflow names already in the database are skipped: n8n's importer
    # always creates a new workflow, so a plain re-import would leave
    # duplicates fighting over the same webhook path. Use -Reset to replace.
    $existing = @{}
    & $n8nCmd list:workflow | Where-Object { $_ -match '^\s*([A-Za-z0-9]+)\|(.+)$' } |
        ForEach-Object {
            if ($_ -match '^\s*([A-Za-z0-9]+)\|(.+)$') { $existing[$matches[2].Trim()] = $matches[1] }
        }

    Get-ChildItem (Join-Path $PSScriptRoot "*.workflow.json") | ForEach-Object {
        $name = (Get-Content $_.FullName -Raw | ConvertFrom-Json).name
        if ($existing.ContainsKey($name)) {
            Write-Host "Skipping $($_.Name) - '$name' is already imported ($($existing[$name]))."
            return
        }
        Write-Host "Importing $($_.Name)..."
        & $n8nCmd import:workflow --input="$($_.FullName)"
        if ($LASTEXITCODE -ne 0) { throw "Import failed for $($_.Name)" }
    }

    # n8n 2.x replaced activation with explicit publish: webhooks only listen
    # for published workflows, and `update:workflow --all` no longer exists.
    $ids = & $n8nCmd list:workflow | Where-Object { $_ -match '^\s*[A-Za-z0-9]{8,}\|' } |
        ForEach-Object { ($_ -split '\|')[0].Trim() }
    foreach ($id in $ids) {
        Write-Host "Publishing workflow $id..."
        & $n8nCmd publish:workflow --id=$id
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Workflow $id was imported but not published - it needs credentials this machine doesn't have (e.g. SMTP / Supabase / Postgres). Its webhook stays off; the HTTP-only workflows are unaffected."
        }
    }
}

Write-Host "Starting n8n on http://localhost:$Port"
Write-Host "  webhook base : http://localhost:$Port/webhook/"
Write-Host "  backend URL  : $env:FINSIGHT_API_BASE_URL"
& $n8nCmd start
