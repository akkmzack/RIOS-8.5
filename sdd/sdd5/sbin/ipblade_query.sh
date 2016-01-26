# echo "1" - if at least 1 rule has all the following properties
#   a. rule-is-enabled
#   b. rule-is-ipblade
#   c. rule-protocol-matches-arg1
#
# echo "0" - no rule with all the above property was found.
function pm_proto_rules_enabled {
    nrules=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/sport/intercept/config/rule/* | wc -l`
    for ((i=1; i<=$nrules; i++))
    do
        rule_en=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/sport/intercept/config/rule/$i/enable | grep true`
        ipb_rule=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/sport/intercept/config/rule/$i/ipblade_enable | grep true`
        proto_en=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/sport/intercept/config/rule/$i/protocol | grep $1`
        if [ "$rule_en" -a "$ipb_rule" -a "$proto_en" ]; then
                echo "1"
                return
        fi
    done
    echo "0"
}

# echo "1" - if at least 1 rules has all the following properties
#   a. rule-is-enabled
#   b. rule-is-ipblade
#   c. rule-is-shared-tunnel
#
# echo "0" - no rule with all the above property was found. 
function pm_shared_tun_rules_enabled {
    nrules=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/sport/intercept/config/rule/* | wc -l`
    for ((i=1; i<=$nrules; i++))
    do
        rule_en=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/sport/intercept/config/rule/$i/enable | grep true`
        ipb_rule=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/sport/intercept/config/rule/$i/ipblade_enable | grep true`
        shared_tun=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/sport/intercept/config/rule/$i/tunnel_mode| grep shared`
        if [ "$rule_en" -a "$ipb_rule" -a "$shared_tun" ]; then
            echo "1"
            return
        fi
    done
    echo "0"
}

if [ $# -eq 1 ]; then
    if [ $1 == "pm_tcp_rules_enabled" ]; then
        pm_proto_rules_enabled tcp
    elif [ $1 == "pm_udp_rules_enabled" ]; then
        pm_proto_rules_enabled udp
    elif [ $1 == "pm_shared_tun_rules_enabled" ]; then
        pm_shared_tun_rules_enabled
    else
        exit -1
    fi
else
    exit -1
fi
