#! /bin/sh
#
# Description
# ----------------------------------------------------------------------
# Script to deal with auto-negotiation problem on the SH100s where they
# fail to auto-negotiate about 4% of the time. Basically, the Intel 
# 10/100 NICs weren't very good at auto-negotiating. The workaround
# basically restarts auto-negotiation if the interface is in the right
# state. The right state means:
#
#   * Does not have link
#   * Not in bypass for an inpath interface
#   * Interface is up
#   * Interface is set to auto-negotiate
#
# This is tracked as bug 26457.
#
# Testing:
# ----------------------------------------------------------------------
# Test code is integrated into this script. To run the test, start the
# script normally to begin tracking the interfaces. In the image, this
# will be the default for affected units (SH100 rev A and rev B). To
# start the script manually, and enable debugging, you can do this:
# 
#   killall dtaa-net.sh
#   debug=1 /sbin/dtaa-net.sh
#
# Then, run the test script:
#
#   dtaa-net.sh test
#
# This will use bypass controls to cause link to go up and down
# It temporarily suspends the processes that poll the watchdog
# in different versions (wdt and sport), then puts the system into
# bypass, waits for a couple seconds, then pulls it back out, and
# waits for 30 seconds more before checking if the renegotiation
# has succeeded. This simulates externally induced link loss, and
# it does trigger the problem. The number of times it finds a
# permanent auto-negotiation failure is printed in this kind of manner:
#
#   Fri Jun 27 10:40:37 PDT 2008: Good: 286   Bad: 0
#   Fri Jun 27 10:41:07 PDT 2008: Good: 287   Bad: 0
#   Fri Jun 27 10:41:36 PDT 2008: Good: 288   Bad: 0
#
# To compare to a system that is not running the auto-negotiation script,
# kill the non-test version of the script first:
#   killall dtaa-net.sh
# Then run the test script:
#   dtaa-net.sh test
# You should see some percentage of Bad results.
#
# Test cases to cover:
# * interface is configured down
# * interface has speed and duplex hard coded
# * interface loses link and regains it
# * system startup
# * Checks on all interfaces: lan0_0, wan0_0, primary, and aux

PATH=/opt/tms/bin:/opt/rbt/bin:/sbin:/usr/sbin:/bin:/usr/bin
export PATH

# To get messages logged to /var/log/messages that would show when
# the unit restarted auto-negotiation, set debug=1.
debug=${debug:=0}
export debug

# This is how long to delay before checking again after getting link.
# For test purposes, it is good to set this to 5.
delay_after_link=15

# If we haven't found link on a properly setup interface, then this
# is the delay to use.
delay_after_no_link=5

#
# Check if this is a hardware platform where we need to do this
# Only do it on models DTAAA and DTABA.
#
hwtool -q motherboard | egrep 'CMP-00097|400-00011' > /dev/null 2>/dev/null
if [ $? -ne 0 ]; then
    exit 0
fi

track_inpath_ifaces() {
    #
    # Check if the unit is in bypass or not
    #
    prevstatus=None
    while :; do
	sleeptime=$delay_after_no_link

	status=`na0043_ctl bypass_status | grep Status | awk '{print $3;}'`
	if [ $status = "Normal" -a $prevstatus = "Normal" ]; then
	    status=`check_iface lan0_0 $status`
	    status=`check_iface wan0_0 $status`
	    if [ $status = "Normal" ]; then
		sleeptime=$delay_after_link
	    fi
	fi

	prevstatus=$status
	sleep $sleeptime
    done
}

track_mgmt_ifaces() {
    prevstatus=None

    ip link show prihw 2>/dev/null
    if [ $? -eq 0 ]; then
	primary_iface=prihw
    else
	primary_iface=primary
    fi

    while :; do
	sleeptime=$delay_after_no_link

	status=Normal
	if [ $status = "Normal" -a $prevstatus = "Normal" ]; then
	    status=`check_iface $primary_iface $status`
	    status=`check_iface aux $status`
	    if [ $status = "Normal" ]; then
		sleeptime=$delay_after_link
	    fi
	fi

	prevstatus=$status
	sleep $sleeptime
    done
}

