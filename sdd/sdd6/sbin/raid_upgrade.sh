#!/bin/sh
#
# Script to perform LSI MegaRAID card firmware upgrade checks
# on startup.  
#
#

UPGRADE_REBOOT_NEEDED=0
UPGRADE_LOG_WARN="/usr/bin/logger -p user.warn -t upgrade"
UPGRADE_LOG_ERR="/usr/bin/logger -p user.err -t upgrade"
UPGRADE_DIR="/tmp/upgrade"
UPGRADE_DEV_RAM="/dev/ram"
UPGRADE_RAID_DEV="/dev/megadev0"
UPGRADE_FILE_LIST_300="/sbin/shutdown /usr/sbin/linflash /usr/sbin/lindsay815F.rom /bin/grep"
CARDTYPE="unknown"

print_both_warn()
{
    echo $1
#   $UPGRADE_LOG_WARN $1
}

create_ram_disk()
{
    if [ ! -d $UPGRADE_DIR ]; then
        mkdir -p $UPGRADE_DIR 

        if [ ! -c $UPGRADE_DEV_RAM ]; then
            mke2fs $UPGRADE_DEV_RAM > /dev/null 2>&1
            if [ $? -ne 0 ]; then
	        print_both_warn "Unable to put extfs on ramdisk. Aborting raid flash update."
	        return 1
            fi
        fi

        mount $UPGRADE_DEV_RAM $UPGRADE_DIR > /dev/null 2>&1
        if [ $? -ne 0 ]; then
	    print_both_warn "Unable to mount ramdisk, aborting raid flash update."
	    return 1
        fi
    fi

    for f in $1; do
	cp $f $UPGRADE_DIR
	if [ $? -ne 0 ]; then
	    print_both_warn "Unable to copy $f to ramdisk, aborting RAID flash update"
	    return 1
	fi
    done

    return 0
}

#----------------------------------------------------------------------------
# On some bios upgrades the disk becomes unavailable 
# The procedure is:
# 1. Create a ramdisk
# 2. Copy linflash, rom file, reboot to ramdisk
# 3. Execute linflash
# This restriction limits shared rebooting and clean up
#----------------------------------------------------------------------------
upgrade_raid_fw()
{
    create_ram_disk "$1" 
    if [ $? -ne 0 ]; then
        print_both_warn "Failed to create ram disk."
        return 1
    fi

    cd $UPGRADE_DIR

    PASS=`./linflash -r -f ./$2 | ./grep changed` > /dev/null 2>&1
    if [ $? = 0 ]; then
        print_both_warn "FW update is successful"
        UPGRADE_REBOOT_NEEDED=1 
    else
        print_both_warn "FW update failed."
        UPGRADE_REBOOT_NEEDED=0
    fi

    return 0
}

get_card_type_by_bios()
{
    if [ "x$BIOS_FAMILY" = "xH" ]; then
        CARDTYPE="300"

    elif [ "x$BIOS_FAMILY" = "xG" ]; then
        CARDTYPE="150"

    else
        echo "Unrecognized bios family"
        return 1
    fi        

    return 0
}

#----------------------------------------------------------------------------
# Latest FW version for 150-6 card is 713R and for 300-8 card is 815C
# Perform an upgrade to 713G and 713N
# Majority of 712T cannot be updated 
# A few of 712T without Sharp chip might be updated
#----------------------------------------------------------------------------
if [ -e /proc/megaraid ]; then

    if [ ! -c $UPGRADE_RAID_DEV ]; then
        /bin/mknod $UPGRADE_RAID_DEV c 254 0
        if [ $? -ne 0 ]; then
            print_both_warn "Unable to make megadev0. Aborting RAID FW flash."
            exit 1
        fi
    fi

    VERSTR=`grep 'Version =' /proc/megaraid/hba0/config | \
        sed -e 's/.*=\([0-9]*\)\([A-Z]\):\([A-Z]\)\([0-9]*\).*/\1 \2 \3 \4/'`

    if [ "x$VERSTR" != "x" ] ; then
        set $VERSTR
        FW_MAJOR=$1
        FW_MINOR=$2
        BIOS_FAMILY=$3
        BIOS_VER=$4
    else
        VERSTR=`egrep '^FW Version' /proc/megaraid/hba0/config | \
            sed -e 's/.*: \([0-9]*\)\([A-Z]\)/\1 \2/'`
        set $VERSTR
        FW_MAJOR=$1
        FW_MINOR=$2

        VERSTR=`egrep '^Bios Version' /proc/megaraid/hba0/config | \
            sed -e 's/.*: \([A-Z]\)\([0-9]*\)/\1 \2/'`
        set $VERSTR
        BIOS_FAMILY=$1
        BIOS_VER=$2
    fi

    print_both_warn "RAID firmware & bios version: [$FW_MAJOR$FW_MINOR:$BIOS_FAMILY$BIOS_VER]"

    MODEL=`grep 'MegaRAID SATA300-8' /proc/megaraid/hba0/config`
    if [ $? -ne 0 ]; then
	
	get_card_type_by_bios
	if [ $? -ne 0 ]; then
	    print_both_warn "Unknown raid card. No fw upgrade."
	    exit 1
	fi
    else
	CARDTYPE="300"
    fi

    if [ "x$CARDTYPE" = "x300" ]; then
        if [ $FW_MAJOR -gt 815 ]; then
            print_both_warn "Current RAID fw version is newer. No need to update FW."
        elif [ $FW_MAJOR -eq 815 -a ! "x$FW_MINOR" = "xC" ]; then
            print_both_warn "RAID firmware version is appropriate"
        else
            print_both_warn "RAID firmware needs to be updated - Performing update NOW..."
            upgrade_raid_fw "$UPGRADE_FILE_LIST_300" "lindsay815F.rom"
            if [ $? -ne 0 ]; then
                exit 1
            fi
        fi
    else
        print_both_warn "Unknown card type. No FW update."
    fi
fi

if [ ${UPGRADE_REBOOT_NEEDED} -eq 1 ]; then
    print_both_warn  "Rebooting system after FW update..."
    ./shutdown -n -r now
fi

exit 0


