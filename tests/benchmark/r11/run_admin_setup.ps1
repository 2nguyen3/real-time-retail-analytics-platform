# Run by the person who holds the PostgreSQL administrator account. Reads .env; prints no secret.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..\..\..").Path
$cfg = @{}
Get-Content "$root\.env" | Where-Object { $_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$' } |
    ForEach-Object { $null = $_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$'; $cfg[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'") }
$env:PGPASSWORD = $cfg.AZURE_PG_ADMIN_PASSWORD
$env:PGSSLMODE = 'require'
try {
    docker run --rm -e PGPASSWORD -e PGSSLMODE -v "${PSScriptRoot}:/sql:ro" postgres:17-alpine psql -X `
        -h $cfg.AZURE_PG_HOST -U $cfg.AZURE_PG_ADMIN_USER -d $cfg.AZURE_PG_DB `
        -v "app_role=$($cfg.AZURE_PG_APP_USER)" -v "reader_role=$($cfg.AZURE_PG_READER_USER)" `
        -f /sql/01_admin_setup.sql
    if ($LASTEXITCODE -ne 0) { throw "psql exited with code $LASTEXITCODE" }
}
finally { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
