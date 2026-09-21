# Download and verify the Windows installer, then run its installation wizard.
param([string]$Version = $env:CADKIT_VERSION)
$ErrorActionPreference = 'Stop'
$Repository = if ($env:CADKIT_REPOSITORY) { $env:CADKIT_REPOSITORY } else { 'aurkakoak/cadkit' }
if ($env:OS -ne 'Windows_NT') { throw 'This installer supports Windows. On macOS use install.sh.' }
if (-not [Environment]::Is64BitOperatingSystem) { throw 'CadKit requires 64-bit Windows.' }
if ($Repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') { throw 'Invalid repository.' }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if (-not $Version) {
    $Release = Invoke-RestMethod "https://api.github.com/repos/$Repository/releases/latest"
    $Version = $Release.tag_name
}
$Version = $Version -replace '^v', ''
if ($Version -notmatch '^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$') { throw 'Invalid release version.' }
$Asset = "CadKit-$Version-windows-x64.exe"
$Base = "https://github.com/$Repository/releases/download/v$Version"
$Scratch = Join-Path ([IO.Path]::GetTempPath()) ("cadkit-install-" + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $Scratch | Out-Null
try {
    $Installer = Join-Path $Scratch $Asset
    Write-Host "Downloading CadKit $Version for Windows..."
    Invoke-WebRequest "$Base/$Asset" -OutFile $Installer -UseBasicParsing
    $ChecksumPath = Join-Path $Scratch 'SHA256SUMS'
    Invoke-WebRequest "$Base/SHA256SUMS" -OutFile $ChecksumPath -UseBasicParsing
    $Checksums = [IO.File]::ReadAllText($ChecksumPath)
    $Pattern = '(?m)^([a-f0-9]{64})  ' + [regex]::Escape($Asset) + '\r?$'
    $MatchesFound = [regex]::Matches($Checksums, $Pattern)
    if ($MatchesFound.Count -ne 1) { throw 'Release checksum is missing or ambiguous.' }
    $Actual = (Get-FileHash $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $MatchesFound[0].Groups[1].Value) { throw 'Checksum verification failed; nothing was installed.' }
    $Process = Start-Process -FilePath $Installer -Wait -PassThru
    if ($Process.ExitCode -ne 0) { throw "Installer exited with code $($Process.ExitCode)." }
    Write-Host 'CadKit installed. Launch it from the Start menu.'
} finally {
    Remove-Item -LiteralPath $Scratch -Recurse -Force
}
