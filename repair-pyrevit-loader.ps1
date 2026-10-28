param([string]$ConfigPath = "$env:APPDATA\pyRevit\pyRevit_config.ini")
$ErrorActionPreference = 'Stop'
$content = [IO.File]::ReadAllText($ConfigPath)
$pattern = '(?m)^(new_loader\s*=\s*)true\s*$'
if ($content -notmatch $pattern) {
    if ($content -match '(?m)^new_loader\s*=\s*false\s*$') { Write-Output 'Legacy loader already enabled.'; exit 0 }
    throw 'Expected new_loader=true setting was not found; configuration was not changed.'
}
$backup = $ConfigPath + '.before-bimengine-loader-fix-' + [DateTime]::Now.ToString('yyyyMMdd-HHmmss') + '.bak'
Copy-Item -LiteralPath $ConfigPath -Destination $backup
$updated = [regex]::Replace($content, $pattern, '${1}false')
[IO.File]::WriteAllText($ConfigPath, $updated, [Text.UTF8Encoding]::new($false))
if ([IO.File]::ReadAllText($ConfigPath) -ne $updated) { throw 'Configuration verification failed.' }
Write-Output "Enabled the legacy pyRevit loader. Backup: $backup"
Write-Output 'Fully restart Revit; reload cannot reset a failed Python.NET static initializer.'
