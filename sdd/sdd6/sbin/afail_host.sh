#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision$
#  Date:      $Date$
#  Author:    $Author: abutala $
#
#  (C) Copyright 2002-2010 Riverbed Technology, Inc.
#  All rights reserved.
#

PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/tms/bin
export PATH

PROCESS_NAME=
HOST_NAME="host"
CORE_PATH="/esxi/var/core/"
FIRST_BOOT=0

HOST_PRIMARY_MAC=`/sbin/vmware-rpctool 'info-get guestinfo.hostprimarymac'`
STRIPPED_MAC=`echo ${HOST_PRIMARY_MAC} | sed -e 's/://g'`

VMX_CORE_PATH="/esxi/vmfs/volumes/RVMFS1_${STRIPPED_MAC}/BOB/"
VMX_CORE_PATTERN="vmx-zdump*"
LAUNCH_ESXI_SSH="/opt/tms/bin/launch_esxi_ssh.py"
SNAPSHOT_DIR="/var/opt/tms/snapshots"
NO_VM_OR_ESX_CRASH=127

usage()
{
    echo "usage: $0 -n process_name [-c core_path] [-p host_name] [-f]"
    echo ""
    exit 1
}


while getopts n:c:p:fh OPTION
do
    case ${OPTION} in
        h) usage;;
        n) PROCESS_NAME=$OPTARG;;
        c) CORE_PATH=$OPTARG;;
        p) HOST_NAME=$OPTARG;;
        f) FIRST_BOOT=1;;
        ?) usage;;
    esac
done

if [ x${PROCESS_NAME} == x -a ${FIRST_BOOT} -eq 0 ]; then
    usage
else
    TEMP_PROCESS_NAME=${PROCESS_NAME##*/}
    PROCESS_NAME=${TEMP_PROCESS_NAME}
fi

CURR_TIME=`date '+%Y%m%d-%H%M%S'`
if [ $FIRST_BOOT -eq 1 ]; then
    DIR_NAME="${HOST_NAME}-system-${CURR_TIME}"
else
    DIR_NAME="${HOST_NAME}-${PROCESS_NAME}-${CURR_TIME}"
fi

STAGING_TMP=/var/opt/tms/snapshots/.staging
STAGING_AREA=${STAGING_TMP}/${DIR_NAME}/
if [ -d ${STAGING_AREA} ]; then
    rm -rf ${STAGING_AREA}
fi
mkdir ${STAGING_AREA}

if [ $FIRST_BOOT -eq 1 ]; then
    # First boot, try to check if there is any vmx core file and vmkernel dump
    num_vmx_core=`find ${VMX_CORE_PATH} -name "${VMX_CORE_PATTERN}" | wc -l`

    if [ ${num_vmx_core} -gt 0 ]; then
        mv ${VMX_CORE_PATH}/${VMX_CORE_PATTERN} ${STAGING_AREA}
    fi

    # Extract new vmkernel dump core
    vmk_dumppart=`${LAUNCH_ESXI_SSH} esxcfg-dumppart -l | awk ' /vmfs/ {printf("%s ",$2)} '`
    vmk_core_name="/tmp/vmkernel-zdump"
    ${LAUNCH_ESXI_SSH} esxcfg-dumppart -C -D ${vmk_dumppart} -z ${vmk_core_name} -n

    num_vmk_core=`find /esxi/tmp -name "vmkernel-zdump*" | wc -l`

    if [ ${num_vmk_core} -gt 0 ]; then
        mv /esxi/${vmk_core_name}* ${STAGING_AREA}
    fi

    # Reboot not because of vmx or vmkernel crash
    if [ ${num_vmk_core} -eq 0 -a ${num_vmx_core} -eq 0 ]; then
        rm -rf ${STAGING_AREA}
        exit ${NO_VM_OR_ESX_CRASH}
    fi
else
    # Find the core file at specified location
    num_core=`find ${CORE_PATH} -name "${PROCESS_NAME}*" | wc -l`

    # Copy the core file to stage folder
    if [ $num_core -gt 0 ]; then
        mv ${CORE_PATH}/${PROCESS_NAME}* ${STAGING_AREA}
    fi
fi

# Generate sysdump and copy to stage folder
FAILURE=0
OPS=`/sbin/sysdump.sh -p` || FAILURE=1
if [ ${FAILURE} -eq 1 ]; then
    logger -p user.err "Could not generate system dump for host process ${PROCESS_NAME}"
    exit 1
fi
# Set SYSINFO and SYSDUMP
eval ${OPS}

SNAPSHOT_NAME=${DIR_NAME}.tar.gz
if [ ! -d ${STAGING_AREA} ]; then
    logger -p user.err "Staging directory not found. Recreate"
    mkdir ${STAGING_AREA}
    if [ -f ${SNAPSHOT_DIR}/${SNAPSHOT_NAME} ]; then
        mv ${SNAPSHOT_DIR}/${SNAPSHOT_NAME} ${STAGING_AREA}
        cd ${STAGING_AREA} && tar -zxf ${SNAPSHOT_NAME} && rm -f ${SNAPSHOT_NAME}
    fi
fi

cp ${SYSINFO} ${STAGING_AREA}
cp ${SYSDUMP} ${STAGING_AREA}

# Generate the snapshot package and move to snapshot folder
cd ${STAGING_TMP} && tar -czf ${SNAPSHOT_NAME} ${DIR_NAME}/
mv ${STAGING_TMP}/${SNAPSHOT_NAME} ${SNAPSHOT_DIR}
rm -rf ${STAGING_AREA}

MD5_FILENAME=${DIR_NAME}.md5
md5sum ${SNAPSHOT_DIR}/${SNAPSHOT_NAME} | awk '{ print $1 }' > ${SNAPSHOT_DIR}/md5/${MD5_FILENAME}

exit 0
