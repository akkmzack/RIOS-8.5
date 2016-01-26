#!/bin/sh
#
# rbt_flash_disk.sh
#
# General routines used by the CLI to handle flash device related activities.
#
# These routines will return errors if flash support is not allowed.
#

CLI="/opt/tms/bin/cli"

CFG_FL_DEV="/dev/hda1"
IMG1_FL_DEV="/dev/hda2"
IMG2_FL_DEV="/dev/hda3"
CFG_MNT_DIR="/flash/cfg"
IMG1_MNT_DIR="/flash/img1"
IMG2_MNT_DIR="/flash/img2"

RBTFL_LOG_WARN="/usr/bin/logger -t rbtflash -p user.warn [rbt_flash_disk.WARN]"
RBTFL_LOG_INFO="/usr/bin/logger -t rbtflash -p user.info [rbt_flash_disk.INFO]"

# use grub.conf as its the last item created to determine
# if flash has been setup.
FLASH_SETUP_FILE="/flash/cfg/boot/grub/grub.conf"
FLASH_SETUP_FAILED_FILE="/var/opt/rbt/.flash_setup_failed"

REBOOT_NEEDED=0
SFDISK="/sbin/sfdisk -s"
IL_FLASH_DEVICE="/dev/hda"
FLASH_DEV="${IL_FLASH_DEVICE}"
HWTOOL="/opt/hal/bin/hwtool.py"
MOBO=`${HWTOOL} -q motherboard`

#
# need to manually redirect to the hal because
# the link may not be set up when we run on startup
#
case "x${MOBO}" in
    "xCMP-00109"|"xCMP-00031"|"xCMP-00072"|"xCMP-00013")
	HAL="/opt/hal/bin/amax/hal"
    ;;
    "xCMP-00136"|"xCMP-00087"|"xCMP-00088")
	HAL="/opt/hal/bin/dell/hal"
    ;;
    "xCMP-00097")
	HAL="/opt/hal/bin/axiomtek/hal"
    ;;
    "x400-00100-01"|"x400-00300-01")
	HAL="/opt/hal/bin/mitac/hal"
    ;;
    "x400-00099-01"|"x400-00098-01")
	HAL="/opt/hal/bin/minnow/hal"
    ;;
    *)
	HAL="/opt/hal/bin/amax/hal"
    ;;
    
esac

FLASH_SUP=`${HAL} uses_flash_disk`

#-----------------------------------------------------------------------------
# Flash Setup Failed
#
# If we fail to set up the flash configuration, we will set a file 
# on /var/opt/rbt to indicate that the startup procedure should
# not reattempt to configure the flash.
#
# The user can then use the CLI command to rebuild the flash drive 
# manually.
#
#----------------------------------------------------------------------------
mark_flash_setup_failed()
{
    touch ${FLASH_SETUP_FAILED_FILE}
}

clear_flash_setup_failed()
{
    rm -f ${FLASH_SETUP_FAILED_FILE}
    if [ $? -ne 0 ]; then
	${RBTFL_LOG_WARN} "Unable to remove (${FLASH_SETUP_FAILED_FILE}), flash \
will not be configured on boot"
    fi
}

#------------------------------------------------------------------------------
# get_platform
#------------------------------------------------------------------------------

get_platform()
{
    RESULT=`cat /etc/build_version.sh | grep "^BUILD_PROD_ID=" | sed 's/^BUILD_PROD_ID="//' | sed 's/"//'`
    if [ $? != 0 ]; then
        echo "Failed to determine platform number."
        exit 1
    fi
    echo ${RESULT}
}

#
# on upgrades we need to find the appropriate image (from /var/opt/tms/images)
# and move it to "/". The scripts need that file to be there now.
#
# This is accomplished by getting the BUILD_PRODUCT_VERSION string and matching
# it with the appropriate file in the images dir.
#
IMAGES_DIR=/var/opt/tms/images
move_this_image_to_root()
{
    PLATFORM=`get_platform`
    CURRENT_BOOTVAR=`get_boot_part`
    THIS_VERSION=`cat /etc/build_version.sh | grep BUILD_PROD_VERSION= | sed 's/BUILD_PROD_VERSION=//'`
    if [ -e /image.img ]; then
        case $PLATFORM in
            "CMC"|"GW")
                # Remove the image if present no matter what
                # The symlink will be created later
            	rm -f /image.img
		# In some CMC and GW versions we moved /image.img to /var/opt/tms/flash_image/image.img
		# Remove it if its present
		rm -f /var/opt/tms/flash_image/disk${CURRENT_BOOTVAR}/image.img
            ;;
            *)            
		# if the image is already on root and the version matches the current
		# software version.. we don't need to do a copy
		#
		IMG_VERSION=`unzip -qqp /image.img build_version.sh 2>&1 | grep BUILD_PROD_VERSION= | sed 's/BUILD_PROD_VERSION=//'`
		if [ "x${IMG_VERSION}" = "x${THIS_VERSION}" ]; then
			return 0
		else 
			# forcibly remove the incorrect image.img so we don't get
			# a root image out of sync with the installed sw
			rm -f /image.img
		fi
            ;;
        esac
    fi

    FILE_LIST=`ls ${IMAGES_DIR}`
    for f in ${FILE_LIST}; do
        IMG_VERSION=`unzip -qqp ${IMAGES_DIR}/${f} build_version.sh 2>&1 | grep BUILD_PROD_VERSION= | sed 's/BUILD_PROD_VERSION=//'`
        if [ "${IMG_VERSION}" = "${THIS_VERSION}" ]; then
            case $PLATFORM in
                "CMC"|"GW")
                    mkdir -p /var/opt/tms/flash_image/disk${CURRENT_BOOTVAR}
                    cp ${IMAGES_DIR}/${f} /var/opt/tms/flash_image/disk${CURRENT_BOOTVAR}/image.img
                    if [ $? -ne 0 ]; then
                        ${RBTFL_LOG_WARN} "Unable to copy $f to /var/opt/tms/flash_image/disk${CURRENT_BOOTVAR}/image.img"
                        return 1
                    fi
                    ln -s /var/opt/tms/flash_image/disk${CURRENT_BOOTVAR}/image.img /image.img
                    if [ $? -ne 0 ]; then
                        ${RBTFL_LOG_WARN} "Unable to link /var/opt/tms/flash_image/disk${CURRENT_BOOTVAR}/image.img to /image.img"
                        return 1
                    else
                        return 0
                    fi
                    ;;
                *)
                    cp ${IMAGES_DIR}/${f} /image.img
                    if [ $? -ne 0 ]; then
                        ${RBTFL_LOG_WARN} "Unable to copy $f to /image.img"
                        return 1
                    else
                        return 0
                    fi
                    ;;
            esac
        fi
    done

    # indicate that there is no image on the root partition.
    return 1;
}

