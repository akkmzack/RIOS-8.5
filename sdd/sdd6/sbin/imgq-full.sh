#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 74918 $
#  Date:      $Date: 2011-01-19 14:09:06 -0800 (Wed, 19 Jan 2011) $
#  Author:    $Author: msmith $
#
#  (C) Copyright 2002-2010 Riverbed Technology, Inc.
#  All rights reserved.
#

# This script is used for BOB based appliances. This is an intermediate script
# between mgmtd and imgq.sh, it will untar the BOB image
# finally call imgq with the correct image file

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
IMGQ_STRING="/sbin/imgq.sh"


clean_up_bob_dir()
{
    /bin/rm -rf ${VAR_BOB_IMAGES_DIR}
}

make_bob_dir()
{
    /bin/mkdir -p ${VAR_BOB_IMAGES_DIR}
}

usage()
{
    echo "usage: $0 -t -f imagefile.img"
    echo "usage: $0 -i -f imagefile.img"
    echo "usage: $0 -i -d -l [1|2]"

    exit 1
}


while true ; do
    case "$1" in
        -i) shift
            IMGQ_STRING="${IMGQ_STRING} -i"
            ;;
        -f) SYSIMAGE_FILE=$2; shift 2
            # Do not set the image file for imgq here
            # we will do it after extracting it from the BOB image
            ;;
        -d)
            shift
            IMGQ_STRING="${IMGQ_STRING} -d"
            ;;
        -l) INSTALL_IMAGE_ID=$2; shift 2
            IMGQ_STRING="${IMGQ_STRING} -l ${INSTALL_IMAGE_ID}"
            ;;
        -t) shift
            IMGQ_STRING="${IMGQ_STRING} -t"
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
# "-i","-f" image_path, "-d", "-l" location all other options are
# just passed along to imgq as is.

# The "-f" image path will be changed for imgq as the BOB image has extra
# esxi bits as well as the signature file, imgq doesn't care about it

# Clean out the BOB directory
clean_up_bob_dir

# Make the temp BOB dir
make_bob_dir

# Untar the image file in the BOB dir
FAILURE=0
tar -x -f ${SYSIMAGE_FILE} -C ${VAR_BOB_IMAGES_DIR} 2>&1 || FAILURE=1
if [ ${FAILURE} -eq 1 ]; then
    echo "*** Could not extract image from ${SYSIMAGE_FILE}"
    clean_up_bob_dir
    exit 17 #lc_err_upgrade_image_integrity_failure
fi

# Change the imgq SYSIMAGE filename to the
IMGQ_STRING="${IMGQ_STRING} -f ${VAR_BOB_IMAGES_DIR}/image.img"

# Call imgq.sh at the end of this script with the correct image file
# location for the RiOS image
${IMGQ_STRING}
RC=$?
if [ $RC -ne 0 ]; then
    clean_up_bob_dir
    exit $RC
fi

# Clean up the BOB directory now
clean_up_bob_dir
