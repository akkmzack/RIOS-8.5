#!/bin/sh

############################################################
# This file is used to collect ESXi host logs generated
# during shutdown/start period, and merge with normal host
# logs saved on RiOS
############################################################
HOST_PRIMARY_MAC=`/sbin/vmware-rpctool 'info-get guestinfo.hostprimarymac'`
STRIPPED_MAC=`echo ${HOST_PRIMARY_MAC} | sed -e 's/://g'`

HOST_SAVED_LOG_DIR=/esxi/vmfs/volumes/RVMFS1_${STRIPPED_MAC}/BOB
ERR_FILE_NOT_MOUNTED=1

# Copy logs from ESXi host to RiOS /var/tmp directory
if [ ! -d ${HOST_SAVED_LOG_DIR} ]; then
    exit ${ERR_FILE_NOT_MOUNTED}
fi

CURR_TIME=`date '+%Y-%m-%d-%H-%M-%S'`

LOG_TMP_DIR=/var/tmp/${CURR_TIME}
mkdir ${LOG_TMP_DIR}

# Test if temp_messages exists
if [ ! -f ${HOST_SAVED_LOG_DIR}/temp_messages ]; then
    exit 0
fi

# There should be only one temp_messages file ideally.
# But, search all temp_messages* in case log file has been force rotated
cp ${HOST_SAVED_LOG_DIR}/temp_messages* ${LOG_TMP_DIR}

FILE_NUM=`ls -l ${LOG_TMP_DIR} | grep ^\- | wc -l`

# Merge log file(s) into one file
TEMP_FILE=${LOG_TMP_DIR}/all_messages

echo "==========Shutdown and Restart Log/Begin==========" >> ${TEMP_FILE}

for ((i=(($FILE_NUM - 2)); i>=0; i--)); do
    gzip -dc ${LOG_TMP_DIR}/temp_messages.${i} >> ${TEMP_FILE}
done

cat ${LOG_TMP_DIR}/temp_messages >> ${TEMP_FILE}

echo "==========Shutdown and Restart Log/End==========" >> ${TEMP_FILE}

# Dump the shutdown/start log into /var/log/host_message
cat ${TEMP_FILE} >> /var/log/host_messages

# Remove copies left at /var/tmp directory
rm -rf ${LOG_TMP_DIR}

# Remove original copies on ESXi host
rm -f ${HOST_SAVED_LOG_DIR}/temp_messages*
