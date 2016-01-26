#!/bin/bash
# $Id: cpu_util_indiv.sh 95791 2011-11-18 23:48:43Z timlee $
# $URL: svn://svn/mgmt/branches/malta_529_fix_branch/framework/src/base_os/common/script_files/cpu_util_indiv.sh $
# ---------------------------------------------------------------------------
# NOTE: GDB stack tracing has been disabled due to concerns from engineering.
# ---------------------------------------------------------------------------
# How long to sleep between GDB invocations in seconds
# GDBSLEEP=10
# Which process to capture stack trace from
# GDBPROCESS="sport"
# ---------------------------------------------------------------------------

# XXX/llempart Disabling callgraph functionality due to potential system hangs.

# How long to run the oprofile for
export SLEEPFOR=30

# At what CPU idle level (in %) to terminate the oprofile if the appliance is no longer busy
# Set to zero to disable detection
# e.g. export IDLETHRESHOLD=80
export IDLETHRESHOLD=0

# Whether to generate system dump, needs to be 'yes' to work
export SYSDUMP=yes
# export SYSDUMP=no

# How many times to run the oprofile
# The total run time will be REPEAT * SLEEPFOR seconds (plus a bit)
export REPEAT=5

execfind() {
    prog=$1
    PROGPATH=`which "${prog}" 2>/dev/null`
    if [ ! -x "${PROGPATH}" ]; then
        PROGPATH="/usr/local/bin/${prog}"
    fi
    if [ ! -x "${PROGPATH}" ]; then
        PROGPATH="/usr/bin/${prog}"
    fi
    if [ ! -x "${PROGPATH}" ]; then
        log "Cannot find executable path for ${prog}, aborting execution"
        exit 1
    fi
    echo -n "${PROGPATH}"
}

uptime() {
    cut -d . -f 1 /proc/uptime
}

cpuidle() {
    MINIDLE=100
    ( grep '^cpu[0-9]' /proc/stat ; sleep 1 ; grep '^cpu[0-9]' /proc/stat ) | while read CPU NA NA NA IDLE NA; do
        CPUNUM=`echo $CPU | cut -c 4-`
        if [ -z ${CPUIDLE[$CPUNUM]} ]; then
            CPUIDLE[$CPUNUM]=$IDLE
        else
            echo $(($IDLE - ${CPUIDLE[$CPUNUM]}))
        fi
    done | while read CPUIDLE; do
        if [ $CPUIDLE -lt $MINIDLE ]; then
            MINIDLE=$CPUIDLE
            echo $MINIDLE
        fi
    done | tail -1
}

log() {
    DT=`date "+%Y%m%d-%H%M%S"`
    echo "[$DT] $*" >&2
    echo "[$DT] $*" >> $LOG_FILE
}

header() {
    echo "-------------------------------";
    echo $*
    echo "-------------------------------";
}

onexit() {
    ${OPCONTROL} --shutdown >/dev/null 2>&1
    ${OPCONTROL} --reset >/dev/null 2>&1
    TGZ="oprofile-${HOSTNAME}-${EXECDATE}.tgz"
    cd ${OUTPUTDIR}
    tar --remove-files -czf ${TGZ} oprofile-${HOSTNAME}-${EXECDATE}-*.txt
    log "Wrote oprofile tgz: ${OUTPUTDIR}/${TGZ}"
# Commented out by Akos Szechy as a result of bug #79640
#    if [ ${SYSDUMP} == 'yes' ]; then
#        log "Generating system dump..."
#        /sbin/sysdump.sh
#    fi
}

OPCONTROL=`execfind opcontrol`
OPREPORT=`execfind opreport`
GDBBINARY=`execfind gdb`
export OUTPUTDIR="/var/opt/tms/sysdumps"
export DEBUGDIR="/var/tmp/debug"
export MODULEDIR="/opt/rbt/lib/modules"
export EXECDATE=`date "+%Y%m%d-%H%M%S"`
export LOG_FILE="${OUTPUTDIR}/oprofile-${HOSTNAME}-${EXECDATE}-log.txt"

${OPCONTROL} --status 2>&1 | grep --quiet 'Daemon not running'
if [ $? -ne 0 ]; then
    log "Profiler already running, aborting execution."
    exit 1
fi

trap onexit EXIT

mkdir -p "${DEBUGDIR}"

