#!/bin/bash
###############################################################################
# Misc HAL utilities
#
# Routines that are common across all the hal's that we don't 
# need to duplicate.
#
# uses_system_led_control
#
# set_system_led_state
#
# get_system_led_state
#
#
###############################################################################
HAL_LOG_WARN="/usr/bin/logger -p user.warn -t hal"
HAL_LOG_NOTICE="/usr/bin/logger -p user.notice -t hal"
HAL_LOG_INFO="/usr/bin/logger -p user.info -t hal"
HAL_LOG_CRIT="/usr/bin/logger -p user.CRIT -t hal"

###############################################################################
# Misc utility paths
###############################################################################
HAL=/opt/hal/bin
HWTOOL_PY=${HAL}/hwtool.py
HW_CTL_PY="/opt/hal/bin/hw_ctl.py"
IPMITOOL="/sbin/ipmitool"
HALD_MODEL=/opt/tms/bin/hald_model
MDDBREQ=/opt/tms/bin/mddbreq
MFDB=/config/mfg/mfdb
MODPROBE=/sbin/modprobe
RMMOD=/sbin/rmmod
BYPASSCTL=/opt/rbt/bin
BYPASS_CTL=bypass_ctl
MINNOW_CTL=minnow_ctl
NA0043_CTL=na0043_ctl
ADLINK_CTL=adlinkctl
HP_CTL=hp_ctl
SMARTCMD="/usr/sbin/smartctl"
KERNEL_OPT_TEST=/var/opt/rbt/.kernel_opt

HAL_CACHE=/var/tmp/hal_cache/
CACHED_MOBO=${HAL_CACHE}/motherboard
CACHED_MOBO_TYPE=${HAL_CACHE}/mobo_type
CACHED_MODEL=${HAL_CACHE}/model

RRDM_TOOL="${HAL}/raid/rrdm_tool.py"

###############################################################################
# Filesystem Utilities
###############################################################################
RESIZE2FS=/sbin/resize2fs
E2FSCK=/sbin/e2fsck
SFDISK=/sbin/sfdisk
TUNE2FS=/sbin/tune2fs

# riverbed internal filesystem recovery script.
DO_FS_RECOVERY=/sbin/do_fs_recovery.sh

###############################################################################
# Config Paths
###############################################################################
DB_PATH=/config/mfg/mfdb

###############################################################################
# Flexible Licensing Paths
###############################################################################
FLEXPY=/opt/hal/bin/flexpy
UPGRADE_SCRIPTS_DIR=/opt/hal/bin/upgrade
MODEL_PATH="/opt/hal/lib/specs/model"

###############################################################################
# get_motherboard
###############################################################################
get_motherboard()
{
    if [ -f ${CACHED_MOBO} ]; then
        MOBO=`cat ${CACHED_MOBO}`
        if [ "x${MOBO}" != "x" ]; then
            echo ${MOBO}
            return
        fi
    fi

    MOBO=`${HWTOOL_PY} -q motherboard`
    if [ $? != 0 ]; then
        ${HAL_LOG_WARN} "Hwtool unable to determine motherboard part number"
        exit 1
    fi

    # if we don't have a set up /var filesystem, we might not be able to create 
    # this directory.  Thats ok. if we can't create it just return the 
    # motherboard, we'll try again next time.
    if [ ! -d ${HAL_CACHE} ]; then
        mkdir -m 0755 ${HAL_CACHE} > /dev/null 2>&1
    fi

    # only set the cache mobo if we were able to make the cache dir.
    if [ -d ${HAL_CACHE} ]; then
        echo ${MOBO} > ${CACHED_MOBO}
    fi

    echo ${MOBO}
    return
}

###############################################################################
# get_motherboard_type
###############################################################################
get_motherboard_type()
{
    if [ -f ${CACHED_MOBO_TYPE} ]; then
        TYPE=`cat ${CACHED_MOBO_TYPE}`
        if [ "x${TYPE}" != "x" ]; then
            echo ${TYPE}
            return
        fi
    fi

    TYPE=`${HWTOOL_PY} -q mobo-type`
    if [ $? != 0 ]; then
        ${HAL_LOG_WARN} "Hwtool unable to determine motherboard part number"
        exit 1
    fi

    # if we don't have a set up /var filesystem, we might not be able to create 
    # this directory.  Thats ok. if we can't create it just return the 
    # motherboard, we'll try again next time.
    if [ ! -d ${HAL_CACHE} ]; then
        mkdir -m 0755 ${HAL_CACHE} > /dev/null 2>&1
    fi

    # only set the cache mobo if we were able to make the cache dir.
    if [ -d ${HAL_CACHE} ]; then
        echo ${TYPE} > ${CACHED_MOBO_TYPE}
    fi

    echo ${TYPE}
    return
}

###############################################################################
# get_platform
###############################################################################
get_platform()
{
    RESULT=`cat /etc/build_version.sh | grep "^BUILD_PROD_ID=" | sed 's/^BUILD_PROD_ID="//' | sed 's/"//'`
    if [ $? != 0 ]; then
        echo "Failed to determine platform."
        exit 1
    fi
    echo ${RESULT}
}


###############################################################################
# get_model
###############################################################################
get_model()
{
    PLAT=`get_platform`
    if [ "x${PLAT}" = "xSH" -o "x${PLAT}" = "xEX" ]; then
    	if [ ! -f ${HALD_MODEL} ]; then
        	echo "$HALD_MODEL not installed.  Can't determine model number."
        	return 1
    	fi
    
    	model=`$HALD_MODEL | awk '{print $1}'`
    	if [ "x${model}" = "x" ]; then
        	${HAL_LOG_WARN} "Failed to determine model number."
        	exit 1
    	fi
   else
	if [ ! -f ${MDDBREQ} ]; then
		echo "$MDDBREQ does not exist, Can't determine model number"
	fi
	
	model=`${MDDBREQ} -v ${MFDB} query get - /rbt/mfd/model`
    	if [ "x${model}" = "x" ]; then
        	${HAL_LOG_WARN} "Failed to determine model number."
        	exit 1
    	fi
   fi

    echo "${model}"
}


###############################################################################
# check_kernel_options
# Check Grub kernel option, if they arent correctly set, reboot the box
###############################################################################

check_kernel_options()
{
    # If this check is carried out at startup, it means we have set the clock=pmtmr
    # param using aigen. If there is an upgrade from an unsupported version
    # we need a second reboot to set the boot option, if its just a reboot in the same 
    # partition, the /proc/cmdline will have the option set and we are good to go
    KOPTS=`${HWTOOL_PY} -q kernel-opts`
    if [ $? -ne 0 ]; then
        ${HAL_LOG_NOTICE} "Cannot get the kernel options, setting kernel options to nothing"
        KOPTS=""
    fi

    if [ "x${KOPTS}" != "x" ]; then
        /bin/cat /proc/cmdline | /bin/grep "${KOPTS}"
        if [ $? -ne 0 ]; then
            ${HAL_LOG_NOTICE} "Need to reboot to get the kernel with the ${KOPTS} option"

            # Find the current partition and rerun aigen, to regenerate the grub.conf file
            eval `/sbin/aiget.sh`
            if [ ! -z "${AIG_THIS_BOOT_ID}" ]; then
                /sbin/aigen.py -i -l ${AIG_THIS_BOOT_ID}
            fi

            if [ ! -f ${KERNEL_OPT_TEST} ]; then
                # Create the kernel options test file
                # If the file is present, we wont reboot
                /bin/touch ${KERNEL_OPT_TEST}
                /sbin/reboot
            else
                # If we reached here, it means that even after a reboot we
                # could not boot with the correct options
                # log a WARNING. I am banking that hwtool gave some issue 
                # and will remove the kernel options file, if its a permanent 
                # failure, we will reboot two times on every reboot
                ${HAL_LOG_WARN} "Cannot get the machine to boot with the correct kernel options"
                /bin/unlink ${KERNEL_OPT_TEST} > /dev/null 2>&1
            fi
        else
            # The kernel booted with the correct options
            # Remove the kernel options test file
            ${HAL_LOG_NOTICE} "Kernel booted with the correct options"
            /bin/unlink ${KERNEL_OPT_TEST} > /dev/null 2>&1
        fi
    else
        # This means either we 
        # 1) Dont have any options
        # 2) hwtool returned failure and we set KOPTS to ""
        # If 1) we are good to go, if 2) we need to remove the KERNEL_OPT_TEST file
        # we should retry on next reboot, either case I will try to remove the 
        # KERNEL_OPT_TEST file 
        /bin/unlink ${KERNEL_OPT_TEST} > /dev/null 2>&1
    fi
}




###############################################################################
# System LED Control 
###############################################################################

###############################################################################
# uses_system_led_control
#
# Indicates whether this platform has a software controllable health status
# LED.
#
###############################################################################
uses_system_led_control()
{
    
    MOBO=`get_motherboard`
    case "x${MOBO}" in
	"x425-00140-01"|"x425-00205-01"|"x400-00100-01"|"x400-00300-01"|"x400-00099-01"|"x400-00300-10"|"x400-00098-01")
	    echo "true"
	;;
	*)
	    echo "false"
	;;
    esac
}

