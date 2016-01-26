#!/bin/sh

#
#  URL:       $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/sysdump.sh $
#  Revision:  $Revision: 107513 $
#  Date:      $Date: 2013-08-27 16:17:21 -0700 (Tue, 27 Aug 2013) $
#  Author:    $Author: jhou $
# 
#  (C) Copyright 2003-2012 Riverbed Technology, Inc.
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#


PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/tms/bin
export PATH

export BRIEF=0
export FORCE_DB=0
# initialize stats variable so we don't get a bash error 
STATS=0
NO_REVMAP=0
UNLIMITED_LOGS=0

SYSDUMP_OPTIONS='bdRsu'

# This will get us product specific customer_options, usage and case 
#statements. Note that this will append product specific options to 
#variable SYSDUMP_OPTIONS.
if [ -f /etc/customer_sysdump_options.sh ]; then
. /etc/customer_sysdump_options.sh
fi

usage()
{
    echo "usage: $0 [-$SYSDUMP_OPTIONS] [extra file list]"
    echo "-b    brief output"
    echo "-d    include databases (only useful when -b is used)"
    echo "-R    no show running output"
    echo "-s    get stats"
    echo "-u    unlimited logs"
# Append any product specific sysdump options' usage
if [ -f /etc/customer_sysdump_options.sh ]; then 
    customer_usage
fi    
    echo
    exit 1
}


PARSE=`/usr/bin/getopt $SYSDUMP_OPTIONS "$@"`

if [ $? != 0 ] ; then
    usage
fi

eval set -- "$PARSE"

while true ; do
    case "$1" in
        --) shift ; break ;;
        -b) export BRIEF=1 ; shift ;;
        -d) export FORCE_DB=1 ; shift ;;
        -R) export NO_REVMAP=1 ; shift ;;
        -s) STATS=1 ; shift ;;
        -u) UNLIMITED_LOGS=1 ; shift ;;

# Which flags are used by other products?  You may want to play it safe
# by verifying this list before trusting it.  I make no guarantees about
# its accuracy beyond today (6/11/2010).  :)
#
# -p is used in SH, FG, and DD.

#All product specific option are ORed together in CUSTOMER_OPTIONS and handled 
#in a single case block.
        $CUSTOMER_OPTIONS) 
            if [ -f /etc/customer_sysdump_options.sh ]; then 
                customer_opt_handler "$1"
            fi ; shift ;;

        *) echo "sysdump.sh: parse failure" >&2 ; usage ;;
    esac
done

if [ ! -z "$*" ] ; then
    EXTRA_FILES="$*"
fi



DATE_STR=`date '+%Y-%m-%d %H:%M:%S'`
DATE_STR_FILE=`echo ${DATE_STR} | sed 's/-//g' | sed 's/://g' | sed 's/ /-/g'`
OUTPUT_PREFIX=sysdump-`uname -n`-${DATE_STR_FILE}
FINAL_DIR=/var/opt/tms/sysdumps/
FINAL_MD5_DIR=/var/opt/tms/sysdumps/md5/
WORK_DIR=/var/tmp/${OUTPUT_PREFIX}-$$
STAGE_DIR_REL=${OUTPUT_PREFIX}
STAGE_DIR=${WORK_DIR}/${STAGE_DIR_REL}
SYSINFO_FILENAME=/var/tmp/sysinfo-${OUTPUT_PREFIX}.txt
DUMP_FILENAME=${WORK_DIR}/${OUTPUT_PREFIX}.tgz
MD5_FILENAME=${DUMP_FILENAME}.md5
HARDWARE_INFO_FILENAME=${STAGE_DIR}/hardwareinfo.txt
BYPASS_STATE_FILENAME=${STAGE_DIR}/bypassstate.txt
RAID_INFO_FILENAME=${STAGE_DIR}/raidinfo.txt
SMART_INFO_FILENAME=${STAGE_DIR}/smart.txt
UNSCHED_REBOOTS_FILENAME=/var/opt/rbt/.unscheduled_reboots
SENSORS_DIR=${STAGE_DIR}/sensors
HARDWARE_RULES_FILENAME=${STAGE_DIR}/hardware_rules_10g.txt
PRODUCT_ID=`cat /etc/build_version.sh |grep BUILD_PROD_ID= | cut -c 15-`
NUM_LOG_LINES=50

# Variables of storing the locations of executables used for sysdump purposes.
TW_CLI="/usr/sbin/tw_cli"

# Variable of storing the locations of samba account db.
SAMBA_TDB_FILENAME=${STAGE_DIR}/config/samba/private/secrets.tdb

# These are used for saving stuff from /proc and /proc/sys respectively
KERNEL_PROC_DIR=${STAGE_DIR}/kernel/proc
KERNEL_PROC_SYS_DIR=${STAGE_DIR}/kernel/proc/sys
mkdir -p ${KERNEL_PROC_SYS_DIR}

# Make the sysinfo.txt, which has output from useful commands


# Function to dump command output
do_command_output()
{
    local command_name="$1"
    echo "==================================================" >> ${SYSINFO_FILENAME}
    echo "Output of '${command_name}':"  >> ${SYSINFO_FILENAME}
    echo "" >> ${SYSINFO_FILENAME}
    echo "`${command_name} 2>&1`" >> ${SYSINFO_FILENAME} 
    echo "" >> ${SYSINFO_FILENAME}
    echo "==================================================" >> ${SYSINFO_FILENAME}
    echo "" >> ${SYSINFO_FILENAME}
}

# Function to dump command output to an alternate file other than
# the sysinfo file.
# File names passed in as arg $2 should be absolute paths residing in the
# staging directory, otherwise the file won't be included in the dump
#
do_command_output_file()
{
    local command_name="$1"
    local OUTPUT_FILENAME="$2"
    echo "==================================================" >> ${OUTPUT_FILENAME}
    echo "Output of '${command_name}':"  >> ${OUTPUT_FILENAME}
    echo "" >> ${OUTPUT_FILENAME}
    echo "`${command_name} 2>&1`" >> ${OUTPUT_FILENAME}
    echo "" >> ${OUTPUT_FILENAME}
    echo "==================================================" >> ${OUTPUT_FILENAME}
    echo "" >> ${OUTPUT_FILENAME}
}

