#!/bin/sh

#
#  URL:       $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/scrub.sh $
#  Revision:  $Revision: 101851 $
#  Date:      $Date: 2013-01-03 14:51:11 -0800 (Thu, 03 Jan 2013) $
#  Author:    $Author: timlee $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  (C) Copyright 2003-2012 Riverbed Technology, Inc.
#  All rights reserved.
#

#
# This script is used to scrub a system clean to its default/initial state.
#
#

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

INC_DB_PATH=/config/mfg/mfincdb
MDREQ=/opt/tms/bin/mdreq
MDDBREQ=/opt/tms/bin/mddbreq

usage() {
    echo "usage: $0 [--reload] [--clear-licenses] [--preserve-images]"
    echo "       [--keep-mgmt-ip] [product specific flags]"
    exit 1
}

while [ $# -gt 0 ] ; do
    case "$1" in
	reload)			REBOOT=true ; shift ;;
	-r)			REBOOT=true ; shift ;;
	--reload)		REBOOT=true ; shift ;;
	clear)			CLEAR_LICENSES=true ; shift ;;
	clear-licenses)		CLEAR_LICENSES=true ; shift ;;
	-c)			CLEAR_LICENSES=true ; shift ;;
	--clear-licenses)	CLEAR_LICENSES=true ; shift ;;
	preserve)		PRESERVE_IMAGES=true ; shift ;;
	preserve-images)	PRESERVE_IMAGES=true ; shift ;;
	-i)			PRESERVE_IMAGES=true ; shift ;;
	--preserve-images)	PRESERVE_IMAGES=true ; shift ;;
	keep-mgmt-ip)		PRESERVE_MGMT_IP=true ; shift ;;
	preserve-mgmt-ip)	PRESERVE_MGMT_IP=true ; shift ;;
	-m)			PRESERVE_MGMT_IP=true ; shift ;;
	--keep-mgmt-ip)		PRESERVE_MGMT_IP=true ; shift ;;
	--preserve-mgmt-ip)	PRESERVE_MGMT_IP=true ; shift ;;
	--debug)		DEBUG=true ; shift ;;
	--)			shift ;;
	*)			EXTRA_PARAMS="$EXTRA_PARAMS $1" ; shift ;;
    esac
done

if [ "x$DEBUG" != "x" ]; then
    echo "REBOOT=$REBOOT"
    echo "CLEAR_LICENSES=$CLEAR_LICENSES"
    echo "PRESERVE_IMAGES=$PRESERVE_IMAGES"
    echo "PRESERVE_MGMT_IP=$PRESERVE_MGMT_IP"
    echo "DEBUG=$DEBUG"
    echo "EXTRA_PARAMS=$EXTRA_PARAMS"
fi

# Licenses that contain these strings are preserved in a reset-factory.
# Override these strings, if necessary, in scrub_graft_1() in the product-side
# customer.sh.
BASE_LICENSES="BASE"
FLEX_LICENSES="$BASE_LICENSES"

# Define graft functions
if [ -f /etc/customer.sh ]; then
    . /etc/customer.sh
fi

#
# perform customer specific clean, which should process any extra
# parameters and call the usage function if any are unrecognized
#
if [ "$HAVE_SCRUB_GRAFT_1" = "y" ]; then
    scrub_graft_1 $EXTRA_PARAMS
elif [ "x$EXTRA_PARAMS" != "x" ]; then
    echo "$0: unrecognized parameters: $EXTRA_PARAMS"
    usage
fi

#
# Retrieve licenses to be saved in new db using mfincdb
# (preserve EXCH, BASE, CIFS licenses and remove the rest)
#

key_num=1
license_db=/config/local/db
license=`$MDDBREQ $license_db query get - /license/key/${key_num}/license_key | grep -m 1 "Value:" | cut -d' ' -f2`
key_num_save=1

while [ "x$license" != "x" ] # loop until all licenses are examined
    do
    if [ "x$CLEAR_LICENSES" != "x" ]; then
        # only base licenses to be preserved
	license_save=`echo $license | grep -E "$BASE_LICENSES"` 
    else
        # base and flex licenses to be preserved
	license_save=`echo $license | grep -E "$FLEX_LICENSES"` 
    fi

    if [ "x$license_save" != "x" ]; then
	if [ "$HAVE_SCRUB_GRAFT_3" = "y" ]; then
            # if VBASE license preserve it's token
	    scrub_graft_3 $license_save
	fi
	$MDDBREQ -c $INC_DB_PATH set modify "" /license/key/${key_num_save} uint32 ${key_num_save}
	$MDDBREQ -c $INC_DB_PATH set modify "" /license/key/${key_num_save}/license_key string "$license_save"

        # Write the install method and time to defaults; don't use the actual
        # time, as that effectively timestamps when the box was manufactured

        $MDDBREQ -c $INC_DB_PATH set modify "" /license/key/${key_num_save}/properties/install_method string "Manual"
        $MDDBREQ -c $INC_DB_PATH set modify "" /license/key/${key_num_save}/properties/install_time uint32 "0"

	key_num_save=`expr $key_num_save + 1`
    fi
    key_num=`expr $key_num + 1`
    license=`$MDDBREQ $license_db query get - /license/key/${key_num}/license_key | grep -m 1 "Value:" | cut -d' ' -f2`
