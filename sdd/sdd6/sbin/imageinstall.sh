#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 81039 $
#  Date:      $Date: 2011-04-28 14:37:23 -0700 (Thu, 28 Apr 2011) $
#  Author:    $Author: munirb $
# 
#  (C) Copyright 2002-2010 Riverbed Technology Inc.  
#  All rights reserved.
#

# This script is used for BOB based appliances. This is an intermediate script
# between mgmtd and writeimage.sh, it will untar the BOB image, get the 
# esxi image out of it, do the signing checks, install ESXi image
# onto the host and finally call writeimage with the correct image file

PATH=/mfg:/usr/bin:/bin:/usr/sbin:/sbin
export PATH

# Constants
VAR_IMAGES_DIR="/var/opt/tms/images"
VAR_BOB_IMAGES_DIR="${VAR_IMAGES_DIR}/.tmp"

# Defaults
DO_MANUFACTURE=-1
SYSIMAGE_USE_URL=-1
SYSIMAGE_FILE=
SYSIMAGE_URL=
INSTALL_IMAGE_ID=-1
IMAGE_LAYOUT=
PTOOL=sfdisk
LAST_PART=
MODEL=0
WRITEIMAGE_STRING="/sbin/writeimage.sh"
ESXI_IMG="esxi_upgrade_image.tgz"
ESXI_FILES="a.z b.z boot.cfg c.z cimstg.tgz k.z license.tgz m.z oem.tgz pkgdb.tgz s.z tboot.gz"
ESXI_MOUNT="/esxi"
TAR="/bin/tar"
CAT="/bin/cat"
GREP="/bin/grep"
AWK="/bin/awk"
MKDIR="/bin/mkdir"
RM="/bin/rm"
CP="/bin/cp"


clean_up_bob_dir()
{
    ${RM} -rf ${VAR_BOB_IMAGES_DIR}
}

make_bob_dir()
{
    ${MKDIR} -p ${VAR_BOB_IMAGES_DIR}
}

check_md5_sum()
{
    FILE=$1
    SUM=$2
    MDSUM="`/usr/bin/md5sum ${FILE} | ${AWK} '{print $1}'`"

    if [ "x${MDSUM}" != "x${SUM}" ]; then
        echo "MD5sum check failed for ${FILE}"
        return 1
    fi

    echo "File ${FILE} passed the md5sum check"
    return 0
}

copy_files()
{
    for file in ${ESXI_FILES}; do
        ${CP} ${VAR_BOB_IMAGES_DIR}/esxi/${file} /esxi/altbootbank
        if [ $? -ne 0 ]; then
            return 1
        fi
    done

    return 0
}


copy_esxi_image()
{
    # Check the md5sum of the esxi image before ftp'ing it over
    SUM=`${CAT} ${VAR_BOB_IMAGES_DIR}/md5sums | ${GREP} esxi_upgrade_image | ${AWK} '{print $1}'`

    check_md5_sum ${VAR_BOB_IMAGES_DIR}/${ESXI_IMG} ${SUM}
    if [ $? -ne 0 ]; then
        echo "ESXi image did not pass the md5sum check"
        exit 17 #lc_err_upgrade_image_integrity_failure
    fi

    # Make a ESXI directory in the tmp directory to untar esxi files
    ${MKDIR} -p ${VAR_BOB_IMAGES_DIR}/esxi

    # Untar the esxi image
    FAILURE=0
    ${TAR} zxf ${VAR_BOB_IMAGES_DIR}/${ESXI_IMG} -C ${VAR_BOB_IMAGES_DIR}/esxi 2>&1 || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        exit 17 #lc_err_upgrade_image_integrity_failure
    fi

    copy_files
    if [ $? -ne 0 ]; then
        echo "Could not copy ESXi files to host"
        exit 17 #lc_err_upgrade_image_integrity_failure
    fi
}