do_timed_command_output()
{
    local command_name="$1"
    command_output=`/sbin/timed_exec.py -t 30 ${command_name} 2>&1`
    ret_val=$?
    if [ ${ret_val} -eq 0 ]; then
        echo "==================================================" >> ${SYSINFO_FILENAME}
        echo "Output of '${command_name}':"  >> ${SYSINFO_FILENAME}
        echo "" >> ${SYSINFO_FILENAME}
        echo "${command_output}" >> ${SYSINFO_FILENAME} 
        echo "" >> ${SYSINFO_FILENAME}
        echo "==================================================" >> ${SYSINFO_FILENAME}
        echo "" >> ${SYSINFO_FILENAME}
    fi
    return ${ret_val}
}

do_df_Pka_output()
{
    do_timed_command_output 'df -Pka'

    if [ $? -ne 0 ]; then
        do_command_output 'df -Pka --exclude-type=fuse'
    fi
}

do_df_ha_output()
{
    do_timed_command_output 'df -ha'

    if [ $? -ne 0 ]; then
        do_command_output 'df -ha --exclude-type=fuse'
    fi
}
# function to dump ecc error information
show_ecc_status()
{
    for i in /sys/devices/system/edac/mc/mc*/*_count; do
        echo -n $i:
        cat $i
    done

    for i in /sys/devices/system/edac/mc/mc*/*/{*_count,*_label,size_mb}; do
        echo -n $i:
        cat $i
    done
}

# Get the SCSI state of all the disks
get_scsi_state()
{
    local FILENAME="$1"
    echo "==================================================" >> ${FILENAME}
    for disk in `/opt/hal/bin/hwtool.py -q disk=map |awk '{print $1'}`; do
        if [ "x${disk}" != "xunknown" ]; then
            echo "Output of cat /sys/bus/scsi/devices/${disk}/state: " >> ${FILENAME}
            echo "`cat /sys/bus/scsi/devices/${disk}/state`" >> ${FILENAME}
            echo "" >> ${FILENAME}
        fi
    done
    echo "==================================================" >> ${FILENAME}
    echo "" >> ${FILENAME}
}

# FW version
show_firmware_version()
{
    local FILENAME="${HARDWARE_INFO_FILENAME}"
    echo "==================================================" >> ${FILENAME}
    echo "Output of /opt/hal/bin/hal get_ipmi_ver: " >> ${FILENAME}
    echo "`/opt/hal/bin/hal get_ipmi_ver`" >> ${FILENAME}
    echo "" >> ${FILENAME}
    echo "Output of /opt/hal/bin/hal get_controller_ver: " >> ${FILENAME}
    echo "`/opt/hal/bin/hal get_controller_ver`" >> ${FILENAME}
    echo "" >> ${FILENAME}
    echo "Output of ipmitool sdr list: " >> ${FILENAME}
    echo "`ipmitool sdr list`" >> ${FILENAME}
    echo "" >> ${FILENAME}
    echo "==================================================" >> ${FILENAME}
    echo "" >> ${FILENAME}
}

# Save BIOS nvram
save_bios_nvram()
{
    local MOBO=`/opt/tms/bin/hwtool -q motherboard | awk -F- '{ print $1"-"$2}'`
    if [ "x${MOBO}" = "x400-00100" ] || [ "x${MOBO}" = "x400-00300" ]; then
        echo "Saving BIOS nvram to file bios_nvram"

        modprobe nvram
        local WAIT_TIME=0
        while [ ! -e /dev/nvram ] && [ ${WAIT_TIME} -lt 5 ]; do
            sleep 1
            let WAIT_TIME=WAIT_TIME+1
        done
        if [ ! -e /dev/nvram ]; then
            echo "nvram kernel module not creating /dev/nvram device"
        else
            cat /dev/nvram > ${STAGE_DIR}/bios_nvram
        fi
        modprobe -r nvram
        echo "Done"
    fi
}

#Branding information for all xx50 and later models
show_branding_information()
{
    local FILENAME="${HARDWARE_INFO_FILENAME}"
    local SUPPORTED=`hwtool -q branding`
    echo "==================================================" >> ${FILENAME}
    if [ "x${SUPPORTED}" = "xtrue" ]; then
        echo "Output of /opt/hal/bin/hwtool.py -q disk-license: " >> ${FILENAME}
        echo "`/opt/hal/bin/hwtool.py -q disk-license`" >> ${FILENAME}
        echo "" >> ${FILENAME}
        echo "Output of /opt/hal/bin/hwtool.py -q nic-license: " >> ${FILENAME}
        echo "`/opt/hal/bin/hwtool.py -q nic-license`" >> ${FILENAME}
        echo "" >> ${FILENAME}
    fi 
    echo "Output of /opt/hal/bin/hwtool.py -q memory: " >> ${FILENAME}
    echo "`/opt/hal/bin/hwtool.py -q memory`" >> ${FILENAME}
    echo "" >> ${FILENAME}
    echo "Output of /opt/hal/bin/hwtool.py -q cpu: " >> ${FILENAME}
    echo "`/opt/hal/bin/hwtool.py -q cpu`" >> ${FILENAME}
    echo "" >> ${FILENAME}
    echo "==================================================" >> ${FILENAME}
    echo "" >> ${FILENAME}
}

# Show spare disks in a system
show_spare_information()
{
    local SPAREDRIVES=`/opt/hal/bin/raid/rrdm_tool.py --show-spares`
    local FILENAME="${HARDWARE_INFO_FILENAME}"
    echo "==================================================" >> ${FILENAME}
    echo "Output of /opt/hal/bin/raid/rrdm_tool.py --show-spares: " >> ${FILENAME}
    echo "$SPAREDRIVES" >> ${FILENAME}
    echo "==================================================" >> ${FILENAME}
    echo "" >> ${FILENAME}
}