#-------------------------------------------------------------------------
# unpack_restore_image
#
# Assuming you are in the directory with image.img, this will unpack
# the restore image, or fail.
#
#-------------------------------------------------------------------------
unpack_restore_image()
{
    unzip -qqp image.img mfg_restore.tgz | tar xzf -
    if [ $? -ne 0 ]; then
        ${RBTFL_LOG_WARN} "Could not unpack restore image."
	return 1
    fi

    unzip -qqp image.img build_version.sh > build_version.sh
    if [ $? -ne 0 ]; then
        ${RBTFL_LOG_WARN} "Could not unpack build_version."
	return 1
     fi

    return 0
}

#-------------------------------------------------------------------------
# rollback_restore_image
#
# Assuming you are in the directory with image.img, this will
# clear out the installed files so the state is left clean
# after a failure.  
#
#-------------------------------------------------------------------------
rollback_restore_image()
{
    rm -rf . >> /dev/null 2>&1
    if [ $? -ne 0 ]; then
	${RBTFL_LOG_WARN} "Unable to roll back restore image"
    fi
}

#
# procedure to partition and format the flash disk
# 
# NOTE - no need to go into uni mode any more as we hope the patch fixes the 
# formatting problems seen on these units.
#
# return 0 if successful.
# return 1 if an error occurred and a retry should take place.
# return 2 if an unrecoverable error occurred.
#
rebuild_flash()
{
    # do necessary steps to initialize a flash part.
    # this could be a transition to either a mixed mode
    # or a total flash mode transition

    if [ ! -e /dev/hda ]; then
	${RBTFL_LOG_WARN} "/dev/hda does not exist."
	return 2
    fi

    # first repartition the flash device
    # 
    SIZE_TEST=`sfdisk -s /dev/hda`
    if [ $? -eq 1 ]; then
        ${RBTFL_LOG_WARN} "Flash drive does not appear to be present"
        return 1
    fi

    if [ ${SIZE_TEST} -lt 500000 ]; then
        ${RBTFL_LOG_WARN} "Flash drive is not large enough"
        return 1
    fi

    # set up the geometry for this appliance.
    #
    cat > /tmp/geomlayout <<EOF
,83,83,*
,200,83,
,200,83,

EOF

    # format the flash disk, given the above layout into 3 partitions.
    # 
    sfdisk  -L -uM --no-reread /dev/hda < /tmp/geomlayout >> /dev/null 2>&1
    rm /tmp/geomlayout
    sfdisk -l /dev/hda 2>&1 | grep "No partitions" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        ${RBTFL_LOG_WARN} "Flash drive was not partitioned correctly"
        return 1
    fi
 
    # on startup the device may not show up immediately
    # in fact it can take up to 10s to show up
    if [ ! -e /dev/hda1 ]; then
        ${RBTFL_LOG_WARN} "Waiting 5s for device to initialize"
        sleep 5
        if [ ! -e /dev/hda1 ]; then
                ${RBTFL_LOG_WARN} "Waiting 5s for device to initialize"
                sleep 5
                if [ ! -e /dev/hda1 ]; then
                        ${RBTFL_LOG_WARN} "HDA device not initialized in time, bailing"
                        return 1
                fi
        fi
    fi

    #format the partitions.
    for i in `seq 1 3`; do  
        count=0
	TMPRV=1
        while [ $TMPRV -eq 1 -a ${count} -lt 3 ]; do
            mke2fs -j /dev/hda${i} >> /dev/null 2>&1
	    TMPRV=$?
	    if [ $TMPRV -ne 0 ]; then	
		${RBTFL_LOG_WARN} "unable to mke2fs hda${i} with $TMPRV"
	    fi
            count=`expr ${count} + 1`
        done
        if [ ${count} -eq 3 ]; then #we've failed
            ${RBTFL_LOG_WARN} "Could not format flash partition ${i}"
            return 1
        fi
    done

    mount_flash_disk
    if [ $? -ne 0 ]; then
        ${RBTFL_LOG_WARN} "Could not mount flash device"
        return 1
    fi

    # Once the flash is set up, we need to move the appropriate image to
    # the flash restore partition.  For upgrades we install the flash enabled image
    # as both backup images.
    if [ $? -eq 0 ]; then
	if [ -f /image.img ]; then

	    cp /image.img /flash/img1
	    if [ $? -ne 0 ]; then
		${RBTFL_LOG_WARN} "Could not copy image one to restore dir"
	    fi
	    cp /image.img /flash/img2
	    if [ $? -ne 0 ]; then
		${RBTFL_LOG_WARN} "Could not copy image two to restore dir"
	    fi
	else
	    ${RBTFL_LOG_WARN} "Could not update restore image on flash.  System is vulnerable."
	fi
    fi
    MODEL=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/model`
    SERIAL_NUM=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/serialnum`

    echo "$SERIAL_NUM" > /flash/cfg/serial
    echo "$MODEL" > /flash/cfg/model

    # unpack the restore images.
    # if these fail its not an failure condition, we just proceed without
    # a restore image on that flash partition
    #
    if [ -f /flash/img1/image.img ]; then
	# we need to be in the img directory
	# the unpack and rollback routines assume it.
	cd /flash/img1/
	unpack_restore_image
	if [ $? -ne 0 ]; then
	    rollback_restore_image
	fi
    fi

    if [ -f /flash/img2/image.img ]; then
	cd /flash/img2/
        unpack_restore_image
        if [ $? -ne 0 ]; then
            rollback_restore_image
        fi
    fi

    #install grub on the flash and run aiset.
    /sbin/grub-install --root-directory=/flash/cfg/ --no-floppy /dev/hda >> /dev/null 2>&1
    if [ $? = 1 ]; then
        ${RBTFL_LOG_WARN}  "Could not install grub on the flash device"
        return 1
    fi

    eval `/sbin/aiget.sh`
    /sbin/aigen.py -i -l ${AIG_THIS_BOOT_ID}
    if [ $? -ne 0 ]; then
        ${RBTFL_LOG_WARN}  "Could not set up the grub configuration"
        return 1
    fi

    # we don't consider boot order to be a flash setup failure.
    #
    clear_flash_setup_failed
    
    # removed flash setup file touch here since we are using grub.conf
    # now to indicate a complete setup
    if [ "x${MODEL}" = "x3520" ]; then 
	MODEL="3020"  #after here we don't care and they use the same cfg
    fi

    # make a call to write the bios config if necessary.
    #
    
    if [ "x${MOBO}" = "xCMP-00109" ]; then
	update_bios_cfg
    fi

    return 0
}


