#!/bin/sh
                                                                                
#
#  Filename:  $Source$
#  Revision:  $Revision: 5402 $
#  Date:      $Date: 2005-01-21 12:10:14 -0800 (Fri, 21 Jan 2005) $
#  Author:    $Author: ltrac $
#
#  (C) Copyright 2003-2005 Riverbed Technology, Inc.
#  All rights reserved.
#

DCNAME=$1
PATH=$2

if [ x$2 = x ]; then
    /bin/echo $DCNAME > /var/opt/rbt/.dc_name
else
    /bin/echo $DCNAME > $PATH
fi

exit 0