#Wear level of FTS disks
show_wear_information()
{
    local FILENAME="${HARDWARE_INFO_FILENAME}"
    local FTSMODEL=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/fts`
    
    if [ "x${FTSMODEL}" = "xtrue" ]; then
        FTSDRIVES=`/opt/hal/bin/raid/rrdm_tool.py -s /fts  |awk '{print $1}'`
        echo "==================================================" >> ${FILENAME}
        for dnum in ${FTSDRIVES}; do 
            MAX=0
            CURRENT=0
            OUTPUT=`/opt/tms/bin/rvbd_super -g /dev/disk${dnum}p1`
            if [ $? -eq 0 ]; then
                for line in ${OUTPUT}; do
                    if [ "x${line:0:21}" = "xmax_write_lifetime_gb" ]; then
                        MAX=${line:22}
                    elif [ "x${line:0:19}" = "xcurrent_data_stored" ]; then
                        CURRENT=${line:20}
                    fi
                done
                if [ ${MAX} -gt 0 ]; then
                    # MAX is in GB and CURRENT in bytes, 
                    # if I multiple by 100 before, there is a chance of overflow
                    WEAR=`echo "${CURRENT} ${MAX}" | awk '{printf("%d", (($1 / $2) * 100) / (1024 * 1024 * 1024))}'`
                else
                    WEAR=0 
                fi
                echo "Wear for /dev/disk${dnum} = ${WEAR}%" >> ${FILENAME}
            else
                if [ -e /dev/disk${dnum} ]; then
                    echo "Drive /dev/disk${dnum} may not be partitioned with Riverbed superblock as yet" >> ${FILENAME}
                else
                    echo "Could not get wear information for /dev/disk${dnum} drive missing" >> ${FILENAME}
                fi
            fi
        done
        echo "==================================================" >> ${FILENAME}
        echo "" >> ${FILENAME}
    else
        echo "==================================================" >> ${FILENAME}
        echo "Non FTS model, no disk wear information" >> ${FILENAME}
        echo "==================================================" >> ${FILENAME}
        echo "" >> ${FILENAME}
    fi
}


# Read the EEPROM serial for minnow and barramundi machines
read_eeprom_serial()
{
    local FILENAME="${HARDWARE_INFO_FILENAME}"
    local MOBO=`/opt/tms/bin/hwtool -q motherboard | awk -F- '{ print $1"-"$2}'`
    case ${MOBO} in
        "400-00100"|"400-00300")
            echo "==================================================" >> ${FILENAME}
            echo "Output of /sbin/read_eeprom_serial.py: " >> ${FILENAME}
            echo "`/sbin/read_eeprom_serial.py`" >> ${FILENAME}
            echo "" >> ${FILENAME}
            echo "==================================================" >> ${FILENAME}
            echo "" >> ${FILENAME}
        ;;
        "400-00099"|"400-00098")
            echo "==================================================" >> ${FILENAME}
	    if [ -e /sys/bus/i2c/devices/0-0051/eeprom ]; then
	            echo "Output of cat /sys/bus/i2c/devices/0-0051/eeprom: " >> ${FILENAME}
        	    echo "`cat /sys/bus/i2c/devices/0-0051/eeprom`" >> ${FILENAME}
        else
	            echo "Could not read EEPROM! File does not exist. " >> ${FILENAME}
	    fi
            echo "" >> ${FILENAME}
            echo "==================================================" >> ${FILENAME}
            echo "" >> ${FILENAME}
        ;;
    esac
}

show_flex_specs()
{
    if [ "${PRODUCT_ID}" = '"SH"' -o "${PRODUCT_ID}" = '"EX"' ]; then
        MODEL=`/opt/tms/bin/hald_model | awk '{print $1}'`
        BW=`/opt/tms/bin/hald_model | awk '{print $4}'`
        echo "System Spec : ${MODEL}"
        echo "System Bw   : ${BW}"
    fi
}

# function to display Minnow sensors
show_minnow_sensors()
{
    for i in /sys/devices/pci0000:00/0000:00:1f.3/i2c-0/0-002e/*; do
        if [ -f $i ]; then
            echo -n \"$i: \"; cat $i;
        fi
    done
}

# function to get the USB information
show_usb_flash_info()
{
    local CMD_NAME="cat /proc/scsi/usb-storage/*"
    if [ -d /proc/scsi/usb-storage ]; then
        echo "" 
        echo "`${CMD_NAME}`"
        echo "" 
    else
        echo "No /proc/scsi/usb-storage/* file to get flash information"
    fi
}

# show the unscheduled reboots (if any)
show_unscheduled_reboots()
{
	if [ -e "$UNSCHED_REBOOTS_FILENAME" ]; then
		cat "$UNSCHED_REBOOTS_FILENAME"
	else
		echo "No unscheduled reboots recorded."
	fi
}

# function to display ipmi information
show_ipmi_info()
{
    local CMD_NAME="/sbin/ipmitool sel list -v"
    local INFO_CMD_NAME="/sbin/ipmitool mc info"
    # we'll add functions to the HAL for determining whether platforms
    # support IPMI later, we'll use whether or not we can get 
    # the MC info as an indicator as to whether IPMI is supported.
    #
    
    local MOBO=`hwtool -q motherboard`
    ${INFO_CMD_NAME} >> /dev/null 2>&1
    if [ $? -eq 0 ]; then
        # we found a BMC IPMI adapter
        echo "Motherboard '${MOBO}'"
        echo "" 
        echo "`${CMD_NAME} 2>&1`"
        echo ""
        echo ""
    else
        # no BMC
        echo "IPMI is not supported on this hardware."
    fi
    # output remote port IP address info
    local IPMI=`hwtool -q ipmi`
    if [ "x${IPMI}" = "xTrue" ]; then
        echo "Output of uh8l --open -d: "
        echo "`uh8l --open -d`"
        echo ""
    fi
}

# function to display boot log information
BOOT_LOG_FILE="/tmp/boot_log"
show_boot_log()
{
    if [ -f ${BOOT_LOG_FILE} ]; then
        cat ${BOOT_LOG_FILE}
    fi
}

# function to display the output of the CLI command "show hardware error-log all"
show_hardware_err_log()
{
    local ERR_LOG_CMD="show hardware error-log all"
    /sbin/pidof mgmtd > /dev/null 2>&1
    IS_MGMTD_RUNNING=$?
    if [ $IS_MGMTD_RUNNING -eq 0 ]; then
	echo "==================================================" >> "${HARDWARE_INFO_FILENAME}"
	echo "Output of 'show_hardware_err_log()':" >> "${HARDWARE_INFO_FILENAME}"
	echo "" >> "${HARDWARE_INFO_FILENAME}"
	echo "${ERR_LOG_CMD}" | /opt/tms/bin/cli --no-history >> "${HARDWARE_INFO_FILENAME}"
	echo "" >> "${HARDWARE_INFO_FILENAME}"
	echo "==================================================" >> "${HARDWARE_INFO_FILENAME}"
    fi
}

# function to display the bypass card state information
show_bypass_card_state()
{
    local FILENAME="${BYPASS_STATE_FILENAME}"

    if [ "${PRODUCT_ID}" != '"CMC"' ] && [ "${PRODUCT_ID}" != '"GW"' ]; then
        WAN_INTERFACES=`ls /sys/class/net | egrep "^wan"`
        for IFACE in $WAN_INTERFACES; do
            echo "==================================================" >> ${FILENAME}
            local CMD="/opt/hal/bin/hal get_if_status ${IFACE}"
            echo "Output of '${CMD}': `${CMD}`"  >> ${FILENAME}
            CMD="/opt/hal/bin/hal get_hw_if_status ${IFACE}" 
            echo "Output of '${CMD}': `${CMD}`"  >> ${FILENAME}
            CMD="/opt/hal/bin/hal get_if_wdt_status ${IFACE}" 
            echo "Output of '${CMD}': `${CMD}`"  >> ${FILENAME}
        done
    fi
}

show_smart_data_smartctl_xx50()
{
    local FILENAME="${SMART_INFO_FILENAME}"
    local CMD="$1"

    echo "" >> ${FILENAME}
    echo "==================================================" >> ${FILENAME}
    for line in `/opt/hal/bin/hwtool.py -q disk=map | cut -f 2,3 -d " "| sed -e s'/ /#/'`; do
        type=`echo $line | cut -f 1 -d "#" | sed s'/[0-9]\+//'`
        if [ "disk" = "${type}" ]; then
            partition=`echo $line | cut -f 2 -d "#"`
            if [ "missing" != "$partition" ]; then
                echo "${CMD} /dev/${partition}" >> ${FILENAME}
                $CMD "/dev/$partition" >> ${FILENAME}
            fi
        fi
        echo "" >> ${FILENAME}
    done
    echo "==================================================" >> ${FILENAME}
    echo ""
}

    

show_smart_data_smartctl()
{
    local FILENAME="${SMART_INFO_FILENAME}"
    local MDDBREQ="/opt/tms/bin/mddbreq -v"
    local SMARTCMD="/usr/sbin/smartctl -a "
    local ATA=" -d ata "
    local DB_FILE="/config/mfg/mfdb"
    local MOBO=`hwtool -q motherboard`
    case ${MOBO:0:9} in
        "400-00100"|"400-00300"|"425-00205"|"425-00140"|"400-00400"|"425-00135"|"425-00120")
            show_smart_data_smartctl_xx50 "${SMARTCMD}"
            ;;
        "400-00099"|"400-00098")
            show_smart_data_smartctl_xx50 "${SMARTCMD} ${ATA}"
            ;;
        *)
            if [ "${PRODUCT_ID}" = '"CMC"' ] || [ "${PRODUCT_ID}" = '"GW"' ]; then 
                # These are old 8000 and whatever the GW equivalent is 
                # The wont have the strings set in mfdb, so just hardcode sda
                # and set DUAL to false as its a single disk
                disk1="/dev/sda"
                DUAL="false"
            else
                DUAL=`${MDDBREQ} ${DB_FILE} query get - /rbt/mfd/store/dual`

                if [ "x${DUAL}" = "xfalse" ]; then
                    disk1=`${MDDBREQ} ${DB_FILE} query get - /rbt/mfd/store/dev`
                else
                    disk1=`${MDDBREQ} ${DB_FILE} query get - /rbt/mfd/store/mdraid1`
                    disk2=`${MDDBREQ} ${DB_FILE} query get - /rbt/mfd/store/mdraid2`
                fi
            fi

            echo "" >> ${FILENAME}
            echo "==================================================" >> ${FILENAME}
            if [ "x${DUAL}" = "xfalse" ]; then
                echo "Output of ${SMARTCMD} ${disk1:0:8} :"  >> ${FILENAME}
                echo "" >> ${FILENAME}
                echo "`${SMARTCMD} ${disk1:0:8} 2>&1`" >> ${FILENAME}
                echo "" >> ${FILENAME}
            else
                echo "Output of ${SMARTCMD} ${disk1:0:8} :"  >> ${FILENAME}
                echo "" >> ${FILENAME}
                echo "`${SMARTCMD} ${disk1:0:8} 2>&1`" >> ${FILENAME}
                echo "" >> ${FILENAME}
                echo "" >> ${FILENAME}
                echo "" >> ${FILENAME}
        	do_command_output_file "${SMARTCMD} ${disk2:0:8}" "${FILENAME}"
                echo "" >> ${FILENAME}
            fi
            echo "==================================================" >> ${FILENAME}
            echo ""
            ;;
    esac
}

show_smart_data_tw_cli()
{
    local FILENAME="${SMART_INFO_FILENAME}"
    local SMARTCMD="/usr/sbin/smartctl"
    NUMOFDISK=`${TW_CLI} /c0 show numdrives| head -n1 | cut -d'=' -f 2`

    echo "" >> ${FILENAME}
    echo "==================================================" >> ${FILENAME}
    echo "Output of ${TW_CLI} Num of disks ${NUMOFDISK} :"  >> ${FILENAME}
    for ((i=0;i<${NUMOFDISK};i+=1)); do
        echo "" >> ${FILENAME}
        do_command_output_file "${SMARTCMD} -a -d 3ware,$i /dev/twa0" ${FILENAME}
    done
    echo "==================================================" >> ${FILENAME}
    echo "" >> ${FILENAME}
}

show_proc_lc_files()
{
    for file in `ls /proc/lc`; do
		echo $file:
		cat /proc/lc/${file}
		echo ""
    done
}

# copy a file if it exists, preserving permissions
do_safe_cp()
{
    file="$1"
    dest="$2"
    if [ -e "$file" ]; then
        cp -p "$file" "$dest"
    fi
}

do_safe_cp_zip()
{
    file="$1"
    dest="$2"
    fname=`basename $1`
    if [ -e "$file" ]; then
	cp -p "$file" "$dest"
	gzip "$dest/$fname"
    fi
}

mkdir -p ${WORK_DIR}
mkdir -p ${STAGE_DIR}
touch ${SYSINFO_FILENAME}
chmod 644 ${SYSINFO_FILENAME}

if [ -f /opt/tms/release/build_version.sh ]; then
    . /opt/tms/release/build_version.sh
fi

# Define graft functions
if [ -f /etc/customer.sh ]; then
    . /etc/customer.sh
fi

echo "==================================================" >> ${SYSINFO_FILENAME}
echo "System information:" >> ${SYSINFO_FILENAME}
echo ""  >> ${SYSINFO_FILENAME}
echo "Hostname: "`uname -n` >> ${SYSINFO_FILENAME}

if [ "$HAVE_SYSDUMP_GRAFT_1" = "y" ]; then
    sysdump_graft_1
fi

echo "Version:  ${BUILD_PROD_VERSION}"  >> ${SYSINFO_FILENAME}
echo "Manufactured version: "`cat /bootmgr/mfg_version` >> ${SYSINFO_FILENAME}
echo "Date:     ${DATE_STR}" >> ${SYSINFO_FILENAME}
echo "Time Zone:   "`date +%Z` >> ${SYSINFO_FILENAME}

UPTIME_STRING=`cat /proc/uptime | awk '{fs=$1; d=int(fs/86400); fs=fs-d*86400; h=int(fs/3600); fs=fs-h*3600; m=int(fs/60); fs=fs-m*60; s=int(fs); fs=fs-s; print d "d " h "h " m "m " s "s\n"}'`

echo "Uptime:   ${UPTIME_STRING}" >> ${SYSINFO_FILENAME}
echo "" >> ${SYSINFO_FILENAME}

if [ "$HAVE_SYSDUMP_GRAFT_2" = "y" ]; then
    sysdump_graft_2
fi

do_command_output 'uname -a'
do_command_output 'uptime'
do_df_Pka_output
do_df_ha_output
do_command_output 'swapon -s'
do_command_output 'free'
do_command_output 'cat /proc/meminfo'
do_command_output 'cat /proc/cpuinfo'
do_command_output 'cat /proc/interrupts'
do_command_output 'lsmod'
do_command_output 'lspci'
do_command_output 'ifconfig -a'
do_command_output 'route -n'
do_command_output 'route -Cn'
do_command_output 'ntpq -pn'
do_command_output 'show_ecc_status'
do_command_output 'show_flex_specs'
do_command_output 'show_proc_lc_files'
do_command_output_file 'dmidecode' "${HARDWARE_INFO_FILENAME}"
do_command_output_file '/usr/bin/sensors' "${HARDWARE_INFO_FILENAME}"
do_command_output_file 'show_minnow_sensors' "${HARDWARE_INFO_FILENAME}"
do_command_output_file 'lspci -n -tv' "${HARDWARE_INFO_FILENAME}"
do_command_output_file 'lspci -n -v' "${HARDWARE_INFO_FILENAME}"
do_command_output_file '/opt/hal/bin/hwtool.py -q motherboard' "${HARDWARE_INFO_FILENAME}"
do_command_output_file '/opt/hal/bin/hwtool.py -q mactab' "${HARDWARE_INFO_FILENAME}"
do_command_output_file '/opt/hal/bin/hwtool.py -q cli' "${HARDWARE_INFO_FILENAME}"
USES_RRDM=`/opt/hal/bin/raid/rrdm_tool.py --supported`
if [ "x${USES_RRDM}" = "xTrue" ]; then
    do_command_output_file 'cat /proc/mdstat' "${HARDWARE_INFO_FILENAME}"
    do_command_output_file '/opt/hal/bin/hwtool.py -q disk=map' "${HARDWARE_INFO_FILENAME}"
    do_command_output_file '/opt/hal/bin/raid/rrdm_tool.py -d /disk' "${HARDWARE_INFO_FILENAME}"
    do_command_output_file '/opt/hal/bin/raid/rrdm_tool.py -d /raid' "${HARDWARE_INFO_FILENAME}"
    do_command_output_file '/opt/hal/bin/raid/rrdm_tool.py --get-led-status' "${HARDWARE_INFO_FILENAME}"
    do_command_output_file '/opt/hal/bin/raid/rrdm_tool.py --get-rebuild-rate' "${HARDWARE_INFO_FILENAME}"
    do_command_output_file '/opt/hal/bin/raid/rrdm_tool.py --get-physical' "${HARDWARE_INFO_FILENAME}"
    do_command_output_file '/opt/hal/bin/raid/rrdm_tool.py --raid-info' "${HARDWARE_INFO_FILENAME}"
    do_command_output_file '/opt/hal/bin/raid/rrdm_tool.py --get-raid-configuration' "${HARDWARE_INFO_FILENAME}"
    get_scsi_state "${HARDWARE_INFO_FILENAME}"
fi

do_command_output 'show_firmware_version'
do_command_output 'show_branding_information'
do_command_output 'show_spare_information'
do_command_output 'show_wear_information'
do_command_output 'read_eeprom_serial'
do_command_output_file 'show_ipmi_info' "${HARDWARE_INFO_FILENAME}"
do_command_output_file 'save_bios_nvram' "${HARDWARE_INFO_FILENAME}"
do_command_output_file 'cat /proc/scsi/scsi' "${HARDWARE_INFO_FILENAME}"
do_command_output 'show_bypass_card_state'
do_command_output 'ls -al /data'
do_command_output_file 'show_usb_flash_info' "${HARDWARE_INFO_FILENAME}"
do_command_output_file 'show_unscheduled_reboots' "${HARDWARE_INFO_FILENAME}"
do_command_output_file '/sbin/count_ce_errors.py -l' "${HARDWARE_INFO_FILENAME}"
do_command_output 'show_hardware_err_log'
do_command_output 'show_boot_log'

RAID_TYPE=`/opt/hal/bin/hal raid_card_vendor`
if [ "x${RAID_TYPE}" = "xNone" -o "x${RAID_TYPE}" = "x" ]; then
    show_smart_data_smartctl
fi

if [ "x${RAID_TYPE}" = "x3ware" ]; then
    show_smart_data_tw_cli
    do_command_output "/opt/hal/bin/hal get_raid_status"
    do_command_output_file "${TW_CLI} /c0/u0 show all" "${RAID_INFO_FILENAME}"
    do_command_output_file "${TW_CLI} /c0 show alarms" "${RAID_INFO_FILENAME}"
    do_command_output_file "${TW_CLI} /c0 show all" "$RAID_INFO_FILENAME"
    NUMOFDISK=`${TW_CLI} /c0 show numdrives| head -n1 | cut -d'=' -f 2`
    for disk in `seq 1 $NUMOFDISK`; do
        DISKNUM=$[ $disk - 1 ];
        do_command_output_file "${TW_CLI} /c0/p${DISKNUM} show all" "$RAID_INFO_FILENAME"
    done

    do_command_output_file "${TW_CLI} /c0 show diag" "${RAID_INFO_FILENAME}"
fi

if [ -d /proc/megaraid ]; then
    megarc -pdFailInfo -ch0 -a0 -idAll >> "${RAID_INFO_FILENAME}" 2>&1
    do_command_output "/opt/hal/bin/hal get_raid_status"
    do_command_output_file "cat /proc/megaraid/hba0/config" "${RAID_INFO_FILENAME}"
    do_command_output_file "cat /proc/megaraid/hba0/diskdrives-ch0" "${RAID_INFO_FILENAME}"
fi

# in-path route info
# XXX/jshilkaitis: move this to SH/IB customer.sh?
ROUTES=`ip rule show | grep proxytable | grep -v fwmark | awk '{print $5}'`
for ROUTE in ${ROUTES}; do
    do_command_output "ip route show table ${ROUTE}"
done

# Specifying individual table IDs instead of 'all' for clarity
do_command_output "ip -6 route show table local"
do_command_output "ip -6 route show table main"
do_command_output "ip -6 route show table default"

#Use ss instead of netstat for getting socket data
do_command_output 'ss -s'
do_command_output 'ss -meanoiA inet,unix'
do_command_output 'arp -na'

do_command_output "ip -6 neigh show"

do_command_output 'ps -ALww -o user,pid,ppid,tid,pcpu,psr,pri,nice,vsize,rss,majflt,tty,stat,wchan=WIDE-WCHAN-COLUMN -o start,bsdtime,command'
# List failure snapshots
do_command_output 'who -a'
# List miscellaneous files
do_command_output 'find /var/opt ( -name .running -prune ) -o -type f -ls -mount'
# List decrypted secure vault files skipped by above command
# (due to -mount option); see bug 81450
do_command_output 'find /var/opt/rbt/decrypted -type f -ls'
# List log files
do_command_output 'find /var/log -type f -ls'
# List config files
do_command_output 'find /config -type f -ls'
do_command_output "tail -${NUM_LOG_LINES} /var/log/messages"

# Add iptables output
do_command_output 'iptables-save'

if [ "$HAVE_SYSDUMP_GRAFT_3" = "y" ]; then
    sysdump_graft_3
fi

# XXX possible additions
# include dump of mgmtd monitoring tree

echo "Done." >> ${SYSINFO_FILENAME}

# Copy all the files we want into the stage
if [ ${BRIEF} -eq 0 -o ${FORCE_DB} -eq 1 ]; then
    cp -a /config ${STAGE_DIR}
    rm -rf ${STAGE_DIR}/config/lost+found
    rm -rf ${STAGE_DIR}/config/ssh
    # Copy all files under /var/samba if /config/samba does not exist
    if [ ! -d /config/samba -a -d /var/samba ]; then
        cp -a /var/samba ${STAGE_DIR}
        SAMBA_TDB_FILENAME=${STAGE_DIR}/samba/private/secrets.tdb
    fi
    if [ -f ${SAMBA_TDB_FILENAME} ]; then
    	/usr/local/samba/bin/tdbdump ${SAMBA_TDB_FILENAME} | grep MACHINE_PASSWORD | awk '{print $3}' | xargs -i{} /usr/local/samba/bin/tdbtool ${SAMBA_TDB_FILENAME} delete {}    	
    fi
    if [ -f ${SAMBA_TDB_FILENAME}.bak ]; then
    	/usr/local/samba/bin/tdbdump ${SAMBA_TDB_FILENAME}.bak | grep MACHINE_PASSWORD | awk '{print $3}' | xargs -i{} /usr/local/samba/bin/tdbtool ${SAMBA_TDB_FILENAME}.bak delete {}    	
    fi
fi

cp -p /config/db/`cat /config/db/active` ${STAGE_DIR}/active.db
cp -p /config/local/db ${STAGE_DIR}/local.db
cp -p /config/local/statedb ${STAGE_DIR}/state.db
for DBNAME in "active" "local" "state"; do
    /opt/tms/bin/mddbreq ${STAGE_DIR}/${DBNAME}.db query iterate subtree / > ${STAGE_DIR}/${DBNAME}.txt
    /opt/tms/bin/mddbreq -b ${STAGE_DIR}/${DBNAME}.db query iterate subtree / > ${STAGE_DIR}/${DBNAME}-brief.txt
done

cp -p /config/mfg/mfdb ${STAGE_DIR}/mfdb
/opt/tms/bin/mddbreq ${STAGE_DIR}/mfdb query iterate subtree / > ${STAGE_DIR}/mfdb.txt
lsof -b -n 2>&- > ${STAGE_DIR}/lsof.txt

if [ -f /opt/rbt/etc/built-modules-revisions ]; then
    cp /opt/rbt/etc/built-modules-revisions ${STAGE_DIR}/built-modules-revisions
fi

#only do this for particular models:
LTLMODEL=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/model`
case ${LTLMODEL} in
    "3000"|"3010"|"3020"|"3510"|"3520"|"5000"|"5010"|"5520"|"6020")
	linttylog /F raid.log 2>&1 > /dev/null
	mv raid.log ${STAGE_DIR}/raidtty.log
	;;
