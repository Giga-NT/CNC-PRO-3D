$ErrorActionPreference = "Stop"
$engineUrl = "https://github.com/OneManLabs/cam.git"
$engineCommit = "66eba04bc576d0432ec5cb512cb6a8d73c4dedc1"
$engineDir = Join-Path $PSScriptRoot "engine"
$nodeMajor = 0
try {
    $nodeMajor = [int](node -p 'process.versions.node.split(".")[0]')
} catch {
    throw "Node.js не найден. Установи Node.js 22 или новее."
}
if ($nodeMajor -lt 22) {
    throw "Нужен Node.js 22 или новее. Обнаружена версия: $(node --version)"
}
if (-not (Test-Path (Join-Path $engineDir ".git"))) {
    if (Test-Path $engineDir) {
        throw "Папка engine уже существует, но это не Git-клон. Переименуй или удали её вручную."
    }
    git clone --filter=blob:none --no-checkout $engineUrl $engineDir
    if ($LASTEXITCODE -ne 0) { throw "Не удалось клонировать CAM-репозиторий." }
}
Push-Location $engineDir
try {
    git fetch --depth 1 origin $engineCommit
    if ($LASTEXITCODE -ne 0) { throw "Не удалось получить зафиксированную версию CAM." }
    git checkout --detach $engineCommit
    if ($LASTEXITCODE -ne 0) { throw "Не удалось переключиться на зафиксированный CAM commit." }
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci завершился с ошибкой." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Сборка CAM завершилась с ошибкой." }
} finally {
    Pop-Location
}
Write-Host "CAM-движок подготовлен и собран."
Write-Host "Для запуска: cd `"$engineDir`"; npm run dev"
