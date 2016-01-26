#!/bin/sh

#
#  Filename:  $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/imgq.sh $
#  Revision:  $Revision: 105481 $
#  Date:      $Date: 2013-05-22 11:01:41 -0700 (Wed, 22 May 2013) $
#  Author:    $Author: timlee $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  (C) Copyright 2003-2013 Riverbed Technology, Inc.
#  All rights reserved.
#

#
# This script is used to verify a .img file, or to query information about
# the image.  These are tar files for BoB and zip files for everything else.
#

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

#XXX/tsternberg These examples cover just a few of the options.  Maybe someone
#               more familiar with typical use cases can deal with this.

#XXX/mkumar -c was added in the initial BOB release. But it is not required
# and not used on a non-BOB. On non-BOB where aiget.sh works properly, this
# script finds the current boot id correctly. I don't think BOB uses this
# script anymore. What this means is you can use this script without -c option.
# Based on the the -l argument, it will do the right thing if it is boot
# partition or install partition. In other words, you can invoke this script
# with either "-l 1" or "-l 2" without knowing which is the boot partition.

usage()
{
    echo "usage: $0 -t -f imagefile"
    echo "usage: $0 -i -f imagefile"
    echo "usage: $0 -i -d -l {1|2}"
    echo "usage: $0 -i -d -l {1|2} -c {1|2} # on bob systems only"

    clean_up_tmp_dir
    exit 1
}

bail_complain()
{
    echo $1
    clean_up_tmp_dir
    exit ${FAILURE}
}

invalid_image()
{
    FILENAME=`basename ${IMAGE_FILE}`
    echo "Invalid image ${FILENAME}. $1"
    clean_up_tmp_dir
    exit ${FAILURE}
}

invalid_partition()
{
    echo "Could not get partition information."
    clean_up_tmp_dir
    exit ${FAILURE}
}

normal_exit()
{
    clean_up_tmp_dir
    exit 0
}

IMGQ_TMPDIR=/var/tmp/imgq-$$
clean_up_tmp_dir()
{
    /bin/rm -rf ${IMGQ_TMPDIR}
    # ignore any errors on the way out.
    # it will overwrite any other error found.
}

make_tmp_dir()
{
    /bin/mkdir -p ${IMGQ_TMPDIR} || FAILURE=10
    if [ ${FAILURE} -ne 0 ]; then
        bail_complain "Could not create tmp directory"
    fi
}


FAILURE=0
INFO_SH=build_version.sh
LOCAL_INFO_SH=/opt/tms/release/build_version.sh
TMP_MNT_IMAGE=/tmp/mnt-imgq.$$
UNZIP=/usr/bin/unzip
TAR=/bin/tar

PARSE=`/usr/bin/getopt -- 'Ftif:dl:c:' "$@"`

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
USE_FIPS_MODE=0

while true ; do
    case "$1" in
        -F) USE_FIPS_MODE=1; shift ;;
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

# beginning of the script execution.
make_tmp_dir

# Deal with BoB images -- the image is inside a tar.  Untar that in a
# temporary directory; there'll be an image.img; reset IMAGE_FILE to that
# and continue normal processing.
if [ $HAVE_FILE -eq 1 ]; then
    /usr/bin/file ${IMAGE_FILE} | grep "tar archive" > /dev/null
    if [ $? -eq 0 ]; then
        ${TAR} xf ${IMAGE_FILE} -C ${IMGQ_TMPDIR} image.img 2>&1 || FAILURE=20
        if [ ${FAILURE} -ne 0 ]; then
            bail_complain "Could not extract image from ${IMAGE}"
        fi
        IMAGE_FILE=${IMGQ_TMPDIR}/image.img
        if [ ! -f ${IMAGE_FILE} ]; then
            FAILURE=30
            bail_complain "Unexpected tarball contents -- no image.img"
        fi
    fi
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

