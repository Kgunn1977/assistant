# Creates the scheduled task "{LISTENER_TASK}", the assistant's one background job: it serves the page, acts on
# the owner's answers the moment they are given, and runs the 15-minute check itself. It starts when the owner signs
# in to Windows, hidden, as that user, no admin rights, and is started again within 5 minutes if it has stopped.
# The 5-minute start runs side by side (-MultipleInstances Parallel): a second copy finds the first one's lock and
# ends at once with 0, so a healthy listener never shows a refused start (0x800710E0) as its last result.
# Run once. To remove it later:
#   Unregister-ScheduledTask -TaskName "{LISTENER_TASK}" -Confirm:$false
$a = New-ScheduledTaskAction -Execute "{PYTHONW}" -Argument '"{LIVE_PAGE}\listen.py"' -WorkingDirectory "{LIVE_PAGE}"
$atLogon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$keepAlive = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$s = New-ScheduledTaskSettingsSet -MultipleInstances Parallel -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -Hidden -Priority 4
$p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "{LISTENER_TASK}" -Action $a -Trigger $atLogon, $keepAlive -Settings $s -Principal $p -Description "{OWNER}'s assistant: serves the page, acts on answers the moment they are given, and reads new mail and messages every 15 minutes." | Format-List TaskName, State
