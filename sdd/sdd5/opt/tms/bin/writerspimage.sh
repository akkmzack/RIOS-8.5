#!/bin/sh
#
#  Filename:  $Source$
#  Revision:  $Revision: 117884 $
#  Date:      $Date: 2012-12-18 16:06:32 -0800 (Tue, 18 Dec 2012) $
#  Author:    $Author: llim $
# 
#  (C) Copyright 2003-2005 Riverbed Technology, Inc.  
#  All rights reserved.
#

# This script to used to write an RSP image to disk - and uninstall it.
#
# The RSP image can be retreived from a URL or from locally on disk. This 
# selection is made on the command line.

# Work around bug 38451 that sets incorrect (empty) timezone
unset TZ

#
# Exit codes
#

ERR_NONE=0
ERR_ARCHITECTURE_MISMATCH=1
ERR_DECOMPRESSION_FAILED=2
ERR_IMAGE_FETCH_FAILED=3
ERR_IMAGE_FILE_NOT_FOUND=4
ERR_IMAGE_FILE_INVALID=5
ERR_IMAGE_EXTRACT_FAILED=6
ERR_IMAGE_HASH_MISMATCH=7
ERR_RELEASE_INFO_NOT_FOUND=8
ERR_TARBALL_NOT_FOUND=9
ERR_INSTALL_DISKLIB_NOT_FOUND=10
ERR_INSTALL_SCRIPT_NOT_FOUND=11
ERR_INSTALL_SCRIPT_FAILED=12
ERR_USAGE=13
ERR_ROOT_PARTITION_NOT_FOUND=14
ERR_ROOT_DISK_SPACE=15
ERR_ELEMENT_COUNT=16

#
# Script parameters
#

RSP_ROOT_PARTITION=/proxy
RSP_ROOT_DIR=$RSP_ROOT_PARTITION/__RBT_VSERVER_SHELL__/rsp2

RSP_IMAGE_HISTORY=/var/opt/tms/rsp_image_history

# If you change the path below, you will also need to change the symlink targets
# created in: -
#
#   products/rbt_sh/src/base_os/linux_centos/42/image_files/Makefile
#   products/rbt_sh/src/base_os/common/script_files/var_upgrade_rbt.sh

RSP_VMWARE_STORAGE=$RSP_ROOT_PARTITION/__RBT_VSERVER_SHELL__/vmware_server
RSP_PERL_STORAGE=$RSP_ROOT_PARTITION/__RBT_VSERVER_SHELL__/perl

RSP_INSTALL_SCRATCH_DIR=$RSP_ROOT_PARTITION/__RBT_VSERVER_SHELL__/rsp2/tmp-install
RSP_IMAGE_RELEASE_FILE=$RSP_ROOT_PARTITION/__RBT_VSERVER_SHELL__/rsp2/.rsp_version
RSP_INSTALL_SCRIPT=rvbd-install.sh
RSP_INSTALL_TARBALL_FILE=$RSP_INSTALL_SCRATCH_DIR/vmware_tarball
RSP_INSTALL_DISKLIB_TARBALL_FILE=$RSP_INSTALL_SCRATCH_DIR/vmware_disklib_tarball
RSP_RELEASE_FILE=$RSP_INSTALL_SCRATCH_DIR/rsp_release
LOGGER=/usr/bin/logger

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

# Get needed info about the software running on the Steelhead

RIOS_RELEASE_INFO_PATH=/opt/tms/release/
RELEASE_INFO_SCRIPT=build_version.sh
GET_RIOS_RELEASE_INFO=$RIOS_RELEASE_INFO_PATH/$RELEASE_INFO_SCRIPT

. $GET_RIOS_RELEASE_INFO

RIOS_BUILD_TARGET_ARCH_LC=$BUILD_TARGET_ARCH_LC

RSP_BUILD_PROD_RELEASE=0
RSP_BUILD_TARGET_ARCH_LC=0
SYSIMAGE_USE_URL=0

DEBUG=0

log_error()
{
    echo "$1"
    /usr/bin/logger -p user.err "RSP Install" "$1"
}

log_info()
{
    echo $1
    /usr/bin/logger -p user.info "RSP Install" $1
}

