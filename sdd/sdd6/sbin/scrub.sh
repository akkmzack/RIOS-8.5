#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 99345 $
#  Date:      $Date: 2012-02-01 14:32:59 -0800 (Wed, 01 Feb 2012) $
#  Author:    $Author: svichare $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#

#
# This script is used to scrub a system clean to its default/initial state.
#
#

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

INC_DB_PATH=/config/mfg/mfincdb
MDDBREQ=/opt/tms/bin/mddbreq

ACTION=$1
FORCE_REBOOT=${2:-"false"}
REBOOT="false"
if [ "x$ACTION" = "xreload" ] || [ "$FORCE_REBOOT" = "true" ]; then
	REBOOT="true"
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
# perform customer specific clean
#
if [ "$HAVE_SCRUB_GRAFT_1" = "y" ]; then
    scrub_graft_1 $1
fi

#
# retrieve licenses to be saved in new db using mfincdb (preserve EXCH, BASE, CIFS licenses and remove the rest)
#

key_num=1
license_db=/config/local/db
license=`$MDDBREQ $license_db query get - /license/key/${key_num}/license_key | grep -m 1 "Value:" | cut -d' ' -f2`
key_num_save=1

while [ "x$license" != "x" ] # loop until all licenses are examined
    do
    if [ "x$ACTION" = "xclear" ]; then
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
# kill all images if preserve is not specified
#

if [ "x$ACTION" != "xpreserve" ]; then
	rm -f /var/opt/tms/images/*
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
    scrub_graft_2 $1
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

rm -f /var/etc/disable_console_timeout

#
# Halt or reboot the box
#
if [ $REBOOT = "true" ]; then
	/sbin/reboot
    exit 0
else
	/sbin/shutdown -h now
	exit 0
fi
