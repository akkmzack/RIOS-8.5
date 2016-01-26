#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 75858 $
#  Date:      $Date: 2011-02-09 09:19:36 -0800 (Wed, 09 Feb 2011) $
#  Author:    $Author: demmer $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#

#
# This script is used to verify a .img file , or to query information about
# the image.  Internally these files are currently zips.  
#

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

usage()
{
    echo "usage: $0 -t -f imagefile.img"
    echo "usage: $0 -i -f imagefile.img"
    echo "usage: $0 -i -d -l [1|2] -c [1|2]"

    exit 1
}


INFO_SH=build_version.sh
LOCAL_INFO_SH=/opt/tms/release/build_version.sh
MD5SUMS=md5sums
TMP_MNT_IMAGE=/tmp/mnt-imgq.$$

PARSE=`/usr/bin/getopt -- 'tif:dl:c:' "$@"`

if [ $? != 0 ] ; then
    usage
fi

eval set -- "$PARSE"

DO_TEST=0
DO_INFO=0
DO_DEV=0
AUTO_DEV=1
HAVE_LOC=0
HAVE_FILE=0
LOC_ID=0
CURR_BOOT_ID=1

while true ; do
    case "$1" in
        -t) DO_TEST=1; shift ;;
        -i) DO_INFO=1; shift ;;
        -f) HAVE_FILE=1; IMAGE_FILE=$2; shift 2 ;;
        -d) DO_DEV=1; shift ;;
        -l) HAVE_LOC=1; LOC_ID=$2; shift 2 ;;
        -c) CURR_BOOT_ID=$2; shift 2 ;;
        --) shift ; break ;;
        *) echo "imgq.sh: parse failure" >&2 ; usage ;;
    esac
done

if [ $CURR_BOOT_ID -ne 1 -a $CURR_BOOT_ID -ne 2 ]; then
    usage
fi

if [ $DO_TEST -eq $DO_INFO ]; then
    usage
fi

if [ $DO_TEST -eq 1 -a $HAVE_FILE -eq 0 ]; then
    usage
fi

if [ $DO_INFO -eq 1 -a \( $DO_DEV -eq 0 -a $HAVE_FILE -eq 0 \) ]; then
    usage
fi

if [ ${DO_DEV} -eq 1 ]; then
    if [ ${HAVE_LOC} -eq 0 -o \( "${LOC_ID}" -ne 1 -a "${LOC_ID}" -ne 2 \) ]; then
        usage
    fi

    # Get the active image location if required
    AIG_BOOTED_DEV=
    AIG_THIS_BOOT_ID=
    AIG_NEXT_BOOT_ID=

    eval `/sbin/aiget.sh`

    if [ -z "${AIG_THIS_BOOT_ID}" ]; then
        AIG_BOOTED_DEV=
        AIG_THIS_BOOT_ID=
        AIG_NEXT_BOOT_ID=
    fi

    DEV_IS_LOCAL=0
    MOUNT_DEV=
    if [ "${LOC_ID}" = "${AIG_THIS_BOOT_ID}" ]; then
        DEV_IS_LOCAL=1
    else

        # Now we have to figure out the location of the other root partition 
        . /etc/image_layout.sh
        . /etc/layout_settings.sh
        . /etc/image_layout.sh

        eval 'name_other_root="${IL_LO_'${IL_LAYOUT}'_LOC_ROOT_'${LOC_ID}'_PART}"'
        eval 'part_other_root="${IL_LO_'${IL_LAYOUT}'_PART_'${name_other_root}'_DEV}"'
        eval 'dir_other_root="${IL_LO_'${IL_LAYOUT}'_LOC_ROOT_'${LOC_ID}'_DIR}"'
    fi
fi