LINIMAGE="${DEBUGDIR}/vmlinux"
if [ -f "${LINIMAGE}" ]; then
    VMLINUX="--vmlinux=${LINIMAGE}"
    CAPTURE=lib,kernel,cpu
else
    log "WARNING: ${DEBUGDIR}/vmlinux not found, kernel debug symbols will not be available."
    VMLINUX="--no-vmlinux"
    CAPTURE=lib,cpu
fi

log "Linking in modules... "
cd "${MODULEDIR}"
for ext in .o .ko; do
    for modulefile in *${ext}; do
        modulelink=`basename $modulefile ${ext}`
        rm -f "${DEBUGDIR}/${modulelink}"
        ln -s "${MODULEDIR}/${modulefile}" "${DEBUGDIR}/${modulelink}"
    done
done

RUNCOUNT=0
while [ $RUNCOUNT -lt $REPEAT ]; do
    RUNCOUNT=$((RUNCOUNT + 1))
    TAG="${HOSTNAME}-${EXECDATE}-${RUNCOUNT}-`date "+%Y%m%d-%H%M%S"`"
    REPORT_FILE="${OUTPUTDIR}/oprofile-${TAG}-report.txt"
    #CALLGRAPH_FILE="${OUTPUTDIR}/oprofile-${TAG}-callgraph.txt"
    DEBUG_FILE="${OUTPUTDIR}/oprofile-${TAG}-debug.txt"
    log "Starting oprofile... "
    ${OPCONTROL} --shutdown >/dev/null 2>&1
    ${OPCONTROL} --reset >/dev/null 2>&1
    ${OPCONTROL} --setup "${VMLINUX}" --separate=${CAPTURE} >/dev/null 2>&1
    #${OPCONTROL} --callgraph=10
    sleep 2
    ${OPCONTROL} --start >/dev/null 2>&1
    if [ $? -eq 0 ] ; then
        log "Waiting ${SLEEPFOR} seconds..."
    
        UPTIME=$(uptime)
        FINISH=$((UPTIME + SLEEPFOR))
        GDBTIMER=$(uptime)
        GDBCOUNT=0
        while [ $UPTIME -le $FINISH ]; do
            if [ $IDLETHRESHOLD -gt 0 ]; then
                IDLE=$(cpuidle)
                # log "Uptime: $UPTIME Finish: $FINISH Idle: $IDLE GDBtimer: $GDBTIMER GDBcount: $GDBCOUNT"
                if [ "$IDLE" != "" ] && [ $IDLE -gt $IDLETHRESHOLD ]; then
                    log "CPU utilisation dropped below threshold, aborting analysis"
                    exit
                fi
            fi
            # if [ $UPTIME -gt $GDBTIMER ]; then
                # GDB_FILE_NAME="${OUTPUTDIR}/oprofile-${HOSTNAME}-${EXECDATE}-gdb-${GDBCOUNT}.txt"
                # ${GDBBINARY} --batch --eval-command="thread apply all where" -p `pidof ${GDBPROCESS}` > $GDB_FILE_NAME 2>&1
                # log "Wrote GDB info: $GDB_FILE_NAME"
                # GDBTIMER=$((UPTIME + GDBSLEEP))
                # GDBCOUNT=$((GDBCOUNT + 1))
            # fi
            sleep 1
            UPTIME=$(uptime)
        done
    
        log "Going to shutdown opcontrol"
        ${OPCONTROL} --shutdown >/dev/null 2>&1
    
        header "opreport" >> $REPORT_FILE
        ${OPREPORT} -l --image-path="${DEBUGDIR}" >> $REPORT_FILE 2>$DEBUG_FILE
    #    ${OPREPORT} --callgraph --image-path="${DEBUGDIR}" -o $CALLGRAPH_FILE \
    #                >> $DEBUG_FILE 2>&1
        ${OPCONTROL} --reset >/dev/null 2>&1
        ${OPCONTROL} --deinit >/dev/null 2>&1
        header "sockstat" >> $REPORT_FILE
        cat /proc/net/sockstat >> $REPORT_FILE
    
        log "Wrote oprofile info: ${REPORT_FILE}"
    #    log "Wrote callgraph info: ${CALLGRAPH_FILE}"
    else
        log "failed to start oprofile."
        break
    fi
done
