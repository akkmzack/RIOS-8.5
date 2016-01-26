#!/bin/sh

# This script is used to start and stop CPU profiling

OPCONTROL_PATH="/usr/local/bin/opcontrol"
OPREPORT_PATH="/usr/local/bin/opreport"

start_profiling()
{
    echo "Starting opcontrol"
    ${OPCONTROL_PATH} -h
    ${OPCONTROL_PATH} --reset
    ${OPCONTROL_PATH} --setup --no-vmlinux --separate=library
    sleep 2
    ${OPCONTROL_PATH} --start
}

stop_profiling()
{
    PID=`pidof oprofiled`

    # only need to shutdown profiling if it's running
    if [ x${PID} != "x" ]; then
        echo "Going to shutdown opcontrol"
        ${OPCONTROL_PATH} --shutdown

        YEAR=`date +%Y`
        MON=`date +%m`
        DAY=`date +%d`
        HR=`date +%H`
        MIN=`date +%M`
        SEC=`date +%S`
        SUFFIX="_oprofile.txt"

        FILE_NAME=${YEAR}"_"${MON}"_"${DAY}"_"${HR}"_"${MIN}"_"${SEC}${SUFFIX}
        ${OPREPORT_PATH} -l > /var/tmp/${FILE_NAME}
        ${OPCONTROL_PATH} -h
        echo "Wrote oprofile info: " ${FILE_NAME}
    fi
}

case "$1" in
    start)  start_profiling;;
    stop) stop_profiling;;
    *)     echo "Going to run opcontrol for a period of time";  \
           start_profiling;                                     \
           if [ $? -eq 0 ] ; then                               \
               echo "Going to sleep for 120 sec";               \
               sleep 120;                                       \
               stop_profiling;                                  \
           else                                                 \
               echo "opcontrol is already running";             \
           fi;;
esac
