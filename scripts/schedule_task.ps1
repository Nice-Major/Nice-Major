<#
.SYNOPSIS
    Automated Windows Task Scheduler Registration for Daily 8:00 AM Career Dispatch.
.DESCRIPTION
    Registers a daily scheduled task running at 08:00 AM WAT to execute the
    Career Automation and Stepcon Solutions dispatch pipeline via Python.
.PARAMETER TaskName
    Name of the scheduled task (default: "CareerAutomationDailyDispatch").
.PARAMETER RunTime
    Daily execution time in 24-hr format (default: "08:00").
.PARAMETER ProjectPath
    Root path to the career_automation repository.
.PARAMETER PythonExe
    Path to the python interpreter executable (auto-detected if omitted).
.PARAMETER DryRun
    Configure task to execute in offline dry-run mode (exporting .eml).
.PARAMETER Unregister
    Removes the scheduled task from the system.
#>

[CmdletBinding()]
param (
    [string]$TaskName = "CareerAutomationDailyDispatch",
    [string]$RunTime = "08:00",
    [string]$ProjectPath = "C:\Users\user\teamwork_projects\career_automation",
    [string]$PythonExe = "",
    [switch]$DryRun = $true,
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "Career Automation & Stepcon Solutions — Task Scheduler Manager" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Handle Unregister Request
if ($Unregister) {
    Write-Host "[*] Checking for existing task '$TaskName'..." -ForegroundColor Yellow
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "[+] Task '$TaskName' successfully unregistered." -ForegroundColor Green
    } else {
        Write-Host "[-] Task '$TaskName' not found." -ForegroundColor Yellow
    }
    exit 0
}

# 2. Resolve Python Path
if (-not $PythonExe -or -not (Test-Path -Path $PythonExe)) {
    $pyCmd = Get-Command "python" -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $PythonExe = $pyCmd.Source
    } else {
        $PythonExe = "C:\Program Files\Python315\python.exe"
    }
}

if (-not (Test-Path -Path $PythonExe)) {
    Write-Error "Python executable not found at: '$PythonExe'. Please specify -PythonExe parameter."
}

# 3. Validate Project Directory
if (-not (Test-Path -Path $ProjectPath)) {
    Write-Error "Project workspace directory not found at: '$ProjectPath'."
}

Write-Host "[*] Configuration Parameters:" -ForegroundColor Cyan
Write-Host "    Task Name    : $TaskName"
Write-Host "    Daily Time   : $RunTime AM WAT"
Write-Host "    Project Root : $ProjectPath"
Write-Host "    Python Exe   : $PythonExe"
Write-Host "    Dry Run Mode : $DryRun"

# 4. Construct Quoted Action Command
$argString = "-m scheduler.daily_dispatch"
if ($DryRun) {
    $argString += " --dry-run"
}

$action = New-ScheduledTaskAction `
    -Execute "`"$PythonExe`"" `
    -Argument $argString `
    -WorkingDirectory "`"$ProjectPath`""

# 5. Construct Daily Trigger at 8:00 AM
$trigger = New-ScheduledTaskTrigger -Daily -At $RunTime

# 6. Configure Resilience Settings (Wake to run, start when available)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

# 7. Register Task
Write-Host "[*] Registering Scheduled Task '$TaskName'..." -ForegroundColor Yellow

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Automated Daily 8:00 AM WAT Career Opportunity Digest & Application Tailoring" `
    -Force | Out-Null

Write-Host "[+] Task '$TaskName' successfully registered and active!" -ForegroundColor Green
Write-Host "[*] Next run scheduled for: $((Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo).NextRunTime)" -ForegroundColor Cyan
