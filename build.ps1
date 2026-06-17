[CmdletBinding()]
param (
    [Parameter()]
    [String]
    $Version
)
Set-Location $PSScriptRoot

Start-Process uv -ArgumentList "run pyinstaller --onefile --noconsole --distpath=$PSScriptRoot\dist\Windows\ --paths=$PSScriptRoot\src\Windows --name ClassificationBanner $PSScriptRoot/src/Windows/main.py" -wait

# Build the ETW event-log provider resource DLL (mc -> rc -> link). This needs
# the Windows SDK + VS Build Tools; if they're absent, warn and continue so a
# banner package can still be produced (it then installs without event logging).
$eventDllBuilt = $false
try {
    & "$PSScriptRoot\EventManifest\build-eventmanifest.ps1"
    $eventDllBuilt = $true
}
catch {
    Write-Warning "Event-log provider DLL was not built: $($_.Exception.Message)"
    Write-Warning "Package will install WITHOUT Windows event-log integration."
}

Get-ChildItem "$PSScriptRoot\ClassificationBanner_Install" | ForEach-Object {
    Copy-Item $_.FullName .\dist\Windows -Recurse
}
Get-ChildItem "$PSScriptRoot\src\Windows\Group Policy" | ForEach-Object {
    Copy-Item $_.FullName .\dist\Windows\SupportFiles -Recurse
}
Move-Item "$PSScriptRoot\dist\Windows\ClassificationBanner.exe" "$PSScriptRoot\dist\Windows\Files\ClassificationBanner.exe"

# Stage the event-log provider DLL + manifest alongside the exe so the
# installer can copy them into place and register the manifest with wevtutil.
# Skipped when the DLL couldn't be built; the installer then degrades to no
# event logging rather than failing.
if ($eventDllBuilt) {
    Copy-Item "$PSScriptRoot\EventManifest\bin\ClassificationBannerEvents.dll" "$PSScriptRoot\dist\Windows\Files\ClassificationBannerEvents.dll" -Force
    Copy-Item "$PSScriptRoot\EventManifest\ClassificationBanner.man" "$PSScriptRoot\dist\Windows\Files\ClassificationBanner.man" -Force
}

(Get-Content "$PSScriptRoot\dist\Windows\Invoke-AppDeployToolkit.ps1") -replace "AppVersion\s*=.*", "AppVersion                  = `'$($Version.Substring(1))`'" | Set-Content ".\dist\Windows\Invoke-AppDeployToolkit.ps1" -Force


Compress-Archive -Path "$PSScriptRoot\dist\Windows\" -DestinationPath "$PSScriptRoot\dist\ClassificationBanner-$Version.zip"