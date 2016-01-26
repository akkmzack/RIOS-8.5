#!/bin/sh
#
# Script to perform hardware upgrade checks
# on startup.  This file can be used to perform
# specific initialization on hardware in the following cases:
#
# 1. Hardware support needs to be added and the device was not 
#    initialized previously.
# 2. Software/Firmware upgrades need to be performed while RiOS
#    software is not running (Raid upgrades, etc..)
#

REBOOT_NEEDED=0

#
# Check for initialization needed on compact flash disk
#
if [ -f /sbin/rbt_flash_disk.sh ]; then
FLASH_UPGRADE_SCRIPT="/sbin/rbt_flash_disk.sh"
	${FLASH_UPGRADE_SCRIPT} configure_flash
	RV=$?
	if [ $RV -eq 2 ]; then
        	echo "Signalling reboot - due to flash setup"
		REBOOT_NEEDED=1
	elif [ $RV -eq 1 ]; then
       	 	echo "Error configuring flash disk"
	else
        	echo "Flash configuration ok"
	fi
fi

MODEL=`/opt/tms/bin/mddbreq  -v /config/mfg/mfdb query get - /rbt/mfd/model`
case $MODEL in 
    "50"|"100"|"200"|"300")
	VERS=`/opt/hal/bin/hwtool.py -q bios=version`
	if [ "x$VERS" != "xRBD-1.2" ]; then
	    REV=`/opt/hal/bin/hwtool.py -q revision`
	    if [ ! -f /var/opt/rbt/.100_bios_img_fix -a "x$REV" = "xA" ]; then
		echo "Updating BIOS image, PLEASE DO NOT REBOOT."
		/sbin/flashrom -w /opt/rbt/lib/8A806R12.BIN
		echo "BIOS image update complete, unit will reboot."
		
		touch /var/opt/rbt/.100_bios_img_fix
		REBOOT_NEEDED=1 
	    fi
	    if [ ! -f /var/opt/rbt/.100_ram_fix ]; then
		echo "Updating BIOS configuration."
		modprobe nvram > /dev/null 2>&1
		mknod /dev/nvram c 10 144 > /dev/null 2>&1
		cat /etc/100_nopxe.cfg > /dev/nvram 
		
		echo "BIOS configuration updated, unit will reboot."
		touch /var/opt/rbt/.100_ram_fix
		REBOOT_NEEDED=1 
	    fi
	fi
	;;
esac

# MegaRAID updates
/sbin/upgrade_megaraid.sh

	
# IPMI updates
IPMI_UP=/opt/hal/bin/ipmi/ipmi_upgrade.py
IPMI_UP_FAILED_FILE=/var/opt/rbt/.ipmi_update_failed
if [ -f ${IPMI_UP} ]; then
    UNLOAD=0

    # first check to see what we have to do
    # this includes loading modules
    # 
    IPMI_ACTION=`${IPMI_UP} -l -a`
    if [ $? -ne 0 ]; then
        echo "Error determining the IPMI action"
        # unload the modules just to be sure nothing got loaded
        #
        UNLOAD=1

    else
        # we got a response
        case "x${IPMI_ACTION}" in
            "xnotsup")
                # nothing to do IPMI is not supported.
            ;;
            "xnoimages")
                echo "No IPMI images registered for this appliance"
            ;;
            # only need to unload modules when we actually had to compare versions
            # of the ipmi files in the image and the hw.
            "xuptodate")
                echo "IPMI FW and SDR are up to date for this appliance"
                UNLOAD=1
            ;;
            "xneedsupgrade")
                echo "Checking IPMI updates for this appliance."
                # we used the -l option above, so we don't need to use it here
                UNLOAD=1

                # do the upgrade and display results to stdout.
                ${IPMI_UP} -c
                if [ $? -ne 0 ]; then
                    echo "Failed to update IPMI"
                    if [ ! -f ${IPMI_UP_FAILED_FILE} ]; then
                        # we'll try twice to update the IPMI file, and if
                        # we fail, we'll touch a file to prevent
                        # us from rebooting again, we'll still try
                        # to update the images though, as the failure
                        # may leave the IPMI files inconsistant.
                        touch ${IPMI_UP_FAILED_FILE}
                        REBOOT_NEEDED=1
                    fi
                else
                    REBOOT_NEEDED=1
                fi

            ;;
            *)
                # in case of an error, we want to unload the drivers,
                # since things may be left inconsistant
                UNLOAD=1
                echo "Error processing IPMI upgrade action"
            ;;
        esac
        
    fi
    #
    # unload modules only if we don't need to reboot.
    # in the case where we update the BIOS on a barramundi unit, we'll need to 
    # actually do a hard shut down due to a bug in the BIOS code.
    #
    if [ ${UNLOAD} -ne 0 ]; then
        # if we completed an action that required loading the IPMI modules
        # unload them
        ${IPMI_UP} -u  > /dev/null
    fi

fi