###############################################################################
# set_system_led_state
#
# Sets the system LED to the appropriate color based on the parameter.
# normal   : blue
# degraded : yellow
# critical : red
#
###############################################################################
set_system_led_state()
{
    SUP=`uses_system_led_control`
    if [ "x${SUP}" != "xtrue" ]; then
        echo "Not implemented"
	return 128
    fi

    STATE="$1"
    if [ "x${STATE}" = "x" ]; then
	${HAL_LOG_WARN} "Invalid led state for set_system_led_state"
	return 1
    fi

    MOBO=`get_motherboard`
    case "x${MOBO}" in
	"x400-00100-01"|"x400-00300-01"|"x400-00300-10")
            case "x${STATE}" in
	        "xnormal")
                    major="off"
        	    minor="off"
        	;;
        	"xdegraded")
                    major="off"
                    minor="on"
        	;;
        	"xcritical")
                    major="on"
                    minor="off"
        	;;
        	*)
        	    ${HAL_LOG_WARN} "Invalid LED state requested ${STATE}"
        	    return 1
        	;;
            esac
            major_output=`${HW_CTL_PY} -w led_strip alarm major_${major}`
            major_error=$?
            minor_output=`${HW_CTL_PY} -w led_strip alarm minor_${minor}`
            minor_error=$?
            if [ $major_error -ne 0 ] || [ $minor_error -ne 0 ]; then
                ${HAL_LOG_WARN} "Unable to set system led state to ${STATE}."
                return 1
            fi
            echo $major_output | grep "Bad input." > /dev/null
            major_error=$?
            echo $minor_output | grep "Bad input." > /dev/null
            minor_error=$?
            if [ $major_error -eq 0 ] || [ $minor_error -eq 0 ]; then
                ${HAL_LOG_WARN} "Unable to set system led state to ${STATE}."
                return 1
            fi
        ;;
        "x400-00099-01"|"x400-00098-01")
            case "x${STATE}" in
                "xnormal")
                    newstate=ok
                ;;
                "xdegraded")
                    newstate=warn
                ;;
                "xcritical")
                    newstate=err
                ;;
                *)
                    ${HAL_LOG_WARN} "Invalid LED state requested ${STATE}"
                    return 1
                ;;
            esac
            hw_ctl_output=`${HW_CTL_PY} -w led_strip system $newstate`
            if [ $? -ne 0 ]; then
                ${HAL_LOG_WARN} "Unable to set system led state to ${STATE}."
                return 1
            fi
            echo $hw_ctl_output | grep "Bad input." > /dev/null
            if [ $? -eq 0 ]; then
                ${HAL_LOG_WARN} "Unable to set system led state to ${STATE}."
                return 1
            fi
        ;;

        # redfin 1U non-lsi and 1U/2U lsi
        "x425-00140-01"|"x425-00205-01")
            case "x${STATE}" in
                "xnormal")
                    newstate="blue"
                ;;
                "xdegraded")
                    newstate="yellow"
                ;;
                "xcritical")
                    newstate="orange"
                ;;
                *)
                    ${HAL_LOG_WARN} "Invalid LED state requested ${STATE}"
                    return 1
                ;;
            esac
            echo "$newstate" > /sys/class/system_led/led5/color 
            if [ $? -ne 0 ]; then
                ${HAL_LOG_WARN} "Unable to set system led state to ${STATE}."
                return 1
            fi
        ;;
    esac
    return 0
}

###############################################################################
# get_system_led_color
#
# Gets the system LED color depending on the platform
###############################################################################
get_system_led_color()
{
        RET=`get_system_led_state`
        if [ $? -ne 0 ]; then
            echo "Not implemented"
            return 128
        fi

        MOBO=`get_motherboard`
        case "x${MOBO:0:9}" in
            "x425-00140"|"x425-00205"|"x400-00100"|"x400-00300")
                normal="Blue"
                degraded="Yellow"
                critical="Red"
                ;;
            "x400-00099"|"x400-00098")
                normal="Blue"
                degraded="Yellow"
                critical="Red"
                ;;
        esac

        case "x${RET}" in
            "xcritical")
                echo ${critical}
                ;;
            "xdegraded")
                echo ${degraded}
                ;;
            "xnormal")
                echo ${normal}
                ;;
            *)
                return 1
                ;;
        esac
        return 0
}

###############################################################################
# get_system_led_state
#
# Gets the system LED to the appropriate color based on the parameter.
# normal   : blue
# degraded : yellow
# critical : red
#
###############################################################################
get_system_led_state()
{
    SUP=`uses_system_led_control`
    if [ "x${SUP}" != "xtrue" ]; then
        return 1
    fi
    
    MOBO=`get_motherboard`
    case "x${MOBO}" in
        "x400-00100-01"|"x400-00300-01"|"x400-00300-10")
            ${HW_CTL_PY} -r led_strip alarm major_off | grep True > /dev/null
            major_error=$?
            ${HW_CTL_PY} -r led_strip alarm minor_off | grep True > /dev/null
            minor_error=$?
            if [ $major_error -eq 0 ] && [ $minor_error -eq 0 ]; then
                echo "normal"
                return 0
            fi
            
            ${HW_CTL_PY} -r led_strip alarm major_off | grep True > /dev/null
            major_error=$?
            ${HW_CTL_PY} -r led_strip alarm minor_on | grep True > /dev/null
            minor_error=$?
            if [ $major_error -eq 0 ] && [ $minor_error -eq 0 ]; then
                echo "degraded"
                return 0
            fi
            
            ${HW_CTL_PY} -r led_strip alarm major_on | grep True > /dev/null
            major_error=$?
            ${HW_CTL_PY} -r led_strip alarm minor_off | grep True > /dev/null
            minor_error=$?
            if [ $major_error -eq 0 ] && [ $minor_error -eq 0 ]; then
                echo "critical"
                return 0
            fi
            
            ${HAL_LOG_WARN} "Unknown LED status for system LED"
            echo "unknown"
            return 1
            ;;
        "x400-00099-01"|"x400-00098-01")
            ${HW_CTL_PY} -r led_strip system ok | grep True > /dev/null
            if [ $? -eq 0 ]; then
                echo "normal"
                return 0
            fi
            
            ${HW_CTL_PY} -r led_strip system warn | grep True > /dev/null
            if [ $? -eq 0 ]; then
                echo "degraded"
                return 0
            fi
            
            ${HW_CTL_PY} -r led_strip system err | grep True > /dev/null
            if [ $? -eq 0 ]; then
                echo "critical"
                return 0
            fi
            
            ${HAL_LOG_WARN} "Unknown LED status for system LED"
            echo "unknown"
            return 1
            ;;
        "x425-00140-01"|"x425-00205-01")
            state=`cat /sys/class/system_led/led5/color`
            case "$state" in 
                "blue")
                    echo "normal"
                    return 0; 
                    ;;
                "yellow")
                    echo "degraded"
                    return 0; 
                    ;;
                "orange")
                    echo "critical"
                    return 0; 
                    ;;
                *)
                    echo "unknown"
                    ${HAL_LOG_WARN} "Unknown system LED status"
                    return 1
                    ;;
            esac
            ;;
    esac
}

###############################################################################
# initialize_scsi
#
# Do hardware specific initialization of the scsi layer, based on the 
# appliance type.
# 
# Generally to work around lsi cards causing system crashes because they lock
# the raid arrays when enough drive timeouts happen, we set the timeout really
# high on appliances with LSI cards, and to a normal value on everything else.
#
###############################################################################
DEFAULT_TIMEOUT=30
initialize_scsi()
{
    MOBO=`get_motherboard`
    case "x${MOBO}" in
        "xCMP-00109"|"CMP-00072"|"CMP-00013")
            # either 3ware or LSI RAID
            SCSI_TIMEOUT=180
        ;;
        *)
            # default to 30 s.
            SCSI_TIMEOUT=30
        ;;
    esac

    # change scsi timeout on scsi devices that are not Intel 
    # flash parts. On old systems we don't have flash drives to set.
    DEV_LIST=`ls /sys/bus/scsi/devices`
    for f in ${DEV_LIST}; do
        VENDOR=`cat /sys/bus/scsi/devices/$f/vendor | tr -d "[:space:]"`
        if [ "x${VENDOR}" != "xIntel" ]; then
            # check for non Intel vendor since those are flash disks.
            echo ${SCSI_TIMEOUT} > /sys/bus/scsi/devices/$f/timeout
            if [ $? -ne 0 ]; then
                ${HAL_LOG_WARN} "Unable to set scsi timeout on device $f to ${SCSI_TIMEOUT}"
            fi
        else
            #  if intel, then set the default timeout for flash disks.
            echo ${DEFAULT_TIMEOUT} > /sys/bus/scsi/devices/$f/timeout
            if [ $? -ne 0 ]; then
                ${HAL_LOG_WARN} "Unable to set scsi timeout on device $f to ${SCSI_TIMEOUT}"
            fi
        
        fi
    done
    
}