#-----------------------------------------------------------------------
# check_bios_cfg 
#
# dump the bios cfg and make sure it has the right values
# Assumes : nvram is loaded
#-----------------------------------------------------------------------
check_bios_cfg()
{
    cat /dev/nvram > /tmp/bios_cfg	

    diff /tmp/bios_cfg  /etc/${MODEL}_nopxeflash.cfg
    if [ $? -ne 0 ]; then
	return 1
    fi

    return 0
}

#-----------------------------------------------------------------------
# write_bios_cfg 
#
# writes the appropriate bios configuration for this model to nvram
# 
# Assumes : nvram is loaded
#           MODEL variable is set
#----------------------------------------------------------------------
write_bios_cfg()
{
	for WRITE_TRY in `seq 1 3`; do
		cat  /etc/${MODEL}_nopxeflash.cfg > /dev/nvram

		sleep 1

		check_bios_cfg
		if [ $? -eq 0 ]; then
			${RBTFL_LOG_INFO} "Bios configuration written and verified. "
			return 0
		fi
	done

	return 1
}

#
# update_bios_cfg
# 
# set the model before running this routine
#
# Routine to check the bios cfg against the one provided with
# the release.  If the cfg's differ, the new one is written into
# nvram.
#
# Currently nvram module does not return status information
# regarding write success.
# 
#
update_bios_cfg()
{
    modprobe nvram
    if [ $? -ne 0 ]; then
        ${RBTFL_LOG_WARN} "couldn't load nvram module"
    else

	if [ "x${MODEL}" = "x" ]; then
             ${RBTFL_LOG_WARN} "Model unset when attempting to update bios cfg"
	    return
	fi
        #
        # check the bios config for booting from flash.
        # If the bios is already set up then we don't need to reflash it
        # and reboot.
	if [ ! -e /dev/nvram ]; then
	    # give a 2s sleep to see if nvram shows up
	    sleep 2
	    if [ ! -e /dev/nvram ]; then
		${RBTFL_LOG_WARN} "/dev/nvram does not exist, not updating flash"
	    fi
	fi

        cat /dev/nvram > /tmp/bios_cfg
        if [ $? -ne 0 ]; then
             ${RBTFL_LOG_WARN} "couldn't get bios cfg - forcing bios reflash"
	    write_bios_cfg
        else
            diff /tmp/bios_cfg /etc/${MODEL}_nopxeflash.cfg >> /dev/null 2>&1
            if [ $? -ne 0 ]; then
                ${RBTFL_LOG_INFO} "Reflashing bios config to boot from flash"
		write_bios_cfg
            else
                ${RBTFL_LOG_INFO} "bios config is up to date."
            fi
        fi

    fi
}

#
# Flash Disk Helper Routines.
#

setup_flash_dir()
{
    if [ ! -f /flash/cfg ]; then
        mkdir -p /flash/cfg >> /dev/null
    fi
    if [ ! -f /flash/img1 ]; then
        mkdir -p /flash/img1 >> /dev/null
    fi
    if [ ! -f /flash/img2 ]; then
        mkdir -p /flash/img2 >> /dev/null
    fi
}

mount_flash_disk_try()
{

    mount | grep "${FLASH_DEV}1" >> /dev/null 2>&1
    if [ $? -eq 1 ]; then
	mount ${FLASH_DEV}1 /flash/cfg >> /dev/null 2>&1
	if [ $? -ne 0 ]; then
	    ${RBTFL_LOG_WARN} "Unable to mount flash cfg partition"
	    return 1
	fi
    fi

    mount | grep "${FLASH_DEV}2" >> /dev/null 2>&1
    if [ $? -eq 1 ]; then
	mount ${FLASH_DEV}2 /flash/img1 >> /dev/null 2>&1
	if [ $? -ne 0 ]; then
	    ${RBTFL_LOG_WARN} "Unable to mount flash img1 partition"
	    return 1
	fi
    fi

    mount | grep "${FLASH_DEV}3" >> /dev/null 2>&1
    if [ $? -eq 1 ]; then
	mount ${FLASH_DEV}3 /flash/img2 >> /dev/null 2>&1
	if [ $? -ne 0 ]; then
	    ${RBTFL_LOG_WARN} "Unable to mount flash img2 partition"
	    return 1
	fi
    fi

    return 0
}

mount_flash_disk()
{
    setup_flash_dir

    for ATTEMPT in `seq 1 3`; do
        mount_flash_disk_try
        if [ $? -ne 0 ]; then
           unmount_flash_disk
           usleep 250000
        else
            return 0
        fi
    done

    return 1
}

unmount_flash_disk_try()
{
    RV=0

    OUTPUT=`umount /flash/cfg 2>&1`
    echo "${OUTPUT}" | grep "not mounted" >> /dev/null
    if [ $? -ne 0 ]; then
        RV=1
    fi

    OUTPUT=`umount /flash/img1 2>&1`
    echo "${OUTPUT}" | grep "not mounted" >> /dev/null
    if [ $? -ne 0 ]; then
        RV=1
    fi

    OUTPUT=`umount /flash/img2 2>&1`
    echo "${OUTPUT}" | grep "not mounted" >> /dev/null
    if [ $? -ne 0 ]; then
        RV=1
    fi

    return $RV ;
}

