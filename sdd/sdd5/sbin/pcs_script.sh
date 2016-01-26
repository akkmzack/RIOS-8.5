#!/bin/sh

#  URL:       $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/pcs_script.sh $
#  Revision:  $Revision: 102320 $
#  Date:      $Date: 2013-01-23 11:48:49 -0800 (Wed, 23 Jan 2013) $
#  Author:    $Author: cliu $
#
#  (C) Copyright 2003-2012 Riverbed Technology, Inc.

PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/tms/bin:/opt/rbt/bin
export PATH

PCS_SCRIPT_OPTIONS='w:d:f:'
WORKING_DIR=
TARGET_DIR=
OUTPUT_FILE=

usage()
{
    echo "usage: $0 [-$PCS_SCRIPT_OPTIONS]"
    echo "-w    working dir"
    echo "-d    dir to package by tar"
    echo "-f    zipped tar output file name"
    echo
    exit 1

}

PARSE=`/usr/bin/getopt $PCS_SCRIPT_OPTIONS "$@"`

if [ $? != 0 ] ; then
    usage
fi

eval set -- "$PARSE"

while true ; do
    case "$1" in
        --) shift ; break ;;
        -w) WORKING_DIR=$2 ; shift 2 ;;
        -d) TARGET_DIR=$2 ; shift 2;;
        -f) OUTPUT_FILE=$2 ; shift 2;;
        *) echo "pcs_script.sh: parse failure" >&2 ; usage ;;
    esac
done

if [ -z "${WORKING_DIR}" -o -z "${TARGET_DIR}" -o -z "${OUTPUT_FILE}" ]; then
    usage
fi

# syslog tag
LOG_TAG=`basename $0 .sh`
# Make sure working dir exists
if [ ! -d ${WORKING_DIR} ]; then
    logger -i -t ${LOG_TAG} -p user.err "Working directory does not exist"
    exit 1
fi

# Make sure target directory to be packaged exists
ABS_TARGET_DIR=${WORKING_DIR}/${TARGET_DIR}
if [ ! -d ${ABS_TARGET_DIR} ]; then
    logger -i -t ${LOG_TAG} -p user.err "Target directory does not exist"
    exit 1
fi

# Make sure the parent directory of output file exists
P_OUTPUT_FILE=`dirname ${OUTPUT_FILE}`
if [ ! -d ${P_OUTPUT_FILE} ]; then
    logger -i -t ${LOG_TAG} -p user.err "Output file path does not exist"
    exit 1
fi

# Use AHA card when it's present, otherwise use gzip with fatest compression method(-1)
if [ -e /dev/sdrcard ]; then
    ZIP_UTIL="/opt/rbt/bin/ahazip"
else
    ZIP_UTIL="/bin/gzip -1"
fi

tar -C ${WORKING_DIR} -cS ${TARGET_DIR} --mode="a+rX" | ${ZIP_UTIL} > ${OUTPUT_FILE}

exit 0
