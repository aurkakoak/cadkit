# Exercise the real PowerShell installer with local download/process doubles.
$ErrorActionPreference = 'Stop'
$script:Started = 0
$script:Corrupt = $false
$script:Downloads = @()
$script:Payload = [Text.Encoding]::UTF8.GetBytes('cadkit-installer-fixture')
$Hash = [Security.Cryptography.SHA256]::Create()
$script:Digest = ([BitConverter]::ToString($Hash.ComputeHash($script:Payload))).Replace('-', '').ToLowerInvariant()
$Hash.Dispose()
function Invoke-RestMethod {
    param([string]$Uri)
    if ($Uri -notlike 'https://api.github.com/repos/*/releases/latest') { throw "Unexpected URL: $Uri" }
    return @{ tag_name = 'v0.2.0' }
}
function Invoke-WebRequest {
    param([string]$Uri, [string]$OutFile, [switch]$UseBasicParsing)
    $script:Downloads += $OutFile
    if ($Uri.EndsWith('/SHA256SUMS')) {
        $Checksum = if ($script:Corrupt) { '0' * 64 } else { $script:Digest }
        [IO.File]::WriteAllText($OutFile, "$Checksum  CadKit-0.2.0-windows-x64.exe`n")
    } elseif ($Uri.EndsWith('/CadKit-0.2.0-windows-x64.exe')) {
        [IO.File]::WriteAllBytes($OutFile, $script:Payload)
    } else { throw "Unexpected URL: $Uri" }
}
function Start-Process {
    param([string]$FilePath, [switch]$Wait, [switch]$PassThru)
    if (-not (Test-Path $FilePath) -or -not $Wait -or -not $PassThru) { throw 'Invalid installer launch' }
    $script:Started += 1
    return @{ ExitCode = 0 }
}
$Installer = Join-Path $PSScriptRoot '../scripts/install.ps1'
& $Installer -Version ''
if ($script:Started -ne 1) { throw 'Verified installer was not started' }
if ($script:Downloads.Count -ne 2) { throw 'Expected binary and checksum downloads' }
foreach ($Path in $script:Downloads) {
    if (Test-Path $Path) { throw 'Installer temporary files were not cleaned' }
}
$script:Corrupt = $true
$Rejected = $false
try { & $Installer -Version '0.2.0' } catch {
    if ($_.Exception.Message -notlike '*Checksum verification failed*') { throw }
    $Rejected = $true
}
if (-not $Rejected -or $script:Started -ne 1) { throw 'Corrupt installer was not rejected before launch' }
$Rejected = $false
try { & $Installer -Version '../../invalid' } catch {
    if ($_.Exception.Message -notlike '*Invalid release version*') { throw }
    $Rejected = $true
}
if (-not $Rejected) { throw 'Invalid version was not rejected' }
Write-Host 'Windows installer checks passed (verified download, checksum rejection, cleanup, version validation).'
