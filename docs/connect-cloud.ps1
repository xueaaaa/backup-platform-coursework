param(
    [Parameter(Mandatory = $true)][string]$Server,
    [string]$User = 'root',
    [int]$Port = 22
)
$ErrorActionPreference = 'Stop'
$keyPath = Join-Path $env:USERPROFILE '.ssh/coursework_backup_ed25519'
$hostsPath = Join-Path $env:USERPROFILE '.ssh/coursework_backup_known_hosts'
if (-not (Test-Path -LiteralPath $keyPath)) { throw 'SSH key not found. Configure VPS access first.' }
Write-Host 'Cloud panel: http://localhost:8081. Keep this terminal open.'
& ssh -i $keyPath -p $Port -o ExitOnForwardFailure=yes -o "UserKnownHostsFile=$hostsPath" -N -L '8081:127.0.0.1:18081' "$User@$Server"
if ($LASTEXITCODE -ne 0) { throw 'SSH tunnel failed. Check network access and the local port 8081.' }