unmount_flash_disk()
{
        for ATTEMPT in `seq 1 3`; do
                unmount_flash_disk_try
                if [ $? -ne 0 ]; then
                        usleep 500000
                else
                        return 0
                fi
        done

        ${RBTFL_LOG_INFO} "One or more flash unmounts failed."
        return 1
}

CFG_MNT_DIR="/flash/cfg"
FLASH_CFG_MIN_SIZE_KB=75000

#
# check to see if the flash partitions are possible set up wrong.
# we assume the flash is already mounted and ok.
#
check_flash_partitions()
{
    # due to a previous bug some machines have flash that is half the size
    # it should be .. in this case we want to resize the partitions
    #
    CFG_SIZE=`sfdisk -s /dev/hda1`
    if [ "x${CFG_SIZE}" = "x" ]; then
	# skip it and next boot we'll try again.
	return 0
    fi

    if [ $CFG_SIZE -lt $FLASH_CFG_MIN_SIZE_KB ]; then
	# we need to reformat the flash
	return 1
    fi

    return 0
}

FLASH_DIAG_FILES="memdisk diags860.img"
DIAG_TMP_DIR="/var/tmp"

cleanup_tmp_diags()
{
    for f in ${FLASH_DIAG_FILES}; do
	rm -f ${DIAG_TMP_DIR}/${f} >> /dev/null
    done

    return 0
}

# save_flash_diags
# copy the diags off to an appropriate location so they can be restored 
#
save_flash_diags()
{
    for f in ${FLASH_DIAG_FILES}; do
	if [ ! -f /flash/cfg/${f} ]; then
	    return 0
	fi
    
	cp -f /flash/cfg/${f} ${DIAG_TMP_DIR} >> /dev/null
	if [ $? -ne 0 ]; then
	    cleanup_tmp_diags 
	    ${RBTFL_LOG_INFO} "insufficient space to backup diagnostics"
	    ${RBTFL_LOG_INFO} "diagnostics will be unavailable"
	    return 0
	fi
    done

    return 1
}

# restore_flash_diags
# will only be called if we saved off the diags
#
restore_flash_diags()
{
    for f in ${FLASH_DIAG_FILES}; do
	mv -f ${DIAG_TMP_DIR}/${f} /flash/cfg/${f} >> /dev/null
	if [ $? -ne 0 ]; then
	    ${RBTFL_LOG_WARN} "Unable to restore ${f} to flash."
	    ${RBTFL_LOG_WARN} "Diagnostics will be unavailable."
	    return 1
	fi
    done

    return 0
}

#
# reformat the flash so it has the correct partition table
# should only be done for those units that have half-sized flash
# partitions
#
# We're only handling restoration of the diagnostics and not the 
# backup images. 
#
perform_flash_part_upgrade()
{
    save_flash_diags
    TEMP_DIAGS=$?

    ${RBTFL_LOG_INFO} "Repartitioning flash disk."
    echo "Repartitioning flash disk, this may take up to 60 seconds."
    echo "Do not Ctrl-C, Unplug, or otherwise reboot this appliance"

    unmount_flash_disk

    rebuild_flash
    if [ $? -ne 0 ]; then
	# log the error and set the failed state.
	#
	${RBTFL_LOG_WARN} "Flash initialization failed."
	cleanup_tmp_diags
	mark_flash_setup_failed
	exit 1
    fi

    # now restore the diags if we had them
    if [ $TEMP_DIAGS -ne 0 ]; then
	restore_flash_diags	
	if [ $? -eq 0 ]; then
	    # we need to run aigen.py to set up grub on flash
	    eval `/sbin/aiget.sh`
	    /sbin/aigen.py -i -l ${AIG_THIS_BOOT_ID}
	    if [ $? -ne 0 ]; then
		${RBTFL_LOG_WARN}  "Could not set up the grub configuration"
	    fi
	fi

	cleanup_tmp_diags
    fi 

    ${RBTFL_LOG_WARN} "Flash reparitioning complete."
    
    return 0
}

#
# check if the flash disk is partitioned and formatted 
# 
# only call this on units that have returned true to uses_flash_disk
# 
# return code:
# 0 : flash partitioned and formatted properly
# 1 : flash notpartitioned or formatted properly
# 2 : failure determining state.
#
check_flash_state()
{
    SF_OUTPUT=`sfdisk -d /dev/hda 2>&1`
    if [ $? -ne 0 ]; then
	# since we knew uses_flash_disk returned true previously
	# assume that we have a sw error and fail.
	return 2;
    fi

    # do basic checks to ensure that the flash disk is 
    # 1. partitioned
    # 2. each partition is formatted
    #
    SEQ=`seq 1 3`
    for i in `seq 1 3`; do
	echo "$SF_OUTPUT" | grep hda${i} 2>&1 >> /dev/null
	if [ $? -ne 0 ]; then
	    return 1
    	fi
    
	dumpe2fs /dev/hda${i} >> /dev/null 2>&1
	if [ $? -ne 0 ]; then
	    return 1
	fi
	
    done

    return 0
}

