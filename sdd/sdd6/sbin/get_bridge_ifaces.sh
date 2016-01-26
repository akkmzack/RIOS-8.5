#!/bin/sh
#
# This script goes through and returns a string containing
# the bridge interfaces on this appliance.
#
# Valid types (argument #1) are: 'lan', 'wan', and 'inpath'.
#
# NOTE: If you change the file name "get_bridge_ifaces.sh" or make this script
# obsolete, make corresponding change to
# - /mgmt/framework/src/base_os/common/script_files/jumbo_enable.sh
#

if [ x$1 = x ]; then
    TYPE=inpath
else
    TYPE=$1
fi

IFACE_PATTERN="^${TYPE}.*_.*"

INTERFACES=`/sbin/ifconfig -a | \
            /bin/grep "Link encap:Ethernet" | \
            /bin/sed -e "s,\(.*\)Link.*,\1," | \
            /bin/sort`

MATCHING_INTERFACES=""

for IFACE in $INTERFACES; do
    if echo $IFACE | /bin/grep -e "$IFACE_PATTERN" > /dev/null; then
        MATCHING_INTERFACES="$MATCHING_INTERFACES $IFACE"
    fi
done

echo $MATCHING_INTERFACES