esac 

# Copy up to 10 raidcheck files into the sysdump
files=`ls -1t /var/opt/tms/snapshots/raidcheck-* 2>/dev/null | head -10`
for i in $files; do
    cp -p $i ${STAGE_DIR}/
done

# Copy the SCSI Record I/O files.
mkdir ${STAGE_DIR}/record_io
for i in `ls -1d /sys/block/{sd*,hd*} 2>/dev/null`; do
    dev=`echo $i | sed -e 's/\//\n/g' | tail -1`
    for j in `ls -1 /sys/block/$dev/device/record_io_* 2>/dev/null`; do
        file=`echo $j | sed -e 's/\//\n/g' | tail -1`
        cp $j ${STAGE_DIR}/record_io/$file-$dev
        # echo cp $j ${STAGE_DIR}/$file-$dev
    done
done

if [ ${BRIEF} -eq 0 ]; then
    MAX_KBYTES=50000
    MIN_LINES=160000 #16MB(default log size)/100(character per line)
else
    MAX_KBYTES=300
    MIN_LINES=1000
fi

# Yes, these numbers are conservative, but we don't want to risk a giant mail
avg_bytes_per_line=100
avg_compression_ratio=10
total_size=0

# Use the SYSDUMP_GRAFT4 as an additional list of files to process. Products
# can also define new files under /var/log to be provided in the sysdump.
# graft4 is added to the find command, since we didn't want to sort twice.
graft4=''
if [ "$HAVE_SYSDUMP_GRAFT_4" = "y" ]; then
    sysdump_graft_4
