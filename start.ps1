param([switch]$NoBuild)
$ErrorActionPreference = 'Stop'
$previousLocation = Get-Location
try {
    Set-Location -LiteralPath $PSScriptRoot
    $dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
    $dockerPath = if ($dockerCommand) { $dockerCommand.Source } else { $null }
    if (-not $dockerPath) {
        $candidates = @(
            (Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin/docker.exe'),
            (Join-Path $env:ProgramFiles 'Docker/Docker/resources/bin/docker.exe')
        )
        $dockerPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $dockerPath) { throw 'Docker Desktop не найден. Установите Docker Desktop с Linux-контейнерами.' }
    if (-not (Test-Path -LiteralPath '.env')) {
        $content = [IO.File]::ReadAllText((Join-Path $PSScriptRoot '.env.example'))
        foreach ($placeholder in @('replace-with-a-long-random-secret', 'replace-with-at-least-12-characters',
            'replace-source-password', 'replace-restore-password', 'replace-and-save-this-encryption-passphrase')) {
            $randomBytes = New-Object byte[] 40
            $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
            try { $generator.GetBytes($randomBytes) } finally { $generator.Dispose() }
            $secret = [Convert]::ToBase64String($randomBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
            $content = $content.Replace($placeholder, $secret)
        }
        [IO.File]::WriteAllText((Join-Path $PSScriptRoot '.env'), $content, (New-Object Text.UTF8Encoding $false))
        Write-Host 'Создан .env с локальными паролями. Сохраните его отдельно.'
    }
    & $dockerPath compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Ошибка конфигурации Compose. Проверьте .env.' }
    & $dockerPath info --format '{{.ServerVersion}}'
    if ($LASTEXITCODE -ne 0) { throw 'Движок Docker Desktop не готов. Дождитесь запуска или устраните ошибку Docker Desktop.' }
    $composeArguments = @('compose', 'up', '-d', '--wait', '--wait-timeout', '180')
    if (-not $NoBuild) { $composeArguments += '--build' }
    & $dockerPath @composeArguments
    if ($LASTEXITCODE -ne 0) { throw 'Стенд не запущен. Проверьте docker compose logs.' }
    Write-Host 'Панель: http://localhost:8080'
    Write-Host 'Логин admin; пароль ADMIN_PASSWORD находится в .env.'
} finally {
    Set-Location -LiteralPath $previousLocation
}
