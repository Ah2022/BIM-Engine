param([string]$ExtensionRoot = "$env:APPDATA\pyRevit\Extensions")
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'BIMEngine.extension'
$manifestPath = Join-Path $source 'build-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Run build.ps1 first.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if (-not $manifest.files) { throw 'Rebuild to generate the package file manifest.' }
$target = [IO.Path]::GetFullPath((Join-Path $ExtensionRoot 'BIMEngine.extension'))
$rootPath = [IO.Path]::GetFullPath($ExtensionRoot).TrimEnd('\') + '\'
if (-not $target.StartsWith($rootPath, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid install target.' }
$backupRoot = [IO.Path]::GetFullPath((Join-Path (Split-Path $ExtensionRoot -Parent) 'BIMEngine-backups'))
$stamp = [DateTime]::Now.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,6)
$staging = Join-Path $backupRoot ('staging-' + $stamp)
$backup = Join-Path $backupRoot ('BIMEngine-' + $stamp)
foreach ($path in @($staging, $backup)) {
    if (-not ([IO.Path]::GetFullPath($path)).StartsWith($backupRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid backup target.' }
}
New-Item -ItemType Directory -Force -Path $staging | Out-Null
foreach ($property in $manifest.files.PSObject.Properties) {
    $inputFile = [IO.Path]::GetFullPath((Join-Path $source $property.Name))
    $outputFile = [IO.Path]::GetFullPath((Join-Path $staging $property.Name))
    if (-not $inputFile.StartsWith($source + '\', [StringComparison]::OrdinalIgnoreCase) -or
        -not $outputFile.StartsWith($staging + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid manifest path.' }
    if ((Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash -ne $property.Value) { throw "Package changed since build: $inputFile" }
    New-Item -ItemType Directory -Force -Path (Split-Path $outputFile -Parent) | Out-Null
    Copy-Item -LiteralPath $inputFile -Destination $outputFile
}
Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $staging 'build-manifest.json')
New-Item -ItemType Directory -Force -Path $ExtensionRoot | Out-Null
$hadPrevious = Test-Path -LiteralPath $target
if ($hadPrevious) { Move-Item -LiteralPath $target -Destination $backup }
try {
    Move-Item -LiteralPath $staging -Destination $target
}
catch {
    if ($hadPrevious -and -not (Test-Path -LiteralPath $target)) { Move-Item -LiteralPath $backup -Destination $target }
    throw
}
$result = [ordered]@{ installed=$target; backup=$(if ($hadPrevious) {$backup} else {$null}); version=$manifest.version; fileCount=@($manifest.files.PSObject.Properties).Count; installedUtc=[DateTime]::UtcNow.ToString('o') }
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'verification/installation.json') -Encoding utf8
$result | ConvertTo-Json
Write-Output 'Restart Revit to replace any already loaded engine DLL.'