fi

LOGS_LIST=`find /var/log -name messages\* -print -o -name user_messages\* -print -o -name web_access_log\* -print -o -name web_error_log\* -print ${graft4} 2> ${STAGE_DIR}/findlogs.stderr | sort -n -t . -k 2`
for vlm in ${LOGS_LIST}; do
    curr_size=`du -ks $vlm | awk '{print $1}'`

    # See if it is compressed on disk already
    if [ `echo $vlm | sed s/.gz$//` != "${vlm}" ]; then
        compressed=1
    else
        compressed=0
    fi

    # Estimate compressed size
    if [ ${compressed} -eq 0 ]; then
        est_size=`expr ${curr_size} / ${avg_compression_ratio}`
    else
        est_size=${curr_size}
    fi
    # Always add at least 10k so rounding error doesn't kill us
    if [ ${est_size} -lt 10 ]; then
        est_size=10
    fi

    new_total=`expr ${total_size} + ${est_size}`
    if [ ${UNLIMITED_LOGS} -eq 1 ]; then
        # XXX/jshilkaitis: lame hack to defeat log size limit check
        new_total=0
    fi

    if [ ${new_total} -gt ${MAX_KBYTES} ]; then

        # We never uncompress a file because doing so could uncompress a
        # multi-gigabyte log just to tail a few kilobytes.
        if [ ${compressed} -eq 1 ]; then
            break
        fi

        # If it's an uncompressed file, take some trailing lines
        space_left=`expr ${MAX_KBYTES} - ${total_size}`
        lines_left=`expr ${space_left} \* 1024 \* ${avg_compression_ratio} / ${avg_bytes_per_line}`

        if [ ${lines_left} -lt ${MIN_LINES} ]; then
            lines_left=${MIN_LINES}
        fi
        tail -${lines_left} ${vlm} > ${STAGE_DIR}/`basename ${vlm}`

    else
        cp -p ${vlm} ${STAGE_DIR}
    fi

    total_size=${new_total}
