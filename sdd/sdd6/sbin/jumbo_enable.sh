lan_if=`/sbin/get_bridge_ifaces.sh lan`
wan_if=`/sbin/get_bridge_ifaces.sh wan`

for if_name in $lan_if $wan_if
do
    mtu=`/sbin/ifconfig $if_name | egrep -o "MTU:[0-9]+" | cut -d ":" -f 2`
    if (($mtu>1500)); then
        echo "1"
        exit
    fi
done

echo "0"
