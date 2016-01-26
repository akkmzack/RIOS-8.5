#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 51385 $
#  Date:      $Date: 2009-05-07 17:01:17 -0700 (Thu, 07 May 2009) $
#  Author:    $Author: aanantha $
#
#  (C) Copyright 2003-2009 Riverbed Technology, Inc.
#  All rights reserved.
#

###############################################################################
#
# Look through the list of mounted devices to find the encfs entry for
# secure vault.
#
# Returns "true" if /var/opt/rbt/decrypted is found to be an encfs type.
# Otherwise, it returns "false".
#
###############################################################################

MOUNT=`mount | grep '/var/opt/rbt/decrypted' | awk '{print $1}'`

if [ "x${MOUNT}" = "xencfs" ]; then
    echo "true"
else
    echo "false"
fi
