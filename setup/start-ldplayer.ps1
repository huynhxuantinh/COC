# Start LDPlayer emulator for COC bot
$LDCONSOLE = "D:\LDPlayer\LDPlayer9\ldconsole.exe"
$INDEX = 0

$running = & $LDCONSOLE isrunning --index $INDEX 2>&1
if ($running -eq "running") {
    Write-Host "LDPlayer already running."
} else {
    Write-Host "Launching LDPlayer..."
    & $LDCONSOLE launch --index $INDEX | Out-Null
    Write-Host "Waiting 40s for Android boot..."
    Start-Sleep -Seconds 40
}

& $LDCONSOLE list2
