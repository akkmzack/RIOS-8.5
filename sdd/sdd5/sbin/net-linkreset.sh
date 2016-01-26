#!/bin/sh
# Description
# ----------------------------------------------------------------------------
# Script to deal with auto-negotiation issues observed on SteelHead Sturgeon,
# Gar, Redfin EX/CX and Minnows models, where the interface Link fails to
# come up when bypass switch is toggled. This issue has been seen only
# on-board Intel ethernet controllers. The workaround basically is to restart
# the auto-negotiation if the interfaces are in the right state shown below and
# the PHY fails to auto-negotiate and Link fails to come up.
#
# * Not in Bypass state
# * ethtool shows that Link is down
# * Interface is set to auto-negotiate
# * Interface is up
#
# For details refer bug #93712
# Testing:
#------------------------------------------------------------------
# while [ 1 ]
# do
#    lanlink=`ethtool lan0_0 | grep 'Link detected' | awk '{print $3}'`
#    wanlink=`ethtool wan0_0 | grep 'Link detected' | awk '{print $3}'`
#    if [[ $lanlink != "no" || $wanlink != "no" ]]; then
#       /opt/hal/bin/bypass_ctl -w lan0_0 bypass
#       /opt/hal/bin/bypass_ctl -w wan0_0 bypass
#    fi
#    sleep 40
#    lanlink=`ethtool lan0_0 | grep 'Link detected' | awk '{print $3}'`
#    wanlink=`ethtool wan0_0 | grep 'Link detected' | awk '{print $3}'`
#    if [[ $lanlink != "no" || $wanlink != "no" ]]; then
#         echo "link failure detected Link on lan0_0: $lanlink wan0_0: $wanlink"
#         exit
#    fi
#done
PATH=/opt/tms/bin:/opt/rbt/bin:/sbin:/usr/sbin:/bin:/usr/bin
export PATH

# This delay must be bigger than LSP poll interval which is 30sec.
# But blocking the traffic for longer period may not be acceptable.
# To be on safer, by default it is set to 5 sec
delay_between_link=5

# This delay is the poll interval to check any Link/Auto-negotiation failure
# condition.
delay_poll_interval=60

# This delay is for pm to launch all other threads, before the script
# starts checking for interface states.
# When PM is not started, the NICs will be in hardware bypass, and
# we won't trigger the bug #93712.
delay_pm_wait=180

# Check if this is a hardware platform where we need toto this
# Only do it Cx & Ex Redfins, Bagrumandi, Sturgeon, Gar and minnow models.

hwtool -q motherboard | egrep '425-00140-01|425-00205-01|400-00099-01|400-00098-01|400-00300-01|400-00300-10|400-00100-01' > /dev/null 2>/dev/null
if [ $? -ne 0 ]; then
    exit 0
fi
# 
# This issues is observed only on on-board ethernet interfaces
# List all the on-board interfaces
#
nic_list=`hwtool  -q mactab | grep [lw]an0_ | awk '{print $1}'`

#
# Argurment:
# iface: This interface is to check if nothing is broken, the NIC's bypass
#        state is normal, interface has the link, NIC interface is set to use
#        fixed speed and duplex, or NIC interface is configured down.
#
# Returns: 1 if nothing is required to be done and 0 if auto-negiation is
#          required to be restarted.
#
check_iface() {
    local iface=$1
    local link
    local down
    local autoneg
    local bypass

    bypass=`/opt/hal/bin/hal get_hw_if_status ${iface}`
    if [ "$bypass" != "Normal" ]; then
 	return 1
    fi
    link=`ethtool ${iface} | grep 'Link detected' | awk '{print $3}'`
    if [ "$link" != "no" ]; then
 	return 1
    fi
    autoneg=`ethtool ${iface} | grep 'Advertised auto-negotiation:' | awk '{print $3}'`
    if [ "$autoneg" != "Yes" ]; then
 	return 1
    fi
    ifconfig ${iface} | egrep '^[ \t]*UP' > /dev/null 2>&1
    down=$?
    if [ $down -eq 1 ]; then
 	return 1
    fi
  
    return 0
}


#
# This keeps polling the interfaces every 60sec to check for any incorrect
# interface state. If any incorrect interface state is detected, restart
# the auto-negotiation after double checking the interface states.
while [ 1 ]
do
    for an0 in ${nic_list}; do
	# Check if pm is running, if not wait for 180 seconds
	# for pm to enable other tasks.
	/sbin/pidof pm > /dev/null 2>&1
	if [ $? -ne 0 ]; then
	    sleep $delay_pm_wait
	    break
	fi
        check_iface $an0
        if [ $? -eq 0 ]; then
             # LSP polls every 30 sec and brings other pair of interface up/down
	     # Avoid conflicts with LSP if enabled, by sleeping for 5 sec.
             # Its better to sleep for 70 seconds to avoid any conflict with LSP
             # Min traffic block time : 10 sec
             # Max traffic block time : 60-70sec
             sleep $delay_between_link
             check_iface $an0
             if [ $? -eq 0 ]; then
	         ethtool -r $an0
             fi
         fi
    done
    sleep $delay_poll_interval
done