verify_image() {
    local IMAGE_FILE=$1
    local VERIFIED=0
    local FIPS_MODE=""
    local alg=""
    #
    # The plan: first verify that we have an image file, and that the zip
    # checksum validates.  Then make sure the image contains an image ball.
    # Next check for a sha512sums or md5sums file, in that order.
    # Next get a list of all the files, and walk this, doing a sha512sum
    # md5sum on each.  Make a list of just the hashes (no files
    # names) sorted by filename, and compare it to the original hash list
    # (no filenames) sorted by filename.  
    #

    if [ ! -r ${IMAGE_FILE} ]; then
        invalid_image "Could not read image file" 1
    fi

    ${UNZIP} -qqt ${IMAGE_FILE} > /dev/null || FAILURE=40
    if [ ${FAILURE} -ne 0 ]; then
        invalid_image "Corrupted image file"
    fi

    ${UNZIP} -qql ${IMAGE_FILE} image-\*.\* > /dev/null || FAILURE=50
    if [ ${FAILURE} -ne 0 ]; then
        invalid_image "Image binary missing in the image file"
    fi

    if [ ${USE_FIPS_MODE} != 0 ]; then
        HASH_ALGS=sha512
    else
        HASH_ALGS="sha512 md5"
    fi
    for alg in ${HASH_ALGS} ; do
        ${UNZIP} -qqp ${IMAGE_FILE} ${alg}sums > ${IMGQ_TMPDIR}/${alg}sums

        if [ -x /usr/bin/${alg}sum -a -s ${IMGQ_TMPDIR}/${alg}sums ]; then
            FILE_LIST="`cat ${IMGQ_TMPDIR}/${alg}sums |awk '{print $2}'|sed 's,./,,'`" \
                || FAILURE=70
            if [ ${FAILURE} -ne 0 ]; then
                invalid_image "Could not read the file list in the image file"
            fi

            HASHLIST="`cat ${IMGQ_TMPDIR}/${alg}sums | awk '{print $1}'`" || FAILURE=80
            if [ ${FAILURE} -ne 0 ]; then
                invalid_image "Could not read the expected ${alg} values"
            fi
            
            SHL=
            for sif in ${HASHLIST}; do
                SHL="${SHL} ${sif}"
            done

            HL=
            for tif in ${FILE_LIST}; do
                ## echo "Testing $tif"

                if [ ${USE_FIPS_MODE} != 0 ]; then
                    ZFH=`${UNZIP} -qqp ${IMAGE_FILE} $tif | \
                        OPENSSL_FORCE_FIPS_MODE=1 ${alg}sum -` || FAILURE=90
                else
                    ZFH=`${UNZIP} -qqp ${IMAGE_FILE} $tif | \
                        ${alg}sum -` || FAILURE=90
                fi
                if [ ${FAILURE} -ne 0 ]; then
                    invalid_image "Could not compute ${alg}sum for $tif"
                fi

                JUST_HASH=`echo $ZFH | awk '{print $1}'`
                HL="${HL} ${JUST_HASH}"
            done

            if [ "${HL}" != "${SHL}" ]; then
                FAILURE=100
                invalid_image "Computed and expected ${alg}sum values do not match"
            fi

            VERIFIED=1
            break
        fi
    done
    if [ ! ${VERIFIED} -eq 1 ]; then
        # No failure, but not verified either indicates that no sum
        # files were found.
        FAILURE=60
        invalid_image "Could not find any checksum files for ${HASH_ALGS}."
    fi
}

if [ ${DO_TEST} -eq 1 ]; then
    verify_image ${IMAGE_FILE}
fi


if [ ${DO_INFO} -eq 1 ]; then

    if [ ${DO_DEV} -eq 0 ]; then
        # The plan is to extract the build_info.sh info file, grep'ing out the 
        # lines the caller won't care about.
    
        ${UNZIP} -qqp ${IMAGE_FILE} ${INFO_SH} 2>/dev/null| grep '=' \
                 > ${IMGQ_TMPDIR}/${INFO_SH} || FAILURE=110
        if [ ${FAILURE} -ne 0 ]; then
            invalid_image "Could not extract build info in the image file"
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

                cat ${ROOT_DIR}/${LOCAL_INFO_SH} | grep '='  \
                    > ${IMGQ_TMPDIR}/${INFO_SH} || FAILURE=120
                if [ ${FAILURE} -ne 0 ]; then
                    bail_complain "Could not read build info on non-boot partition"
                fi
                ;;
            *)
                if [ ${DEV_IS_LOCAL} -eq 1 ]; then
                    cat $LOCAL_INFO_SH | grep '=' > ${IMGQ_TMPDIR}/${INFO_SH} || FAILURE=130
                    if [ ${FAILURE} -ne 0 ]; then
                        bail_complain "Could not read build info on boot partition"
                    fi
                else
                    other_root_mount="${TMP_MNT_IMAGE}/ROOT_${LOC_ID}"
                    other_root_dir=${other_root_mount}/${dir_other_root}
                    mkdir -p ${other_root_dir}
                    mount -o ro ${part_other_root} ${other_root_mount} || FAILURE=140

                    if [ ${FAILURE} -ne 0 ]; then
                        bail_complain "Could not mount non-boot partition ${MOUNT_DEV}"
                    fi

                    cat ${other_root_dir}/${LOCAL_INFO_SH} | grep '=' \
                       > ${IMGQ_TMPDIR}/${INFO_SH} || FAILURE=150
                    umount ${other_root_mount}
                    rm -rf ${TMP_MNT_IMAGE}
                    if [ ${FAILURE} -ne 0 ]; then
                        bail_complain "Could not unmount non-boot partition"
                    fi
                fi
                ;;
        esac
    fi

    cat ${IMGQ_TMPDIR}/${INFO_SH}
fi

normal_exit
