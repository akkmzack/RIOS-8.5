#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 64494 $
#  Date:      $Date: 2010-04-06 19:10:02 -0700 (Tue, 06 Apr 2010) $
#  Author:    $Author: gavin $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#

#
# This script is used to analyze a failure, which may or may not have caused
# a core dump.  It is designed to be run as a crash handler from pm.
#

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

usage()
{
    echo "usage: $0 -n process_name -b binary_path [-c core_path] [-x exit_code] [-s term_signal] [-a staging_area]"
    echo ""
    exit 1
}

get_node_value()
{
    # mgmtd could be blocked or dead, so obtain saved values
    local active_db=`/bin/cat /config/db/active`
    /opt/tms/bin/mddbreq -v $active_db query get - $1
}

PARSE=`/usr/bin/getopt 'n:p:b:c:x:s:a:u:' "$@"`

if [ $? != 0 ] ; then
    usage
fi

eval set -- "$PARSE"

# If we should only handle failures that have coredumps, or all failures
CORE_CRITICAL_ONLY=1

PROCESS_NAME=
PROCESS_PID=-1
BINARY_PATH=
CORE_PATH=
EXIT_CODE=
TERM_SIGNAL=
STAGING_AREA=
HAS_COREDUMP=0
PROCESS_UPTIME=

while true ; do
    case "$1" in
        -n) PROCESS_NAME=$2; shift 2 ;;
	-p) PROCESS_PID=$2; shift 2 ;;
        -b) BINARY_PATH=$2; shift 2 ;;
        -c) HAS_COREDUMP=1; CORE_PATH=$2; shift 2 ;;
        -x) EXIT_CODE=$2; shift 2 ;;
        -s) TERM_SIGNAL=$2; shift 2 ;;
        -a) STAGING_AREA=$2; shift 2 ;;
        -u) PROCESS_UPTIME=$2; shift 2 ;;
        --) shift ; break ;;
        *) echo "afail.sh: parse failure" >&2 ; usage ;;
    esac
done

if [ ! -z "$*" ]; then
    usage
fi

if [ -z "${PROCESS_NAME}" -o -z "${BINARY_PATH}" ]; then
    usage
fi

# See if we want to do our thing
if [ ${CORE_CRITICAL_ONLY} ]; then
    if [ ${HAS_COREDUMP} -eq 0 ]; then
        exit 0
    fi
fi

OUTPUT_FILE=/var/tmp/afail-out-tmp-fsum.$$
rm -f ${OUTPUT_FILE}
touch ${OUTPUT_FILE}
BT_FULL_TMP=/var/tmp/afail-out-tmp-btfull.$$
rm -f ${BT_FULL_TMP}
touch ${BT_FULL_TMP}
MAIL_FILE=/var/tmp/afail-out-tmp-mail.$$
rm -f ${MAIL_FILE}
touch ${MAIL_FILE}

echo "==================================================" >> ${OUTPUT_FILE}
echo "Event information:" >> ${OUTPUT_FILE}
echo ""  >> ${OUTPUT_FILE}

if [ ! -z "${CORE_PATH}" ]; then
    core_size=`stat -c %s ${CORE_PATH}`
    core_time=`date '+%Y-%m-%d %H:%M:%S' -r ${CORE_PATH}`
fi

if [ ! -z "${BINARY_PATH}" ]; then
    binary_size=`stat -c %s ${BINARY_PATH}`
    binary_time=`date '+%Y-%m-%d %H:%M:%S' -r ${BINARY_PATH}`
fi

if [ ${HAS_COREDUMP} -eq 1 ]; then
    echo "Description:    Unexpected failure of process ${PROCESS_NAME} ."  >> ${OUTPUT_FILE}

else
##################################################
    echo "Description:    Unexpected exit of process ${PROCESS_NAME} ."  >> ${OUTPUT_FILE}
fi

echo "Binary name:    ${PROCESS_NAME}"  >> ${OUTPUT_FILE}
echo "Binary size:    ${binary_size}" >> ${OUTPUT_FILE}
echo "Binary time:    ${binary_time}" >> ${OUTPUT_FILE}
if [ ! -z ${CORE_PATH} ]; then
    core_name=`basename ${CORE_PATH}`
    echo "Core name:      ${core_name}" >> ${OUTPUT_FILE}
    echo "Core size:      ${core_size}" >> ${OUTPUT_FILE}
    echo "Core time:      ${core_time}" >> ${OUTPUT_FILE}