###############################################################################
# Unsupported MODEL fallback code
#
# In 5.5 and later, we will no longer support the xx00, xx11, and the xx10 models.
#
###############################################################################
log_fallback_failure()
{
    ${HAL_LOG_WARN} "No Fallback Partition found, skipping reboot"
    ${HAL_LOG_WARN} "Manually reboot into RiOS 4.1.X, 5.0.Y and earlier."
}

# if this is an unsupported model, we want to check the ROOT_ software versions
# if both versions are 5.5 and later, we'll allow user to run (this is the VLAB  mfg case).
# if the other version is < 5.5, we will boot back into that version,
# as it will still function properly with this model#
do_unsupported_model_action()
{

    # figure out the current boot and fallback boot id's
    THIS_BOOT_ID=`/sbin/aiget.sh | grep THIS_BOOT_ID | sed 's/AIG_THIS_BOOT_ID=//g'`
    case "x${THIS_BOOT_ID}" in
        "x1"|"x2")
            FALLBACK_BOOT_ID=`/sbin/aiget.sh | grep FALLBACK_BOOT_ID | sed 's/AIG_FALLBACK_BOOT_ID=//g'`

        ;;
        *)            
            ${HAL_LOG_WARN} "Unable to determine current boot partition"
            ${HAL_LOG_WARN} "A system error has occurred."
            ${HAL_LOG_WARN} "Please boot into the other boot partition."            
            return 1
        ;;
    esac

    if [ "x${FALLBACK_BOOT_ID}" = "x" ]; then
        log_fallback_failure
        return 1
    fi

    # grab the root software versions from the fallback partition
    #
    CHECK_PROD_RELEASE=`/sbin/imgq.sh -i -d -l ${FALLBACK_BOOT_ID} | grep BUILD_PROD_RELEASE= | sed 's/BUILD_PROD_RELEASE=//' | tr -d '"'`
    echo "${CHECK_PROD_RELEASE}" | grep flamebox >> /dev/null
    if [ $? -eq 0 ]; then
        # don't fall back to a flamebox build.  its internal 
        FB_MAJOR_VERSION_NUMBER=100
        FB_MINOR_VERSION_NUMBER=100
    else
        FB_MAJOR_VERSION_NUMBER=`echo "$CHECK_PROD_RELEASE" | tr '.' ' ' | cut -d' ' -f1`
        FB_MINOR_VERSION_NUMBER=`echo "$CHECK_PROD_RELEASE" | tr '.' ' ' | cut -d' ' -f2`
    fi

    if [ -z ${FB_MAJOR_VERSION_NUMBER} -o -z ${FB_MINOR_VERSION_NUMBER} ]; then
        # error fetching the other boot partitions id's
        log_fallback_failure
        return 1
    elif [ ${FB_MAJOR_VERSION_NUMBER} -ge 5 -a ${FB_MINOR_VERSION_NUMBER} -ge 5 ]; then
        # fallback partition is running 5.5 or later, so skip the fallback
        ${HAL_LOG_WARN} "Fallback partition is running flamebox, 5.5, or later, skipping fallback"
    elif [ ${FB_MAJOR_VERSION_NUMBER} -gt 5 ]; then
        # fallback partition is running 6.0 or later, so skip the fallback
        ${HAL_LOG_WARN} "Fallback partition is running flamebox, 6.0 or later, skipping fallback"
    else
        # fallback partition is running a version of SW that is supported for this model.
        /sbin/aigen.py -i -l ${FALLBACK_BOOT_ID}
        if [ $? -ne 0 ]; then
            log_fallback_failure
            return 1
        fi

        ${HAL_LOG_CRIT} "Fallback partition is running ${FB_MAJOR_VERSION_NUMBER}.${FB_MINOR_VERSION_NUMBER}"
        ${HAL_LOG_CRIT} "Rebooting Appliance back into fallback partition ${FALLBACK_BOOT_ID}"
        /sbin/reboot
    fi
}

###############################################################################
#
# do_55_sw_version_check
#
# If we're running 5.5 and later, and this is a model xx00, xx10, xx11,
# don't allow the appliance to run in the image. This routine will force the appliance
# to boot into the fallback partition, if the fallback partition is running
# an older build 5.0, or 4.1, etc.
#
# if the fallback partition is running 5.5, messages are logged, but we don't
# force the appliance to reboot.
#
###############################################################################
do_55_sw_version_check()
{
    local MODEL=`get_model`

    case ${MODEL} in
        # these are no longer allowed in 5.5
        "500"|"510"|"1000"|"1010"|"2000"|"2001"|"2010"|"2011"|"2510"|"2511"|"3000"|"3010"|"3510"|"5000"|"5010")
            # Do some logging to tell ppl that this image is no longer supported
            ${HAL_LOG_CRIT} "CRITICAL: Model ${MODEL} appliances are not supported in this version of RiOS"
            ${HAL_LOG_CRIT} "CRITICAL: This appliance requires RiOS 3.X, 4.X, or 5.0.X"

            # if both partitions have 5.5 or newer, the version is not supported
            # but we don't have anywhere to boot back into.
            do_unsupported_model_action

        ;;
        "520"|"1020"|"1520"|"2020")
            # for dell 1U based appliances, we do not want to allow 32 bit appliances 
            # to run
            ARCH=`uname -i`
            if [ "x${ARCH}" = "xi386" ]; then

                # Do some logging to tell ppl that this image is no longer supported
                ${HAL_LOG_CRIT} "CRITICAL: Model ${MODEL}:${ARCH} appliances are not supported in this version of RiOS"
                ${HAL_LOG_CRIT} "CRITICAL: This appliance requires a x86_64 RiOS image."

                # this is an unsupported model
                do_unsupported_model_action
            fi
        
        ;;

        *)
        # good to go, this model is supported in 5.5 and later
        ;;
    esac
}

###############################################################################
# Disk Firmware Updates
###############################################################################

FW_UPDATE_CMD="/opt/hal/bin/disk/fw_util.py"

###############################################################################
#
# check_disk_fw_updates
#
# Loop over each disk that isnt missing, and check to see if scsi thinks we 
# can talk to the disk. If so, run the firmware util, which will
# read the configuration file and check to see if an update is necessary.
#
# If so, it will perform the update, and print to stdout.
# this routine should be run from within an initlog context, so messages will
# be sent to syslog.
#
###############################################################################
check_disk_fw_updates()
{
    # do not use get_motherboard here. it requires /var access, and var is not
    # started yet when this routine is called
    MOBO=`${HWTOOL_PY} -q motherboard`
    case "x${MOBO:0:9}" in 
        "x400-00100"|"x400-00300")
            echo "Checking Disk Firmware Revisions:"
            ;;
        *)
            # not supported on this platform
            return
            ;;
    esac
    
    DISK_LIST=`${HWTOOL_PY} -q disk=map | grep disk | grep -v missing | awk '{print $3}'`

    for disk in ${DISK_LIST}; do
        # assume offline
        STATE="offline"
        SYSFS=/sys/block/$disk/device/state
        if [ -f ${SYSFS} ]; then
            STATE=`cat ${SYSFS}`
        fi

        # only attempt to update fw if the disk is running
        if [ "x${STATE}" = "xrunning" ]; then
            ${FW_UPDATE_CMD} /dev/${disk}
        fi
    done
}

###############################################################################
#
# Bypass routines
#
###############################################################################

find_nic_prefix()
{
    PLATFORM=`get_platform`
    case "x${PLATFORM}" in
        "xDD"|"xFG"|"xBGL"|"xCB"|"xDVA"|"xEVA")
            echo "eth"
        ;;
        *)
            echo "[lw]an"
        ;;
    esac
}

find_nic_target()
{
    PLATFORM=`get_platform`
    case "x${PLATFORM}" in
        "xDD"|"xFG"|"xBGL"|"xCB"|"xDVA"|"xEVA")
            echo "eth"
        ;;
        *)
            echo "wan"
        ;;
    esac
}


#------------------------------------------------------------------------------
# Bypass NIC HAL Utilities
#------------------------------------------------------------------------------
verify_nic_arg()
{
    INTF="$1"
    PREFIX=`find_nic_prefix`
    echo "${INTF}" | grep "^${PREFIX}" > /dev/null
    if [ $? -ne 0 ]; then
        ${HAL_LOG_WARN} "Invalid nic argument to ${FUNCTION} [${INTF}]"
        exit 1
    else
        return 0
    fi
}

###############################################################################
# sw_supports_ether_relay
# Only SH and IB software today support ether-relay watchdogs
###############################################################################
sw_supports_ether_relay()
{
    PLATFORM=`get_platform`
    case "x${PLATFORM}" in
        "xSH"|"xIB"|"xEX")
            echo "True"
        ;;
        *)
            echo "False"
        ;;
    esac
}