# BIOS check for Minnow
/usr/sbin/dmidecode | grep "Product Name: DTAB" 2>&1 > /dev/null
if [ $? -eq 0 ]; then
    VERS=`/usr/sbin/dmidecode | grep -A1 Megatrends | grep Version | /bin/sed -e "s,.*MINOW,," | /bin/cut -c 0-9`
    if [ "x${VERS}" = "x" -o "${VERS}" -lt 027 ]; then
        echo "Updating BIOS image, PLEASE DO NOT REBOOT."
        /sbin/flashrom -w /opt/rbt/lib/MINOW027.ROM
        if [ $? -ne 0 ]; then
            echo "BIOS image update failed, please contact support."
        else
            echo "BIOS image update complete, unit will reboot."
            REBOOT_NEEDED=1
        fi
    fi
fi


# BIOS_UPDATE is used for barramundi's to indicate that we need a hard cycle via IPMI
# after we do the reflash.
BIOS_UPDATE=0
/usr/sbin/dmidecode | grep "Product Name: S6631" 2>&1 > /dev/null
if [ $? -eq 0 ]; then 
    VERS=`/usr/sbin/dmidecode | grep -A1 Megatrends | grep Version | /bin/sed -e "s,.*V1\.,," | /bin/cut -c 0-2`
    if [ $VERS -lt 10 ]; then
	echo "Updating BIOS image, PLEASE DO NOT REBOOT."
	/sbin/flashrom -w /opt/rbt/lib/6631V110.rom
	if [ $? -ne 0 ]; then
	    echo "BIOS image update failed, please contact support."
	else
	    echo "BIOS image update complete, unit will reboot."
	    BIOS_UPDATE=1
	    REBOOT_NEEDED=1
	fi
    fi
    echo "Checking virtualization bit and fan mode"
    /sbin/update_bios_nvram.py product=S6631 offset=0x97 bits_on=0x08 offset=0x90 bits_on=0x01 offset=0x90 bits_off=0x02
    VB=$?
    if [ $VB -eq 1 ]; then
        echo "Error setting virtualization bit and fan mode"
    elif [ $VB -eq 2 ]; then
        echo "Bit(s) set, will power cycle"
        BIOS_UPDATE=1
        REBOOT_NEEDED=1
    fi
fi

# on sturgeon/gar upgrade to BIOS 1.18
/usr/sbin/dmidecode | grep "Product Name: S6673" 2>&1 > /dev/null
if [ $? -eq 0 ]; then 
    # BIOS
    VERS=`/usr/sbin/dmidecode | grep -A1 Megatrends | grep Version | /bin/sed -e "s,.*V1\.,," | /bin/cut -c 0-2`
    if [ "x${VERS}" = "x" -o "${VERS}" -lt 18 ]; then
        echo "Updating BIOS image, PLEASE DO NOT REBOOT."
        /sbin/flashmac.py -wb /opt/rbt/lib/6673V118.ROM
        if [ $? -ne 0 ]; then
            echo "BIOS image update failed, please contact support."
        else
            echo "BIOS image update complete, unit will reboot."
            REBOOT_NEEDED=1
        fi
    fi
fi

# if gar (not sturgeon) also change the DIMM speed settings in the BIOS
/opt/hal/bin/hwtool.py -q motherboard | grep "400-00300-10" 2>&1 > /dev/null
if [ $? -eq 0 ]; then
    echo "Checking memory speed setting"
    /sbin/update_bios_nvram.py product=S6673 offset=0xA6 bits_on=0x02 offset=0xA6 bits_off=0x01 offset=0xC1 bits_off=0x80 offset=0xC4 bits_on=0x08
    UB=$?
    if [ $UB -eq 1 ]; then
        echo "Error forcing proper memory speed setting"
    elif [ $UB -eq 2 ]; then
        echo "Bit(s) set, will power cycle"
        BIOS_UPDATE=1
        REBOOT_NEEDED=1
    elif [ $UB -eq 3 ]; then
        /usr/bin/logger -p user.notice "Memory speed already forced to 667MHz"
    fi
    echo "Checking Hypertransport settings"
    /sbin/update_bios_nvram.py product=S6673 offset=0x8E bits_off=0x03 offset=0xC1 bits_off=0x80
    UB=$?
    if [ $UB -eq 1 ]; then
        echo "Error forcing proper hypertransport settings"
    elif [ $UB -eq 2 ]; then
        echo "Bit(s) set, will power cycle"
        BIOS_UPDATE=1
        REBOOT_NEEDED=1
    elif [ $UB -eq 3 ]; then
        /usr/bin/logger -p user.notice "Hypertransport OK"
    fi
fi