fi
if [ ! -z ${PROCESS_PID} -a ${PROCESS_PID} != 0 -a ${PROCESS_PID} != -1 ]; then
    echo "Process ID:     ${PROCESS_PID}"  >> ${OUTPUT_FILE}
fi
if [ ! -z ${EXIT_CODE} ]; then
    echo "Exit code:      ${EXIT_CODE}"  >> ${OUTPUT_FILE}
fi
if [ ! -z ${TERM_SIGNAL} ]; then
    echo "Fatal signal:   ${TERM_SIGNAL}"  >> ${OUTPUT_FILE}
fi
if [ ! -z "${PROCESS_UPTIME}" ]; then
    echo "Process uptime: ${PROCESS_UPTIME}"  >> ${OUTPUT_FILE}
fi


# Do coredump
if [ ${HAS_COREDUMP} -eq 1 ]; then

    cp ${OUTPUT_FILE} ${BT_FULL_TMP}

    # Normal (brief) backtrace

    GDB_COMMANDS_TMP=/var/tmp/afail-tmp-bt.$$
    rm -f ${GDB_COMMANDS_TMP}
    touch ${GDB_COMMANDS_TMP}
    cat >> ${GDB_COMMANDS_TMP} <<EOF
set height 0
set width 0
thread apply all backtrace
EOF
    echo "" >> ${OUTPUT_FILE}
    echo "Backtrace:" >> ${OUTPUT_FILE}
    echo "" >> ${OUTPUT_FILE}
    gdb --batch --command ${GDB_COMMANDS_TMP} --se ${BINARY_PATH} --core ${CORE_PATH} >> ${OUTPUT_FILE}
    echo "" >> ${OUTPUT_FILE}
    rm -f ${GDB_COMMANDS_TMP}

    # Full (detailed) backtrace

    GDB_COMMANDS_TMP=/var/tmp/afail-tmp-btf.$$
    rm -f ${GDB_COMMANDS_TMP}
    touch ${GDB_COMMANDS_TMP}
    cat >> ${GDB_COMMANDS_TMP} <<EOF
set height 0
set width 0
thread apply all backtrace full
EOF
    echo "" >> ${BT_FULL_TMP}
    echo "Backtrace:" >> ${BT_FULL_TMP}
    echo "" >> ${BT_FULL_TMP}
    gdb --batch --command ${GDB_COMMANDS_TMP} --se ${BINARY_PATH} --core ${CORE_PATH} >> ${BT_FULL_TMP}
    echo "" >> ${BT_FULL_TMP}
    rm -f ${GDB_COMMANDS_TMP}

fi

# Now copy our output file into the pm snapshot directory
if [ ! -z "${STAGING_AREA}" ]; then
    cp ${OUTPUT_FILE} ${STAGING_AREA}/fsummary.txt
    cp ${BT_FULL_TMP} ${STAGING_AREA}/backtrace_full.txt
fi

# if the process that crashed is mgmtd or cli, we don't want to ask for a 'show run' output
# as these two proceses are integral to generating this output
SYSDUMP_OPTS="-bd"
if [ "x${PROCESS_NAME}" = "xcli" -o "x${PROCESS_NAME}" = "xmgmtd" ]; then
    SYSDUMP_OPTS="-bdR"
fi

# We now want to take a system dump 
FAILURE=0
OPS=`/sbin/sysdump.sh ${SYSDUMP_OPTS} ${STAGING_AREA}/fsummary.txt ${STAGING_AREA}/backtrace_full.txt` || FAILURE=1
if [ ${FAILURE} -eq 1 ]; then
    logger -p user.err "Could not generate dump"
    exit 1
fi

# Set SYSINFO and SYSDUMP
eval ${OPS}

# Copy the sysinfo and sysdump files into the staging area.
# The sysdump contains the sysinfo file as well as fsummary.txt;
# they are just included separately as a convenience.
if [ ! -z "${STAGING_AREA}" ]; then
    cp ${SYSINFO} ${STAGING_AREA}
fi
if [ ! -z "${STAGING_AREA}" ]; then
    cp ${SYSDUMP} ${STAGING_AREA}
fi

# Finally, tack the summary info from the dump onto our summary, and send the 
# combined summary with the dump off to the critical failure email address

echo "" >> ${OUTPUT_FILE}
cat ${SYSINFO} >> ${OUTPUT_FILE}