###############################################################################
# get_bypass_util
#
# Return the bypass utility for this slot. 
#
###############################################################################
get_bypass_util()
{
    local slot
    local utility
    local util

    slot=$1
    utility=`${HWTOOL_PY} -q if_util=${slot}`
    if [ "x${utility}" = "x" ]; then
        ${HAL_LOG_WARN} "No utility associated with slot [${slot}]"
        return 1
    fi

    util="${BYPASSCTL}/${utility}"
    if [ ! -x "${util}" ]; then
    	util="${HAL}/${utility}"
        if [ ! -x "${util}" ]; then
            ${HAL_LOG_INFO} "no application assigned"
            return 1
        fi
    fi

    echo $util
}

###############################################################################
# get_hw_if_status
#
# Return the hardware state for this interface. 
# Valid returns are "Bypass" | "Disconnect" | "Normal"
#
###############################################################################
get_hw_if_status()
{
    verify_nic_arg $1

    #the interface has format of wan0_0, lan1_0, etc.
    slot_port=`echo $1 | tr -d '[a-z][A-Z]'`
    slot=`echo $slot_port | cut -c 1`
    port=`echo $slot_port | cut -c 3`
    wan_lan=`echo $1 | cut -c 1-3`
    UTIL=`get_bypass_util $slot`
    PREFIX=`find_nic_target`
    if [ $? -ne 0 ]; then
	exit 1
    else
        # per a bug in many of the utilities we control each interface using its "wan"
        # master side. many of the utilities fail to wan0_0 when you specify a lan port.
        #
        ${UTIL} -w ${PREFIX}${slot_port} bypass_status > /dev/null
        CODE=$?

        if [ ${CODE} -ne 0 -a ${CODE} -ne 2 -a ${CODE} -ne 3 ]; then
            ${HAL_LOG_WARN} "${UTIL} failed with status ${CODE} while calling bypass_status with port [${slot_port}]"
            exit 1
        fi
    fi

    if [ ${CODE} -eq 2 ]; then
        echo "Bypass"
    elif [ ${CODE} -eq 3 ]; then
        echo "Disconnect"
    elif [ ${CODE} -eq 0 ]; then
        echo "Normal"
    fi

    return 0
}

#------------------------------------------------------------------------------
# get_hw_if_wdt_status
#
# works for mitac and slcmi and minnow
#------------------------------------------------------------------------------
get_hw_if_wdt_status()
{
    verify_nic_arg $1

    #the interface has format of wan0_0, lan1_0, etc.
    slot_port=`echo $1 | tr -d '[a-z][A-Z]'`
    slot=`echo $slot_port | cut -c 1`
    port=`echo $slot_port | cut -c 3`
    wan_lan=`echo $1 | cut -c 1-3`
    PREFIX=`find_nic_target`

    bcap=`get_if_block_cap ${PREFIX}${slot}_${port}`
    if [ "x${bcap}" != "xTrue" ]; then
	echo "Bypass"
	exit 0
    fi

    UTIL=`get_bypass_util $slot`
    if [ $? -ne 0 ]; then
        exit 1
    fi

    ${UTIL} -d /dev/nbtwd${slot}${port} -w ${PREFIX}${slot_port} get_wd_exp_mode > /dev/null
    CODE=$?
    if [ ${CODE} -ne 2 -a ${CODE} -ne 3 ]; then
        ${HAL_LOG_WARN} "${UTIL} failed with status ${CODE} while calling get_wd_exp_mode with port [${slot_port}]"
        exit 1
    fi
    if [ ${CODE} -eq 2 ]; then
            echo "Bypass"
    else
            echo "Disconnect"
    fi

    return 0
}

#------------------------------------------------------------------------------
# set_if_wdt_block
#------------------------------------------------------------------------------
set_if_wdt_block()
{
    verify_nic_arg $1

    #the interface has format of wan0_0, lan1_0, etc.
    slot_port=`echo $1 | tr -d '[a-z][A-Z]'`
    slot=`echo $slot_port | cut -c 1`
    port=`echo $slot_port | cut -c 3`
    PREFIX=`find_nic_target`


    wan_lan=`echo $1 | cut -c 1-3`

    UTIL=`get_bypass_util $slot`
    if [ $? -ne 0 ]; then
	exit 1
    fi
    utility=`basename $UTIL`

    part_num=`${HWTOOL_PY} -q if_part_num=${slot}`
    if [ "x${part_num}" = "x" ]; then
        ${HAL_LOG_WARN} "Can't find part number for slot [${slot}]"
        exit 1
    fi

    if [ "x`sw_supports_ether_relay`" = "xTrue" ]; then
        RELAY_IF="inpath${slot}_${port}"
        RELAY_IX=`get_er_relay_index ${RELAY_IF}`
        if [ $? -ne 0 ]; then
            ${HAL_LOG_WARN} "No ether-relay interface for [${RELAY_IF}]"
            exit 1
        fi

        set_er_if_wdt_block ${RELAY_IX}
        if [ $? -ne 0 ]; then
            ${HAL_LOG_WARN} "Unable to configure software fail to block on [${RELAY_IF}]"
            exit 1
        fi
    fi

    block=`${HWTOOL_PY} -q if_block=${slot}`
    if [ "x${block}" != "xtrue" ]; then
        ${HAL_LOG_INFO} "Interface [$1] does not support block"
        return 0
    fi

    ${UTIL} -w ${PREFIX}${slot_port} disable_bypass > /dev/null
	    CODE=$?
    if [ ${CODE} -ne 0 ]; then
        ${HAL_LOG_WARN} "${UTIL} failed with status ${CODE} while calling disable_bypass with port [${slot_port}]"
        exit 1
    fi

    ${HAL_LOG_INFO} "Set watchdog mode to block successfully for port [${slot_port}]"

    return 0
}

#------------------------------------------------------------------------------
# set_if_wdt_bypass
#------------------------------------------------------------------------------
set_if_wdt_bypass()
{
    verify_nic_arg $1

    #the interface has format of wan0_0, lan1_0, etc.
    slot_port=`echo $1 | tr -d '[a-z][A-Z]'`
    slot=`echo $slot_port | cut -c 1`
    port=`echo $slot_port | cut -c 3`
    PREFIX=`find_nic_target`

    wan_lan=`echo $1 | cut -c 1-3`

    UTIL=`get_bypass_util $slot`
    if [ $? -ne 0 ]; then
        exit 1
    fi
    utility=`basename $UTIL`

    if [ "x`sw_supports_ether_relay`" = "xTrue" ]; then
        RELAY_IF="inpath${slot}_${port}"
        RELAY_IX=`get_er_relay_index ${RELAY_IF}`
        if [ $? -ne 0 ]; then
            ${HAL_LOG_WARN} "No ether-relay interface for [${RELAY_IF}]"
            exit 1
        fi

        set_er_if_wdt_bypass "${RELAY_IX}"
        if [ $? -ne 0 ]; then
            ${HAL_LOG_WARN} "Unable to configure software fail to bypass on [${RELAY_IF}]"
            exit 1
        fi
    fi

    # bypass is always the wdt target on the adlink/other cards
    block=`${HWTOOL_PY} -q if_block=${slot}`
    if [ "x${block}" != "xtrue" ]; then
        # bypass is always the wdt target on the cards that 
	# do not support block
        exit 0
    fi

    ${UTIL} -w ${PREFIX}${slot_port} enable_bypass > /dev/null
	    CODE=$?
    if [ ${CODE} -ne 0 ]; then
        ${HAL_LOG_WARN} "${UTIL} failed with status ${CODE} while calling enable_bypass with port [${slot_port}]"
        exit 1
    fi

    ${HAL_LOG_INFO} "Set Watchdog timeout mode to bypass successfully for port [${slot_port}]"
    return 0
}

#------------------------------------------------------------------------------
# set_if_bypass
#------------------------------------------------------------------------------
set_if_bypass()
{
    verify_nic_arg $1

    #the interface has format of wan0_0, lan1_0, etc.
    slot_port=`echo $1 | tr -d '[a-z][A-Z]'`
    slot=`echo $slot_port | cut -c 1`
    wan_lan=`echo $1 | cut -c 1-3`
    PREFIX=`find_nic_target`

    UTIL=`get_bypass_util $slot`
    if [ $? -ne 0 ]; then
        exit 1
    fi
    utility=`basename $UTIL`

    # bypass is always enabled on the adlink/other cards.
    bypass_sup=`bp_util_supports_bypass ${utility}`
    if [ "x${bypass_sup}" != "xTrue" ]; then

	${HAL_LOG_INFO} "Card in slot [${slot}] doesnt support force bypass"
        exit 1
    fi

    ${UTIL} -w ${PREFIX}${slot_port} bypass > /dev/null
    CODE3=$?

    if [ ${CODE3} -ne 0 ]; then
        ${HAL_LOG_WARN} "${UTIL} failed with status ${CODE3} while calling bypass with port [${slot_port}]"
        exit 1
    fi

    ${HAL_LOG_INFO} "Set interface mode to bypass successfully for port [${slot_port}]"
    return 0
}

bp_util_supports_normal()
{
    utility=$1
    case "${utility}" in
        "${BYPASS_CTL}"|"${MINNOW_CTL}"|"${NA0043_CTL}"|"${ADLINK_CTL}"|"${HP_CTL}")
            echo "True"
        ;;
        *)
            echo "False"
        ;;
    esac 
}   

