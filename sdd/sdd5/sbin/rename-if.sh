#!/bin/sh

#
# rename-if.sh
# $Id: rename-if.sh 29881 2008-02-20 00:05:25Z mschreiber $
#
# (C) Copyright 2003-2005 Riverbed Technology
#
# This shell script renames the given network interfaces with the
# given vendor prefix in the MAC address to lan, wan, etc..  It
# renames other interfaces to ceth0, ceth1, etc..
#
# The only command line option is the vendor prefix.  It defaults to
# "00:30:64|00:0C:BD|00:E0:ED|00:08:9B|00:90:FB"
#
# Required programs:
# /bin/sh
# /sbin/ifconfig
# /bin/sed
# /bin/grep
# /bin/sort
# /usr/bin/wc
# /usr/bin/uniq
# /sbin/nameif
# /usr/bin/expr
# /usr/bin/hexsub
#

export PATH=.:$PATH

rbt_prefix="00:0E:B6"

if [ x$1 = x ]; then
    # Adlink, Interface Masters, Silicom, ICP Electronics, Portwell
    vendor_prefix="00:30:64|00:0C:BD|00:E0:ED|00:08:9B|00:90:FB|(00:13:21:B4:[0-9A-F][BCDE])"
    vendor_prefix2="00:04:23" # Intel
else
    vendor_prefix=$1
    vendor_prefix2=
fi

uid=`/usr/bin/id -u`

#
# Call nameif if root, otherwise print a message.
#
call_nameif() {
    if [ $uid -eq 0 ]; then
	echo nameif $1 $2
	nameif $1 $2
    else
	echo You need to be root to execute nameif $1 $2
    fi
}

#
# Finds designated MAC addresses and set mac_addresses to that list.
# If there are more than four that match the vendor prefix (first parameter),
# then try to figure out which four match the next byte of the MAC address
# to figure out which ones are on a quad ethernet card and which are not.
#
# The second parameter determines whether to invert the matching (to find
# everything other than the designated MAC addresses or quad card).
#
# Known bugs:  If the fourth byte of the MAC addresses on the quad card
# and another interface is the same, this method could still fail.  Also,
# if a non-quad ethernet card that we are trying to match happens to have
# a MAC address prefix that is the same as one that we don't want to match,
# this method could fail.
#
find_macs_or_quad() {
    # Get the parameters, vendor prefix and whether to invert
    if [ x$1 != x ]; then
    	prefix=$1
    else
	prefix="00:30:64|00:C0:95|00:04:23"
    fi
    if [ x$2 != x ]; then
	invert=$2
    else
    	invert=0
    fi

    # Set the grep flag for inversion appropriately
    if [ $invert -ne 0 ]; then
    	invert_flag="v"
    else
    	invert_flag=""
    fi

    # Preset mac_addresses to those which match. 
    mac_addresses=`/sbin/ifconfig -a | \
		   /bin/grep "^eth.*Ethernet" | \
		   /bin/sed -e "s,.*HWaddr ,," | \
		   sort | \
		   /bin/grep -Ei$invert_flag "^($prefix)"`

    # Find out how many matching MAC addresses there are.
    count=`/sbin/ifconfig -a | \
	   /bin/grep "^eth.*Ethernet" | \
	   /bin/sed -e "s,.*HWaddr ,," | \
	   sort | \
	   /bin/grep -Ei "^($prefix)" | \
	   /usr/bin/wc -l`

    # If we have more than four, try to find the four (or more)
    # which have the same fourth byte in the MAC address.
    if [ $count -gt 4 ]; then
	uniq_macs=`/sbin/ifconfig -a | \
	    /bin/grep "^eth.*Ethernet" | \
	    /bin/sed -e "s,.*HWaddr ,," | \
	    /bin/grep -Ei "^($prefix)" | \
	    sort -t : -k 4,4 | \
	    uniq -s 9 -w 2 | \
	    /bin/sed -e "s,:..:.. *$,,"`
	for match in $uniq_macs ; do
	    count=`/sbin/ifconfig -a | \
			   /bin/grep "^eth.*Ethernet" | \
			   /bin/sed -e "s,.*HWaddr ,," | \
			   sort | \
			   /bin/grep -i $match | \
			   /usr/bin/wc -l`
	    if [ $count -ge 4 ]; then
		additional_mac_addresses=`/sbin/ifconfig -a | \
			       /bin/grep "^eth.*Ethernet" | \
			       /bin/sed -e "s,.*HWaddr ,," | \
			       sort | \
			       /bin/grep -i$invert_flag $match`
		new_mac_addresses="$new_mac_addresses $additional_mac_addresses"
	    fi
	done
	if [ x$new_mac_addresses != x ]; then
	    mac_addresses=$new_mac_addresses
	fi
    fi
}