#-----------------------------------------------------------------------------------
# do_recovery_image_checks
#
# We want to replace any old images that don't have flash support
# from flash disk. (pre 4.0 images)
#
# assume flash is already mounted and configured and 
# image.img is on "/" if no image is on "/" we'll just remove the
# installed recovery image from flash since it is likely 
# incompatible with the grub templates for 4.0
#----------------------------------------------------------------------------------
do_recovery_image_checks()
{
    
    for IMAGE_DIRECTORY in /flash/img1 /flash/img2; do
	IMAGE_NAME="$IMAGE_DIRECTORY/image.img"

	${RBTFL_LOG_INFO} "Checking recovery image in ${IMAGE_DIRECTORY}"
	cd ${IMAGE_DIRECTORY}

	if [ -f ${IMAGE_NAME} ]; then

	    VERSION=`/usr/bin/unzip -qqp ${IMAGE_NAME} build_version.sh | grep "BUILD_PROD_RELEASE=" | sed "s/BUILD_PROD_RELEASE=//" | tr -d '"'`
	    if [ "x${VERSION}" = "x" ]; then
		# image is corrupt and needs to be removed.
		rm -rf ${IMAGE_DIRECTORY}
	    else
		# check if this is a 2.0 or a 3.0 based image.
		echo "${VERSION}" | grep "^[23]" > /dev/null
		if [ $? -eq 0 ]; then
		    rm -rf ${IMAGE_DIRECTORY}/*
		    
		    if [ -f /image.img ]; then
			${RBTFL_LOG_INFO} "Installing recovery image in $IMAGE_DIRECTORY"

			cp -f /image.img ${IMAGE_DIRECTORY}
			if [ $? -ne 0 ]; then
			    echo "Unable to install recovery image ${IMAGE_DIRECTORY}"
			    return 1
			fi

			unpack_restore_image
			if [ $? -ne 0 ]; then
			    ${RBTFL_LOG_WARN} "unable to install recovery image on $IMAGE_DIRECTORY"
			    rollback_restore_image 
			fi
		    else 
			${RBTFL_LOG_WARN} "Recovery image incompatible with current sw, removing."
			${RBTFL_LOG_WARN} "No new recovery image found, system is at risk"
		    fi
		else
		    ${RBTFL_LOG_INFO} "Recovery image version on flash is acceptable"
		fi 
	    fi
	else 
	
	    # no recovery image put one in there
            rm -rf ${IMAGE_DIRECTORY}/*

            if [ -f /image.img ]; then
		${RBTFL_LOG_INFO} "Installing recovery image in $IMAGE_DIRECTORY"

                cp -f /image.img ${IMAGE_DIRECTORY}
	        if [ $? -ne 0 ]; then
	            echo "Unable to install recovery image ${IMAGE_DIRECTORY}"
		    return 1
		fi

		unpack_restore_image
		if [ $? -ne 0 ]; then
		    ${RBTFL_LOG_WARN} "unable to install recovery image on $IMAGE_DIRECTORY"
		    rollback_restore_image
		fi
	    else
		${RBTFL_LOG_WARN} "No new recovery image found, system is at risk"
	    fi
	fi
    done
}

# assume this is run before init_hardware_phase1 which means
# we need to mount the appropriate disks, etc.
#
configure_flash()
{

    case "${FLASH_SUP}" in
        "true")
        ;;
        "false")
            ${RBTFL_LOG_INFO} "Flash disks are not supported"
            exit 0;
        ;;
        *)
            ${RBTFL_LOG_WARN} "Flash disk error"
            exit 1;
        ;;
    esac

    if [ -f /webimage.tbz ]; then
	rm -f /webimage.tbz 
    fi

    # if we have flash support we need to have a image.img in "/"
    #
    move_this_image_to_root
    if [ $? -ne 0 ]; then
        ${RBTFL_LOG_WARN} "Unable to copy sw image to rootfs, proceeding."
        ${RBTFL_LOG_WARN} "Some services may be unavailable later."
    fi

    if [ -f ${FLASH_SETUP_FAILED_FILE} ]; then
	${RBTFL_LOG_WARN} "Flash setup failed previously, manually configure the flash from the CLI"
	exit 1
    fi 

    # check if we set up the flash properly previously
    #
    check_flash_state
    if [ $? -ne 0 ]; then
        #
        # flash can't be mounted and it has never been set up properly.
        #
        ${RBTFL_LOG_INFO} "Flash disk is uninitialized.  Performing initialization."
        echo "Flash disk is uninitialized. Performing initialization."
        echo "Do NOT unplug, CTRL-C, or reboot the appliance."
        echo "This may operation may take up to 60 seconds to complete."
        unmount_flash_disk

        rebuild_flash
        if [ $? -ne 0 ]; then
            ${RBTFL_LOG_WARN} "Flash disk initialization failed"
	    mark_flash_setup_failed
            exit 1
        fi
    else
	# if we hit this spot we should be able to mount
	# and use the flash disk since it passed the flash state check
	# then we check to see if the flash has the .flash_setup file
	# on the config partition, if not then we need to set up the flash again.
	#
	mount_flash_disk
	if [ $? -eq 0 ]; then
	    if [ ! -f $FLASH_SETUP_FILE ]; then
		${RBTFL_LOG_INFO} "Flash disk is uninitialized.  Performing initialization."
		echo "Flash disk is uninitialized. Performing initialization."
		echo "Do NOT unplug, CTRL-C, or reboot the appliance."
		echo "This may operation may take up to 60 seconds to complete."   
		unmount_flash_disk
    
		rebuild_flash
		if [ $? -ne 0 ]; then
		    ${RBTFL_LOG_WARN} "Flash disk initialization failed"
		    mark_flash_setup_failed
		    exit 1
		fi
	    else
		# patch for some flash disks that got formatted with the wrong
		# size.
		check_flash_partitions
		if [ $? -ne 0 ]; then	
		    perform_flash_part_upgrade
		else 
		    ${RBTFL_LOG_INFO} "Flash has been previously set up, continuing."
		fi

		# check to make sure that images that exist on flash match up
		do_recovery_image_checks
		
	    fi
	fi
    fi

    if [ -d /flash/cfg/ ]; then
	if [ ! -d /flash/cfg/data/ ]; then 
	    mkdir -p /flash/cfg/data/ 
	    if [ $? -ne 0 ]; then 
		${RBTFL_LOG_WARN} "Unable to create GW persistent data directory." 
		exit 1
	    fi
	fi
    fi

    # XXX taking this out for now.
#    if [ ${REBOOT_NEEDED} -eq 1 ]; then
#	# signal reboot to caller
#	exit 2
#    fi

    return 0;
}

#
# reformat_flash
#
# Reset the flash to defaults, and attempt to put the active image
# in as the restore image. (if they have access to this command, 
# it should be a flash enabled image).
#
reformat_flash()
{
    case "${FLASH_SUP}" in
        "true")
        ;;
        "false")
	    echo "Recovery flash disks are not supported on this appliance"
            ${RBTFL_LOG_INFO} "Flash disks are not supported"
            exit 0;
        ;;
        "error")
	    echo "Error accessing the flash device"
            ${RBTFL_LOG_WARN} "Flash disk error"
            exit 1;
        ;;
    esac

    # forced attempt at reconfiguring the flash
    #
    ${RBTFL_LOG_INFO} "Attempting flash disk reinitialization"
    unmount_flash_disk
    mark_flash_setup_failed

    rebuild_flash
    if [ $? -ne 0 ]; then
	echo "Flash disk initialization failed"
        ${RBTFL_LOG_WARN} "Flash disk initialization failed"
        return 1
    fi

    clear_flash_setup_failed
    echo "The recovery flash disk has been rebuilt"
}

#-------------------------------------------------------------------------
# check_prepare_flash
#
# make sure that flash support is enabled on this device
# make sure that if flash support is enabled then the flash disk
# is mounted
#
# routine is used to filter CLI commands that shouldnt be allowed.
#-------------------------------------------------------------------------
check_prepare_flash()
{
    case "${FLASH_SUP}" in
        "false")
            echo "Flash disk support is not available on this appliance"
            exit 1;
       ;;
        "error")
            echo "Flash disk configuration error.  Check the flash disk"
            exit 1;
        ;;
        "true")
        ;;
        *)
	    echo "Error detecting flash disk support"
	    exit 1;
        ;;
    esac

    # we're here and have flash support.
    # make sure the device is mounted properly
    #
    mount | grep "/flash/cfg" >> /dev/null 2>&1
    if [ $? -ne 0 ]; then
	echo "Flash disk is not correctly mounted"
	exit 1;
    fi

    mount | grep "/flash/img1" >> /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "Flash disk is not correctly mounted"
        exit 1 
    fi

    mount | grep "/flash/img2" >> /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "Flash disk is not correctly mounted"
        exit 1 
    fi
}

#-------------------------------------------------------------------------
# cfg_flash_backup
#
# Save the running configuration to flash disk.
# part of the information stored with this configuration is:
# 	1. The binary configuration
#	2. A text representation of the configration
#	3. an info file which contains the date the configuration was saved.
#
#-------------------------------------------------------------------------

ACTIVE_CONFIG="/config/db/active"
BACKUP_CONFIG_NAME="${CFG_MNT_DIR}/backup_config"
BACKUP_CONFIG_INFO_NAME="${CFG_MNT_DIR}/backup_config-info"
cfg_flash_backup()
{
    check_prepare_flash

    CFG_FILE=`cat ${ACTIVE_CONFIG}`
    if [ ! -f /config/db/${CFG_FILE} ]; then
        echo "Error obtaining active configuration ${CFG_FILE}"
        exit 0;
    fi

    cp -f /config/db/${CFG_FILE} ${BACKUP_CONFIG_NAME}
    if [ $? -ne 0 ]; then
        echo "Failed to copy active configuration to ${BACKUP_CONFIG_NAME}"
        exit 0;
    else
        echo "`date +%C%y-%m-%d-%H-%M`" > ${BACKUP_CONFIG_INFO_NAME}

        echo "show configuration flash" | ${CLI} > ${BACKUP_CONFIG_NAME}.txt

        echo "Active configuration ${CFG_FILE} has been backed up to flash disk"
    fi

}

#-------------------------------------------------------------------------
# tmp_config_flash_restore
#
# This is used to temporarily restore a configuration from flash
# so the management utilities can be used to dump the contents of the
# configuration.
#
# The temporary configuration is removed after execution completes.
# 
# - the management utilities require all configurations to be in
# /config/db which is why we need this workaround.
#
#-------------------------------------------------------------------------
tmp_cfg_flash_restore()
{
    check_prepare_flash

    if [ ! -f ${BACKUP_CONFIG_NAME} ]; then
        echo "No backup configuration found on flash disk"
        exit 1;
    fi

    NEW_CFG_NAME="/config/db/tmp_config.$$"

    if [ -f ${NEW_CFG_NAME} ]; then
        echo "Configuration file ${NEW_CFG_NAME} already exists"
        exit 1;
    fi

    cp -f ${BACKUP_CONFIG_NAME} ${NEW_CFG_NAME}
    if [ $? -ne 0 ]; then
        echo "Unable to stage temporary configuration, copy failed"
        exit 1;
    fi

    echo "${NEW_CFG_NAME}"
}

#-------------------------------------------------------------------------
# cfg_flash_restore
#
# Restore the saved configuration on flash to the /config/db directory.
# 
# The restored configuration will have a name like restore-cfg.<date saved>
# this configuration will need to be activated by using the cli/webui 
# activation commands
#
#-------------------------------------------------------------------------
cfg_flash_restore()
{
    check_prepare_flash

    if [ ! -f ${BACKUP_CONFIG_NAME} ]; then
        echo "No backup configuration found on flash disk"
        exit 0;
    fi

    if [ ! -f ${BACKUP_CONFIG_INFO_NAME} ]; then
        CFG_NAME_SUFFIX="unknown"
    else
        CFG_NAME_SUFFIX=`cat ${BACKUP_CONFIG_INFO_NAME}`
    fi

    NEW_CFG_NAME="/config/db/restored-cfg.${CFG_NAME_SUFFIX}"

    if [ -f ${NEW_CFG_NAME} ]; then
        echo "Configuration file ${NEW_CFG_NAME} already exists"
        exit 0;
    fi

    cp -f ${BACKUP_CONFIG_NAME} ${NEW_CFG_NAME}
    if [ $? -ne 0 ]; then
        echo "Unable to restore configuration, copy failed"
        exit 0;
    fi

    echo "Configuration image has been restored to ${NEW_CFG_NAME}"
    echo "This configuration still needs to be activated"
}


#-------------------------------------------------------------------------
# mount_sw_part
#
# this routine is used to mount one of the software partitions on 
# normal disk.  These routines should be cleaned up later and merged
# with the other places we mount the sw partitions.
#
#-------------------------------------------------------------------------
SW_MNT_DIR="/tmp/img"
mount_sw_part()
{
    P_PART="$1"
    if  [ ${P_PART} -eq 1 ]; then
	DEV=5
    elif [ ${P_PART} -eq 2 ]; then
	DEV=6
    else 
	return 1;
    fi

    mkdir -p ${SW_MNT_DIR} >> /dev/null 2>&1

    mount -o ro /dev/sda${DEV} ${SW_MNT_DIR} >> /dev/null 2>&1
    if [ $? -ne 0 ]; then
	return 1;
    fi
}

#-------------------------------------------------------------------------
# unmount_sw_part
#
# Bring down a software partition mounted for the flash commands.
#
#-------------------------------------------------------------------------
unmount_sw_part()
{
    umount ${SW_MNT_DIR} 
}



#-------------------------------------------------------------------------
# image_flash_backup
#
# This routine takes a software image from "/" on one of the software 
# partitions and puts it and extracted information on the indicated flash
# partition.
#
# the first parameter identifies the DISK partition to use (disk_1/2)
#     or a software version
# the second parameter indicates which flash partition to store the image on.
#     (flash_1/2)
#
# The contents of the flash partition will be (after this command)
#     1. build_version.sh
#     2. unpacked manufacture.tgz file
#     3. original image.img file.
#
#-------------------------------------------------------------------------
image_flash_backup()
{
    DISK="$1"
    PART="$2"

    PART=`validate_flash_partition "${PART}"`
    if [ $? -ne 0 ]; then
	echo "${PART}"
	exit 1;
    fi
    DISK=`validate_disk_partition "${DISK}"`
    if [ $? -ne 0 ]; then
	echo "${DISK}"
	exit 1;
    fi

    check_prepare_flash

    mount_sw_part "${DISK}"
    if [ $? -ne 0 ]; then
	echo "Unable to mount software partition"
	exit 0;
    fi 
    
    if [ ! -f ${SW_MNT_DIR}/image.img ]; then
	echo "Software partition $DISK does not contain a backup image"
	unmount_sw_part
	exit 0
    fi
    
    case "${PART}" in
	"1") 
	    DIR="$IMG1_MNT_DIR"
	;;
	"2")
	    DIR="$IMG2_MNT_DIR"
	;;
    esac

    unzip -qqp ${SW_MNT_DIR}/image.img build_version.sh > ${DIR}/build_version.sh
    if [ $? = 1 ]; then
        echo "Image file on disk partition ${DISK} is not a proper image file"
	unmount_sw_part
        exit 1
    fi

    cd ${DIR}
    unzip -qqp ${SW_MNT_DIR}/image.img mfg_restore.tgz | tar xzf -
    if [ $? -ne 0 ]; then
	echo "Image file on disk partition ${DISK} is not a proper image file"
	unmount_sw_part
	exit 1
    fi

    cp -f ${SW_MNT_DIR}/image.img ${DIR}
    if [ $? -ne 0 ]; then
	echo "Unable to backup image from partition (${PART}) to ${DIR}"
	unmount_sw_part
	exit 1
    fi

    eval `/sbin/aiget.sh`
    /sbin/aigen.py -i -l ${AIG_THIS_BOOT_ID}
    if [ $? -ne 0 ]; then
        ${RBTFL_LOG_WARN}  "Could not set up the grub configuration"
    fi

    echo "Software image from disk partition ${DISK} has been saved to flash image ${PART}"

    unmount_sw_part
}

#-------------------------------------------------------------------------
# check_image_option
#
# resolves a software image name to a disk partition (1,2)
# 
# The first parameter identifies a version of a sw image
# the second parameter identifies whether this is a flash part or disk
#
#
#-------------------------------------------------------------------------
check_image_option()
{
    IMG_OPTION="$1"
    PART_TYPE="$2"

    if [ "${PART_TYPE}" = "flash" ]; then
    	FILE_LIST="/flash/img1/image.img /flash/img2/image.img"
    elif [ "${PART_TYPE}" = "disk" ]; then
        mkdir -p /tmp/disk1 >> /dev/null 2>&1
        mkdir -p /tmp/disk2 >> /dev/null 2>&1
        mount -o ro /dev/sda5 /tmp/disk1 >> /dev/null 2>&1
        mount -o ro /dev/sda6 /tmp/disk2 >> /dev/null 2>&1
    	FILE_LIST="/tmp/disk1/image.img /tmp/disk2/image.img"
    else
	echo "invalid"
	return 1
    fi
    WORK=0

    for f in ${FILE_LIST}; do
        WORK=$[ $WORK + 1 ]
        if [ -f $f ]; then
            VERSION=`/usr/bin/unzip -qqp ${f} build_version.sh | grep "BUILD_PROD_VERSION=" | sed "s/BUILD_PROD_VERSION=//" | tr -d '"'`

            OPTION=`echo $VERSION | awk '{print $1 "-" $2 "-" $3 "-" $4}'`
            if [ "${OPTION}" = "${IMG_OPTION}" ]; then
		echo "${WORK}"
		if [ "${PART_TYPE}" = "disk" ]; then
			umount /tmp/disk1 >> /dev/null 2>&1
			umount /tmp/disk2 >> /dev/null 2>&1
		fi
		return 0;
            fi
        fi
    done

    if [ "${PART_TYPE}" = "disk" ]; then
	umount /tmp/disk1 >> /dev/null 2>&1
	umount /tmp/disk2 >> /dev/null 2>&1
    fi

    echo "invalid"
    return 1
}

#-------------------------------------------------------------------------
# validate_disk_partition
#
# validates a parameter identifying a disk partition to be
# a valid version string from an image.img file, or a valid 
# partition identifier.
#
#-------------------------------------------------------------------------
validate_disk_partition()
{
        D_PARTITION="$1"

        case "${D_PARTITION}" in
                "disk_1"*)
                        echo "1"
                        return 0
                ;;
                "disk_2"*)
                        echo "2"
                        return 0
                ;;
                *)
                        # non standard .. may be a software version
                        RESULT=`check_image_option "${D_PARTITION}" "disk"`
                        if [ $? -eq 0 ]; then
                                echo "${RESULT}"
                                return 0;
                        fi

                        echo "Invalid flash partition or image ${D_PARTITION}"
                        exit 1
                ;;
        esac
}


#-------------------------------------------------------------------------
# validate_flash_partition
#
# validates a parameter identifying a flash partition to be
# a valid version string from an image.img file, or a valid
# partition identifier.
#
#-------------------------------------------------------------------------
validate_flash_partition()
{
	P_PARTITION="$1"

	case "${P_PARTITION}" in
		"flash_1"*)
			echo "1"
			return 0
		;;	
		"flash_2"*)
			echo "2"
			return 0
		;;
		*)
			# non standard .. may be a software version
			RESULT=`check_image_option "${P_PARTITION}" "flash"`
			if [ $? -eq 0 ]; then
				echo "${RESULT}"
				return 0;
			fi
			
			echo "Invalid flash partition or image version ${P_PARTITION}"
			exit 1
		;;
	esac
}

#-------------------------------------------------------------------------
# get_info_from_flash_image
#
# extracts information from an image.img file.
#    1. PRODUCT_VERSION
#    2. FLASH_SUPPORT
# displays the output for the cli show flash iamges command
#
#-------------------------------------------------------------------------
get_info_from_flash_image()
{
    # assume flash is already mounted

    PART="$1"
    case "${PART}" in
	"1")
	    DIR="${IMG1_MNT_DIR}"
	;;
	"2")
	    DIR="${IMG2_MNT_DIR}"
	;;
    esac

    IMAGE_FILE="${DIR}/image.img"

    if [ ! -f ${IMAGE_FILE} ]; then
	echo "Image ${PART}: No image file is present"
	return 0 
    fi     
    
    ENV_VARIABLE="BUILD_PROD_VERSION="

    VERSION=`/usr/bin/unzip -qqp ${IMAGE_FILE} build_version.sh | grep "BUILD_PROD_VERSION=" | sed "s/${ENV_VARIABLE}//" | tr -d '"'`
    FSUPPORT=`/usr/bin/unzip -qqp ${IMAGE_FILE} build_version.sh | grep "BUILD_FLASH_SUPPORT" | sed "s/${ENV_VARIABLE}//" | tr -d '"'`
    
    if [ "$VERSION" = "" ]; then
	VERSION="No version information stored in image" 
    fi
    
    if [ "${FSUPPORT}" = "" ]; then
	FSUPPORT="Not Supported"
    else
	FSUPPORT="yes"
    fi

    echo "Flash Image ${PART}: ${VERSION}"
    echo "      Flash support: ${FSUPPORT}" 
}

#-------------------------------------------------------------------------
# show_image_flash_versions
#
# Displays the software versions and flash support information
# for all images backed up on flash.
#
#-------------------------------------------------------------------------
show_image_flash_versions()
{
    check_prepare_flash

    get_info_from_flash_image "1"
    get_info_from_flash_image "2"

}


#-------------------------------------------------------------------------
# get_image_restore_options
# displays formatted image names for use in the restore process
#
#-------------------------------------------------------------------------
get_image_options()
{
    IMG_SOURCE="$1"

    if [ "${IMG_SOURCE}" = "flash" ]; then
        check_prepare_flash
    	FILE_LIST="/flash/img1/image.img /flash/img2/image.img"
	DEFAULT_NAME="flash_"
    elif [ "${IMG_SOURCE}" = "disk" ]; then
	mkdir -p /tmp/disk1
	mkdir -p /tmp/disk2
	mount -o ro /dev/sda5 /tmp/disk1 >> /dev/null 2>&1
	mount -o ro /dev/sda6 /tmp/disk2 >> /dev/null 2>&1
	
	FILE_LIST="/tmp/disk1/image.img /tmp/disk2/image.img /tmp/disk1/var/opt/tms/flash_image/disk1/image.img /tmp/disk2/var/opt/tms/flash_image/disk2/image.img"
	DEFAULT_NAME="disk_"
    else
	echo "Invalid Option ${IMG_SOURCE}"
	exit 1
    fi
    WORK=0

    for f in ${FILE_LIST}; do
        WORK=$[ $WORK + 1 ]
        if [ -f $f ]; then
            VERSION=`/usr/bin/unzip -qqp ${f} build_version.sh | grep "BUILD_PROD_VERSION=" | sed "s/BUILD_PROD_VERSION=//" | tr -d '"'`

            OPTION=`echo $VERSION | awk '{print $1 "-" $2 "-" $3 "-" $4}'`
            if [ "${OPTION}" != "" ]; then
		echo "${DEFAULT_NAME}${WORK}_${OPTION}"
	    else 
		echo "${DEFAULT_NAME}${WORK}"
     	    fi
		
        fi
    done

    if  [ "${IMG_SOURCE}" = "disk" ]; then
	umount /tmp/disk1 >> /dev/null 2>&1
	umount /tmp/disk2 >> /dev/null 2>&1
    fi 
}

get_boot_part()
{
	CUR_BOOT_PART=`/sbin/aiget.sh | grep AIG_THIS_BOOT_ID= | sed 's/AIG_THIS_BOOT_ID=//'`
	case "${CUR_BOOT_PART}" in
		"1"|"2")
			echo "${CUR_BOOT_PART}"
			exit 0
		;;
		*)
			echo "Invalid"
			exit 1
		;;
	esac
}


#--------------------------------------------------------------------------
# Dispatch routine
#--------------------------------------------------------------------------

FUNCTION="$1"

case "${FUNCTION}" in
    "cfg_flash_write")	
	cfg_flash_backup	
    ;;
    "cfg_flash_restore")
	cfg_flash_restore
    ;;
    "show_cfg_flash")
	show_cfg_flash
    ;;
    "show_cfg_flash_text")
	show_cfg_flash_text
    ;;
    "show_image_flash_versions")
	show_image_flash_versions
    ;;
    "image_flash_backup")
	image_flash_backup "$2" "$3"	
    ;;
    "tmp_cfg_flash_restore")
	tmp_cfg_flash_restore
    ;;
    "get_image_options")
	get_image_options "$2"
    ;;
    "get_boot_part")
	get_boot_part
    ;;
    "configure_flash")
	configure_flash
    ;;
    "reformat_flash")
	reformat_flash
    ;;
    "update_bios_cfg")
	update_bios_cfg
    ;;
    "check_flash_state")
	check_flash_state
    ;;
    *)
	echo "Unknown Option."
	exit 1
    ;;
esac

exit $?