bp_util_supports_bypass()
{
    utility=$1
    case "${utility}" in
        # adlink binary does not have a forced bypass cmd
        "${BYPASS_CTL}"|"${MINNOW_CTL}"|"${NA0043_CTL}"|"${HP_CTL}")
            echo "True"
        ;;
        *)
            echo "False"
        ;;
    esac 
}   

bp_util_supports_block()
{
    utility=$1
    case "${utility}" in
        # neither adlink nor na0043 support block
        "${BYPASS_CTL}"|"${MINNOW_CTL}"|"${HP_CTL}")
            echo "True"
        ;;
        *)
            echo "False"
        ;;
    esac 
}  


#------------------------------------------------------------------------------
# set_if_normal
#------------------------------------------------------------------------------
set_if_normal()
{
    verify_nic_arg $1
    
    #the interface has format of wan0_0, lan1_0, etc.
    slot_port=`echo $1 | tr -d '[a-z][A-Z]'`
    slot=`echo $slot_port | cut -c 1`
    wan_lan=`echo $1 | cut -c 1-3`
    PREFIX=`find_nic_target`
    
    UTIL=`get_bypass_util $slot`
    if [ $? -ne 0 ]; then
        exit 1
    fi
    utility=`basename $UTIL`
    
    normal_sup=`bp_util_supports_normal ${utility}`
    if [ "x${normal_sup}" != "xTrue" ]; then
        ${HAL_LOG_INFO} "Card in slot [${slot}] doesnt support force normal"
        exit 1
    fi

    ${UTIL} -w ${PREFIX}${slot_port} wdt_disable > /dev/null
    ${UTIL} -w ${PREFIX}${slot_port} nobypass > /dev/null
    CODE3=$?

    if [ ${CODE3} -ne 0 ]; then
        ${HAL_LOG_WARN} "${UTIL} failed with status ${CODE3} while calling nobypass with port [${slot_port}]"
        exit 1
    fi

    ${HAL_LOG_INFO} "Set interface mode to normal successfully for port [${slot_port}]"
    return 0
}


#------------------------------------------------------------------------------
# set_if_block
#------------------------------------------------------------------------------
set_if_block()
{
    verify_nic_arg $1

    #the interface has format of wan0_0, lan1_0, etc.
    slot_port=`echo $1 | tr -d '[a-z][A-Z]'`
    slot=`echo $slot_port | cut -c 1`
    wan_lan=`echo $1 | cut -c 1-3`
    PREFIX=`find_nic_target`

    UTIL=`get_bypass_util $slot`
    if [ $? -ne 0 ]; then
        exit 1
    fi
    utility=`basename $UTIL`

    block_cap=`get_if_block_cap ${PREFIX}${slot_port}`
    if [ "x${block_cap}" != "xTrue" ]; then
        ${HAL_LOG_INFO} "Card in slot [${slot}] does not support block"
        exit 1
    fi

    part_num=`${HWTOOL_PY} -q if_part_num=${slot}`
    if [ "x${part_num}" = "x" ]; then
        ${HAL_LOG_WARN} "Can't find part number for slot [${slot}]"
        exit 1
    fi

    if [ "x${part_num}" = "xCMP-00074" -o  "x${part_num}" = "xCMP-00062" ]; then
        echo "not supported"
        exit 0
    fi

    ${UTIL} -w ${PREFIX}${slot_port} disc_on > /dev/null
    CODE2=$?
    if [ ${CODE2} -ne 0 ]; then
        ${HAL_LOG_WARN} "${UTIL} failed with status ${CODE2} while calling disc_on with port [${slot_port}]"
        exit 1
    fi
    ${HAL_LOG_INFO} "Set interface mode to block successfully for port [${slot_port}]"
    return 0
}

# get_if_status now checks first to see if the hardware is in bypass, block, or normal
# If hardware is in normal, then we check ether-relay.  If ether-relay is in normal
# mode then we report normal, otherwise we report the mode of the specific interface
#
get_if_status()
{       
        INTF="${1}"

        # if validity checking will be done by the hw_if_status routine
        STATUS=`get_hw_if_status ${INTF}`
        if [ $? -ne 0 ]; then
            ${HAL_LOG_WARN} "Failed to get hardware interface status for [${INTF}]"
            exit 1
        fi
        
        case "x${STATUS}" in
            "xNormal")
                if [ "x`sw_supports_ether_relay`" = "xTrue" ]; then
                    # Check ether-relay
                    STATUS=`get_er_if_status ${INTF}`
                    if [ $? -ne 0 ]; then
                        # get er logged the error, so just exit
                        exit 1
                    fi
                fi
    
                echo "${STATUS}"
            ;;
                # no point in checking ether-relay since hardware is not passing traffic
                # to the host
            "xBypass"|"xDisconnect")
                echo "${STATUS}"
            ;;
            *)
                #{HAL_LOG_WARN} "Invalid hardware if status for [${INTF}] [${STATUS}]"
                exit 1
            ;;
        esac

        return 0
}

###############################################################################
# get_er_if_wdt_status
#
# given a lan/wan pair find out if ether-relay is set to fail-to-bypass
# or fail to block.
#
###############################################################################
get_er_if_wdt_status()
{
    verify_nic_arg $1

    slot_port=`echo $1 | tr -d '[a-z][A-Z]'`
    slot=`echo $slot_port | cut -c 1`
    port=`echo $slot_port | cut -c 3`

    RELAY_IF="inpath${slot}_${port}"

    # first figure out what the failure mode is
    FAIL_MODE=`cat /proc/eal/watchdog_mode | grep -A2 ${RELAY_IF} | grep watchdog_failure_type | awk '{print $2}'`

    if [ $? -ne 0 ]; then
        ${HAL_LOG_WARN} "Unknown relay interface [${RELAY_IF}]"
        return 1
    fi

    case "x${FAIL_MODE}" in
        "x1")
            # mode is bypass
            echo "Bypass"
            return 0
        ;;
        "x2")
            echo "Disconnect"
            return 0
        ;;
        *)
                ${HAL_LOG_WARN} "Invalid ether-relay watchdog fail mode for relay [${RELAY_IF}] [${FAIL_MODE}]"
                return 1
        ;;

    esac
}


###############################################################################
# Generic wdt status routine, if we're using ether-relay,
# we always report the ether-relay wdt status (mgmt can't handle multiple
# status values).
# if we're on a sw version without ER support, we'll just return the 
# hardware status. 
###############################################################################
get_generic_if_wdt_status()
{
    if [ "x`sw_supports_ether_relay`" = "xTrue" ]; then

        # use ether-relay status for determining block mode since we always set er 
        # and then set the hardware 
        # mgmt should really eventually use both er and hw status separately
        get_er_if_wdt_status ${1}
    else
        # if use hardware status if there is no ether-relay watchdog 
        # support
        get_hw_if_wdt_status ${1}
    fi
}


###############################################################################
# ER support routines
###############################################################################

#
# in order to talk to ether relay for a given relay interface, you need to know the 
# relay number, which is obtained by reading /proc/eal/watchdog_mode
#
get_er_relay_index()
{

    RELAY_IF="$1"

    # first figure out what the failure mode is
    RELAY_IX=`cat /proc/eal/watchdog_mode | grep -A2 ${RELAY_IF} | grep init_index | awk '{print $2}'`
    if [ $? -ne 0 ]; then
        # index not found, ether-relay doesnt know about that interface.
        return 1
    fi

    echo "${RELAY_IX}"

    return 0
}


#-------------------------------------------------------------------------------
# set_er_if_wdt_block 
#
#
# Setting 1 to /proc/sys/eal/X/watchdog_fail_mode sets bypass
# setting 2 to /proc/sys/eal/X/watchdog_fail_mode sets the mode to block
#-------------------------------------------------------------------------------
set_er_if_wdt_block()
{
    RELAY_IX="$1"
    ${HAL_LOG_INFO} "Setting ether-relay index ${RELAY_IX} watchdog to block"

    ETHER_PROCFS="/proc/sys/eal/${RELAY_IX}/watchdog_fail_mode"
    if [ ! -e ${ETHER_PROCFS} ]; then
        return 1
    fi

    echo 2 > ${ETHER_PROCFS}
    if [ $? -ne 0 ]; then
        return 1
    fi

    return 0
}

#-------------------------------------------------------------------------------
# set_er_if_wdt_bypass
#-------------------------------------------------------------------------------
set_er_if_wdt_bypass()
{
    RELAY_IX="$1"
    ${HAL_LOG_INFO} "Setting ether-relay index ${RELAY_IX} watchdog to bypass"

    ETHER_PROCFS="/proc/sys/eal/${RELAY_IX}/watchdog_fail_mode"
    if [ ! -e ${ETHER_PROCFS} ]; then
        return 1
    fi

    echo 1 > ${ETHER_PROCFS}
    if [ $? -ne 0 ]; then
        return 1
    fi

    return 0
}

