#!/bin/sh 

status=`/opt/tms/bin/mdreq -b query pattern_match - /rbt/sport/fcip/config/rule/src_ip/*/dst_ip/*/dif_settings/enable | awk ' {printf("%s ", $3);}'`

blks=`/opt/tms/bin/mdreq -b query pattern_match - /rbt/sport/fcip/config/rule/src_ip/*/dst_ip/*/dif_settings/block_size | awk ' {printf("%s ", $3);}'`

ret=0
set $blks
for s in $status; do
    if [ "$s" = 'true' ]; then
	case "$1" in
	512)
		if [ $ret -eq '0' ]; then
			ret=1;
		else if [ $ret -ne '1' ]; then
			ret=3; #mixed
		     fi;
		fi;;
	520)
		if [ $ret -eq '0' ]; then
			ret=2;
		else if [ $ret -ne '2' ]; then
			ret=3; #mixed
		     fi;
		fi;;
	*) ;;
	esac
    fi
    shift
done

case "$ret" in
    0) echo "none";;
    1) echo "512";;
    2) echo "520";;
    *) echo "mixed";;
esac