HOSTNAME=`uname -n`
FAILURE=0
RECIPS_FILE=`cat /etc/opt/tms/output/notifies.txt | grep RECIPIENTS=`

# Set FAILURE_RECIPIENTS and AUTOSUPPORT_RECIPIENTS
eval ${RECIPS_FILE}

# Customer.sh should set the SUBJECT_PREFIX variable for us.
# But set it ourselves first in case it doesn't.
SUBJECT_PREFIX=System
if [ -f /etc/customer.sh ]; then
    . /etc/customer.sh
fi

# XXX/jcho: this is a temporary implementation.
# Check if webpost is enabled. If so, we should only send the autosupport
# message by webpost. If not, we should continue sending it via email.
AUTOSUPPORT_WEBPOST_ENABLED=`get_node_value /email/autosupport/webpost/enable`
AUTOSUPPORT_WEBPOST_URL=`get_node_value /email/autosupport/webpost/url`

if [ ! -z "${AUTOSUPPORT_WEBPOST_URL}" ]; then
    # URL may be "PROXY URL"
    PROXY=`echo ${AUTOSUPPORT_WEBPOST_URL} | sed -n -e 's/ .*//p'`
    if [ ! -z "${PROXY}" ]; then
        AUTOSUPPORT_WEBPOST_URL=`echo ${AUTOSUPPORT_WEBPOST_URL} | sed -n -e 's/.* //p'`
        AUTOSUPPORT_WEBPOST_PROXY=${PROXY}
    fi
fi

MAKEMAIL_OPTS=
if [ ${AUTOSUPPORT_WEBPOST_ENABLED} = true ]; then
    # Tell makemail to not mail, just to format a message into a file.
    MAKEMAIL_OPTS="-o ${MAIL_FILE}"
fi

# At this point, all we have left to do is send email and cleanup after
# ourselves.  We do this in the background so we can return immediately.

(

    # Send the autosupport and failure emails separately to avoid relay issues

    AUTOSUPPORT_RECIPIENTS="`echo ${AUTOSUPPORT_RECIPIENTS} | sed 's/ /,/g'`"
    if [ ! -z "${AUTOSUPPORT_RECIPIENTS}" ]; then
        makemail.sh -s "$SUBJECT_PREFIX failure on $HOSTNAME: Process failure: ${PROCESS_NAME}" -t "${AUTOSUPPORT_RECIPIENTS}" -i ${OUTPUT_FILE} ${MAKEMAIL_OPTS} -S "-C /etc/ssmtp-auto.conf" -m application/x-gzip ${SYSDUMP} || FAILURE=1
        if [ ${FAILURE} -eq 1 ]; then
            logger -p user.err "Could not send autosupport failure notification mail"
        fi
	if [ ${AUTOSUPPORT_WEBPOST_ENABLED} = true ]; then
	    URL="${AUTOSUPPORT_WEBPOST_URL}?to=${AUTOSUPPORT_RECIPIENTS}"
	    if ! /sbin/webpost.sh ${URL} ${MAIL_FILE} ${AUTOSUPPORT_WEBPOST_PROXY}; then
		logger -p user.err "Could not post failure notification mail"
	    fi
	fi
    fi

    FAILURE_RECIPIENTS="`echo ${FAILURE_RECIPIENTS} | sed 's/ /,/g'`"
    if [ ! -z "${FAILURE_RECIPIENTS}" ]; then
        if [ ! -z ${CORE_PATH} ]; then
            makemail.sh -s "$SUBJECT_PREFIX failure on $HOSTNAME: Process failure: ${PROCESS_NAME} at ${core_time}" -t "${FAILURE_RECIPIENTS}" -i ${OUTPUT_FILE} -m application/x-gzip ${SYSDUMP} || FAILURE=1
        else
            makemail.sh -s "$SUBJECT_PREFIX failure on $HOSTNAME: Process failure: ${PROCESS_NAME}" -t "${FAILURE_RECIPIENTS}" -i ${OUTPUT_FILE} -m application/x-gzip ${SYSDUMP} || FAILURE=1
        fi

        if [ ${FAILURE} -eq 1 ]; then
            logger -p user.err "Could not send failure notification mail"
        fi
    fi
    
    rm -f ${OUTPUT_FILE}
    rm -f ${BT_FULL_TMP}
    rm -f ${MAIL_FILE}
    rm -f ${SYSINFO}

) &

exit 0