usage()
{
    echo "usage: $0 -u URL | -f FILE [-d] [-r] | [-x]"
    echo "Either '-u' (URL) or '-f' (file) must be specified."
    echo -n "'-r' will uninstall RSP and all installed slots. RSP can be "
    echo "re-installed at any time."
    echo -n "'-x' will uninstall RSP, remove all Images and Packages, "
    echo "and delete all RSP-related directories."
    echo "     A mgmtd restart will be required before RSP can be re-installed."
    echo "'-d' will pause the script before running $RSP_INSTALL_SCRIPT"
    log_error "Invalid params passed to image install script"
    cleanup_exit $ERR_USAGE
}

uninstall_rsp()
{
    if [ -f $RSP_IMAGE_RELEASE_FILE ]; then
        if [ -f $RSP_ROOT_DIR/$RELEASE_INFO_SCRIPT ]; then
            . $RSP_ROOT_DIR/$RELEASE_INFO_SCRIPT
        fi
        # Only log clean uninstalls.
        RSP_REMOVED_VERSION=`cat $RSP_IMAGE_RELEASE_FILE`
        echo "Uninstalled $RSP_REMOVED_VERSION $BUILD_PROD_VERSION on `date`" >> $RSP_IMAGE_HISTORY
    fi
    rm -rf $RSP_INSTALL_SCRATCH_DIR
    rm -rf $RSP_VMWARE_STORAGE
    rm -rf $RSP_PERL_STORAGE
    rm -rf $RSP_IMAGE_RELEASE_FILE
    for d in `ls $RSP_ROOT_DIR/slots`; do
        if [ -d $RSP_ROOT_DIR/slots/$d ]; then
            cd $RSP_ROOT_DIR/slots/$d
            rm -rf *
            rm -rf .*
        fi
    done
    log_info "RSP successfully uninstalled."
}

nuke_rsp()
{
    rm -rf $RSP_ROOT_DIR
    rm -rf $RSP_VMWARE_STORAGE
    rm -rf $RSP_PERL_STORAGE
    log_info "All RSP-related files and directories deleted from system."
    log_info "A mgmtd restart is required before RSP can be re-installed."
}

# ==================================================
# Remove all temporary files and exit with the given
# return code.
# ==================================================

cleanup_exit()
{
    rm -rf $RSP_INSTALL_SCRATCH_DIR
    exit $1
}

# ==================================================
# Remove and re-create the scratch directory - it might exist from
# a previous aborted installation.
# ==================================================

rm -rf $RSP_INSTALL_SCRATCH_DIR
mkdir -p $RSP_INSTALL_SCRATCH_DIR

# ==================================================
# Parse command line parameters
# ==================================================

if  [ $# -lt 1 ]; then
    usage
fi

if [ $# -gt 3 ]; then
    usage
fi

until [ -z "$1" ] 
do
    case "$1" in
        -u) SYSIMAGE_USE_URL=1; SYSIMAGE_URL=$2;                \
            if [ -z $SYSIMAGE_URL ]; then                       \
                usage;                                          \
            fi;                                                 \
            shift 2                                             \
            ;;
        -f) SYSIMAGE_USE_URL=0; SYSIMAGE_FILE=$2;               \
            if [ -z $SYSIMAGE_FILE ]; then                      \
                usage;                                          \
            fi;                                                 \
            shift 2                                             \
            ;;                                                  \
        -d) DEBUG=1; shift 1; echo Enabling debug mode.;;
        -r) uninstall_rsp; exit 0;;
        -x) nuke_rsp; exit 0;;
        *) echo "$0: parse failure" >&2 ; usage ;;
    esac
done

# ==================================================
# Check if we have a $RSP_ROOT_PARTITION and that it has enough space.
# ==================================================

df | grep $RSP_ROOT_PARTITION
if [ $? -ne 0 ]; then
    log_error "*** Target install partition ($RSP_ROOT_PARTITION) not found."
    exit $ERR_ROOT_PARTITION_NOT_FOUND
fi

if [ $SYSIMAGE_USE_URL -eq 1 ]; then
    RSP_MIN_SPACE=2000000
else
    RSP_MIN_SPACE=1500000
fi

rsp_free_space=`df | grep $RSP_ROOT_PARTITION | awk '{ print $4}'`
if [ "$rsp_free_space" -lt "$RSP_MIN_SPACE" ]; then
    log_error "*** Insufficient space on $RSP_ROOT_PARTITION"
    exit $ERR_ROOT_DISK_SPACE
fi

# ==================================================
# OK - seems like we can proceed with image fetch 
# ==================================================

