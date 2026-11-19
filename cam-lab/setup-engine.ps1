$ErrorActionPreference = "Stop"
$engineUrl = "https://github.com/OneManLabs/cam.git"
$engineCommit = "66eba04bc576d0432ec5cb512cb6a8d73c4dedc1"
$engineDir = Join-Path $PSScriptRoot "engine"

# Keep this script ASCII-only for Windows PowerShell 5.1 compatibility.
try {
    $nodeVersionText = node -p "process.versions.node"
    if ($LASTEXITCODE -ne 0) { throw "Node.js command failed." }
    $nodeVersion = [version]$nodeVersionText
} catch {
    throw "Node.js was not found. Install Node.js 22.12.0 or newer, then retry."
}
if (($nodeVersion.Major -eq 20 -and $nodeVersion -lt [version]"20.19.0") -or
    ($nodeVersion.Major -eq 22 -and $nodeVersion -lt [version]"22.12.0") -or
    ($nodeVersion.Major -lt 20) -or ($nodeVersion.Major -eq 21)) {
    throw "Vite 8 requires Node.js 20.19+ or 22.12+. Detected: $nodeVersionText"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git was not found. Install Git for Windows, then retry."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Reinstall Node.js with npm included, then retry."
}

if (-not (Test-Path (Join-Path $engineDir ".git"))) {
    if (Test-Path $engineDir) {
        throw "The engine folder exists but is not a Git clone. Rename or remove it manually, then retry."
    }
    git clone --filter=blob:none --no-checkout $engineUrl $engineDir
    if ($LASTEXITCODE -ne 0) { throw "Could not clone the upstream CAM repository." }
}

Push-Location $engineDir
try {
    git fetch --depth 1 origin $engineCommit
    if ($LASTEXITCODE -ne 0) { throw "Could not fetch the pinned CAM revision." }

    git checkout --detach $engineCommit
    if ($LASTEXITCODE -ne 0) { throw "Could not check out the pinned CAM revision. Check for local changes in cam-lab/engine." }

    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed while installing CAM dependencies." }

    npm run build
    if ($LASTEXITCODE -ne 0) { throw "The CAM production build failed." }
} finally {
    Pop-Location
}

Write-Host "CAM engine installed and production build completed."
Write-Host "To start the development server, run:"
Write-Host "  cd `"$engineDir`""
Write-Host "  npm run dev"
