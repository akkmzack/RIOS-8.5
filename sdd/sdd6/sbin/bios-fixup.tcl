#! /usr/bin/tclsh
#
# Updates the BIOS configuration settings on 3010/5010 systems
# that use the Supermicro X5DPE-G2 motherboard if they have the
# Summary Screen enabled
#

# Check that this is using an E7501 chipset
if [catch {
    exec lspci | grep -i e7501
} err] {
    exit 0
}

# Check that this is a Supermicro motherboard of the expected type
if [catch {
    exec dmidecode | grep X5DP8
} err] {
    exit 0
}

# We need to enable the summary screen to resolve Bug 5630
exec /sbin/modprobe nvram
if ![file exists /dev/nvram] {
    exec /bin/mknod /dev/nvram c 10 144
}
set f [open "/dev/nvram" r+]
fconfigure $f -translation binary

# List of addresses and values we want to change to enable the summary screen
set L [list [list 0x31 0xfe 0xd7] [list 0x32 0x3c 0x01] [list 0x45 0x47 0x4f]]

set disabled 1
set enabled 1
foreach pair $L {
    foreach {addr prev new} $pair break
    set cprev [format "%c" $prev]
    set cnew [format "%c" $new]

    seek $f $addr start
    set c [read $f 1]
    if {[string compare $cprev $c] != 0} {
	set disabled 0
    }
    if {[string compare $cnew $c] != 0} {
	set enabled 0
    }
}

if {$enabled} {
    #puts "BIOS Summary Screen is already enabled"
    puts "No BIOS configuration changes required"
    exit 0
}
if {!$disabled} {
    puts "No BIOS configuration changes required"
    exit 0
}

foreach pair $L {
    foreach {addr prev new} $pair break
    set c [format "%c" $new]

    seek $f $addr start
    puts -nonewline $f $c
    seek $f [expr $addr+0x80] start
    puts -nonewline $f $c
}

close $f
puts "Updated BIOS configuration settings"
exit 0
