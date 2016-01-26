#!/bin/sh
##
## $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/image_info.sh $
## $Id: image_info.sh 106689 2013-07-11 01:50:34Z mkumar $
## $Revision: 106689 $
## $Date: 2013-07-10 18:50:34 -0700 (Wed, 10 Jul 2013) $
## $Author: mkumar $
##
## (C) Copyright 2013 Riverbed Technology, Inc.
## All rights reserved.

PATH=/bin:/usr/bin
export PATH

status=0

if [ $# != 1 ]; then
    echo "Usage: $0 <image_file>"
    status=1
elif [ ! -e $1 ]; then
    echo "File $1 is not found"
    status=2
else
    if [ -f $1 -a -r $1 ]; then
        magic_no=`od -x -A n -N 2 $1`
        if [ $magic_no = "4b50" ]; then
            # zip file; may be full image
            unzip -qqp $1 build_version.sh bannow_info.sh 2>/dev/null | fgrep '='|| status=4
        else
            # assume a tar file; may be new delta image format
            tar xfO $1 ./delta_info.txt 2>/dev/null || status=5
            if [ ${status} -eq 0 ]; then
                CHKSUM=`md5sum $1 | cut -d ' ' -f 1`
                echo "DELTA_IMAGE_CHECKSUM=\"$CHKSUM\""
            fi
        fi
    else
        status=6
    fi
    if [ $status -ne 0 ]; then
        echo "File $1 is not an image file"
    fi
fi

exit $status