#------------------------------------------------------------------------------
# get_er_if_status
#------------------------------------------------------------------------------
#
# Read the ether-relay status for a given interface
# ether-relay uses inpaths, and the hal takes either lan or wan,
# so we need to convert to the relay if to start with.
#
get_er_if_status()
{
    verify_nic_arg $1

    slot_port=`echo $1 | tr -d '[a-z][A-Z]'`
    slot=`echo $slot_port | cut -c 1`
    port=`echo $slot_port | cut -c 3`

    RELAY_IF="inpath${slot}_${port}"

    ER_WDT_MODE=`cat /proc/eal/watchdog_status_entry`
    case "x${ER_WDT_MODE}" in
        "x0")
            # normal, just return
            echo "Normal"
            return 0
        ;;
        "x1")
            # failed, pass and check the failure mode from er
        ;;
        *)
            ${HAL_LOG_WARN} "Invalid ether-relay watchdog status [${ER_WDT_MODE}]"
            return 1
        ;;
    esac

    # first figure out what the failure mode is 
    FAIL_MODE=`cat /proc/eal/watchdog_mode | grep -A2 ${RELAY_IF} | grep watchdog_failure_type | awk '{print $2}'`
    if [ $? -ne 0 ]; then
        ${HAL_LOG_WARN} "Unknown relay interface [${RELAY_IF}]"
        return 1
    fi

    case "x${FAIL_MODE}" in
        "x1")
            # mode is bypass
            echo "Bypass"
            return 0
        ;;
        "x2")
            echo "Disconnect"
            return 0
        ;;
        *)
                ${HAL_LOG_WARN} "Invalid ether-relay watchdog fail mode for relay [${RELAY_IF}] [${FAIL_MODE}]"
                return 1
        ;;

    esac
}

###############################################################################
# Interface support routines for HWTOOL info
###############################################################################

#------------------------------------------------------------------------------
# get_if_type
#------------------------------------------------------------------------------
get_if_type()
{

    verify_nic_arg $1

    #the interface has format of wan0_0, lan1_0, etc.
    slot_port=`echo $1 | tr -d '[a-z][A-Z]'`
    slot=`echo $slot_port | cut -c 1`
    wan_lan=`echo $1 | cut -c 1-3`
    iftype=`${HWTOOL_PY} -q if_type=${slot}`
    if [ "x${iftype}" != "x" ]; then
        echo "${iftype}"
    else
        ${HAL_LOG_WARN} "unable to determine type of interface for card in slot [${slot}]"
        exit 1
    fi 

    return 0
}


#------------------------------------------------------------------------------
# get_if_block_cap
#------------------------------------------------------------------------------
get_if_block_cap()
{
    verify_nic_arg $1

    #the interface has format of wan0_0, lan1_0, etc.
    slot_port=`echo $1 | tr -d '[a-z][A-Z]'`
    slot=`echo $slot_port | cut -c 1`
    BLOCK_CAP=`${HWTOOL_PY} -q if_block=${slot}`

    if [ "x${BLOCK_CAP}" = "xtrue" ]; then
        echo "True"
    else
        echo "False"
    fi
}

# supports_txhang_noflap
#
# Returns True if a driver is loaded that supports the txhang noflap 
# procfs. Currently only e1000 supports it.
#
TXHANG_MOD_TYPE="e1000"

supports_txhang_noflap()
{
    if [ -f /proc/bus/pci/devices ]; then
	for DRIVER in ${TXHANG_MOD_TYPE}; do
	    # loop through all the devices and see if we have an e1000
	    # controlled device. if so, we're good to go.
	    cat /proc/bus/pci/devices | grep ${DRIVER} > /dev/null
	    if [ $? -eq 0 ]; then
		echo "True"
		exit 0
	    fi
	done

	echo "False"
    else
	echo "False"
    fi
}

#--------------------------------------------------------------------------
# get_advertised_link_modes
# Older versions of ethtool did not display any speed or duplex options
# for certain fiber cards. If get_avail_speed_duplex() is unable to find
# any of these options under the "Supported link modes" section of
# ethtool, this routine is called. It lists the options found under
# the "Advertised link modes" section.
# ex: /opt/hal/bin/hal get_advertised_link_modes lan0_0
#
#--------------------------------------------------------------------------
get_advertised_link_modes()
{
	INTF="${1}"
	AVAIL=`ethtool ${INTF} | grep "Advertised link modes" \
		| awk -F\: '{print $2}' | sed -e 's/baseT//' -e 's/^[ /t]*//'`
	echo $AVAIL
	return 0
}

#--------------------------------------------------------------------------
# get_avail_speed_duplex
# Lists all the available speed and duplex options for a network interface
# ex: /opt/hal/bin/hal get_avail_speed_duplex lan0_0
#
#--------------------------------------------------------------------------

get_avail_speed_duplex()
{
	INTF="${1}"
	#If interface is primary, make sure that it is not a virtual interface
	if [ "x${INTF}" = "xprimary" ]; then
	   RET=`ls /sys/class/net/primary/device 2>/dev/null`
	   if [ $? -eq 1 ]; then
		INTF="prihw"
	   fi
	fi

	if [ ! -e /sys/class/net/${INTF}/device ]; then
	  #invalid interface
	  return 1
	fi

	for i in  `ethtool ${INTF} | grep -A 4 "Supported link modes:" | grep -v "auto-negotiation\|Advertised\|Speed\|Duplex" \
        | sed -e 's/Supported link modes://' -e 's/baseT//g' -e 's/^[ \t]*//' -e 's/ *$//' |sort -u`
	do
		echo $i
	done

	if [ -z $i ]; then
	   #No speed found in "Supported link modes" section
	   get_advertised_link_modes ${INTF}
	fi

	RET=`ethtool ${INTF} | grep "Supported ports" | grep "FIBRE"`
	if [ $? -eq 1 ]; then
	   #The card is not fiber
	   echo "auto/auto"
	fi
	return 0
}

#--------------------------------------------------------------------------
# get_default_speed_duplex
# Returns the default speed and duplex settings for the interface
# ex: /opt/hal/bin/hal get_default_speed_duplex lan0_0
#
#--------------------------------------------------------------------------

get_default_speed_duplex()
{
	INTF="${1}"
        #If interface is primary, make sure that it is not a virtual interface
        if [ "x${INTF}" = "xprimary" ]; then
           RET=`ls /sys/class/net/primary/device 2>/dev/null`
           if [ $? -eq 1 ]; then
                INTF="prihw"
           fi
        fi

	if [ ! -e /sys/class/net/${INTF}/device ]; then
	  #invalid interface
	  return 1
	fi

	RET=`ethtool ${INTF} | grep "Supported ports" | grep "FIBRE"`
	if [ $? -eq 0 ]; then
           #The card is fibre
           DEF=`ethtool ${INTF} | grep "Advertised link modes" | awk -F\: '{print $2}' | sed -e 's/baseT//' -e 's/^[ /t]*//'`
           echo $DEF
	else
           echo "auto/auto"
        fi

	return 0
}

#--------------------------------------------------------------------------
# set_speed_duplex
# Sets speed and duplex for a interface.
# For a fiber card, just return 0
#
# ex: /opt/hal/bin/hal set_speed_duplex $interface $speed $duplex
#--------------------------------------------------------------------------