done

# Copy /var/lib/logrotate.status
cp -p /var/lib/logrotate.status ${STAGE_DIR}

# show hardware info
do_command_output "hwtool -q system"

# interface info 
IF_LIST=`ls /sys/class/net | egrep -v 'inpath|in-path'`
for IF_NAME in ${IF_LIST}; do
    do_command_output "ethtool ${IF_NAME}"
    do_command_output "ethtool -a ${IF_NAME}"
    do_command_output "ethtool -i ${IF_NAME}"
    ethtool -d ${IF_NAME} > "${STAGE_DIR}/if-${IF_NAME}.regs"
    # we don't want any other info other than the raw info in the file
    if [ "true" != "$(hwtool -q motherboard_is_vm | awk '{ print $1}')" ]; then
        ethtool -e ${IF_NAME} raw on > "${STAGE_DIR}/if-${IF_NAME}.eeprom"
    fi
    do_command_output "ethtool -S ${IF_NAME}"
    do_command_output "ethtool -g ${IF_NAME}"
    do_command_output "ethtool -k ${IF_NAME}"
done

#10G interface information
RDI_MOD=`lsmod | grep rdi`
if [ $? -eq 0 ]; then
    #Count the number of 10G cards on the machine
    NUM=`ls /proc/net/rdi | wc -l`
    for i in `ls /proc/net/rdi`
    do
	do_command_output_file "cat /proc/net/rdi/$i" "$HARDWARE_RULES_FILENAME"
    done

    while [ $NUM -ne 0 ]
    do
        NUM=`expr $NUM - 1`
        do_command_output_file "rdictl dev $NUM get_cfg" "$HARDWARE_RULES_FILENAME"
        do_command_output_file "rdictl dev $NUM query_list" "$HARDWARE_RULES_FILENAME"
        for i in `rdictl dev $NUM query_list`
	do
		do_command_output_file "rdictl dev $NUM query $i" "$HARDWARE_RULES_FILENAME"
	done
    done