if [ $SYSIMAGE_USE_URL -eq 1 ]; then
    local_filename=`echo $SYSIMAGE_URL | sed 's/^.*\/\([^\/]*\)$/\1/'`
    log_info "==== Retrieving image file from $SYSIMAGE_URL"

    SYSIMAGE_FILE=$RSP_INSTALL_SCRATCH_DIR/$local_filename
    rm -f $SYSIMAGE_FILE

    /usr/bin/wget -O $SYSIMAGE_FILE $SYSIMAGE_URL
    if [ $? -ne 0 ]; then
        log_error "*** Could not retrieve image from $SYSIMAGE_URL"
        cleanup_exit $ERR_IMAGE_FETCH_FAILED
    fi
else
    if [ -z "$SYSIMAGE_FILE" -o ! -f "$SYSIMAGE_FILE" ]; then
        log_error "*** No system image file:  ${SYSIMAGE_FILE}"
        cleanup_exit $ERR_IMAGE_FILE_NOT_FOUND
    fi
    local_filename=`echo $SYSIMAGE_FILE | sed 's/^.*\/\([^\/]*\)$/\1/'`
    NEW_SYSIMAGE_FILE=$RSP_INSTALL_SCRATCH_DIR/$local_filename
    if [ "${SYSIMAGE_FILE}" != "${NEW_SYSIMAGE_FILE}" ]; then
        rm -f ${NEW_SYSIMAGE_FILE}
        cp -p ${SYSIMAGE_FILE} ${NEW_SYSIMAGE_FILE}
    fi
    ORIG_SYSIMAGE_FILE=${SYSIMAGE_FILE}
    SYSIMAGE_FILE=${NEW_SYSIMAGE_FILE}
fi

# ==================================================
# Extract and uncompress the RSP image.
# ==================================================

IMG_FIRST_4_BYTES="120 113 003 004"
TBZ_FIRST_3_BYTES="102 132 150"

# This is the name of the file in the image that has the MD5s
MD5SUMS_NAME=md5sums

FILE_TYPE=none

first_four_bytes=`dd if=${SYSIMAGE_FILE} bs=1 count=4 2> /dev/null | od -b | awk '{print $2" "$3" "$4" "$5}' | sed 's, *$,,' | tr -d '\n'`

if [ "${first_four_bytes}" !=  "${IMG_FIRST_4_BYTES}" ]; then
    log_error "*** ${SYSIMAGE_FILE} does not appear to be a valid RSP Install image" 
    cleanup_exit $ERR_IMAGE_FILE_INVALID
fi

log_info "==== Verifying image integrity for ${SYSIMAGE_FILE}"

/usr/bin/unzip -q -d $RSP_INSTALL_SCRATCH_DIR $SYSIMAGE_FILE
if [ $? -ne 0 ]; then
    echo "**** Could not extract image ${SYSIMAGE_FILE}"
    cleanup_exit $ERR_IMAGE_EXTRACT_FAILED
fi

cd $RSP_INSTALL_SCRATCH_DIR

/usr/bin/md5sum -c $MD5SUMS_NAME > /dev/null
if [ $? -ne 0 ]; then
    log_error "**** Invalid image: bad hashes for ${SYSIMAGE_FILE}"
    cleanup_exit $ERR_IMAGE_HASH_MISMATCH
fi

log_info "==== ${SYSIMAGE_FILE} looks good, proceeding with installation."

SYSIMAGE_FILE_TBZ=`ls *.tbz`
RSP_IMAGE_VERSION="Unknown"
RSP_RELEASE="Unknown"

# ==================================================
# Verify that this image will run on the Steelhead
# ==================================================

if [ -f $RELEASE_INFO_SCRIPT ]; then
    . $RELEASE_INFO_SCRIPT
    RSP_IMAGE_VERSION=$BUILD_PROD_VERSION
else
    log_error "**** Unable to find $RELEASE_INFO_SCRIPT"
    log_error "**** Unable to verify RSP build details - aborting."
    cleanup_exit $ERR_RELEASE_INFO_NOT_FOUND
fi

if [ $BUILD_TARGET_ARCH_LC == $RIOS_BUILD_TARGET_ARCH_LC ]; then
    log_info "==== Installing RSP for $BUILD_TARGET_ARCH_LC"
else
    log_error "**** RSP and RIOS image architecture mismatch - aborting."
    cleanup_exit $ERR_ARCHITECTURE_MISMATCH
fi

/bin/tar xjf $SYSIMAGE_FILE_TBZ >/dev/null
if [ $? -ne 0 ]; then
    log_error "Unable to decompress $SYSIMAGE_FILE_TBZ"
    cleanup_exit $ERR_DECOMPRESSION_FAILED
fi

# ==================================================
# Run the RSP image's install script
# ==================================================

