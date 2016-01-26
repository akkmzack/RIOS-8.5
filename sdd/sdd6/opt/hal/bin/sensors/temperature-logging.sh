#!/bin/bash

log_dir=/var/log/sensors
log=${log_dir}/temperature
collect_temps="/opt/hal/bin/sensors/collect-temps.pl"

rotate()
{
    if [ -f $log-9 ]; then
        rm -f $log-9
    fi
    if [ -f $log-8 ]; then
        mv -f $log-8 $log-9
    fi
    if [ -f $log-7 ]; then
        mv -f $log-7 $log-8
    fi
    if [ -f $log-6 ]; then
        mv -f $log-6 $log-7
    fi
    if [ -f $log-5 ]; then
        mv -f $log-5 $log-6
    fi
    if [ -f $log-4 ]; then
        mv -f $log-4 $log-5
    fi
    if [ -f $log-3 ]; then
        mv -f $log-3 $log-4
    fi
    if [ -f $log-2 ]; then
        mv -f $log-2 $log-3
    fi
    if [ -f $log-1 ]; then
        mv -f $log-1 $log-2
    fi
    mv -f $log $log-1
    newlog
}

newlog()
{
    model=`/opt/tms/bin/hald_model | awk '{print $1}'`
    echo "Log created `date` ; model $model" > $log
}

while [ 0 ]; do
    if [ ! -d $log_dir ]; then
        mkdir $log_dir
    fi
    if [ ! -f $log ]; then
        newlog
        log_size=0
    else
        log_size=`wc -l $log | awk '{print $1}'`
    fi
    logday=`head -n1 $log | awk '{print $5}'`
    curday=`date +%d`
    # rotate logs every day
    if [ $logday -ne $curday ]; then
        rotate &>/dev/null
        log_size=0
    fi
    # header every 23 loggings
    if [ `expr $log_size % 23` -eq 0 ]; then 
        echo >> $log
        $collect_temps --header >> $log
    else
        $collect_temps >> $log
    fi
    # sleep 10 minutes
    # looping because if this script is killed, its sleep remains
    # sleep's time is minimized because this script is exposed to CLI
    i=60
    while [ $i -gt 0 ]; do
        sleep 10
        i=`expr $i - 1`
    done
done
