#!/bin/sh
#
# (C) Copyright 2003-2012 Riverbed Technology, Inc.
#  Revision:  $Revision: 117728 $
#  Date:      $Date: 2012-12-17 15:15:45 -0800 (Mon, 17 Dec 2012) $
#  Author:    $Author: jtao $
# Script to check if shadow is enabled.

HWTOOL="/opt/hal/bin/hwtool.py"

echo `${HWTOOL} -q disk=map | awk '{print $3}'|sed -n "/sh[a-z]/p" |wc -l`

