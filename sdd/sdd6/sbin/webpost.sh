#!/bin/sh
#
#  Filename:  $Source$
#  Revision:  $Revision: 64209 $
#  Date:      $Date: 2010-03-31 16:56:57 -0700 (Wed, 31 Mar 2010) $
#  Author:    $Author: gavin $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#
# This script uses HTTP to POST a file to a URL.
#

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

CURL=/usr/bin/curl

usage()
{
    echo "usage: $0 url file [proxy]"
    echo ""
    exit 1
}

if [ $# == 3 ]; then
URL=$1
FILE=$2
    PROXY="-x $3"
elif [ $# == 2 ]; then
    URL=$1
    FILE=$2
else
    usage
fi

if ! $CURL $PROXY --data-binary @$FILE $URL > /dev/null; then
    echo "Failed to upload data"
    exit 1
fi

exit 0
