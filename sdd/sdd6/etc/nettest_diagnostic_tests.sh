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
    ## Usage: nettest_run.sh -t -i -a -p
    exit 1
fi

GATEWAY_TEST=0
CABLE_SWAP_TEST=1
DUPLEX_TEST=2
PEER_REACH_TEST=3
IP_PORT_REACH_TEST=4

MDREQ=/opt/tms/bin/mdreq
PING=/bin/ping
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

if [ $TEST_NUM -lt 0 -o $TEST_NUM -gt 4 ]; then
    echo "Not a valid test. Please try again later with a valid test number."
    exit 1
fi

## Run Gateway Nettest if the test num is 0
if [ "x$TEST_NUM" == "x$GATEWAY_TEST" ]; then
    ## Test the default gateway
    default_addr=`$MDREQ -v query get - /net/routes/state/ipv4/prefix/0.0.0.0\\\\/0/nh/1/gw`
    received=0

    if [ "x$default_addr" != "x0.0.0.0" ]; then
        received=`ping -c 4 $default_addr | grep 'received' | awk -F',' '{ print $2}' | awk '{ print $1}'`
        lost=$((4-received))
        packet_loss=`echo $lost*100/4 | bc -l | cut -d. -f1`
        echo "Default $default_addr $packet_loss"
    fi

    ## Test the other inpath gateways
    inpath_interfaces=`$MDREQ -v query iterate - /rbt/route/state`

    if [ "x$inpath_interfaces" != "x" ]; then
        for interface in $inpath_interfaces
        do
            inpath_gateways=`$MDREQ -v query iterate - /rbt/route/state/$interface/ipv4/prefix`
            for inpath_ip in $inpath_gateways
            do
                ip=`echo $inpath_ip | cut -d\/ -f1`
                subnet=`echo $inpath_ip | cut -d \/ -f2`
                inpath_gateway_ip=`$MDREQ -v query get - /rbt/route/state/$interface/ipv4/prefix/$ip\\\\/$subnet/gw`
                if [ "x$inpath_gateway_ip" != "x0.0.0.0" ]; then
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
    static_interfaces=`$MDREQ -v query iterate - /net/routes/config/ipv4/prefix`

    if [ "x$static_interfaces" != "x" ]; then
        for interface in $static_interfaces
        do
            addr=`echo $interface | cut -d\/ -f1`
            subnet=`echo $interface | cut -d\/ -f2`
            static_gateways_count=`$MDREQ -v query iterate - /net/routes/config/ipv4/prefix/$addr\\\\/$subnet/nh`
            for static_gateway in $static_gateways_count
            do
                ip_addr=`$MDREQ -v query get - /net/routes/config/ipv4/prefix/$addr\\\\/$subnet/nh/$static_gateway/gw`
                if [ "x$ip_addr" != "x0.0.0.0" -a "x$ip_addr" != "x$default_addr" ]; then
                    received=`$PING -c 4 $ip_addr | grep 'received' | awk -F',' '{ print $2}' | awk '{ print $1}'`
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
        tx_error=`$MDREQ -v query get - /net/interface/state/$interface/stats/rx/tx_errors`

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

        ## Convert the Target IP and the Interface IP to integers
        ## and verify if they are in the same subnet
        iface_ip=`$MDREQ -v query get - /net/interface/state/$interface/addr/ipv4/1/ip`
        mask=`$MDREQ -v query get - /net/interface/state/$interface/addr/ipv4/1/mask_len`

        ## This operation converts the IP addr to HEX format
        target_ip_hex=`printf "%02X" ${ip_addr//./ }`
        iface_ip_hex=`printf "%02X" ${iface_ip//./ }`

        ## This operation coverts IP addr from HEX to Integer format
        target_ip_int=`printf "%d" "0x"$target_ip_hex`
        iface_ip_int=`printf "%d" "0x"$iface_ip_hex`
        
        target_ip_int=$[target_ip_int >> (32 - mask)]
        iface_ip_int=$[iface_ip_int >> (32 - mask)]

        if [ "x$target_ip_int" != "x$iface_ip_int" ]; then
            echo "$interface Wrong_subnet "
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
        tx_error=`$MDREQ -v query get - /net/interface/state/$interface/stats/rx/tx_errors`

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
        source_ip=`ifconfig $interface | grep 'inet addr' | cut -d: -f2 | cut -d' ' -f1`
        if [ "x$source_ip" != "x" ]; then
            protocol=Netcat
            ## Output of this command is sent to mgmtd for further processing.
            echo "$interface $ip_addr:$port $protocol"
            `nc -v -w 2 -z -s $source_ip $ip_addr $port | grep 'open'`
            exit 0
        fi
    fi
fi 
