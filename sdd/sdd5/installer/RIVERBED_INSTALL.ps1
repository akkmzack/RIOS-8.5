
Param(
    [string]$VHDLocation = $null,
    [string]$InstallLocation = $null,
    [string]$VMName="Riverbed Steelhead",
    [string]$model = $null,
    [string]$ComputerName = ".",
    [int]$NumInpaths = 1,
    [string]$PrimaryNetwork = $null,
    [string]$AuxNetwork = $null,
    [string]$Wan0_0Network = $null,
    [string]$Lan0_0Network = $null,
    [string]$Wan1_0Network = $null,
    [string]$Lan1_0Network = $null,
    [string]$Wan2_0Network = $null,
    [string]$Lan2_0Network = $null,
    [string]$Wan3_0Network = $null,
    [string]$Lan3_0Network = $null,
    [string]$Wan4_0Network = $null,
    [string]$Lan4_0Network = $null,
    [long]$SegstoreSize = 0,
    [switch]$PowerOn
)

Import-Module Hyper-V

$NumInpathsMax = 5
$AdapterPrimaryName = "primary"
$AdapterAuxName = "aux"
$AdapterLanName = "lan"
$AdapterWanName = "wan"
$defaultVhdName = "mgmt.vhd"
$scriptPath = Split-Path $MyInvocation.MyCommand.Path

Function GetFreeDiskSpace()
{
    param($dir)

    $space = gwmi Win32_Volume -Filter "DriveType=3" `
        | where { $dir -Like "$($_.Name)*" } `
        | sort Name -Desc `
        | select -First 1 FreeSpace

    return [long]$space.FreeSpace
}

Function GetVhdLocation()
{
    param($location)
    if (!($location)) {
        $retLocation = $scriptPath + "\" + $defaultVhdName
    } elseif ((Test-Path $location) -and ((get-item $location).PSIsContainer)) {
        $retLocation = $location + "\" + $defaultVhdName
    } else {
        $retLocation = $location
    }

    $ext = [System.IO.Path]::GetExtension($retLocation)

    if (!(Test-Path $retLocation)) {
        $retLocation = read-host "Unable to locate $retLocation. Please enter the location of the VHD"
        $retLocation = GetVhdLocation $retLocation
    } elseif ($ext -ne ".vhd") {
        $retLocation = read-host "$retLocation does not appear to be a VHD. Please enter the location of the VHD"
        $retLocation = GetVhdLocation $retLocation
    }

    return $retLocation
}

Function GetInstallLocation()
{
    param($location,$vm_name)
    if (!($location)) {
        $retLocation = read-host "Please enter the location to install the VM"
    } else {
        $retLocation = $location
    }

    while (!(Test-Path $retLocation)) {
        $retLocation = read-host "Unable to locate $retLocation. Please enter the location to install the VM"
    }

    $retLocation = $retLocation + "\" + $vm_name
    $baseLocation = $retLocation
    $count = 0
    while (Test-Path $retLocation) {
        $retLocation = $baseLocation + "_$count"
        $count++
    }

    md -Path $retLocation > $null
    return $retLocation
}

Function New-Model()
{
    param($CPU,$RAM,$MGMT,$SEG)
    
    $modelVal = new-object PSObject
    
    $modelVal | add-member -type NoteProperty -Name CPU -Value $CPU
    $modelVal | add-member -type NoteProperty -Name RAM -Value $RAM
    $modelVal | add-member -type NoteProperty -Name MGMT -Value $MGMT
    $modelVal | add-member -type NoteProperty -Name SEG -Value $SEG
    
    return $modelVal
}

$ModelAttrib = @{
    VCX555M = New-Model 1 2048MB 38GB 80GB;
    VCX555H = New-Model 1 2048MB 38GB 80GB;
    VCX755L = New-Model 2 2048MB 38GB 100GB;
    VCX755M = New-Model 2 2048MB 38GB 100GB;
    VCX755H = New-Model 2 4096MB 38GB 150GB;
    VCX1555L = New-Model 4 8192MB 38GB 400GB;
    VCX1555M = New-Model 4 8192MB 38GB 400GB;
    VCX1555H = New-Model 4 8192MB 38GB 400GB;

}

Function ListModels() {
    $sortedList = @{}
    $ModelAttrib.GetEnumerator() | ForEach-Object {
        $sortedList.add(
            $_.Name,
            [int]$_.Name.
            Replace("VCX", "").
            Replace("L", "01").
            Replace("M", "02").
            Replace("H", "03")
        )
    }
    $sortedList = $sortedList.GetEnumerator() | Sort-Object Value | % {
        $_.Key
    }
    return $sortedList -join ", "
}

Function GetModel()
{
    param($modelName)
    $modelList = ListModels

    if (!($modelName)) {
        $retModel = read-host "Please enter a model ($modelList)"
    } else {
        $retModel = $modelName
    }

    while ($ModelAttrib[$retModel] -eq $null) {
        $retModel = read-host "Unknown model $retModel. Please enter a model ($modelList)"
    }

    return $retModel
}

Function CheckDiskSize()
{
    param($modelName,$storeSize,$dir)
    $totalSize = $ModelAttrib[$modelName].MGMT + $storeSize
    $freeSpace = GetFreeDiskSpace $dir

    if ($totalSize -gt $freeSpace) {
        Write-Host "Insufficient space in $dir to install"
        exit
    }
}

Function GetVMName()
{
    param($name)

    $name = $name.trim()
    $exists = get-vm -ComputerName $ComputerName -Name $name `
        -ErrorAction SilentlyContinue

    if ($name -eq "") {
        $name = read-host "A VM name cannot be empty. Please enter a new name"
        $name = GetVMName $name
    } elseif ($exists) {
        $name = read-host "A VM named $name already exists. Please enter a new name"
        $name = GetVMName $name
    }

    return $name
}

