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

set -u

PATH="`dirname "$0"`:/sbin:/usr/bin:$PATH"


# Define all of the subroutines firt...


# Function cat_file will simply cat the file if it exists
function cat_file()
{
if [ -e $1 ]
then
	echo
	echo "\$ $1 "
        cat $1
fi
}

#parse_command for parsing commands
#usage:
#parse_command  "full_path_of_command" "args" "tag_name"

function parse_command() {
FQP_Binary=`whereis -b $1 | awk '{print $2}'`
if [ "$FQP_Binary" -a -x $FQP_Binary ]
then
	echo
	echo "\$ $3 "
	eval "$FQP_Binary $2"
fi
}

show_smart_data_smartctl_xx50()
{
    local CMD="$1"

    for line in `/opt/hal/bin/hwtool.py -q disk=map | cut -f 2,3 -d " "| sed -e s'/ /#/'`; do
        type=`echo $line | cut -f 1 -d "#" | sed s'/[0-9]\+//'`
        if [ "disk" = "${type}" ]; then
            partition=`echo $line | cut -f 2 -d "#"`
            if [ "missing" != "$partition" ]; then
                echo "${CMD} /dev/${partition}"
                $CMD "/dev/$partition"
            fi
        fi
        echo ""
    done
    echo ""
}

show_smart_data_smartctl()
{
    local MDDBREQ="/opt/tms/bin/mddbreq -v"
    local SMARTCMD="/usr/sbin/smartctl -a "
    local ATA=" -d ata "
    local DB_FILE="/config/mfg/mfdb"
    local MOBO=`hwtool -q motherboard`
    echo
    echo "================================================="
    echo " SMART Information "
    echo "================================================="
    echo 
    case ${MOBO} in
        "400-00100-01"|"400-00300-01")
            show_smart_data_smartctl_xx50 "${SMARTCMD}"
            ;;
        "400-00099-01")
            show_smart_data_smartctl_xx50 "${SMARTCMD} ${ATA}"
            ;;
        *)
            DUAL=`${MDDBREQ} ${DB_FILE} query get - /rbt/mfd/store/dual`

            if [ "x${DUAL}" = "xfalse" ]; then
                disk1=`${MDDBREQ} ${DB_FILE} query get - /rbt/mfd/store/dev`
            else
                disk1=`${MDDBREQ} ${DB_FILE} query get - /rbt/mfd/store/mdraid1`
                disk2=`${MDDBREQ} ${DB_FILE} query get - /rbt/mfd/store/mdraid2`
            fi

            if [ "x${DUAL}" = "xfalse" ]; then
                echo "Output of ${SMARTCMD} ${disk1:0:8} :"
                echo "`${SMARTCMD} ${disk1:0:8} 2>&1`"
                echo ""
            else
                echo "Output of ${SMARTCMD} ${disk1:0:8} :"
                echo "`${SMARTCMD} ${disk1:0:8} 2>&1`"
                echo ""
            fi
            echo ""
            ;;
    esac
}

# The exit values for the health script will be interpreted as follows:
#       0 is 'UNKNOWN'.
#       2 is 'OK - all is good'.
#       3 is 'Degraded - Action may be needed further evaluation'
#       4 is 'Minor - Action is needed, however service is running'
#       5 is 'Major - Immediate Action is required'
#       6 is 'Critical - Immediate Action or imminent outage will occur'
#       7 is 'Fatal/NonRecoverable - too late for remedial action'

function check_health() {

echo
echo "\$ Health Check"
eval $1
HEALTH=$? 

if [ "$HEALTH" -eq "0" ]
then
	echo "Health is UNKNOWN"
elif [ "$HEALTH" -eq "2" ]
then
	echo "Health is Good"
elif [ "$HEALTH" -eq "3" ]
then
	echo "Health is Degraded.  Further analysis should be done"
elif [ "$HEALTH" -eq "4" ]
then
	echo "Health has Minor problem. Action is needed, however service is running "
elif [ "$HEALTH" -eq "5" ]
then
	echo "Health has Major problem. Immediate Action is needed "
elif [ "$HEALTH" -eq "6" ]
then
	echo "Health has Major Problem, Immediate Attention is required"
elif [ "$HEALTH" -eq "7" ]
then
	echo "Health is FATAL/NonRecoverable"
else 
	echo "Health is $HEALTH"
fi

# print out error log is not OK

if [ "$HEALTH" -ne "2" ]
then
	cat_file "/var/log/healthcheck.log"
fi
}




#Make sure EUID 0 runs this script
if [ `id -u` != "0" ]
then
	echo "You must be logged in as a superuser" 
exit
fi

PLATFORM=`uname -m`
OS=`uname -s`
SM_DISK_HD=`mount | awk ' / \/ / { print $1 }'`

# for now the script works on Linux
if [ "$OS" != "Linux" ]
then
	echo "This is currently only supported on Linux"
exit
fi

echo "================================================="
echo " General Information "
echo "================================================="
echo 
parse_command "uname" "-a " "uname"
cat_file "/proc/version"
parse_command "runlevel" " " "runlevel"
cat_file "/etc/lsb-release"
parse_command "hostname" " " "/bin/hostname"
parse_command "date" " " "/bin/date"
cat_file "/proc/cpuinfo"
cat_file "/proc/meminfo"
parse_command "df" "-hTal " "Local Disk"
cat_file "/proc/devices"
parse_command "lspci" "-v " "lspci"
cat_file "/etc/issue"
cat_file "/etc/motd"
parse_command "uptime" " " "uptime"
parse_command "w" "-h | user2uid.pl " "Who is on the system now"
parse_command "last" "| user2uid.pl " "Who has been on the system recently"

echo
echo "================================================="
echo " Resource Statistics"
echo "================================================="
echo 

parse_command "iostat" "-c " "CPU iostat"
parse_command "sar" "-A " "sar"
parse_command "vmstat" "-s " "vmstat"
cat_file "/proc/diskstats"
parse_command "iostat" "-d " "Disk iostat"
parse_command "iostat" "-xd " "Disk extended iostat"
cat_file "/proc/interrupts"



echo
echo "================================================="
echo " Network Information "
echo "================================================="
echo 


parse_command "ifconfig" "-a " "ifconfig "
parse_command "route" "-nee " "Route Table "

for NIC in `ifconfig -a |grep eth | awk '{print $1}'`
do
parse_command "ethtool"  "$NIC" "Settings for $NIC"
parse_command "ethtool"  "-S $NIC" "Statistics for $NIC"
done

#parse_command "smartctl" "-a $SM_DISK_HD" "Hard disk S.M.A.R.T. log"
show_smart_data_smartctl

# Change:  Scotty - 9-July-2008
# Commenting out Logging for now.  there is a 'Show Logging'
# command now that displays ESPD logs.  I will leave this in
# as a placeholder for a future dump of non ESPD logs.  For
# example, a logwatch summary output.
# echo
# echo "================================================="
# echo " Logs Summary"
# echo "================================================="
# echo 

# cat_file "/var/log/espd"
# cat_file "/var/log/espd.1"

echo
echo "================================================="
echo " Health Information "
echo "================================================="
echo 

check_health "healthcheck.sh"

echo
echo

