#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 49320 $
#  Date:      $Date: 2009-04-02 16:32:42 -0700 (Thu, 02 Apr 2009) $
#  Author:    $Author: rcenteno $
#
#  (C) Copyright 2003-2009 Riverbed Technology, Inc.
#  All rights reserved.
#

# Calculate the md5sum of the file containing md5sums of files found in a given
# directory
#
# Exits 0 if the checksums of the two directories passed match
# Otherwise, exits 1 if the checksums do not match or the number of args is not
#                    correct

# caller must provide the two directories to compare
if [ $# != 2 ]; then
    echo "false"
    exit 1
fi

check_dir()
{
    DIRNAME=$1
    DIRBASENAME=`basename $DIRNAME`
    TEMP_CHECKFILE="/tmp/.checksum_$DIRBASENAME"
    TEMP_SORTED="/tmp/.sorted_sum"

    cd $DIRNAME

    for file in $( find . -print ); do
        if [ -f $file ]; then
            echo `md5sum $file` >> ${TEMP_CHECKFILE}
        fi
    done

    # sort the entries to ensure we are comparing apples to apples since find
    # could return the contents in some arbitrary order
    cat ${TEMP_CHECKFILE} | sort > ${TEMP_SORTED}
    mv ${TEMP_SORTED} ${TEMP_CHECKFILE}

    # output of md5sum is "<hash> <filename>", but we only use the hash
    CHECKSUM=`md5sum ${TEMP_CHECKFILE} | awk '{print $1}'`
    rm ${TEMP_CHECKFILE}
}

check_dir $1
CHECKDIR1=$CHECKSUM

check_dir $2
CHECKDIR2=$CHECKSUM

if [ x$CHECKDIR1 = x$CHECKDIR2 ]; then
    exit 0
else
    exit 1
fi
