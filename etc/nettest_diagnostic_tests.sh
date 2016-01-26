#!/bin/sh
#
# Run Nettest Gateway Test
#
# Copyright (C) 2006 Riverbed Technology, Inc.
# All right reserved.
#
###############################################################################
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

if [ $# -eq 0 ]; then
    ## This script should have atleast one parameter
    ## -i --interface
    ## -a --ip address
    ## -p --port
    ## -v6 --ipv6 test
    ## Usage: nettest_diagnostic_tests.sh -t -i -a -p -v6
    exit 1
fi

GATEWAY_TEST=0
CABLE_SWAP_TEST=1
DUPLEX_TEST=2
PEER_REACH_TEST=3
IP_PORT_REACH_TEST=4

MDREQ=/opt/tms/bin/mdreq
ARP=/sbin/arp
GREP=/bin/grep
TPROXYTRACE=/usr/sbin/tproxytrace
MAC_TAB_LOCATION=/proc/er
CONN_TABLE_LOC=/proc/nbt/0/connection_table

PEER_PORT=7801
TEST_PASSED=passed
TEST_FAILED=failed
TEST_NUM=$2
interface=$4
ip_addr=$6
port=$8
IPV6=${10}

DEFAULT_INPATH_GW="/rbt/route/state"
if [ "x$IPV6" != "xtrue" ]; then
PING=/bin/ping
DEFAULT_GW_PREFIX="/net/routes/state/ipv4/prefix/0.0.0.0\\/0/nh"
DEFAULT_ADDR="0.0.0.0"
DEFAULT_INPATH_GW_PREFIX="/ipv4/prefix"
DEFAULT_STATIC_IFS="/net/routes/config/ipv4/prefix"
DEFAULT_STATIC_GW_PREFIX="/net/routes/config/ipv4/prefix"
else
PING=/bin/ping6
DEFAULT_GW_PREFIX="/net/routes/state/ipv6/prefix/::\\/0/nh"
DEFAULT_ADDR="::"
DEFAULT_INPATH_GW_PREFIX="/ipv6/prefix"
DEFAULT_STATIC_IFS="/net/routes/config/ipv6/prefix"
DEFAULT_STATIC_GW_PREFIX="/net/routes/config/ipv6/prefix"
fi

if [ $TEST_NUM -lt 0 -o $TEST_NUM -gt 4 ]; then
    echo "Not a valid test. Please try again later with a valid test number."
    exit 1
fi

## Run Gateway Nettest if the test num is 0
if [ "x$TEST_NUM" == "x$GATEWAY_TEST" ]; then
    ## Test the default gateway
    default_gateways=`$MDREQ -v query iterate - $DEFAULT_GW_PREFIX`
    for gateway in $default_gateways
    do
        default_addr=`$MDREQ -v query get - $DEFAULT_GW_PREFIX/$gateway/gw`
        default_metric=`$MDREQ -v query get - $DEFAULT_GW_PREFIX/$gateway/metric`
	default_dev=`$MDREQ -v query get - $DEFAULT_GW_PREFIX/$gateway/interface`
         if [ $default_metric -eq 1 ] && [ "x$default_addr" != "x$DEFAULT_ADDR" -a "x$default_addr" != "x" ]; then
	    if [ "x$default_dev" == "x" ]; then
              received=`$PING -c 4 $default_addr | grep 'received' | awk -F',' '{ print $2}' | awk '{ print $1}'`
	    else
	      received=`$PING -c 4 -I $default_dev $default_addr | grep 'received' | awk -F',' '{ print $2}' | awk '{ print $1}'`
	    fi
            lost=$((4-received))
            packet_loss=`echo $lost*100/4 | bc -l | cut -d. -f1`
            echo "Default $default_addr $packet_loss"
        fi
    done

    ## Test the other inpath gateways
    inpath_interfaces=`$MDREQ -v query iterate - $DEFAULT_INPATH_GW`

    if [ "x$inpath_interfaces" != "x" ]; then
        for interface in $inpath_interfaces
        do
            inpath_gateways=`$MDREQ -v query iterate - $DEFAULT_INPATH_GW/$interface$DEFAULT_INPATH_GW_PREFIX`
            for inpath_ip in $inpath_gateways
            do
                ip=`echo $inpath_ip | cut -d\/ -f1`
                subnet=`echo $inpath_ip | cut -d \/ -f2`
                inpath_gateway_ip=`$MDREQ -v query get - $DEFAULT_INPATH_GW/$interface$DEFAULT_INPATH_GW_PREFIX/$ip\\\/$subnet/gw`
                if [ "x$inpath_gateway_ip" != "x$DEFAULT_ADDR" ]; then
                    ## If the interface is wan or lan change it to inpath
                    is_wan_lan=${interface:0:3}
                    if [ "x$is_wan_lan" == "xwan" -o "x$is_wan_lan" == "xlan" ]; then
                        str_len=${#interface}
                        interface="inpath"${interface:3:$str_len}
                    fi
                    received=`$PING -c 4 -I $interface $inpath_gateway_ip | grep 'received' | awk -F',' '{ print $2}' | awk '{ print $1}'`
                    lost=$((4-received))
                    packet_loss=`echo $lost*100/4 | bc -l | cut -d. -f1`
                    echo "$interface $inpath_gateway_ip $packet_loss"
                fi
            done
        done
    fi 

    ## Test the static route gateways
    static_interfaces=`$MDREQ -v query iterate - $DEFAULT_STATIC_IFS`
    if [ "x$static_interfaces" != "x" ]; then
        for interface in $static_interfaces
        do
            addr=`echo $interface | cut -d\/ -f1`
            subnet=`echo $interface | cut -d\/ -f2`
            static_gateways_count=`$MDREQ -v query iterate - $DEFAULT_STATIC_GW_PREFIX/$addr\\\/$subnet/nh`
            for static_gateway in $static_gateways_count
            do
                ip_addr=`$MDREQ -v query get - $DEFAULT_STATIC_GW_PREFIX/$addr\\\/$subnet/nh/$static_gateway/gw`
		dev=`$MDREQ -v query get - $DEFAULT_STATIC_GW_PREFIX/$addr\\\/$subnet/nh/$static_gateway/interface`
                if [ "x$ip_addr" != "x$DEFAULT_ADDR" -a "x$ip_addr" != "x$default_addr" ]; then
		    if [ "x$dev" == "x" ]; then
                    	received=`$PING -c 4 $ip_addr | grep 'received' | awk -F',' '{ print $2}' | awk '{ print $1}'`
		    else
			received=`$PING -c 4 -I $dev $ip_addr | grep 'received' | awk -F',' '{ print $2}' | awk '{ print $1}'`
		    fi	
                    lost=$((4-received))
                    packet_loss=`echo $lost*100/4 | bc -l | cut -d. -f1`
                    echo "Static $ip_addr $packet_loss"
                fi
            done
        done
    fi 
fi

## Run Duplex Nettest if the test num is 2.
## This test accepts interface and the target ip address as parameters.
if [ "x$TEST_NUM" == "x$DUPLEX_TEST" ]; then
    is_wan_lan=${interface:0:3}
    run_nettest_verify_interface=n
    if [ "x$is_wan_lan" == "xwan" -o "x$is_wan_lan" == "xlan" ]; then
        str_len=${#interface}
        interface="inpath"${interface:3:$str_len}
        run_nettest_verify_interface=y
    fi
    if [ "x$interface" != "xdefault" -a "x$ip_addr" != "xdefault" ]; then
        collisions=`$MDREQ -v query get - /net/interface/state/$interface/stats/tx/collisions`
        carrier=`$MDREQ -v query get - /net/interface/state/$interface/stats/tx/carrier`
        frame=`$MDREQ -v query get - /net/interface/state/$interface/stats/rx/frame`
        rx_error=`$MDREQ -v query get - /net/interface/state/$interface/stats/rx/errors`
        tx_error=`$MDREQ -v query get - /net/interface/state/$interface/stats/tx/errors`

        start_total=$[collisions+carrier+frame+rx_error+tx_error]

        ping_flood=`$PING -I $interface -s 2500 -w 10 -f $ip_addr`
        sleep 15
        received=`$PING -c 4 -I $interface $ip_addr | grep 'received' | awk -F',' '{ print $2}' | awk '{ print $1}'`
        lost=$((4-received))
        packet_loss=`echo $lost*100/4 | bc -l | cut -d. -f1`

        if [ "x$packet_loss" == "x100" ]; then
            echo "$interface Unreachable "
            exit 0
        fi
        ## If the interface is wan or lan run nettest verify interface
        if [ "x$run_nettest_verify_interface" == "xy" ]; then
            target_mac_addr=`$ARP -na | grep -E $ip_addr | grep -E $interface | cut -d' ' -f4`
            interface_found=`$GREP -ri $target_mac_addr $MAC_TAB_LOCATION | $GREP -E $interface`
            if [ "x$interface_found" == "x" ]; then
                echo "$interface Wrong_interface "
                exit 0
            fi
        fi

        collisions=`$MDREQ -v query get - /net/interface/state/$interface/stats/tx/collisions`
        carrier=`$MDREQ -v query get - /net/interface/state/$interface/stats/tx/carrier`
        frame=`$MDREQ -v query get - /net/interface/state/$interface/stats/rx/frame`
        rx_error=`$MDREQ -v query get - /net/interface/state/$interface/stats/rx/errors`
        tx_error=`$MDREQ -v query get - /net/interface/state/$interface/stats/tx/errors`

        end_total=$[collisions+carrier+frame+rx_error+tx_error]
        echo "$interface $[end_total - start_total] "
    fi
fi

## Run Peer Reachability test if the test num is 3
## This test accepts target ip address as parameter
if [ "x$TEST_NUM" == "x$PEER_REACH_TEST" ]; then
    success=n
    if [ "x$ip_addr" != "xdefault" ]; then
        interface_list=(primary aux)
        # Get the list of in-path interfaces
        inpath_list=`$MDREQ -v query iterate - /rbt/route/state`

        # Append in-path interfaces to interface-list
        for interface in $inpath_list
        do
            interface_list=("${interface_list[@]}" $interface)
        done

        # For each interface run peer reachability nettest
        for interface in "${interface_list[@]}"
        do
            peer_test_result=`$TPROXYTRACE -d 10 -i $interface $ip_addr:$PEER_PORT`
            peer_found=`echo $peer_test_result | grep -E "proxy $ip_addr:7800"`
            if [ "x$peer_found" != "x" ]; then
                success=y
                echo "$ip_addr $interface $TEST_PASSED"
            fi
        done
        if [ "x$success" != "xy" ]; then
            echo "$ip_addr none $TEST_FAILED"
        fi
    fi
fi

## Run IP Port Reachability test if the test num is 4
## This test accepts ip address and port as parameters.
if [ "x$TEST_NUM" == "x$IP_PORT_REACH_TEST" ]; then
    if [ "x$interface" == "xdefault" -o "x$ip_addr" == "xdefault" ]; then
        ## Do nothing if these parameters are not passed.
        exit 0
    fi
    ## If port is not passed run ping utility to confirm the reachability
    if [ "x$port" == "xdefault" ]; then
        received=`$PING -c 4 -I $interface $ip_addr | grep 'received' | awk -F',' '{ print $2}' | awk '{ print $1}'`
        lost=$((4-received))
        packet_loss=`echo $lost*100/4 | bc -l | cut -d. -f1`
        protocol=ICMP
        if [ "x$packet_loss" == "x0" ]; then
            echo "$interface $ip_addr $protocol $TEST_PASSED"
        else
            echo "$interface $ip_addr $protocol $TEST_FAILED"
        fi
    else
    ## Run netcat addr utility if addr and port are passed.
    ## Extract the source interface ip address
        protocol=Netcat
        ## Output of this command is sent to mgmtd for further processing.
        if [ "x$IPV6" == "xtrue" ]; then
            ## exclude linklocal address since netcat cannot bind linklocal address
            source_ips=`ifconfig $interface | grep 'inet6 addr' |grep -v 'fe80'| cut -d/ -f1 | cut -d' ' -f13`
            echo "$interface [$ip_addr]:$port $protocol"
	    for source_ip in $source_ips
     	    do
                if [ "x$source_ip" != "x" ]; then
                    nc -v -w 2 -z -s $source_ip $ip_addr $port | grep 'succeeded'
                fi
            done
            exit 0
        else
            source_ip=`ifconfig $interface | grep 'inet addr' | cut -d: -f2 | cut -d' ' -f1`
            if [ "x$source_ip" != "x" ]; then
                echo "$interface $ip_addr:$port $protocol"
                nc -v -w 2 -z -s $source_ip $ip_addr $port | grep 'succeeded'
                exit 0
            fi
        fi
    fi
fi
