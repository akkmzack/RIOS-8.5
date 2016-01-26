#!/bin/sh
##
## $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/cpio.sh $
## $Id: cpio.sh 100805 2012-11-09 23:07:15Z mkumar $
## $Revision: 100805 $
## $Date: 2012-11-09 15:07:15 -0800 (Fri, 09 Nov 2012) $
## $Author: mkumar $
##
## (C) Copyright 2011-2012 Riverbed Technology, Inc.
## All rights reserved.

#
# This script is a wrapper around the cpio command which requires
# handling of stdin and stdout. This script makes it easy for use
# in lc_launch_quick() and lc_launch_quick_status().
#


usage()
{
    echo "extract usage: $0 -i in-package -d out-directory"
    echo "package usage: $0 -o out-package -d in-directory"
    exit 1
}

DO_EXTRACT=0
DO_PACKAGE=0
DIRECTORY_GIVEN=0
PACKAGE=""
DIRECTORY=""
DIR_PATH=""
PKG_PATH=""
CMD=`basename $0`


while [ "$1" != "" ];
do
    case "$1" in
        -i) DO_EXTRACT=1; PACKAGE=$2; shift 2 ;;
        -o) DO_PACKAGE=1; PACKAGE=$2; shift 2 ;;
        -d) DIRECTORY_GIVEN=1; DIRECTORY=$2; shift 2 ;;
        *) usage ;;
    esac
done

if [ "$DIRECTORY" = "" -o "$PACKAGE" = "" ]; then
    usage
fi

if [ $DIRECTORY_GIVEN -ne 1 ]; then
    usage
fi

if [ $DO_EXTRACT -eq 1 -a $DO_PACKAGE -eq 1 ]; then
    usage
fi

case $PACKAGE in
    /*) PKG_PATH=$PACKAGE  ;;
    *) PKG_PATH=$PWD/$PACKAGE  ;;
esac

case $DIRECTORY in
    /*) DIR_PATH=$DIRECTORY  ;;
    *) DIR_PATH=$PWD/$DIRECTORY  ;;
esac

if [ $DO_EXTRACT -eq 1 -a ! -r $PKG_PATH ]; then
    echo "Could not extract package $PACKAGE into directory $DIRECTORY. " \
         "Package is not readable."
    exit 2
fi

if [ $DO_EXTRACT -eq 1 -a ! -d $DIR_PATH ]; then
    # if the directory is not writable; may be there is
    # no directory. So, try to create one. If the directory
    # exists, do nothing.
    mkdir -p $DIR_PATH
    if [ $? -ne 0 ]; then
        echo "Could not extract package $PACKAGE into directory $DIRECTORY. " \
             "Directory is not writable."
        exit 3
    fi
fi

if [ $DO_PACKAGE -eq 1 -a ! -d $DIR_PATH ]; then
    echo "Could not package $DIRECTORY into $PACKAGE. " \
         "Directory is not readable."
    exit 4
fi

# target package should not exist.
if [ $DO_PACKAGE -eq 1 -a -e $PKG_PATH ]; then
    echo "Could not package $DIRECTORY into $PACKAGE. " \
         "Package $PACKAGE already exists."
    exit 5
fi

EXIT_CODE=0
if [ $DO_EXTRACT -eq 1 ]; then
    # extract the package; If it is required that the directory should
    # not exist, it is caller's responsibility to make sure that.
    # Here the files will be overwritten
    (cd $DIR_PATH; cpio -i -d --quiet -c -I $PKG_PATH) 2> /var/tmp/${CMD}.$$
    EXIT_CODE=$?
    CPIO_ERROR=`cat /var/tmp/${CMD}.$$`
    rm -f /var/tmp/${CMD}.$$
    if [ $EXIT_CODE -ne 0 ]; then
        # it is caller's responsibility to delete the directory.
        echo "Could not extract package $PACKAGE into directory $DIRECTORY. " \
             $CPIO_ERROR
        exit 6
    fi
elif [ $DO_PACKAGE -eq 1 ]; then
    # package the directory
    (cd $DIR_PATH; \
        find . -print | \
        sed 's,\./,,' | \
        cpio -o --quiet -c -O $PKG_PATH) 2> /var/tmp/${CMD}.$$
    EXIT_CODE=$?
    CPIO_ERROR=`cat /var/tmp/${CMD}.$$`
    rm -f /var/tmp/${CMD}.$$
    if [ $EXIT_CODE -ne 0 ]; then
        echo "Could not package $DIRECTORY into $PACKAGE. $CPIO_ERROR"
        exit 7
    fi
fi

exit 0