usage()
{
    echo "usage: $0 -m [-M MODEL] [-u URL] [-f FILE] [-L LAYOUT_TYPE] -d /DEV/N1"
    echo "             [-p PARTNAME -s SIZE] [-t] [-k KERNEL_TYPE] "
    echo "usage: $0 -i [-M MODEL] [-u URL] [-f FILE] [-d /DEV/N1] -l {1,2} [-t] [-k KERNEL_TYPE] "

    echo ""
    echo "Either '-u' (url) or '-f' (file) must be specified."
    exit 1
}


while true ; do
    case "$1" in
        -m) DO_MANUFACTURE=1; shift
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -m"
            ;;
        -i) DO_MANUFACTURE=0; shift 
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -i"
            ;;
        -u) SYSIMAGE_USE_URL=1; SYSIMAGE_URL=$2; shift 2 
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -u ${SYSIMAGE_URL}"
            ;;
        -f) SYSIMAGE_USE_URL=0; SYSIMAGE_FILE=$2; shift 2
            # Do not set the image file for writeimage here
            # we will do it after extracting it from the BOB image
            ;;
        -k) IL_KERNEL_TYPE=$2; shift 2 
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -k"
            ;;
        -M) MODEL=$2 shift 2
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -M ${MODEL}"
            ;;
        -d)
            new_disk=$2; shift 2
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -d ${new_disk}"
            ;;
        -l) INSTALL_IMAGE_ID=$2; shift 2
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -l ${INSTALL_IMAGE_ID}"
            ;;
        -p) LAST_PART=$2; shift 2
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -p ${LAST_PART}"
            ;;
        -P) PTOOL=$2; shift 2
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -P ${PTOOL}"
            ;;
        -s)
            LAST_PART_SIZE=$2; shift 2
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -s ${LAST_PART_SIZE}"
            ;;
        -L) IMAGE_LAYOUT=$2; shift 2
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -L ${IMAGE_LAYOUT}"
            ;;
        -r) shift
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -r"
            ;;
        -t) shift
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -t"
            ;;
        -V) shift
            WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -V"
            ;;
        -h) shift
            usage
            ;;
        *) shift ; break ;;
    esac
done

if [ ! -z "$*" ] ; then
    usage
fi

# The only options this file needs to worry about are
# "-i","-f" image_path, "-d" dev_name, "-l" location all other options are
# just passed along to writeimage as is.
# Note that this script will NOT be called at manufacturing time.

# The "-f" image path will be changed for writeimage as the BOB image has extra
# esxi bits as well as the signature file, writeimage doesn't care about it

# Clean out the BOB directory
clean_up_bob_dir

# Make the temp BOB dir
make_bob_dir

# Untar the image file in the BOB dir
FAILURE=0
${TAR} -x -f ${SYSIMAGE_FILE} -C ${VAR_BOB_IMAGES_DIR} 2>&1 || FAILURE=1
if [ ${FAILURE} -eq 1 ]; then
    echo "*** Could not extract image from ${SYSIMAGE_FILE}"
    clean_up_bob_dir
    exit 17 #lc_err_upgrade_image_integrity_failure
fi

# Copy the esxi files to the host
copy_esxi_image
if [ $? -ne 0 ]; then
    echo "*** Could not copy esxi image"
    clean_up_bob_dir
    exit 17 #lc_err_upgrade_image_integrity_failure
fi

echo "ESXi Image upgrade complete"

# Change the writeimage SYSIMAGE filename to the 
WRITEIMAGE_STRING="${WRITEIMAGE_STRING} -f ${VAR_BOB_IMAGES_DIR}/image.img"

# Call writeimage.sh at the end of this script with the correct image file 
# location for the RiOS image
${WRITEIMAGE_STRING}
RC=$?
if [ $RC -ne 0 ]; then
    clean_up_bob_dir
    exit $RC
fi

# Clean up the BOB directory now
clean_up_bob_dir
