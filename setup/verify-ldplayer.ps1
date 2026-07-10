# Verify LDPlayer + ADB setup for COC bot
$ErrorActionPreference = "Stop"

$LD_DIR = "D:\LDPlayer\LDPlayer9"
$ADB = Join-Path $LD_DIR "adb.exe"
$LDCONSOLE = Join-Path $LD_DIR "ldconsole.exe"
$DEVICE = "emulator-5554"
$INDEX = 0

Write-Host "=== LDPlayer Setup Verification ===" -ForegroundColor Cyan

if (-not (Test-Path $LD_DIR)) {
    Write-Host "[FAIL] LDPlayer not found at $LD_DIR" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] LDPlayer installed: $LD_DIR" -ForegroundColor Green

$running = & $LDCONSOLE isrunning --index $INDEX 2>&1
if ($running -ne "running") {
    Write-Host "[INFO] Starting emulator..." -ForegroundColor Yellow
    & $LDCONSOLE launch --index $INDEX | Out-Null
    Start-Sleep -Seconds 40
}

$info = & $LDCONSOLE list2 2>&1
Write-Host "[OK] Emulator info: $info" -ForegroundColor Green

$devices = & $ADB devices 2>&1
Write-Host "[INFO] ADB devices:`n$devices"

if (-not ($devices | Out-String | Select-String $DEVICE)) {
    Write-Host "[FAIL] ADB device $DEVICE not connected" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] ADB connected: $DEVICE" -ForegroundColor Green

$android = & $LDCONSOLE adb --index $INDEX --command "shell getprop ro.build.version.release" 2>&1
Write-Host "[OK] Android version: $android" -ForegroundColor Green

$ssDir = Join-Path $PSScriptRoot "."
$ssPath = Join-Path $ssDir "verify_screenshot.png"
& $ADB -s $DEVICE shell screencap -p /sdcard/verify.png | Out-Null
& $ADB -s $DEVICE pull /sdcard/verify.png $ssPath | Out-Null
Write-Host "[OK] Screenshot saved: $ssPath" -ForegroundColor Green

$coc = & $LDCONSOLE adb --index $INDEX --command "shell pm list packages com.supercell.clashofclans" 2>&1
if ($coc -match "com.supercell.clashofclans") {
    Write-Host "[OK] Clash of Clans installed" -ForegroundColor Green
} else {
    Write-Host "[WARN] Clash of Clans NOT installed yet" -ForegroundColor Yellow
    Write-Host "       Run: .\open-playstore-coc.ps1" -ForegroundColor Yellow
}

Write-Host "`n=== All checks passed ===" -ForegroundColor Cyan
