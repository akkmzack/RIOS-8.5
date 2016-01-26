#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 7853 $
#  Date:      $Date: 2005-10-18 23:47:48 -0700 (Tue, 18 Oct 2005) $
#  Author:    $Author: cjones $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#

#
# Use this to run an action at some time in the future, specified by the sleep
# time parameter.  Invoke this script as follows:
#
#    send-delayed-action SLEEP_TIME ACTION ACTION_ARGS
#

PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/tms/bin
export PATH

SLEEP=/bin/sleep
MDREQ=/opt/tms/bin/mdreq

SLEEP_TIME=$1
ACTION=$2
ACTION_ARGS=$3

# wait a bit
$SLEEP $SLEEP_TIME

# run the action
$MDREQ action $ACTION $ACTION_ARGS
