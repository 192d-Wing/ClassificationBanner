<#
.SYNOPSIS
    Compile ClassificationBanner.man into a resource-only DLL.

.DESCRIPTION
    Runs the standard ETW manifest toolchain:
        mc.exe   -> header + .rc + .bin resources
        rc.exe   -> .res
        link.exe -> ClassificationBannerEvents.dll  (resource-only, -noentry)

    The resulting DLL carries the WEVT_TEMPLATE and message-table resources
    that wevtutil registers (/rf /mf) and Event Viewer uses to render events
    for the ClassificationBanner/Operational channel.

    Auto-discovers mc.exe/rc.exe from the newest Windows 10/11 SDK and
    link.exe from the newest Visual Studio install. Override any of them with
    the -McPath / -RcPath / -LinkPath parameters.

.OUTPUTS
    <repo>\EventManifest\bin\ClassificationBannerEvents.dll
#>
[CmdletBinding()]
param(
    [string]$Manifest = (Join-Path $PSScriptRoot 'ClassificationBanner.man'),
    [string]$OutDir   = (Join-Path $PSScriptRoot 'bin'),
    [string]$McPath,
    [string]$RcPath,
    [string]$LinkPath,
    [ValidateSet('x64', 'arm64', 'x86')]
    [string]$Arch = 'x64'
)

$ErrorActionPreference = 'Stop'

function Get-VersionFromName {
    # Parse a directory name as a [version], or [version]0.0 when it isn't one,
    # so version directories sort numerically (10.0.26100.0 > 10.0.9000.0)
    # instead of lexically.
    param([string]$Name)
    $v = $null
    if ([version]::TryParse($Name, [ref]$v)) { return $v }
    return [version]'0.0'
}

function Find-SdkTool {
    # Locate an SDK tool (mc.exe/rc.exe) by probing only the per-version arch
    # subdir of each SDK bin root — no full-tree recursion — and picking the
    # highest SDK version that actually has the tool for $Arch.
    param([string]$Tool, [string]$Arch)
    $roots = @("${env:ProgramFiles(x86)}\Windows Kits\10\bin", "${env:ProgramFiles}\Windows Kits\10\bin")
    $versionDirs = foreach ($root in $roots) {
        if (Test-Path $root) { Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue }
    }
    foreach ($dir in ($versionDirs | Sort-Object { Get-VersionFromName $_.Name } -Descending)) {
        $candidate = Join-Path $dir.FullName "$Arch\$Tool"
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

function Find-VsLinker {
    # Locate link.exe by walking only VS\<year>\<edition>\VC\Tools\MSVC\<ver>\
    # (not the whole VS tree) and picking the highest MSVC version that has a
    # linker targeting $Arch, preferring an x64-hosted toolset.
    param([string]$Arch)
    $roots = @("${env:ProgramFiles}\Microsoft Visual Studio", "${env:ProgramFiles(x86)}\Microsoft Visual Studio")
    $msvcRoots = foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        foreach ($year in Get-ChildItem $root -Directory -ErrorAction SilentlyContinue) {
            foreach ($edition in Get-ChildItem $year.FullName -Directory -ErrorAction SilentlyContinue) {
                $p = Join-Path $edition.FullName 'VC\Tools\MSVC'
                if (Test-Path $p) { $p }
            }
        }
    }
    $verDirs = foreach ($mr in $msvcRoots) { Get-ChildItem $mr -Directory -ErrorAction SilentlyContinue }
    foreach ($dir in ($verDirs | Sort-Object { Get-VersionFromName $_.Name } -Descending)) {
        foreach ($hostArch in @('Hostx64', 'Hostx86', 'HostARM64')) {
            $candidate = Join-Path $dir.FullName "bin\$hostArch\$Arch\link.exe"
            if (Test-Path $candidate) { return $candidate }
        }
    }
    return $null
}

if (-not $McPath)   { $McPath   = Find-SdkTool 'mc.exe' $Arch }
if (-not $RcPath)   { $RcPath   = Find-SdkTool 'rc.exe' $Arch }
if (-not $LinkPath) { $LinkPath = Find-VsLinker $Arch }

foreach ($t in @(@{n = 'mc.exe'; p = $McPath }, @{n = 'rc.exe'; p = $RcPath }, @{n = 'link.exe'; p = $LinkPath })) {
    if (-not $t.p -or -not (Test-Path $t.p)) {
        throw "Could not locate $($t.n). Install the Windows SDK / Visual Studio Build Tools, or pass the path explicitly."
    }
}

Write-Host "mc.exe   : $McPath"
Write-Host "rc.exe   : $RcPath"
Write-Host "link.exe : $LinkPath"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# mc.exe writes its generated files to the current directory; run from $OutDir.
Push-Location $OutDir
try {
    & $McPath -um $Manifest
    if ($LASTEXITCODE) { throw "mc.exe failed ($LASTEXITCODE)" }

    $rcFile = Join-Path $OutDir 'ClassificationBanner.rc'
    if (-not (Test-Path $rcFile)) { throw "mc.exe did not produce ClassificationBanner.rc" }

    & $RcPath /nologo /r $rcFile
    if ($LASTEXITCODE) { throw "rc.exe failed ($LASTEXITCODE)" }

    $resFile = Join-Path $OutDir 'ClassificationBanner.res'
    $dllFile = Join-Path $OutDir 'ClassificationBannerEvents.dll'
    # /Brepro -> deterministic output (no embedded build timestamp), so an
    # unchanged manifest always yields a byte-identical DLL. The installer's
    # hash check then skips re-copying on upgrade instead of leaving an
    # orphaned, service-locked copy behind.
    & $LinkPath /nologo /dll /noentry /Brepro "/machine:$Arch" "/out:$dllFile" $resFile
    if ($LASTEXITCODE) { throw "link.exe failed ($LASTEXITCODE)" }

    Write-Host "Built: $dllFile" -ForegroundColor Green
}
finally {
    Pop-Location
}