make_base() {
    prefix=`echo $1 | sed -e 's,^\([0-9a-fA-F]*:[0-9a-fA-F]*:[0-9a-fA-F]*:\).*,\1,'`
    midnib=`echo $1 | sed -e 's,^[0-9a-fA-F]*:[0-9a-fA-F]*:[0-9a-fA-F]*:,,' -e 's,\([0-9a-fA-F]\)[0-9a-fA-F]*:[0-9a-fA-F]*:[0-9a-fA-F]*,\1,'`
    serial=`echo $1 | sed -e 's,^[0-9a-fA-F]*:[0-9a-fA-F]*:[0-9a-fA-F]*:[0-9a-fA-F],,' -e 's,.$,,'`
    last=`echo $1 | sed -e 's,.*\(.\)$,\1,'`

    #echo $prefix
    #echo $midnib
    #echo $serial
    #echo $last

    case "x$last" in
	x0|x1|x2|x3|x4|x5|x6|x7) last=0 ;;
	x8|x9|xa|xb|xc|xd|xe|xf|xA|xB|xC|xD|xE|xF) last=8 ;;
	*) ;;
    esac
    case "x$midnib" in
	x8) midnib=0 ;;
	x9) midnib=1 ;;
	xa|xA) midnib=2 ;;
	xb|xB) midnib=3 ;;
	xc|xC) midnib=4 ;;
	xd|xD) midnib=5 ;;
	xe|xE) midnib=6 ;;
	xf|xF) midnib=7 ;;
	*) ;;
    esac

    echo ${prefix}${midnib}${serial}${last}
}

diff_from_base() {
    addr=$1
    base=$2
    addr=`echo $addr | /bin/sed -e 's,:,,g'`
    base=`echo $base | /bin/sed -e 's,:,,g'`
    hexsub $addr $base
}

#
# Find interfaces which match the RBT vendor ID.
# If any are found, then rename them and exit.
#
find_macs_or_quad $rbt_prefix 0
if [ -n "$mac_addresses" ]; then
    m_prihw=''
    m_aux=''
    m_ceth2=''
    m_ceth3=''
    m_lan0_0='' ; m_wan0_0=''
    m_lan0_1='' ; m_wan0_1=''
    m_lan1_0='' ; m_wan1_0=''
    m_lan1_1='' ; m_wan1_1=''
    m_lan2_0='' ; m_wan2_0=''
    m_lan2_1='' ; m_wan2_1=''
    for m in $mac_addresses ; do
	base=`make_base $m`
        offset=`diff_from_base $m $base`
	case "x$offset" in
	    x0) call_nameif prihw $m ;	m_prihw=$m
		#XXX/netflow: disabled for now.
		#call_nameif prihw_p $m
		;;
	    x1) call_nameif aux $m ;		m_aux=$m ;;
	    x2) call_nameif ceth2 $m ;		m_ceth2=$m ;;
	    x3) call_nameif ceth3 $m ;		m_ceth3=$m ;;
	    x4) call_nameif lan0_0 $m ;		m_lan0_0=m ;;
	    x5) call_nameif wan0_0 $m ;		m_wan0_0=m ;;
	    x6) call_nameif lan0_1 $m ;		m_lan0_1=m ;;
	    x7) call_nameif wan0_1 $m ;		m_wan0_1=m ;;
	    x800000) call_nameif lan1_0 $m ;	m_lan1_0=m ;;
	    x800001) call_nameif wan1_0 $m ;	m_wan1_0=m ;;
	    x800002) call_nameif lan1_1 $m ;	m_lan1_1=m ;;
	    x800003) call_nameif wan1_1 $m ;	m_wan1_1=m ;;
	    x800004) call_nameif lan2_0 $m ;	m_lan2_0=m ;;
	    x800005) call_nameif wan2_0 $m ;	m_wan2_0=m ;;
	    x800006) call_nameif lan2_1 $m ;	m_lan2_1=m ;;
	    x800007) call_nameif wan2_1 $m ;	m_wan2_1=m ;;
	    *) echo "Error in rename-if.sh -- unexpected offset = $offset" ;;
	esac
    done
    # To handle fiber as prihw interface, flash the prihw/aux as offset+2,
    # and then this will rename ceth3 to aux
    if test "x$m_aux" = "x"; then
        if test "x$m_ceth3" != "x"; then
            call_nameif aux $m_ceth3 ; m_aux=$m_ceth3 ; m_ceth3=''
	fi
    fi
fi

#
# Get the MAC addresses of the interfaces which match the vendor ID.
# If there are no MAC addresses with prefixes in vendor_prefix, use
# vendor_prefix2.  This is to avoid problems with the case where an
# Intel motherboard has an Adlink 2-port card in it.
#
find_macs_or_quad $vendor_prefix 0
if [ ! -n "$mac_addresses" ]; then
    use_vendor_prefix2=1
else
    use_vendor_prefix2=0
fi

if [ $use_vendor_prefix2 -ne 0 -a "x$vendor_prefix2" != x ]; then
    find_macs_or_quad $vendor_prefix2 0
fi
#echo $mac_addresses

#
# Rename them to xeth*
#
count=0
for m in $mac_addresses ; do
    if [ $count -eq 0 ]; then
	call_nameif lan0_0 $m
    else
	if [ $count -eq 1 ]; then
	    call_nameif wan0_0 $m
	else
	    call_nameif xeth$count $m
	fi
    fi
    count=`expr $count + 1`
done

#
# Get the MAC addresses of the interfaces which do not match the vendor ID.
#
if [ $use_vendor_prefix2 -ne 0 -a "x$vendor_prefix2" != x ] ; then
    find_macs_or_quad $vendor_prefix2 1
else
    find_macs_or_quad $vendor_prefix 1
fi
#echo $mac_addresses

#
# Rename them to ceth*
#
count=0
for m in $mac_addresses ; do
    if [ $count -eq 0 ]; then
        #XXX/netflow: disabled for now
	#call_nameif prihw_p $m
	call_nameif prihw $m
    else
	if [ $count -eq 1 ]; then
	    call_nameif aux $m
	else
	    call_nameif ceth$count $m
	fi
    fi
    count=`expr $count + 1`
done