fi

# Xbridge information
XBRIDGE_XUTIL=/opt/rbt/bin/xutil

if [ -f ${XBRIDGE_XUTIL} ]; then
    lsmod | grep ixgbe_ddp > /dev/null 2>&1
    XBRIDGE_ENABLED=$?

    if [ ${XBRIDGE_ENABLED} -eq 0 ]; then
        /sbin/pidof xbridge > /dev/null 2>&1
        XBRIDGE_RUNNING=$?

        if [ $XBRIDGE_RUNNING -eq 0 ]; then
            do_command_output_file "${XBRIDGE_XUTIL}" "${STAGE_DIR}/xbridge_status"
            do_command_output_file "${XBRIDGE_XUTIL} --print-counters" "${STAGE_DIR}/xbridge_counters"
            do_command_output_file "${XBRIDGE_XUTIL} --print-inpath-route-cache" "${STAGE_DIR}/xbridge_inpath_route_cache"
        fi

        do_command_output_file "${XBRIDGE_XUTIL} --print-nat-status" "${STAGE_DIR}/xbridge_nat_status"
        ${XBRIDGE_XUTIL} --print-nat-status > /dev/null 2>&1
        XBRIDGE_NAT_EXISTS=$?
        if [ ${XBRIDGE_NAT_EXISTS} -eq 0 ]; then
            do_command_output_file "${XBRIDGE_XUTIL} --print-nat-table" "${STAGE_DIR}/xbridge_nat_table"
        fi

        do_command_output_file "${XBRIDGE_XUTIL} --print-route-status" "${STAGE_DIR}/xbridge_global_route_status"
        ${XBRIDGE_XUTIL} --print-route-status > /dev/null 2>&1
        XBRIDGE_ROUTE_CACHE_EXISTS=$?
        if [ ${XBRIDGE_ROUTE_CACHE_EXISTS} -eq 0 ]; then
            do_command_output_file "${XBRIDGE_XUTIL} --print-global-route-cache" "${STAGE_DIR}/xbridge_global_route_cache"
        fi
    fi