set_speed_duplex()
{
	if [ $# -ne 3 ]; then
           echo "Invalid parameters"
           return 1
	fi

	#$1 = interface
	#$2 = speed
	#$3 = duplex

	INTF="${1}"
        #If interface is primary, make sure that it is not a virtual interface
        if [ "x${INTF}" = "xprimary" ]; then
           RET=`ls /sys/class/net/primary/device 2>/dev/null`
           if [ $? -eq 1 ]; then
                INTF="prihw"
           fi
        fi

	if [ ! -e /sys/class/net/${INTF}/device ]; then
	  #invalid interface
	  return 1
	fi

	RET=`ethtool ${INTF} | grep "Supported ports" | grep "FIBRE"`
	if [ $? -eq 0 ]; then
	   #The card is fibre; Can't set speed/duplex
           return 0
	fi

	#The card is copper
	if [ "x${2}" = "xauto" -o "x${3}" = "xauto" ];then
	   ethtool -s ${INTF} autoneg on
	   return 0
	fi
	ethtool -s ${INTF} autoneg off speed $2 duplex $3

	return 0
}

#--------------------------------------------------------------------------
# Disk Power Count Routines
#--------------------------------------------------------------------------
collect_disk_smart_power_stats()
{
        local DISK_LIST=$1
        
        local FAILURE_LOG=/var/opt/rbt/.unscheduled_reboots
        local DISK_COUNTER=0
        local DISK_CYCLED_COUNTER=0
        
        local LAST_SMART_LOGS=/var/opt/rbt/last_smart_data
        local CURRENT_SMART_LOGS=/var/opt/rbt/last_smart_data.tmp
        if [ "x${DISK_LIST}" = "x" ]; then
                /usr/bin/logger -p user.NOTICE -t disk "No devices specified to collect_disk_smart_power_stats"
                return
        fi

        for disk in ${DISK_LIST}; do
                if [ ! -b /dev/${disk} ]; then
                        continue
                fi

                POWER=`${SMARTCMD} -a /dev/$disk | grep "Power_Cycle_Count" | awk '{print $10}'`
                SERIAL=`${SMARTCMD} -a /dev/$disk | grep "Serial Number" | awk 'BEGIN{FS=":"}{print $2}'`

                LAST_POWER=""
                if [ -f ${LAST_SMART_LOGS} ]; then
                        LAST_POWER=`cat ${LAST_SMART_LOGS} | grep ${SERIAL} | awk 'BEGIN{FS=":"}{print $2}'`
                fi

                if [ "x${LAST_POWER}" = "x" ]; then
                        LAST_POWER="UNKNOWN"
                fi
                
                if [ "${LAST_POWER}" != "UNKNOWN" ]; then
                        DISK_COUNTER=$((DISK_COUNTER+1))
                        if [ ${POWER} -gt ${LAST_POWER} ]; then
                                DISK_CYCLED_COUNTER=$((DISK_CYCLED_COUNTER+1))
                        fi
                fi
                
                
                MSG="Drive=${disk}, Serial=${SERIAL}, Current Power Cycle Count=${POWER}, Last Power Cycle Count=${LAST_POWER}"
                /usr/bin/logger -p user.NOTICE -t disk ${MSG}
                echo "${SERIAL}:${POWER}" >> ${CURRENT_SMART_LOGS}
        done

        if [ -f ${CURRENT_SMART_LOGS} ]; then
            mv -f ${CURRENT_SMART_LOGS} ${LAST_SMART_LOGS}
        fi
        
        UNEXPECTED_SHUTDOWN=""       
        if [ -f /var/opt/tms/.unexpected_shutdown ] || [ -f /var/opt/tms/.detected_unexpected_shutdown ]; then
                UNEXPECTED_SHUTDOWN="True"
        fi
        
        DISKS_POWER_CYCLED=""
        if [ ${DISK_COUNTER} -eq ${DISK_CYCLED_COUNTER} ]; then
                DISKS_POWER_CYCLED="True"
        fi

        if [ ${DISK_COUNTER} -ne 0 ]; then
                if [ "x${UNEXPECTED_SHUTDOWN}" = "xTrue" ] && [ "x${DISKS_POWER_CYCLED}" = "x" ]; then
                        /usr/bin/logger -p user.NOTICE -t disk "Reboot Detected: Unscheduled Reboot"
                        echo `date +%s` >> ${FAILURE_LOG}
                elif [ "x${UNEXPECTED_SHUTDOWN}" = "xTrue" ] && [ "x${DISKS_POWER_CYCLED}" = "xTrue" ]; then       
                        /usr/bin/logger -p user.NOTICE -t disk "Reboot Detected: Power Disruption"
                elif [ "x${UNEXPECTED_SHUTDOWN}" = "x" ] && [ "x${DISKS_POWER_CYCLED}" = "xTrue" ]; then
                        /usr/bin/logger -p user.NOTICE -t disk "Reboot Detected: Power Off"
                elif [ "x${UNEXPECTED_SHUTDOWN}" = "x" ] && [ "x${DISKS_POWER_CYCLED}" = "x" ]; then
                        /usr/bin/logger -p user.NOTICE -t disk "Reboot Detected: Reboot"
                fi
        fi
}
#------------------------------------------------------------------------------
# get_default_ipmi_wdt_timeout
# This hal function is called by wdt to figure out the defualt ipmi wdt timeout
#------------------------------------------------------------------------------
get_default_ipmi_wdt_timeout()
{
    MOBO=`get_motherboard`

    case "${MOBO:0:9}" in
        "400-00300"|"400-00100"|"425-00205"|"425-00140")
            if [ -f /var/opt/rbt/.nmi_disable ]; then
                echo "60"
            else
                echo "75"
            fi
            ;;
        *)
            echo "60"
            ;;
    esac
}


#------------------------------------------------------------------------------
# downgrade_bios
# Downgrades the Bios on a sturgeon 
#------------------------------------------------------------------------------
downgrade_bios()
{
        VER=`get_bios_ver 1| sed -e 's/bios_ver=//' -e "s/'//g"`
        if [ "${VER}" != "V1.17" ]; then
                RET=`/sbin/flashmac.py -wb /opt/rbt/lib/6673V117.ROM`
                if [ $? -eq 1 ]; then
                     ${HAL_LOG_WARN} "Bios downgrade to V1.17 failed."
                     return 0   
                fi

                ${HAL_LOG_INFO} "Bios downgraded successfully to V1.17"
        fi
        return 0
}

#------------------------------------------------------------------------------
# check_update_bios
# We have Bios incompatibility issues for Bios version >= 1.08 with older images
# This effects only the SH and for models 6050, 5050.
# Whenever customer downgrades to any image less than
# 4.1.12, 5.0.11, 5.5.7, 6.0.2, we need to downgrade.
#------------------------------------------------------------------------------
check_update_bios()
{
     PLATFORM=`get_platform`
     MOBO=`get_motherboard`

     # this is not supported on EX
     if [ "${PLATFORM}" = "SH" ] && [ "$MOBO" = "400-00300-01" ]; then
        NEXT_BOOT_RIOS=`/bin/sh /sbin/imgq.sh -i -l $1 -d | grep BUILD_PROD_VERSION | \
                                awk '{print $2}' | awk -F\. '{print $1"."$2}'`

        VERSION=`/bin/sh /sbin/imgq.sh -i -l $1 -d | grep BUILD_PROD_VERSION | \
                                awk '{print $2}' | awk -F\. '{print $3}' | sed -e 's/[a-z].*//'`
        BIOS_VER=`get_bios_ver 1| sed -e 's/bios_ver=//' -e "s/'//g"`

        case "${NEXT_BOOT_RIOS}" in
        "4.1")
                if [ ${VERSION} -lt 12 ]; then
                        if [ "${BIOS_VER}" != "V1.17" ]; then
                                echo "Updating BIOS. Please do not interrupt or reboot till the command completes"
                                return 1
                        fi
                fi
                ;;
        "5.0")
                if [ ${VERSION} -lt 11 ]; then
                        if [ "${BIOS_VER}" != "V1.17" ]; then
                                echo "Updating BIOS. Please do not interrupt or reboot till the command completes"
                                return 1
                        fi
                fi
                ;;
        "5.5")
                if [ ${VERSION} -lt 7 ]; then
                        if [ "${BIOS_VER}" != "V1.17" ]; then
                                echo "Updating BIOS. Please do not interrupt or reboot till the command completes"
                                return 1
                        fi
                fi
                ;;
        "6.0")
                if [ ${VERSION} -lt 2 ]; then
                        if [ "${BIOS_VER}" != "V1.17" ]; then
                                echo "Updating BIOS. Please do not interrupt or reboot till the command completes"
                                return 1
                        fi
                fi
                ;;
        esac
     fi
     echo " "
     return 0
}

###############################################################################
# Commom SW RAID related functionality in HAL
###############################################################################

# List of the required volumes to be set up early in the boot process
# so the rest of the system can come up
#
MGMT_VOLUME_LIST="var swap"

do_create_sw_raid()
{
    VOL="${1}"
    
    # if we arent passed in a second param, send output to stdout.
    LOG="$2"

    ${RRDM_TOOL} -c /${VOL} > /dev/null 2>&1
    if [ $? -ne 0 ]; then
	if [ "x${LOG}" = "x" ]; then
	    echo "Unable to recreate RAID array [${VOL}]"
	else
	    ${HAL_LOG_WARN} "Unable to recreate RAID Array [${VOL}]" 
	fi

	return 1
    fi

    return 0
}

DO_HALT="/sbin/halt -p"

# 
# This routine is called before logging is set up, so output messages
# to the console.
#
# We may want to put a failure message on the flash to indicate why we died
# if we couldnt start the array.
#
do_start_mgmt_volumes()
{
    USES_SW_RAID=`${RRDM_TOOL} --uses-sw-raid`
    if [ "x${USES_SW_RAID}" = "xTrue" ]; then
	echo "Starting SW Raid Arrays"

	for VOL in ${MGMT_VOLUME_LIST}; do
	    echo "Starting: ${VOL}"
	    # we have stuff to do
	    ${RRDM_TOOL} --run=/${VOL}
	    if [ $? -ne 0 ]; then
		echo "Unable to Start RAID Array [${VOL}]"
		echo "Starting RAID Recovery for [${VOL}]"

		# starting the array has failed, this is bad!
		# so .. we throw away the RAID and rebuild.
		do_create_sw_raid ${VOL}
		if [ $? -ne 0 ]; then
		    echo "Unable to start required array ${VOL}, halting system"
                    ${DO_HALT}
		fi

		${DO_FS_RECOVERY} ${VOL} -f
		if [ $? -ne 0 ]; then
		    echo "Unable to complete filesystem recovery for ${VOL}, halting system"
                    ${DO_HALT}
		fi
	    fi
	done
    fi

    return 0
}

