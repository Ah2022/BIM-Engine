param([string]$RevitApiPath = 'C:\Program Files\Autodesk\Revit 2024')
$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $RevitApiPath 'RevitAPI.dll'))) { throw 'Revit 2024 API not found.' }
& dotnet build (Join-Path $repo 'BIMEngine.Core/BIMEngine.Core.csproj') -c Release -p:Platform=x64 "-p:REVIT_API_PATH=$RevitApiPath" -p:NuGetAudit=false
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
$binary = Join-Path $repo 'BIMEngine.Core/bin/x64/Release/net48/BIMEngine.Core.dll'
$destination = Join-Path $repo 'BIMEngine.extension/bin'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -LiteralPath $binary -Destination (Join-Path $destination 'BIMEngine.Core.dll') -Force
$packageRoot = Join-Path $repo 'BIMEngine.extension'
$hashes = [ordered]@{}
Get-ChildItem -LiteralPath $packageRoot -File -Recurse | Where-Object { $_.FullName -notmatch '__pycache__' -and $_.Extension -ne '.pyc' -and $_.Name -ne 'build-manifest.json' } | ForEach-Object {
    $relative = $_.FullName.Substring($packageRoot.Length + 1).Replace('\','/')
    $hashes[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
}
$manifest = [ordered]@{ version='0.3.1'; revit='2024'; framework='net48'; builtUtc=[DateTime]::UtcNow.ToString('o'); sha256=(Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash; files=$hashes }
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $repo 'BIMEngine.extension/build-manifest.json') -Encoding utf8
Write-Output 'Built and staged BIMEngine.extension for Revit 2024.'