#
# Arguments:
#   iface: The interface to check on. Nothing is done under when the
#          interface the interface has link, is set to use fixed
#          speed and duplex, or is configured down.
#   status: The current status. If the interface being checked on has nothing
#           wrong with it, just return the passed in status. If there is
#           something wrong with the interface, then restart auto-negotiation
#           and return "Resetting"
# Results
#   Either the passed in status or "Resetting"
#
check_iface() {
    local iface=$1
    local status=$2
    local down
    local link
    local autoneg

    ifconfig $iface | egrep '^[ \t]*UP' > /dev/null 2>&1
    down=$?
    link=`ethtool $iface | grep 'Link detected' | awk '{print $3;}'`
    autoneg=`ethtool $iface | grep 'Advertised auto-negotiation' | awk '{print $3;}'`

    if [ "$link" = "yes" ]; then
	return $status
    fi
    if [ "$autoneg" != "Yes" ]; then
	return $status
    fi
    if [ $down -eq 1 ]; then
	return $status
    fi

    #
    # Reset chip and restart auto-negotiation. The chip reset by doing
    # an offline self-test is a hack, but for some reason, crossover
    # cable detection is not working since 5.0.x without downing and
    # upping the interface again.
    #
    ethtool -t $iface > /dev/null 2>&1
    ethtool -r $iface
    if [ "$debug" -eq 1 ]; then
	logger -t e100_check.NOTICE -p user.notice "$iface: Restarting auto-negotiation"
    fi
    return "Resetting"
}

#
# This is a test routine that can be launched to test the functionality on
# the inpath interfaces. It works by playing with bypass control. It does
# not validate the mgmt interfaces since the problem appears to show up
# when the interfaces lose link and regain link not via ifconfig down and up
# but by some other factor.
#
run_unit_test() {
    good=0
    bad=0
    while :; do
	killall -STOP wdt 2>/dev/null
	killall -STOP sport 2>/dev/null
	/opt/rbt/bin/na0043_ctl wdt_disable > /dev/null
	/opt/rbt/bin/na0043_ctl bypass > /dev/nulls
	sleep 2
	lanstate=`ethtool lan0_0 | grep Link | awk '{print $3;}'`
	wanstate=`ethtool wan0_0 | grep Link | awk '{print $3;}'`

	if [ "$lanstate" = "yes" -o "wanstate" = "yes" ] ; then
	    echo "ERROR: Getting link unexpectedly"
	    exit 1
	fi

	/opt/rbt/bin/na0043_ctl nobypass > /dev/nulls
	/opt/rbt/bin/na0043_ctl wdt_enable > /dev/null
	/opt/rbt/bin/na0043_ctl poll > /dev/null
	killall -CONT wdt 2>/dev/null
	killall -CONT sport 2>/dev/null

	sleep 30

	lanstate=`ethtool lan0_0 | grep Link | awk '{print $3;}'`
	wanstate=`ethtool wan0_0 | grep Link | awk '{print $3;}'`

	if [ "$wanstate" = "yes" -o "$lanstate" = "yes" ]; then
	    good=`expr $good + 1`
	else
	    bad=`expr $bad + 1`
	fi

	d=`date`
	echo "$d: Good: $good   Bad: $bad"
	sleep 2
    done
}

if [ "x$1" = "xtest" ]; then
    run_unit_test
elif [ "x$1" = "xmgmt" ]; then
    track_mgmt_ifaces
elif [ "x$1" = "xinpath" ]; then
    track_inpath_ifaces
elif [ "x$1" = "x" ]; then
    nohup dtaa-net.sh inpath > /dev/null 2>&1 &
    nohup dtaa-net.sh mgmt > /dev/null 2>&1 &
else
    echo "Usage: dtaa-net.sh ?[mgmt|inpath|test]?"
    exit 1
fi
exit 0
