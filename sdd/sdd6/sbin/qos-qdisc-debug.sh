#!/bin/sh

TC_UTIL="/sbin/tc"
TYPE=""
ACTION=""

CLASSIFICATION_QDISC="hfsc"
DSCP_QDISC="dsmark"
DSCP_QDISC_HANDLE="2:0"
ROOT_QDISC=$DSCP_QDISC
ROOT_QDISC_HANDLE=$DSCP_QDISC_HANDLE

#
# $1 == interface name
# $2 == action (show | delete)
# $3 == type (dscp | classification)
# $4 == classification qdisc handle (inbound, outbound)
# All parameters are required.
if [ "$1" == "" ] || [ "$2" == "" ] || [ "$3" == "" ] || [ "$4" == "" ]; then
    echo "Usage: $0 <ifname> <action> <type> <qdisc handle>"
    echo "  where, action = { show | delete }"
    echo "         type   = { dscp | classification }"
    echo "         qdisc handle   = { 1:0 | 8000:0 }"
    exit 1
fi

ACTION="$2"
TYPE="$3"
CLASSIFICATION_QDISC_HANDLE="$4"

case "$TYPE" in 
    classification)
        case "$ACTION" in 
            delete)
                # This has the same effect as disabling QoS classification.
                if [ "$CLASSIFICATION_QDISC_HANDLE" == "8000:0" ]; then
                    #Handle deletion of ingress qdisc
                    $TC_UTIL qdisc del ingress dev $1 root handle $CLASSIFICATION_QDISC_HANDLE
                else
                    $TC_UTIL qdisc del dev $1 parent $ROOT_QDISC_HANDLE handle $CLASSIFICATION_QDISC_HANDLE
                fi
                ;;
            show)
                watch -n 1 --no-title $TC_UTIL -s -d qdisc show dev $1
                ;;

            *)
                echo "$0: Invalid action: $ACTION"
                exit 1
                ;; 
        esac 
        ;;
    dscp)
        case "$ACTION" in 
            delete)
                $TC_UTIL qdisc del dev $1 root
                ;;

            show)
                watch -n 1 --no-title $TC_UTIL -s -d qdisc show dev $1
                ;;
            
            *)
                echo "$0: Invalid action: $ACTION"
                exit 1
                ;;
        esac
        ;;
    *)
        echo "$0: Invalid type: $QDISC_TYPE"
        exit 1
        ;;
esac
