#!/bin/bash
#
# $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/webasd_watchdog.sh $
#
# This is for bug 119126 where webasd gets wedged and stops responding
# to requests.  When this happens, the wkcgi adapter never exits and
# apache eventually kills it (after a 1-hour timeout).  The apache
# concurrent connection limit is 16 so if we see that many wkcgi
# processes, we assume that webasd is unresponsive and we kill it.  pm
# should automatically restart it in a few seconds.

MAX_COUNT=16
PROCESS_COUNT=$(ps -e | grep wkcgi | grep -vc grep)

if [ $PROCESS_COUNT -ge $MAX_COUNT ]
then
    logger -p user.warn -t webasd_watchdog "terminating webasd"
    killall -9 webasd
fi
