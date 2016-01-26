#!/bin/bash

# Copyright (c) 2007-2008, Hewlett-Packard Company.
# All Rights Reserved.
#
# The contents of this software are proprietary and confidential to the
# Hewlett-Packard Company.  No part of this program may be photocopied,
# reproduced, or translated into another programming language without
# prior written consent of the Hewlett-Packard Company.
#
# $Revision: 107 $
# $Date: 2010-01-21 10:10:12 -0800 (Thu, 21 Jan 2010) $

# just check to make sure the espd daemon is running

# The return values will be as follows:
# 	0 is 'UNKNOWN'.  
# 	2 is 'OK - all is good'.  
#	3 is 'Degraded - Action may be needed further evaluation'
#	4 is 'Minor - Action is needed, however service is running'
#	5 is 'Major - Immediate Action is required'
#	6 is 'Critical - Immediate Action or imminent outage will occur'
#	7 is 'Fatal/NonRecoverable - too late for remedial action'


HEALTH=0

ESPD=`ps -ef | awk '{print $8}' | grep espd`
if [ "$?" -eq "0" ]
then
	ESPD_Running=1
else
	ESPD_Running=0
fi
	
# Check the optimization service state and set health accordingly
STATE=`/opt/tms/bin/mdreq -v query get - /rbt/health/current`
case ${STATE} in
    "Normal")
        HEALTH=2
        ;;
    "Healthy")
        HEALTH=2
        ;;
    "Degraded")
        HEALTH=3
        ;;
    "Critical")
        HEALTH=6
        ;;
    *)
        ;;
esac

# ESPD is only for HP riverblade, and its the worst case scenario
# hence that is the last check
MOBO=`/opt/hal/bin/hwtool.py -q motherboard`
case ${MOBO} in
    "CMP-00HP1")
        if [ "$ESPD_Running" -eq "0" ]; then
	    HEALTH=6
        fi
        ;;
    *)
        ;;
    esac


exit $HEALTH