# if sturgeon, modify the LSI 2x12 serial EPROM 
# changes HOLD/HOLDA window size (20DWORDS to 18 DWORDS)
XPNDR_UPDATE_OK=0
/opt/hal/bin/hwtool.py -q motherboard | grep "400-00300-01" 2>&1 > /dev/null
if [ $? -eq 0 ]; then
    echo "Checking LSI 2x12 Expanders firmware"
    if [ -e /opt/tms/bin/lsiutil ]; then
		/opt/tms/bin/lsiutil -V # check expanders version
		if [ $? -ne 0 ]; then  
			echo "Updating LSIx12 Expanders firmware"
			for loop in 1 2 3 4 5 6 7 8 9 10 # try 10 times, roughly 22 seconds
			do
				echo "Attempting Expanders firmare update $loop time(s)"
				/opt/tms/bin/lsiutil -R n # do update
				if [ $? -eq 0 ]; then # success
					REBOOT_NEEDED=1
					XPNDR_UPDATE_OK=1
					break;
				fi
			done
			if [ $XPNDR_UPDATE_OK -eq 0 ]; then 
				echo "FATAL: LSI Expander firmware update failed." > /config/lsiutil.failure
				echo "Please contact support. Unstable system upon reboot." >> /config/lsiutil.failure
			fi
		else
			echo "LSIx12 Expanders contain updated firmare"
		fi
	else
		# supress this warning, until QA qualifies tool
		echo "WARNING: lsiutil tool not found. Unable to update expanders."
	fi
fi

###############################################################################
# Utilities for manually syncing the appliance when we need to hard cycle the unit.
#
###############################################################################

#
# Force a sync on a block device
#
do_sync_blockdev()
{
    if [ -f /sbin/blockdev -a -x /sbin/blockdev ]; then
	/sbin/blockdev --flushbufs $1
    else
        echo "Block flush utility is missing"
    fi
}

#
# Find the block device that corresponds to a given mounted partition
#
# returns an empty string if the partition is not mounted.
#
do_get_fs_blockdev()
{
    local FS="$1"

    if [ "x${FS}" = "x" ]; then
        return
    fi

    BDEV=`mount | grep "${FS} " | awk '{print $1}'`
    if [ "x${BDEV:0:4}" = "x/dev" ]; then
        echo "${BDEV}" 
    else
        return
    fi
}

#
# Shut down an individual FS, unmounting it, and performing a block 
# device sync on its underlying block device
#
do_sync_unmount_fs()
{
    local FS="$1"
    
    if [ "x${FS}" = "x" ]; then
        return
    fi

    FS_BDEV=`do_get_fs_blockdev ${FS}`
    if [ "x${FS_BDEV}" != "x" ]; then
        # unmount it
        echo "Unmounting FS : ${FS}"
        umount ${FS_BDEV} 

        # sync the block device
        echo "Syncing FS : ${FS}"
        do_sync_blockdev ${FS_BDEV}

        # check if this is a MD device
        if [ "${FS_BDEV:0:6}" = "/dev/md" ]; then
            echo "Stopping RAID : ${FS_BDEV}"
            /sbin/mdadm --stop ${FS_BDEV}
        fi 
    fi
}

#
# In the situation where we have to effectively unplug the unit
# because the BIOS upgrade may cause it to hang on reboot, we need to
# manually force IO to hit the disk.
#
do_manual_fs_sync()
{
    # this needs to be a complete list of all partitions we may want to sync
    # for all products.
    local MOUNT_LIST="boot bootmgr config var proxy scratch"

    # force ro and sync on root
    mount -o ro,remount /
    if [ $? -ne 0 ]; then
        echo "Unable to remount root ro, proceeding."
    fi

    do_sync_blockdev /dev/root

    for FS in ${MOUNT_LIST}; do
        do_sync_unmount_fs $FS        
    done
}

#
# In the case of a 400-00100, we'll need to manually sync the filesystems and then
# reboot the box using a hard IPMI chassis power cycle
#
do_upgrade_reboot()
{
    MOBO=`/opt/hal/bin/hwtool.py -q motherboard`
    
    # leave the rev number off the board
    case "x${MOBO:0:9}" in
        "x400-00100")

            # only do the special IPMI power cycle if we've changed the BIOS
            if [ $BIOS_UPDATE -eq 1 ]; then

                # load modules necessary for the ipmitool reboot command
                ${IPMI_UP} -l > /dev/null

                # sync the filesystems/block block devices and stop any sw-raids
                do_manual_fs_sync

                sleep 2
            
                echo "Hard Power Cycling the system..."
                echo ""
                # 
                /sbin/ipmitool chassis power cycle
                if [ $? -ne 0 ]; then
                    echo "Unable to restart system via IPMI, falling back to reboot."
                    sleep 1
                    reboot
                else
                    # ipmitool can take a few seconds to reboot the chassis, so we don't
                    # want to continue booting while we wait for that to happen.
                    sleep 60
    
                    # if we're alive after 60s then IPMI has failed, reboot normally
                    echo "Unable to restart system via IPMI, falling back to reboot."
                    reboot
                fi
            else
                echo "Update complete."
                echo "Rebooting the appliance."
                reboot
            fi
        ;;
        *)
            echo "Update complete."
            echo "Rebooting the appliance."
            # all other platforms use the standard reboot
            # after an upgrade.
            reboot
        ;;
    esac
    
}

if [ ${REBOOT_NEEDED} -eq 1 ]; then
        do_upgrade_reboot
fi

exit 0