fi

if [ ${BRIEF} -eq 0 ]; then
    do_safe_cp_zip /proc/net/tcp ${STAGE_DIR}/kernel/proc/net/
    do_safe_cp_zip /proc/net/tcp6 ${STAGE_DIR}/kernel/proc/net/
fi

if [ -d /var/log/sensors ]; then
    mkdir ${SENSORS_DIR}
    cp -p /var/log/sensors/* ${SENSORS_DIR}
fi

dmesg > ${STAGE_DIR}/dmesg
if [ -f /var/log/dmesg ]; then
    cp /var/log/dmesg ${STAGE_DIR}/dmesg-boot
fi

cp -p ${SYSINFO_FILENAME} ${STAGE_DIR}/sysinfo.txt

# This directory contains private information, which we delete next.
#
# If the exclusion list gets longer in the future, it may be better to use
# 'find' to just copy the files, instead of the current copy-then-remove
# approach.
cp -a /etc/opt/tms/output/ ${STAGE_DIR}
rm -f ${STAGE_DIR}/output/passwd* ${STAGE_DIR}/output/shadow*
rm -f ${STAGE_DIR}/output/pam*

# This is for bug 1199.  It is sufficient for now because there is no
# facility for creating additional local user accounts.  If there
# were, we'd need something fancier to find all of the history files.
# Note that no errors are printed or logged if some of the files we
# try to copy do not exist.
for u in root admin monitor; do
    do_safe_cp /var/home/$u/.cli_history ${STAGE_DIR}/cli_history_$u
done

# copy manufacturing data over if it exists
cp -a /bootmgr ${STAGE_DIR}
if [ -d /config/mfg ]; then
    cp -a /config/mfg/* ${STAGE_DIR}
fi
if [ -f /var/opt/tms/image_history ]; then
    cp /var/opt/tms/image_history ${STAGE_DIR}
fi

if [ $STATS -ne 0 ] ; then
    tar -C /var/opt/tms -czf ${STAGE_DIR}/stats.tgz --mode='a+rX' stats
fi

# Copy output of 'show running' into the sysdump
if [ $NO_REVMAP -eq 0 ]; then
    /sbin/pidof mgmtd > /dev/null 2>&1
    MGMTD_RUNNING=$?
    if [ $MGMTD_RUNNING -eq 0 ]; then
        /usr/bin/printf "enable\nshow running\n" | /opt/tms/bin/cli --no-history > ${STAGE_DIR}/active-running.txt 2>&1
        /usr/bin/printf "enable\nshow running-config full\n" | /opt/tms/bin/cli --no-history > ${STAGE_DIR}/active-running-full.txt 2>&1
        # Output /alarm/state/alarm into the sysdump
        /opt/tms/bin/mdreq -b query iterate subtree /alarm/state/alarm >  ${STAGE_DIR}/alarm-brief.txt 2>&1

        # Copy any product-specific items depending on mgmtd running to the
        # sysdump
        if [ "$HAVE_SYSDUMP_GRAFT_6" = "y" ]; then
            sysdump_graft_6
        fi
    fi
fi

#
# Copy over SSL servers, if we can...
#
if [ "$HAVE_SYSDUMP_GRAFT_5" = "y" ]; then
    sysdump_graft_5
fi

#
# Copy over http_prepop log files, 
# if we can...
#
if [ "$HAVE_SYSDUMP_GRAFT_7" = "y" ]; then
    sysdump_graft_7
fi

# Copy any specified extra files
for ef in ${EXTRA_FILES}; do
    cp -p $ef ${STAGE_DIR}
done

# BOB specific graft.
if [ "$HAVE_BOB_SYSDUMP_GRAFT" = "y" ]; then
    bob_sysdump_graft_1 ${STAGE_DIR}
fi

# Tar and gzip up the stage, then remove it

tar -C ${WORK_DIR} -czSf ${DUMP_FILENAME} --mode='a+rX' ${STAGE_DIR_REL}

md5sum ${DUMP_FILENAME} | awk '{ print $1 }' > ${MD5_FILENAME}

mv ${DUMP_FILENAME} ${FINAL_DIR}

mv ${MD5_FILENAME} ${FINAL_MD5_DIR}

rm -rf ${WORK_DIR} 

# Print the names of the files we generated
echo "SYSINFO=`echo ${SYSINFO_FILENAME}`"
echo "SYSDUMP=`echo ${DUMP_FILENAME} | sed s,${WORK_DIR},${FINAL_DIR},`"

exit 0