if [ $DEBUG = 1 ]; then
    echo "About to execute $RSP_INSTALL_SCRIPT...hit enter to continue."
    read DUMMY
fi

# What version of RSP are we running?

if [ -f $RSP_RELEASE_FILE ]; then
    RSP_RELEASE=`cat $RSP_RELEASE_FILE`
else
    log_error "Unable to determine RSP release info. Is this an RSP Image?"
fi

# What is the name of the RSP tarball?

if [ -f $RSP_INSTALL_TARBALL_FILE ]; then
    RSP_INSTALL_TARBALL=`cat $RSP_INSTALL_TARBALL_FILE`
else
    log_error "Unable to determine RSP tar archive - aborting"
    cleanup_exit $ERR_TARBALL_NOT_FOUND
fi

# What is the name of the RSP disklib tarball?

if [ -f $RSP_INSTALL_DISKLIB_TARBALL_FILE ]; then
    RSP_INSTALL_DISKLIB_TARBALL=`cat $RSP_INSTALL_DISKLIB_TARBALL_FILE`
else
    log_error "Unable to determine RSP disklib tar archive - aborting"
    cleanup_exit $ERR_INSTALL_DISKLIB_NOT_FOUND
fi

RSP_PERL_TARBALL="perl5.`uname -i`.tgz"

if [ -f $RSP_INSTALL_SCRIPT ]; then
    chmod +x $RSP_INSTALL_SCRIPT
else
    log_error "Unable to find $RSP_INSTALL_SCRIPT - aborting"
    cleanup_exit $ERR_INSTALL_SCRIPT_NOT_FOUND
fi

# We are about to affect the actual RSP binaries that run during normal
# operation, so RSP is effectively un-installed from this point on. So 
# remove the version file which mgmt uses to detect if RSP is installed.
rm -f $RSP_IMAGE_RELEASE_FILE

# Copy the build info script - it has lots of useful information worth keeping.

rm -f $RSP_ROOT_DIR/$RELEASE_INFO_SCRIPT
cp $RSP_INSTALL_SCRATCH_DIR/$RELEASE_INFO_SCRIPT $RSP_ROOT_DIR

RSP_COMMAND_PARAMS="$RSP_ROOT_DIR $RSP_VMWARE_STORAGE $RSP_INSTALL_TARBALL $RSP_INSTALL_DISKLIB_TARBALL $RSP_PERL_STORAGE $RSP_PERL_TARBALL"
log_info "=== $RSP_INSTALL_SCRIPT $RSP_COMMAND_PARAMS"
if [ $DEBUG = 1 ]; then
    /bin/bash -x $RSP_INSTALL_SCRIPT $RSP_COMMAND_PARAMS
else
    /bin/bash $RSP_INSTALL_SCRIPT $RSP_COMMAND_PARAMS
fi

if [ $? -ne 0 ]; then
    log_error "$RSP_INSTALL_SCRIPT encountered a failure - aborting"
    cleanup_exit $ERR_INSTALL_SCRIPT_FAILED
fi

# Write the RSP release into the release file and log it to the RSP image history
FULL_RSP_RELEASE="$RSP_RELEASE $RSP_IMAGE_VERSION"
echo "$RSP_RELEASE" > $RSP_IMAGE_RELEASE_FILE

if [ -f $RSP_IMAGE_HISTORY ]; then
    SEEN_BEFORE=0
    SAME_VERSION=0

    grep "$FULL_RSP_RELEASE" $RSP_IMAGE_HISTORY > /dev/null
    if [ $? = 0 ]; then
        SEEN_BEFORE=1
    fi
    tail -1 $RSP_IMAGE_HISTORY | grep "$FULL_RSP_RELEASE" > /dev/null
    if [ $? = 0 ]; then
        SAME_VERSION=1
    fi

    if [ $SAME_VERSION = 0 ]; then
        if [ $SEEN_BEFORE = 0 ]; then
            echo "Installed $FULL_RSP_RELEASE on `date`" >> $RSP_IMAGE_HISTORY
        else
            echo "Reverted $FULL_RSP_RELEASE on `date`" >> $RSP_IMAGE_HISTORY
        fi
    else
        echo "Reinstalled $FULL_RSP_RELEASE on `date`" >> $RSP_IMAGE_HISTORY
    fi
else
    echo "First-install $FULL_RSP_RELEASE on `date`" > $RSP_IMAGE_HISTORY
fi

log_info "==== Installation successful"
cleanup_exit $ERR_NONE
