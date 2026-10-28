param([string]$ScriptPath = (Join-Path $PSScriptRoot 'revit_dashboard.py'))
$ErrorActionPreference = 'Stop'
$workspace = Split-Path $PSScriptRoot -Parent
$startedAt = Get-Date
$runnerExe = (Get-Command pyrevit).Source
$runnerProcess = Start-Process -FilePath $runnerExe -ArgumentList @('run', ('"' + $ScriptPath + '"'), '--revit=2024', '--allowdialogs') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $workspace 'verification/dashboard-runner-output.txt') -RedirectStandardError (Join-Path $workspace 'verification/dashboard-runner-error.txt')
# pyRevit creates its journal before Revit starts. Remove only this test run's
# automatic Quit command, allowing ExternalEvent/Idling tests after command return.
$deadline = (Get-Date).AddSeconds(20)
$journal = $null
while ((Get-Date) -lt $deadline -and -not $journal) {
    $folders = Get-ChildItem -LiteralPath $env:TEMP -Directory | Where-Object { $_.CreationTime -ge $startedAt.AddSeconds(-1) -and $_.Name -match '^[a-f0-9]{8}-' }
    foreach ($folder in $folders) {
        foreach ($file in (Get-ChildItem -LiteralPath $folder.FullName -Filter 'PyRevitRunner_*.txt')) {
            $content = Get-Content -LiteralPath $file.FullName -Raw
            if ($content.Contains($ScriptPath) -and $content.Contains('ID_APP_EXIT')) {
                $lines = Get-Content -LiteralPath $file.FullName
                $lines | Where-Object { $_ -notmatch 'ID_APP_EXIT|TaskDialogResult' } | Set-Content -LiteralPath $file.FullName
                $journal = $file.FullName
                break
            }
        }
    }
    if (-not $journal) { Start-Sleep -Milliseconds 100 }
}
if (-not $journal) { throw 'Test journal was not found. Check dashboard-runner-output.txt.' }
@{ runnerPid=$runnerProcess.Id; journal=$journal } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workspace 'verification/dashboard-runner-session.json')
Write-Output $journal
