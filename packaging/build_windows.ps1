# PowerShell Build Script for Water Business Manager
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Building Water Business Manager Windows Standalone App" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$ProjectRoot = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $ProjectRoot

$env:TEMP = "D:\pip_tmp"
$env:TMP = "D:\pip_tmp"

Write-Host "[1/3] Verifying Python Virtual Environment..." -ForegroundColor Yellow
$PythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$PyInstallerExe = Join-Path $ProjectRoot "venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $PyInstallerExe)) {
    Write-Error "PyInstaller not found in venv. Please run pip install pyinstaller."
    exit 1
}

Write-Host "[2/3] Running PyInstaller..." -ForegroundColor Yellow
& $PyInstallerExe --noconfirm --workpath "$ProjectRoot\build" --distpath "$ProjectRoot\dist" "$ProjectRoot\packaging\water_business_manager.spec"

if ($LASTEXITCODE -eq 0) {
    Write-Host "[3/3] Build succeeded!" -ForegroundColor Green
    Write-Host "Executable generated at: $ProjectRoot\dist\WaterBusinessManager\WaterBusinessManager.exe" -ForegroundColor Green
} else {
    Write-Error "Build failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}
