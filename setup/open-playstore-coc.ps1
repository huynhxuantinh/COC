# Open Google Play Store to Clash of Clans install page
$LDCONSOLE = "D:\LDPlayer\LDPlayer9\ldconsole.exe"
$INDEX = 0

$running = & $LDCONSOLE isrunning --index $INDEX 2>&1
if ($running -ne "running") {
    Write-Host "Starting LDPlayer..."
    & $LDCONSOLE launch --index $INDEX | Out-Null
    Start-Sleep -Seconds 40
}

Write-Host "Opening Play Store -> Clash of Clans..."
& $LDCONSOLE adb --index $INDEX --command 'shell am start -a android.intent.action.VIEW -d "market://details?id=com.supercell.clashofclans"' | Out-Null

Write-Host @"

Next steps (manual, one-time):
1. Sign in Google account on Play Store (if asked)
2. Tap Install Clash of Clans
3. Open game, complete tutorial
4. Set game language to English (easier for bot vision)
5. Run: .\verify-ldplayer.ps1

"@
