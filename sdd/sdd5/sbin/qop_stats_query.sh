#!/bin/sh
#
# Get QOP stats.
# Valid arguments are
# 1. num_qop_configured
# 2. num_gateway_configured
# 3. num_dscp_configured
# 4. rules_with_path_configured
# 5. num_drop_traffic_configured
# 6. qop_to_wan_bytes_percentage 
# 7. dscp_only
# 8. ricochet_no_relay_mismatch
# 9. ricochet_any_relay

path_none=4294967295
path_drop=`expr $path_none - 2`

function get_num_qop_paths {
    num_qops=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/pathmon/qop/config/path/* | wc -l`
    echo $num_qops
}     
 
function get_num_gateways {
    num_gw=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/pathmon/qop/config/path/*/gateway_ip | wc -l`
    count=0 
    for ((i=1; i<=$num_gw; i++))
    do
        is_def_gw=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/pathmon/qop/config/path/$i/gateway_ip | grep 0.0.0.0`
	if [ "$is_def_gw" ]; then
	   continue
	fi
	count=`expr $count + 1`
    done
    echo $count
}     
 
function get_num_dscps {
    num_dscp=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/pathmon/qop/config/path/*/probe_dscp | wc -l`
    dscp_count=0
    for ((i=1; i<=$num_dscp; i++))
    do
        dscp=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/pathmon/qop/config/path/$i/probe_dscp | grep 0`
        if [ "$dscp" ]; then
           continue
        fi
        dscp_count=`expr $dscp_count + 1`
    done
    echo $dscp_count
}     
 
# Get number of qop paths configured for QOS rules
function get_rules_with_path_configured {
    num_sites=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/hfsc/config/site/* | wc -l`
    path_configured=0
    for ((i=1; i<=$num_sites; i++))
    do
        num_filters=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/hfsc/config/site/$i/filter/* | wc -l`
        for ((j=1; j<=$num_filters; j++))
        do
            num_paths=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/hfsc/config/site/$i/filter/$j/paths/* | wc -l`
            # at least one path configured
            if [ "$num_paths" -ne "0" ]; then
                path_configured=`expr $path_configured + 1`
            fi 
        done
    done             
    echo $path_configured
}

function get_num_drop_traffic {
    num_sites=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/hfsc/config/site/* | wc -l`
    drop_count=0
    for ((i=1; i<=$num_sites; i++))
    do
        def_paths=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/hfsc/config/site/1/filter/*/default_path`

        for cnt in $def_paths; do
            if [ $cnt == $path_drop ]; then
                drop_count=`expr $drop_count + 1`
            fi
        done
    done
    echo $drop_count
}

function get_qop_to_wan_bytes_percentage {
    lines=`cat /proc/rbtqosmod/features/qop/paths/stats |awk '$1 ~ /^bytes$/' | sed  "s/ //g" | cut -d "s" -f 2`
    
    total_qop_byte_count=0
    for cnt in $lines; do
        total_qop_byte_count=`expr $total_qop_byte_count + $cnt`
    done    

    total_wan_byte_count=0
    lines=`/opt/tms/bin/mdreq -v query pattern_match - /net/interface/state/* |
grep wan`
    for wan_intf in $lines; do
        wan_byte_count=`/opt/tms/bin/mdreq -v query pattern_match - /net/interface/state/$wan_intf/stats/tx/bytes`
        total_wan_byte_count=`expr $total_wan_byte_count + $wan_byte_count`
    done

    echo $(( $total_qop_byte_count * 100 / $total_wan_byte_count ))
}

function get_dscp_only {
    enabled=`cat /proc/sys/rbtqosmod/qop/dscp_only`
    echo $enabled
}

function get_ricochet_no_relay_mismatch {
    enabled=`cat /proc/sys/rbtqosmod/qop/ricochet_no_relay_mismatch`
    echo $enabled
}

function get_ricochet_any_relay {
    enabled=`cat /proc/sys/rbtqosmod/qop/ricochet_any_relay`
    echo $enabled
}

if [ $# -eq 1 ]; then

    if [ $1 == "num_qop_configured" ]; then
        get_num_qop_paths
    elif [ $1 == "num_gateway_configured" ]; then
        get_num_gateways
    elif [ $1 == "num_dscp_configured" ]; then
        get_num_dscps
    elif [ $1 == "rules_with_path_configured" ]; then
        get_rules_with_path_configured
    elif [ $1 == "num_drop_traffic_configured" ]; then
        get_num_drop_traffic
    elif [ $1 == "qop_to_wan_bytes_percentage" ]; then
        get_qop_to_wan_bytes_percentage
    elif [ $1 == "dscp_only" ]; then
        get_dscp_only
    elif [ $1 == "ricochet_no_relay_mismatch" ]; then
        get_ricochet_no_relay_mismatch
    elif [ $1 == "ricochet_any_relay" ]; then
        get_ricochet_any_relay
    fi

fi