done

#
# If --preserve-mgmt-ip is used, save the primary and aux interface
# settings and the route settings into the mfincdb to be reloaded
# on next startup.
#
if [ "x$PRESERVE_MGMT_IP" != "x" ]; then
    temp_script=`/bin/mktemp /var/tmp/preserve_mgmt_ipXXXXXXXX.sh`
    # generate route, primary, and aux settings in $temp_script
    # convert mdreq -b output like:
    # /net/interface/config/aux/addr/ipv4/static/1/ip = 10.5.6.66 (ipv4addr)
    # into:
    # /opt/tms/bin/mddbreq -c /config/mfg/mfincdb set modify - '/net/interface/config/aux/addr/ipv4/static/1/ip' ipv4addr '10.5.6.66'
    for node in /net/routes/config \
		/net/interface/config/primary \
		/net/interface/config/aux \
		; do
	$MDREQ -b query iterate subtree $node | \
	    sed -e "s,\([^ ]*\) = \([^ ]*\) (\([^)]*\)),'\1' \3 '\2'," \
		-e "s,^,$MDDBREQ -c $INC_DB_PATH set modify '' ," \
		>> $temp_script
    done
    if [ "x$DEBUG" != x ]; then
	/bin/cat $temp_script
    fi
    /bin/sh $temp_script
    /bin/rm $temp_script
fi

if [ "x$DEBUG" != "x" ]; then
    echo "$INC_DB_PATH contains:"
    $MDDBREQ -b $INC_DB_PATH query iterate subtree /
fi

#
# now remove all the other config files
#
cfg_files=`ls /config/db`
for cfg_file in $cfg_files; do
    rm -f /config/db/$cfg_file
done

# Remove eval license timestamps.
rm -rf /config/license

#
# stop statsd so that no more stats are logged
#
/usr/bin/printf "enable\nconfigure terminal\ninternal action - /pm/actions/terminate_process process_name value string statsd\nexit\nexit\n" | /opt/tms/bin/cli

#
# kill all the stats
#
rm -f /var/opt/tms/stats/*.dat

#
# kill all images if --preserve-images is not specified
#
if [ "x$PRESERVE_IMAGES" = "x" ]; then
	rm -f /var/opt/tms/images/*
        rm -f /var/opt/tms/image_version/*.ver
fi

#
# kill all snapshots
#
rm -rf /var/opt/tms/snapshots/*
mkdir /var/opt/tms/snapshots/md5

#
# kill all the logs
#
rm -f /var/log/messages*
rm -f /var/log/user_messages*

#
# kill all the history files
#
rm -f /var/home/*/.bash_history*
rm -f /var/home/*/.cli_history*

#
# kill all tcpdump files
#
rm -rf /var/opt/tms/tcpdumps/md5/*
rm -rf /var/opt/tms/tcpdumps/*
mkdir /var/opt/tms/tcpdumps/md5

#
# kill all sysdump (debug-dump) files
#
rm -rf /var/opt/tms/sysdumps/md5/*
rm -rf /var/opt/tms/sysdumps/*
mkdir /var/opt/tms/sysdumps/md5

#
# re-instate the wizard
#
touch /var/opt/tms/.usewizard


#
# perform customer specific post-clean
#
if [ "$HAVE_SCRUB_GRAFT_2" = "y" ]; then
    scrub_graft_2 $EXTRA_PARAMS
fi


#
# kill encrypted store
#
umount /var/opt/rbt/decrypted
rm -rf /var/opt/rbt/decrypted
rm -rf /var/opt/rbt/encrypted
rm -f /var/opt/rbt/ssl

if [ -d /config/rbt/encrypted ]; then
    rm -rf /config/rbt/encrypted
fi

#
# Delete PFS files.
#
rm -rf /var/opt/rcu/*
rm -rf /var/log/rcu/*
rm -rf /var/log/samba/*
rm -f /etc/samba/smb.conf
rm -f /var/etc/krb.realms
rm -f /var/etc/krb5.conf

#
# Delete any special "getty" control files.
#
rm -f /var/etc/enable_console_timeout

#
# Halt or reboot the box
#
if [ "x$REBOOT" != "x" ]; then
	/sbin/reboot
	exit 0
else
	/sbin/shutdown -h now
	exit 0
fi
