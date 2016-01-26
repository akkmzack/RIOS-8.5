#!/bin/sh
#
# Get qos stats.
# Valid arguments are
# 1. num_ob_sites
# 2. num_ob_rules
# 3. num_ob_classes
# 4. num_ib_rules
# 5. num_ib_classes
# 6. adv_mode_state


# Get num of outbound sites.
#

function get_num_outbound_sites {
    num_sites=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/hfsc/config/site/* | wc -l`
    echo $num_sites
}

# Get num of outbound rules.
#
function get_num_outbound_rules {
    num_rules=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/hfsc/config/site/*/filter/* | wc -l`
    echo $num_rules
}

# Get num of outbound classes.
#
function get_num_outbound_classes {
    num_classes=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/hfsc/config/class/* | wc -l`
    echo $num_classes
}

# Get num of inbound rules.
#
function get_num_inbound_rules {
    num_rules=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/qos/inbound/config/filter/* | wc -l`
    echo $num_rules
}

# Get num of inbound classes.
#
function get_num_inbound_classes {
    num_classes=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/qos/inbound/config/class/* | wc -l`
    echo $num_classes
}

# Is Adv QoS Mode due to migration or upgrade.
# Returns - 0 - If in basic qos mode
#         - 1 - If in adv mode due to upgrade
#         - 2 - If in adv mode due to migration from basic mode
#
function get_adv_mode_state {
    easy_qos_mode=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/hfsc/config/global/easy_qos_mode`
    if [ $easy_qos_mode = "false" ]; then
        num_gapps=`/opt/tms/bin/mdreq -v query get - /rbt/hfsc/config/global_app/1 | wc -l`
        if [ $num_gapps = 0 ]; then
            echo "1"
        else
            echo "2"
        fi
    else
        echo "0"
    fi
}

if [ $# -eq 1 ]; then

    if [ $1 == "num_ob_sites" ]; then
        get_num_outbound_sites
    elif [ $1 == "num_ob_rules" ]; then
        get_num_outbound_rules
    elif [ $1 == "num_ob_classes" ]; then
        get_num_outbound_classes
    elif [ $1 == "num_ib_classes" ]; then
        get_num_inbound_classes
    elif [ $1 == "num_ib_rules" ]; then
        get_num_inbound_rules
    elif [ $1 == "adv_mode_state" ]; then
        get_adv_mode_state
    fi

fi