if [ ${DO_TEST} -eq 1 ]; then
    #
    # The plan: first verify that we have an image file, and that the zip
    # checksum validates.  Then make sure the image contains an image ball
    # and an md5sums file.  Next get a list of all the files, and walk this,
    # doing an md5sum on each.  Make a list of just the hashes (no files
    # names) sorted by filename, and compare it to the original hash list
    # (no filenames) sorted by filename.  
    #

    if [ ! -r ${IMAGE_FILE} ]; then
        echo "*** Could not read file ${IMAGE_FILE}"
        exit 1
    fi

    FAILURE=0
    /usr/bin/unzip -qqt ${IMAGE_FILE} > /dev/null || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Invalid image: corrupted file"
        exit 1
    fi

    FAILURE=0
    /usr/bin/unzip -qql ${IMAGE_FILE} image-\*.\* > /dev/null || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Invalid image: no image ball present"
        exit 1
    fi

    FAILURE=0
    /usr/bin/unzip -qql ${IMAGE_FILE} ${MD5SUMS} > /dev/null || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Invalid image: no hashes present"
        exit 1
    fi

    FAILURE=0
    FILE_LIST=`/usr/bin/unzip -qql ${IMAGE_FILE} | awk '{print $4}' | sort` || \
        FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Invalid image: could not get file list"
        exit 1
    fi

    FAILURE=0
    MD5LIST="`/usr/bin/unzip -qqp ${IMAGE_FILE} ${MD5SUMS} | sort +1 | awk '{print $1}'`" || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Invalid image: hashes could not be extracted"
        exit 1
    fi
    
    SHL=
    for sif in ${MD5LIST}; do
        SHL="${SHL} ${sif}"
    done

    HL=
    for tif in ${FILE_LIST}; do
        if [ "${tif}" = "${MD5SUMS}" ]; then
            continue
        fi

        ## echo "Testing $tif"

        FAILURE=0
        ZFH=`/usr/bin/unzip -qqp ${IMAGE_FILE} $tif | md5sum -` || FAILURE=1
        if [ ${FAILURE} -eq 1 ]; then
            echo "*** Invalid image: could not hash $tif"
            exit 1
        fi

        JUST_HASH=`echo $ZFH | awk '{print $1}'`
        HL="${HL} ${JUST_HASH}"
    done

    if [ "${HL}" != "${SHL}" ]; then
        echo "*** Invalid image: hashes do not match"
        exit 1
    fi
fi


if [ ${DO_INFO} -eq 1 ]; then
    if [ ${DO_DEV} -eq 0 ]; then
        # The plan is to extract the build_info.sh info file, grep'ing out the 
        # lines the caller won't care about.
    
        FAILURE=0
        INFO="`/usr/bin/unzip -qqp ${IMAGE_FILE} ${INFO_SH} 2>/dev/null| grep '='`" || FAILURE=1
        
        if [ ${FAILURE} -eq 1 ]; then
            echo "*** Could not extract image info file"
            exit 1
        fi
    else
        # The plan is to just grep the build_info.sh file if we're asked
        # about the booted image, and otherwise to temporarily mount the
        # other root partition, and grep it from there.

        case ${IL_LAYOUT} in
            "BOBSTD"|"BOBRDM")
                # For BOB we can't rely on the DEV_IS_LOCAL variable as 
                # that comes from aiget.sh, aiget.sh does not work on BOB
                # instead we will use the new -c argument to get the current
                # boot ID and get the version string based on that.
                ROOT_DIR=''
                if [ "${CURR_BOOT_ID}" != "${LOC_ID}" ]; then
                    # Get the build information from the other boot partition image
                    ROOT_DIR="/alt/mnt/root"
                fi

                FAILURE=0
                INFO="`cat ${ROOT_DIR}/${LOCAL_INFO_SH} | grep '='`" || FAILURE=1
                if [ ${FAILURE} -eq 1 ]; then
                    echo "*** Could not extract image info file"
                    exit 1
                fi
                ;;
            *)
                if [ ${DEV_IS_LOCAL} -eq 1 ]; then
                    FAILURE=0
                    INFO="`cat $LOCAL_INFO_SH | grep '='`" || FAILURE=1
                    if [ ${FAILURE} -eq 1 ]; then
                        echo "*** Could not extract image info file"
                        exit 1
                    fi
                else
                    other_root_mount="${TMP_MNT_IMAGE}/ROOT_${LOC_ID}"
                    other_root_dir=${other_root_mount}/${dir_other_root}
                    mkdir -p ${other_root_dir}
                    FAILURE=0
                    mount -o ro ${part_other_root} ${other_root_mount} || FAILURE=1

                    if [ ${FAILURE} -eq 1 ]; then
                        echo "*** Could not mount device ${MOUNT_DEV} to extract image info"
                        exit 1
                    fi

                    FAILURE=0
                    INFO="`cat ${other_root_dir}/${LOCAL_INFO_SH} | grep '='`" || FAILURE=1
                    umount ${other_root_mount}
                    rm -rf ${TMP_MNT_IMAGE}
                    if [ ${FAILURE} -eq 1 ]; then
                        echo "*** Could not extract image info file"
                        exit 1
                    fi
                fi
                ;;
        esac
    fi

    echo "$INFO"
fi
