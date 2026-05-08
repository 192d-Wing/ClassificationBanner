<#

.SYNOPSIS
PSAppDeployToolkit - This script performs the installation or uninstallation of an application(s).

.DESCRIPTION
- The script is provided as a template to perform an install, uninstall, or repair of an application(s).
- The script either performs an "Install", "Uninstall", or "Repair" deployment type.
- The install deployment type is broken down into 3 main sections/phases: Pre-Install, Install, and Post-Install.

The script imports the PSAppDeployToolkit module which contains the logic and functions required to install or uninstall an application.

.PARAMETER DeploymentType
The type of deployment to perform.

.PARAMETER DeployMode
Specifies whether the installation should be run in Interactive (shows dialogs), Silent (no dialogs), NonInteractive (dialogs without prompts) mode, or Auto (shows dialogs if a user is logged on, device is not in the OOBE, and there's no running apps to close).

Silent mode is automatically set if it is detected that the process is not user interactive, no users are logged on, the device is in Autopilot mode, or there's specified processes to close that are currently running.

.PARAMETER SuppressRebootPassThru
Suppresses the 3010 return code (requires restart) from being passed back to the parent process (e.g. SCCM) if detected from an installation. If 3010 is passed back to SCCM, a reboot prompt will be triggered.

.PARAMETER TerminalServerMode
Changes to "user install mode" and back to "user execute mode" for installing/uninstalling applications for Remote Desktop Session Hosts/Citrix servers.

.PARAMETER DisableLogging
Disables logging to file for the script.

.EXAMPLE
powershell.exe -File Invoke-AppDeployToolkit.ps1

.EXAMPLE
powershell.exe -File Invoke-AppDeployToolkit.ps1 -DeployMode Silent

.EXAMPLE
powershell.exe -File Invoke-AppDeployToolkit.ps1 -DeploymentType Uninstall

.EXAMPLE
Invoke-AppDeployToolkit.exe -DeploymentType Install -DeployMode Silent

.INPUTS
None. You cannot pipe objects to this script.

.OUTPUTS
None. This script does not generate any output.

.NOTES
Toolkit Exit Code Ranges:
- 60000 - 68999: Reserved for built-in exit codes in Invoke-AppDeployToolkit.ps1, and Invoke-AppDeployToolkit.exe
- 69000 - 69999: Recommended for user customized exit codes in Invoke-AppDeployToolkit.ps1
- 70000 - 79999: Recommended for user customized exit codes in PSAppDeployToolkit.Extensions module.

.LINK
https://psappdeploytoolkit.com

#>

[CmdletBinding()]
param
(
    # Default is 'Install'.
    [Parameter(Mandatory = $false)]
    [ValidateSet('Install', 'Uninstall', 'Repair')]
    [System.String]$DeploymentType,

    # Default is 'Auto'. Don't hard-code this unless required.
    [Parameter(Mandatory = $false)]
    [ValidateSet('Auto', 'Interactive', 'NonInteractive', 'Silent')]
    [System.String]$DeployMode,

    [Parameter(Mandatory = $false)]
    [System.Management.Automation.SwitchParameter]$SuppressRebootPassThru,

    [Parameter(Mandatory = $false)]
    [System.Management.Automation.SwitchParameter]$TerminalServerMode,

    [Parameter(Mandatory = $false)]
    [System.Management.Automation.SwitchParameter]$DisableLogging
)


##================================================
## MARK: Variables
##================================================

# Zero-Config MSI support is provided when "AppName" is null or empty.
# By setting the "AppName" property, Zero-Config MSI will be disabled.
$adtSession = @{
    # App variables.
    AppVendor                   = 'Department of War'
    AppName                     = 'ClassificationBanner'
    AppVersion                  = '1.3.0'
    AppArch                     = 'x64'
    AppLang                     = 'EN'
    AppRevision                 = '01'
    AppSuccessExitCodes         = @(0)
    AppRebootExitCodes          = @(1641, 3010)
    AppProcessesToClose         = @('ClassificationBanner')  # Close any running instance
    AppScriptVersion            = '1.0.0'
    AppScriptDate               = '2025-11-29'
    AppScriptAuthor             = 'TSGT JOHN EDWARD WILLMAN V <john.willman.1@us.af.mil>'
    RequireAdmin                = $true

    # Install Titles (Only set here to override defaults set by the toolkit).
    InstallName                 = ''
    InstallTitle                = ''

    # Script variables.
    DeployAppScriptFriendlyName = $MyInvocation.MyCommand.Name
    DeployAppScriptParameters   = $PSBoundParameters
    DeployAppScriptVersion      = '4.1.7'
}

function Test-ClassificationBannerInstalled {
    [CmdletBinding()]
    param()

    $installPath = Join-Path $env:ProgramFiles 'Department of War\ClassificationBanner'
    $exeName = 'ClassificationBanner.exe'
    $installedExePath = Join-Path $installPath $exeName

    $fileExists = Test-Path -Path $installedExePath -PathType Leaf

    $taskExists = $null -ne (Get-ScheduledTask -TaskName 'ClassificationBanner' -TaskPath '\Department of War\' -ErrorAction SilentlyContinue)

    return ($fileExists -and $taskExists)
}

function Install-ADTDeployment {
    [CmdletBinding()]
    param
    (
    )

    ##================================================
    ## MARK: Pre-Install
    ##================================================
    $adtSession.InstallPhase = "Pre-$($adtSession.DeploymentType)"

    ## Show Welcome Message, close processes if specified, allow up to 3 deferrals, verify there is enough disk space to complete the install, and persist the prompt.
    $saiwParams = @{
        AllowDefer     = $true
        DeferTimes     = 3
        CheckDiskSpace = $true
        PersistPrompt  = $true
    }
    if ($adtSession.AppProcessesToClose.Count -gt 0) {
        $saiwParams.Add('CloseProcesses', $adtSession.AppProcessesToClose)
    }
    Show-ADTInstallationWelcome @saiwParams

    ## Show Progress Message (with the default message).
    Show-ADTInstallationProgress

    ## <Perform Pre-Installation tasks here>


    ##================================================
    ## MARK: Install
    ##================================================
    $adtSession.InstallPhase = $adtSession.DeploymentType

    ## Handle Zero-Config MSI installations.
    if ($adtSession.UseDefaultMsi) {
        $ExecuteDefaultMSISplat = @{ Action = $adtSession.DeploymentType; FilePath = $adtSession.DefaultMsiFile }
        if ($adtSession.DefaultMstFile) {
            $ExecuteDefaultMSISplat.Add('Transforms', $adtSession.DefaultMstFile)
        }
        Start-ADTMsiProcess @ExecuteDefaultMSISplat
        if ($adtSession.DefaultMspFiles) {
            $adtSession.DefaultMspFiles | Start-ADTMsiProcess -Action Patch
        }
    }

    ## <Perform Installation tasks here>
    try {
        Write-ADTLogEntry -Message "Starting install for $($adtSession.AppName)." -Severity 1

        $installPath = Join-Path $env:ProgramFiles 'Department of War\ClassificationBanner'
        $exeName = 'ClassificationBanner.exe'
        $installedExePath = Join-Path $installPath $exeName

        # Path to payload in .\Files
        $sourceExe = Join-Path (Join-Path $PSScriptRoot 'Files') $exeName

        # Ensure install directory exists
        if (-not (Test-Path $installPath)) {
            New-Item -Path $installPath -ItemType Directory -Force | Out-Null
            Write-ADTLogEntry -Message "Created install directory: $installPath" -Severity 1
        }

        # Copy EXE into place
        Copy-Item -Path $sourceExe -Destination $installedExePath -Force
        Write-ADTLogEntry -Message "Copied $sourceExe to $installedExePath" -Severity 1

        # Migrate from legacy HKLM Run key (used pre-v1.3.26). Removing it
        # here keeps the new scheduled task as the sole autostart so we
        # don't end up launching two banner instances on logon.
        $legacyRunKeyPath = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run'
        $legacyRunKeyName = 'ClassificationBanner'
        if ((Test-Path $legacyRunKeyPath) -and (Get-ItemProperty -Path $legacyRunKeyPath -Name $legacyRunKeyName -ErrorAction SilentlyContinue)) {
            Remove-ItemProperty -Path $legacyRunKeyPath -Name $legacyRunKeyName -ErrorAction SilentlyContinue
            Write-ADTLogEntry -Message "Removed legacy Run key: $legacyRunKeyPath\$legacyRunKeyName" -Severity 1
        }

        # Register a per-machine scheduled task that launches the banner at
        # logon for any user. Unlike the Run key, this can't be disabled
        # from Task Manager > Startup, which matters for a security banner.
        $taskName = 'ClassificationBanner'
        $taskPath = '\Department of War\'
        if (Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false -ErrorAction SilentlyContinue
        }
        $taskAction    = New-ScheduledTaskAction -Execute $installedExePath
        $taskTrigger   = New-ScheduledTaskTrigger -AtLogOn
        $taskPrincipal = New-ScheduledTaskPrincipal -GroupId 'BUILTIN\Users' -RunLevel LeastPrivilege
        $taskSettings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
        Register-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Action $taskAction -Trigger $taskTrigger -Principal $taskPrincipal -Settings $taskSettings -Force | Out-Null
        Write-ADTLogEntry -Message "Registered scheduled task: $taskPath$taskName -> $installedExePath" -Severity 1

        # Optional: kill any running instance and start fresh
        Get-Process -Name 'ClassificationBanner' -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue

        Start-Process -FilePath $installedExePath -ErrorAction SilentlyContinue
        Write-ADTLogEntry -Message "Launched $installedExePath after install." -Severity 1
    }
    catch {
        Write-ADTLogEntry -Message "Error during install: $($_.Exception.Message)" -Severity 3
        throw
    }

    # --- Copy ADMX / ADML to local PolicyDefinitions ---
    $policyDefRoot = Join-Path $env:SystemRoot 'PolicyDefinitions'
    $supportFilesDir = Join-Path $PSScriptRoot 'SupportFiles'

    Write-ADTLogEntry -Message "Copying ADMX/ADML from $supportFilesDir to $policyDefRoot" -Severity 1

    # Ensure PolicyDefinitions exists
    if (-not (Test-Path $policyDefRoot)) {
        New-Item -Path $policyDefRoot -ItemType Directory -Force | Out-Null
        Write-ADTLogEntry -Message "Created PolicyDefinitions folder: $policyDefRoot" -Severity 1
    }

    # 1) Copy all ADMX files in SupportFiles root -> C:\Windows\PolicyDefinitions
    Get-ChildItem -Path $supportFilesDir -Filter '*.admx' -File -ErrorAction SilentlyContinue |
    ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $policyDefRoot -Force
        Write-ADTLogEntry -Message "Copied ADMX: $($_.Name) -> $policyDefRoot" -Severity 1
    }

    # 2) Copy ADML language folders (e.g. SupportFiles\en-US\*.adml)
    Get-ChildItem -Path $supportFilesDir -Directory -ErrorAction SilentlyContinue |
    ForEach-Object {
        $langFolder = $_.Name          # e.g. "en-US"
        $srcLangDir = $_.FullName
        $dstLangDir = Join-Path $policyDefRoot $langFolder

        # Only treat it as a language folder if it actually has .adml files
        $admlFiles = Get-ChildItem -Path $srcLangDir -Filter '*.adml' -File -ErrorAction SilentlyContinue
        if ($admlFiles) {
            if (-not (Test-Path $dstLangDir)) {
                New-Item -Path $dstLangDir -ItemType Directory -Force | Out-Null
                Write-ADTLogEntry -Message "Created language folder: $dstLangDir" -Severity 1
            }

            foreach ($file in $admlFiles) {
                Copy-Item -Path $file.FullName -Destination $dstLangDir -Force
                Write-ADTLogEntry -Message "Copied ADML: $($file.Name) -> $dstLangDir" -Severity 1
            }
        }

        
    }

    # --- Add ARP (Add/Remove Programs) entry ---
    $arpBase = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
    $appKeyName = 'ClassificationBanner'   # Can be a GUID, but product name is fine
    $arpKeyPath = Join-Path $arpBase $appKeyName

    $installPath = Join-Path $env:ProgramFiles 'Department of War\ClassificationBanner'
    $exeName = 'ClassificationBanner.exe'
    $installedExePath = Join-Path $installPath $exeName

    Write-ADTLogEntry -Message "Creating ARP entry at $arpKeyPath" -Severity 1

    # Create the key
    if (-not (Test-Path $arpKeyPath)) {
        New-Item -Path $arpKeyPath -Force | Out-Null
    }

    # Required ARP values
    New-ItemProperty -Path $arpKeyPath -Name "DisplayName"          -Value "Classification Banner" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $arpKeyPath -Name "Publisher"            -Value "Department of War"     -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $arpKeyPath -Name "DisplayVersion"       -Value $adtSession.AppVersion  -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $arpKeyPath -Name "InstallLocation"      -Value $installPath            -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $arpKeyPath -Name "DisplayIcon"          -Value $installedExePath       -PropertyType String -Force | Out-Null

    # Required for Programs and Features uninstall functionality
    $uninstallCmd = "`"$PSScriptRoot\Invoke-AppDeployToolkit.ps1`" -DeploymentType Uninstall -DeployMode Silent"
    New-ItemProperty -Path $arpKeyPath -Name "UninstallString"         -Value "powershell.exe -ExecutionPolicy Bypass -File $uninstallCmd" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $arpKeyPath -Name "QuietUninstallString"    -Value "powershell.exe -ExecutionPolicy Bypass -File $uninstallCmd" -PropertyType String -Force | Out-Null

    # Make it appear as a real installer
    New-ItemProperty -Path $arpKeyPath -Name "NoModify"    -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path $arpKeyPath -Name "NoRepair"    -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path $arpKeyPath -Name "InstallDate" -Value (Get-Date -Format yyyyMMdd) -PropertyType String -Force | Out-Null




    ##================================================
    ## MARK: Post-Install
    ##================================================
    $adtSession.InstallPhase = "Post-$($adtSession.DeploymentType)"

    ## <Perform Post-Installation tasks here>


    ## Display a message at the end of the install.
    if (!$adtSession.UseDefaultMsi) {
        Show-ADTInstallationPrompt -Message "$($adtSession.AppName) installation completed successfully." -ButtonRightText 'OK' -Icon Information -NoWait
    }
}

function Uninstall-ADTDeployment {
    [CmdletBinding()]
    param
    (
    )

    ##================================================
    ## MARK: Pre-Uninstall
    ##================================================
    $adtSession.InstallPhase = "Pre-$($adtSession.DeploymentType)"

    ## If there are processes to close, show Welcome Message with a 60 second countdown before automatically closing.
    if ($adtSession.AppProcessesToClose.Count -gt 0) {
        Show-ADTInstallationWelcome -CloseProcesses $adtSession.AppProcessesToClose -CloseProcessesCountdown 60
    }

    ## Show Progress Message (with the default message).
    Show-ADTInstallationProgress

    ## <Perform Pre-Uninstallation tasks here>


    ##================================================
    ## MARK: Uninstall
    ##================================================
    $adtSession.InstallPhase = $adtSession.DeploymentType

    ## Handle Zero-Config MSI uninstallations.
    if ($adtSession.UseDefaultMsi) {
        $ExecuteDefaultMSISplat = @{ Action = $adtSession.DeploymentType; FilePath = $adtSession.DefaultMsiFile }
        if ($adtSession.DefaultMstFile) {
            $ExecuteDefaultMSISplat.Add('Transforms', $adtSession.DefaultMstFile)
        }
        Start-ADTMsiProcess @ExecuteDefaultMSISplat
    }

    ## <Perform Uninstallation tasks here>
    try {
        Write-ADTLogEntry -Message "Starting uninstall for $($adtSession.AppName)." -Severity 1

        $installPath = Join-Path $env:ProgramFiles 'Department of War\ClassificationBanner'
        $exeName = 'ClassificationBanner.exe'
        $installedExePath = Join-Path $installPath $exeName

        # Stop process if running
        Get-Process -Name 'ClassificationBanner' -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue

        # Unregister scheduled task (current installs)
        $taskName = 'ClassificationBanner'
        $taskPath = '\Department of War\'
        if (Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false -ErrorAction SilentlyContinue
            Write-ADTLogEntry -Message "Unregistered scheduled task: $taskPath$taskName" -Severity 1
        }

        # Clean up the legacy HKLM Run key if it survived from a pre-v1.3.26 install
        $legacyRunKeyPath = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run'
        $legacyRunKeyName = 'ClassificationBanner'
        if ((Test-Path $legacyRunKeyPath) -and (Get-ItemProperty -Path $legacyRunKeyPath -Name $legacyRunKeyName -ErrorAction SilentlyContinue)) {
            Remove-ItemProperty -Path $legacyRunKeyPath -Name $legacyRunKeyName -ErrorAction SilentlyContinue
            Write-ADTLogEntry -Message "Removed legacy Run key: $legacyRunKeyPath\$legacyRunKeyName" -Severity 1
        }

        # Remove EXE
        if (Test-Path $installedExePath) {
            Remove-Item -Path $installedExePath -Force -ErrorAction SilentlyContinue
            Write-ADTLogEntry -Message "Removed file: $installedExePath" -Severity 1
        }

        # Remove folder if empty
        if (Test-Path $installPath) {
            Try {
                Remove-Item -Path $installPath -Recurse -Force -ErrorAction Stop
                Write-ADTLogEntry -Message "Removed directory: $installPath" -Severity 1
            }
            Catch {
                # If folder not empty / locked, just log it.
                Write-ADTLogEntry -Message "Could not fully remove $($installPath): $($_.Exception.Message)" -Severity 2
            }
        }
    }
    catch {
        Write-ADTLogEntry -Message "Error during uninstall: $($_.Exception.Message)" -Severity 3
        throw
    }

    # --- Remove ARP entry ---
    $arpBase = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
    $appKeyName = 'ClassificationBanner'
    $arpKeyPath = Join-Path $arpBase $appKeyName

    if (Test-Path $arpKeyPath) {
        Remove-Item -Path $arpKeyPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-ADTLogEntry -Message "Removed ARP entry at $arpKeyPath" -Severity 1
    }


    ##================================================
    ## MARK: Post-Uninstallation
    ##================================================
    $adtSession.InstallPhase = "Post-$($adtSession.DeploymentType)"

    ## <Perform Post-Uninstallation tasks here>
}

function Repair-ADTDeployment {
    [CmdletBinding()]
    param
    (
    )

    ##================================================
    ## MARK: Pre-Repair
    ##================================================
    $adtSession.InstallPhase = "Pre-$($adtSession.DeploymentType)"

    ## If there are processes to close, show Welcome Message with a 60 second countdown before automatically closing.
    if ($adtSession.AppProcessesToClose.Count -gt 0) {
        Show-ADTInstallationWelcome -CloseProcesses $adtSession.AppProcessesToClose -CloseProcessesCountdown 60
    }

    ## Show Progress Message (with the default message).
    Show-ADTInstallationProgress

    ## <Perform Pre-Repair tasks here>


    ##================================================
    ## MARK: Repair
    ##================================================
    $adtSession.InstallPhase = $adtSession.DeploymentType

    ## Handle Zero-Config MSI repairs.
    if ($adtSession.UseDefaultMsi) {
        $ExecuteDefaultMSISplat = @{ Action = $adtSession.DeploymentType; FilePath = $adtSession.DefaultMsiFile }
        if ($adtSession.DefaultMstFile) {
            $ExecuteDefaultMSISplat.Add('Transforms', $adtSession.DefaultMstFile)
        }
        Start-ADTMsiProcess @ExecuteDefaultMSISplat
    }

    ## <Perform Repair tasks here>
    try {
        Write-ADTLogEntry -Message "Starting repair for $($adtSession.AppName)." -Severity 1

        $installPath = Join-Path $env:ProgramFiles 'Department of War\ClassificationBanner'
        $exeName = 'ClassificationBanner.exe'
        $installedExePath = Join-Path $installPath $exeName
        $sourceExe = Join-Path (Join-Path $PSScriptRoot 'Files') $exeName

        # Refresh the install dir + exe (idempotent; covers both
        # "not-fully-present" and "drift" cases that the prior version
        # branched on).
        if (-not (Test-Path $installPath)) {
            New-Item -Path $installPath -ItemType Directory -Force | Out-Null
        }
        Copy-Item -Path $sourceExe -Destination $installedExePath -Force

        # (Re)register the scheduled task. Same shape as Install.
        $taskName = 'ClassificationBanner'
        $taskPath = '\Department of War\'
        if (Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false -ErrorAction SilentlyContinue
        }
        $taskAction    = New-ScheduledTaskAction -Execute $installedExePath
        $taskTrigger   = New-ScheduledTaskTrigger -AtLogOn
        $taskPrincipal = New-ScheduledTaskPrincipal -GroupId 'BUILTIN\Users' -RunLevel LeastPrivilege
        $taskSettings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
        Register-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Action $taskAction -Trigger $taskTrigger -Principal $taskPrincipal -Settings $taskSettings -Force | Out-Null
        Write-ADTLogEntry -Message "Repaired EXE and scheduled task for $($adtSession.AppName)." -Severity 1
    }
    catch {
        Write-ADTLogEntry -Message "Error during repair: $($_.Exception.Message)" -Severity 3
        throw
    }


    ##================================================
    ## MARK: Post-Repair
    ##================================================
    $adtSession.InstallPhase = "Post-$($adtSession.DeploymentType)"

    ## <Perform Post-Repair tasks here>
}


##================================================
## MARK: Initialization
##================================================

# Set strict error handling across entire operation.
$ErrorActionPreference = [System.Management.Automation.ActionPreference]::Stop
$ProgressPreference = [System.Management.Automation.ActionPreference]::SilentlyContinue
Set-StrictMode -Version 1

# Import the module and instantiate a new session.
try {
    # Import the module locally if available, otherwise try to find it from PSModulePath.
    if (Test-Path -LiteralPath "$PSScriptRoot\PSAppDeployToolkit\PSAppDeployToolkit.psd1" -PathType Leaf) {
        Get-ChildItem -LiteralPath "$PSScriptRoot\PSAppDeployToolkit" -Recurse -File | Unblock-File -ErrorAction Ignore
        Import-Module -FullyQualifiedName @{ ModuleName = "$PSScriptRoot\PSAppDeployToolkit\PSAppDeployToolkit.psd1"; Guid = '8c3c366b-8606-4576-9f2d-4051144f7ca2'; ModuleVersion = '4.1.7' } -Force
    }
    else {
        Import-Module -FullyQualifiedName @{ ModuleName = 'PSAppDeployToolkit'; Guid = '8c3c366b-8606-4576-9f2d-4051144f7ca2'; ModuleVersion = '4.1.7' } -Force
    }

    # Open a new deployment session, replacing $adtSession with a DeploymentSession.
    $iadtParams = Get-ADTBoundParametersAndDefaultValues -Invocation $MyInvocation
    $adtSession = Remove-ADTHashtableNullOrEmptyValues -Hashtable $adtSession
    $adtSession = Open-ADTSession @adtSession @iadtParams -PassThru
}
catch {
    $Host.UI.WriteErrorLine((Out-String -InputObject $_ -Width ([System.Int32]::MaxValue)))
    exit 60008
}


##================================================
## MARK: Invocation
##================================================

# Commence the actual deployment operation.
try {
    # Import any found extensions before proceeding with the deployment.
    Get-ChildItem -LiteralPath $PSScriptRoot -Directory | & {
        process {
            if ($_.Name -match 'PSAppDeployToolkit\..+$') {
                Get-ChildItem -LiteralPath $_.FullName -Recurse -File | Unblock-File -ErrorAction Ignore
                Import-Module -Name $_.FullName -Force
            }
        }
    }

    # Invoke the deployment and close out the session.
    & "$($adtSession.DeploymentType)-ADTDeployment"
    Close-ADTSession
}
catch {
    # An unhandled error has been caught.
    $mainErrorMessage = "An unhandled error within [$($MyInvocation.MyCommand.Name)] has occurred.`n$(Resolve-ADTErrorRecord -ErrorRecord $_)"
    Write-ADTLogEntry -Message $mainErrorMessage -Severity 3

    ## Error details hidden from the user by default. Show a simple dialog with full stack trace:
    # Show-ADTDialogBox -Text $mainErrorMessage -Icon Stop -NoWait

    ## Or, a themed dialog with basic error message:
    # Show-ADTInstallationPrompt -Message "$($adtSession.DeploymentType) failed at line $($_.InvocationInfo.ScriptLineNumber), char $($_.InvocationInfo.OffsetInLine):`n$($_.InvocationInfo.Line.Trim())`n`nMessage:`n$($_.Exception.Message)" -ButtonRightText OK -Icon Error -NoWait

    Close-ADTSession -ExitCode 60001
}