check_volume_is_raid()
{
    local ARRAY_LINE="$1"
    IS_RAID=`echo ${ARRAY_LINE} | awk 'BEGIN{FS=":"}{print $6}'`
    if [ "x${IS_RAID}" = "xtrue" ]; then
        return 0
    fi

    return 1
}

# Start any other RAID devices needed by RiOS, but not necessarily Linux
# this would be PFS and the Segstore(NON FTS).
#
# Logging is OK here since we would have started /var above.
#
do_start_rios_volumes()
{
    USES_SW_RAID=`${RRDM_TOOL} --uses-sw-raid`
    if [ "x${USES_SW_RAID}" = "xTrue" ]; then
	${HAL_LOG_INFO} "Starting RiOS Raid Arrays"
	DEVICE_LIST=`${RRDM_TOOL} -l`
	for LINE in ${DEVICE_LIST}; do
            DO_START=0
	    ARRAY=`echo $LINE | awk 'BEGIN{FS=":"} {print $1}'`

            check_volume_is_raid "${LINE}"
            if [ $? -eq 0 ]; then
                # we might need to start it. 
	        echo "${MGMT_VOLUME_LIST}" | grep $ARRAY > /dev/null
                if [ $? -ne 0 ]; then
                    # its not in the list we already looked at for mgmt volumes so
                    # lets start it
                    DO_START=1
                fi
            fi
            
	    if [ ${DO_START} -eq 1 ]; then
		${RRDM_TOOL} --run=/${ARRAY}
		if [ $? -ne 0 ]; then
		    echo "Unable to Start RAID Array [${ARRAY}]"
		    echo "Starting RAID Recovery for [${ARRAY}], Wiping the array and starting clean"
                    # XXX re-enable these once we get the system hardware config
                    # alarm, and we're not starting all volumes in phase0.
                    #
		    #${HAL_LOG_WARN} "Unable to Start RAID Array [${ARRAY}]"
		    #${HAL_LOG_WARN} "Starting RAID Recovery for [${ARRAY}], Wiping the array and starting clean"

		    # starting the array has failed, this is bad!
		    # so .. we throw away the RAID and rebuild.
		    do_create_sw_raid ${ARRAY}
		    if [ $? -ne 0 ]; then
			echo "Unable to start required array ${ARRAY}, halting system"
			${DO_HALT}
		    fi

		    ${DO_FS_RECOVERY} ${ARRAY}
		    if [ $? -ne 0 ]; then
			echo "Unable to complete filesystem recovery for ${ARRAY}, halting system"
			${DO_HALT}
		    fi
		fi
	    fi
	done
    fi
}

# Routines for show raid diagram
#------------------------------------------------------------------------------
# RAID Interfaces
#------------------------------------------------------------------------------
PADDING="                   "

# Parses output of 'rrdm_tool.py -s /disk' for status for the given slot
# get_status_for_disk <slot> <output>
get_disk_status_by_slot() {
    local SLOT="$1"
    local DINFO="$2"
    local status
    local len

    status=$(echo "${DINFO}" | grep "^${SLOT} " | cut -b3-20 |
		tr -d "[ \n]")

    case "x${status}" in
	"xonline"|"xmissing"|"xdegraded"|"xfailed"|"xrebuilding"|"xunknown"|"xinvalid")
	    # no change
	;;
	"x")
	    # if the drive isnt in rrdm_tool output, its not part of the raid array
	    # just check if the drive exists, if so, its not raided, if not, its missing.
	    #
	    if [ ! -b /dev/disk${SLOT} ]; then
		status="missing"
	    else
		status="noraid"
	    fi
	;;
	*)
	    status="unknown"
	;;
    esac

    echo "$status"
}

#------------------------------------------------------------------------------
# draw_drive_bay
#
# draw a single drive bay, padding by the appropriate amount given
# the status to make all drive bays the same width, regardless of slot
# length or status length.
#------------------------------------------------------------------------------
draw_drive_bay()
{
        SLOT="$1"
        OUTPUT="$2"

        STATUS=$(get_disk_status_by_slot "$SLOT" "$OUTPUT")

        LEN=`expr length ${STATUS}`
        if [ ${LEN} -le 10 ]; then
                POSTPAD_LEN=$[ 10 - ${LEN} ];
        fi

        LEN=`expr length $SLOT`
        if [ $LEN -eq 2 ]; then
                PREPAD_LEN=0
        else
                PREPAD_LEN=1
        fi
        echo -n "[${PADDING:0:${PREPAD_LEN}} ${SLOT} : ${STATUS}${PADDING:0:${POSTPAD_LEN}} ]"
}

#-------------------------------------------------------------------------------
# draw_drive_row
# 
# given a start and end disk index, print a row of drive bays
#
#-------------------------------------------------------------------------------
draw_drive_row()
{
        START="$1"
        END="$2"
        OUTPUT="$3"

        for slot in `seq ${START} ${END}`; do
                draw_drive_bay ${slot} "${OUTPUT}"
        done
        echo ""
}

#------------------------------------------------------------------------------
# check_resource_profile_change
#------------------------------------------------------------------------------
check_resource_profile_change()
{
    if [ -f /config/changeprofile ]; then
        PROFILE=`cat /config/changeprofile`
        rm -f /config/changeprofile
        touch / 2>/dev/null
        READ_ONLY_ROOT=$?

        [ $READ_ONLY_ROOT -ne 0 ] && mount -o rw,remount /

        # Get the current profile from teh MFDB
        FALLBACK_PROFILE=`${MDDBREQ} -v ${MFDB} query get - /rbt/mfd/resman/profile`

        echo "Storage Profile Reconfiguration for:${PROFILE}"
        RESULT=`${RRDM_TOOL} --validate --profile=${PROFILE}`
        if [ "x${RESULT}" != "xTrue" ]; then
            echo "Storage Profile Reconfigurtion Validation failed for ${PROFILE}"
        else
            ${RRDM_TOOL} --change-profile --profile=${PROFILE}
            if [ $? -ne 0 ]; then
                echo "Storage Profile Change Request Failed for ${PROFILE}, we are going to retry in 5 seconds"
                # XXX/munirb: Storage profile change is an important step and
                # we can't keep the machine in a bad state so we will retry
                # The reason profile change may fail is cause there is a race with udev
                # and depending on the time udev takes some disks may not show up 
                # or the links to partitions may take additional time to show up
                # We will touch a file on /config to indicate failure if the retry fails
                # as well which can be used to raise an alarm later
                sleep 5
                # XXX/munirb: Something else to keep in mind is that mdadm may
                # have failed and we have some arrays running, we may want to
                # shut them down as well. 
                ${RRDM_TOOL} --change-profile --profile=${PROFILE}
                if [ $? -ne 0 ]; then
                    echo "Storage Profile Change Request Failed for ${PROFILE} even after retry"

                    # Try to fallback to the orginal profile
                    # We don't know if the RAID arrays were started, if they 
                    # were we should stop them. No RAID array is mounted
                    # at this point for sure
                    # We wont have more than 32 RAID arrays for a lot of 
                    # years to come
                    for i in {0..31}; do
                        if [ -e /dev/md${i} ]; then
                            echo "Shutting down RAID device [/dev/md${i}]"
                            /sbin/mdadm --stop /dev/md${i} > /dev/null 2>&1
                        fi
                    done

                    echo "Now will try to fallback to profile [${FALLBACK_PROFILE}]"
                    # Now its time to fallback to the old partition type
                    ${RRDM_TOOL} --change-profile --profile=${FALLBACK_PROFILE}
                    if [ $? -ne 0 ]; then
                        echo "Cannot even fallback to the original profile [${FALLBACK_PROFILE}]"
                        # At this point we are in a bad situation
                        # hope for the best and tocuh some files to indicate that 
                        # the machine is in a bad state so that user knows
                        # Reset the profile change name to the file so that its attempted 
                        # on next reboot
                        echo "${PROFILE}" > /config/changeprofile
                        # Touch this file which can be used later to
                        # fire an alarm
                        echo "3:Failed to switch the storage profile. Please reboot to try again and contact Riverbed Support if the problem persists." > /config/.profile_change_failed
                    else
                        echo "Fallback to profile [${FALLBACK_PROFILE}] successful"
                        # still touch the file to indicate we were
                        # unable to do the profile switch
                        echo "1:Failed to switch the storage profile to \"${PROFILE}\". The current profile is \"${FALLBACK_PROFILE}\"." > /config/.profile_change_failed
                    fi
                fi
            fi

            # update disk_config.xml
            ${RRDM_TOOL} --write-config
            if [ $? -ne 0 ]; then
                echo "Disk config update failed, disk metadata may be out of date"
            fi

            # Touch a file in /lib/modules tmpfs as thats the only rw partition
            # This file will indicate to the shadow code that a hardware upgrade was done
            # and config on flash is the latest and should not be overwritten
            /bin/touch /lib/modules/.config_fresh_on_flash
        fi
        [ $READ_ONLY_ROOT -ne 0 ] && mount -o ro,remount /
    fi
}