Function GetNumInpaths()
{
    param($num)

    while (($num -gt $NumInpathsMax) -or ($num -lt 0)) {
        $num = read-host "You specified the number of inpath pairs to be $num, but the value must be between 0 and $NumInpathsMax. Please enter a new number of inpath pairs"
        $num = [int]$num
    }

    return $num
}

Function ConfigureAdapter() {
    param($adapterName,$switchName)
    $attachSwitch = $switchName

    Add-VMNetworkAdapter -vmname $VMName -ComputerName $ComputerName `
        -Name $adapterName

    if ($attachSwitch) {
        $exists = Get-VMSwitch -ComputerName $ComputerName -Name $attachSwitch `
            -ErrorAction SilentlyContinue
        while (!($exists)) {
            $attachSwitch = read-host "Unable to find vSwitch $attachSwitch. Please enter a new vSwitch name to attach $adapterName ($switchList), or blank to skip."
            if (!($attachSwitch)) {
                break;
            }

            $exists = Get-VMSwitch -ComputerName $ComputerName `
                -Name $attachSwitch -ErrorAction SilentlyContinue
        }
    }

    if ($attachSwitch) {
        Connect-VMNetworkAdapter -vmname $VMName -ComputerName $ComputerName `
            -Name $adapterName -SwitchName $attachSwitch
    }
}

Function CleanUpExit() {
    param($Name,$Computer,$Location)
    Remove-VM -Name $Name -ComputerName $Computer -Force -ErrorAction `
        SilentlyContinue
    Start-Sleep -m 1000
    Remove-Item $Location -recurse -ErrorAction SilentlyContinue
}

$VMName = GetVMName $VMName
$VHDLocation = GetVhdLocation $VHDLocation
$InstallLocation = GetInstallLocation $InstallLocation $VMName
$model = GetModel $model
$NumInpaths = GetNumInpaths $NumInpaths

if ($SegstoreSize -eq 0) {
    $StoreDiskSize = $ModelAttrib[$model].SEG
} else {
    $StoreDiskSize = $SegstoreSize
}

$InstallComplete = $false
try {
    CheckDiskSize $model $StoreDiskSize $InstallLocation

    Write-Host "Creating New VM... " -nonewline
    new-vm -name $VMName -ComputerName $ComputerName -path $InstallLocation `
        -MemoryStartupBytes $ModelAttrib[$model].RAM -BootDevice IDE -NoVHD

    Set-VMProcessor -vmname $VMName -ComputerName $ComputerName `
        -Count $ModelAttrib[$model].CPU -Reserve 100

    #Remove all network addapters so we start with a clean slate
    $NetAdapters = Get-VMNetworkAdapter -vmname $VMName -ComputerName `
        $ComputerName
    ForEach ($actAdapter in $NetAdapters) {
        Remove-VMNetworkAdapter -vmname $VMName -ComputerName $ComputerName
    }

    $switchList = ""
    $switches = Get-VMSwitch -ComputerName $ComputerName
    ForEach ($switch in $switches) {
        if ($switchList -ne "") {
            $switchList = $switchList + ","
        }
        $switchList = $switchList + $switch.Name
    }

    ConfigureAdapter $AdapterPrimaryName $PrimaryNetwork
    ConfigureAdapter $AdapterAuxName $AuxNetwork

    for ($i = 0; $i -lt $NumInpaths; $i++) {
        $LanNetwork = gv "Lan${i}_0Network" -Valueonly
        $WanNetwork = gv "Wan${i}_0Network" -Valueonly

        ConfigureAdapter "${AdapterLanName}${i}_0" $LanNetwork
        ConfigureAdapter "${AdapterWanName}${i}_0" $WanNetwork
    }

    #Remove the DVD drive
    $DVD = Get-VMDvdDrive -VMName $VMName -ComputerName $ComputerName
    ForEach ($actDVD in $DVD) {
        Remove-VMDvdDrive -VMName $VMName -ComputerName $ComputerName `
            -ControllerNumber $actDVD.ControllerNumber -ControllerLocation `
            $actDVD.ControllerLocation
    }

    Write-Host "Done!"

    Write-Host "Starting Disk Creation (This may take a few moments)... " `
        -nonewline

    $VHDName = Split-Path $VHDLocation -leaf
    Convert-VHD -Path $VHDLocation -ComputerName $ComputerName `
        -DestinationPath "$InstallLocation/$VHDName" -VHDType Fixed

    add-vmharddiskdrive -vmname $VMName -ComputerName $ComputerName `
        -ControllerNumber 0 -ControllerLocation 0 `
        -Path "${InstallLocation}\${VHDName}"

    new-vhd -Path "${InstallLocation}\segstore.vhd" -ComputerName `
        $ComputerName -size $StoreDiskSize -Fixed

    add-vmharddiskdrive -vmname $VMName -ComputerName $ComputerName `
        -ControllerNumber 0 -ControllerLocation 1 `
        -Path "${InstallLocation}\segstore.vhd"

    $InstallComplete = $true
    Write-Host "Done!"
} finally {
    if ($InstallComplete -eq $false) {
        Write-Host "Abort"
        CleanUpExit $VMName $ComputerName $InstallLocation
    }
}

if ($PowerOn -eq $true) {
    Start-VM -Name $VMName -ComputerName $ComputerName
}
