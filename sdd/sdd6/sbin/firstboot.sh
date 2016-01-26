#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 102036 $
#  Date:      $Date: 2012-03-07 10:59:07 -0800 (Wed, 07 Mar 2012) $
#  Author:    $Author: ppanchamukhi $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#

#
# This script is run the first time an image is booted, and does any
# post-installation tweaking that needs to be done.
#
# Note that this script is run from rc.sysinit, so there are no daemons running
# Disks are mounted rw when this script is called
#
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
 
KEYGEN=/usr/bin/ssh-keygen
RSA1_KEY=/config/ssh/ssh_host_key
RSA_KEY=/config/ssh/ssh_host_rsa_key
DSA_KEY=/config/ssh/ssh_host_dsa_key
RSA1_KEY_LN=/var/lib/ssh/ssh_host_key
RSA_KEY_LN=/var/lib/ssh/ssh_host_rsa_key
DSA_KEY_LN=/var/lib/ssh/ssh_host_dsa_key
SMART_CONF_TEMPLATE=/etc/smartd.conf.template
SMART_CONF=/etc/smartd.conf
SERVICE_DIR=/etc/rc.d/init.d
ETHTOOL=/sbin/ethtool
EXPR=/usr/bin/expr

. /etc/init.d/functions
. /etc/build_version.sh

#
# As the management database has one semantic version number per module,
# the firstboot script has two semantic version numbers for /var: one
# for upgrades  pertaining to the baseline code, and one for 
# customer-specific upgrades.  The two groups of defines below reflect
# these two upgrade paths.  One set of customer-specific files are
# installed from whichever customer directory we are building out of.
#

PATH_VAR_VERSION_CURR_GENERIC=/var/var_version.sh
PATH_VAR_VERSION_NEW_GENERIC=/etc/var_version.sh
PATH_VAR_UPGRADE_SCRIPT_GENERIC=/sbin/var_upgrade.sh

PATH_VAR_VERSION_CURR_CUSTOMER=/var/var_version_${BUILD_PROD_CUSTOMER_LC}.sh
PATH_VAR_VERSION_NEW_CUSTOMER=/etc/var_version_${BUILD_PROD_CUSTOMER_LC}.sh
PATH_VAR_UPGRADE_SCRIPT_CUSTOMER=/sbin/var_upgrade_${BUILD_PROD_CUSTOMER_LC}.sh

# Set to 1 if a reboot is needed before the system can be fully started
REBOOT_NEEDED=0
export REBOOT_NEEDED
# If a reboot is going to be done, should we re-run firstboot after this reboot
REBOOT_RERUN_FIRSTBOOT=0
export REBOOT_RERUN_FIRSTBOOT

touch / 2>/dev/null
READ_ONLY_ROOT=$?

[ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,rw

# Do this before anything else, or we might not be able to run binaries
/sbin/ldconfig /lib /usr/lib /usr/kerberos/lib /opt/tms/lib /opt/tms/lib64

trap "do_firstboot_cleanup_exit" HUP INT QUIT PIPE TERM

do_firstboot_startup() {
    return 0
}

do_firstboot_cleanup() {
    if [ ! -e /etc/.disablewizard ]; then
        # If this is the first boot, and they have no config db, use the wizard
        if [ ! -f /config/db/active ]; then
            touch /var/opt/tms/.usewizard
        else
            if [ ! -f /config/db/`cat /config/db/active` ]; then
                touch /var/opt/tms/.usewizard
            fi
        fi
    else
        logger -p user.info "Global Wizard-disable flag detected; skipping launch."
    fi

    if [ ${REBOOT_NEEDED} -ne 0 ]; then
            logger -p user.warn "Reboot needed before system can be started"
            if [ ${REBOOT_RERUN_FIRSTBOOT} -eq 0 ]; then
                rm -f /etc/.firstboot
            fi

            umount -a
            mount -n -o remount,ro /
            reboot -hf
    fi

    unset REBOOT_NEEDED
    unset REBOOT_RERUN_FIRSTBOOT
}

do_firstboot_cleanup_exit() {
    do_firstboot_cleanup
    exit 1
}

######################################################################

do_firstboot_startup

# Define graft functions
if [ -f /etc/customer.sh ]; then
    . /etc/customer.sh
fi

if [ "$HAVE_FIRSTBOOT_GRAFT_1" = "y" ]; then
    firstboot_graft_1
fi

# This function runs the script which will adapt the inittab
# console lines based on the current motherboard. This is used to start
# additional consoles on serial ports that are not reflected in the
# checked in inittab file.
#
do_inittab_fixup() {
    /usr/bin/python /opt/tms/bin/InitTabMgr.pyc
}

do_inittab_fixup

#
# This function is the place to fix up things in /var that have changed
# between versions.
#
# It takes three parameters:
#   - The path to the variable var_version file that reflects the
#     system's current version level
#   - The path to the static var_version file that reflects the
#     currently-booted image's version level
#   - The path to the script containing the upgrade logic
#
do_image_upgrade() {
    PATH_VAR_VERSION_CURR=$1
    PATH_VAR_VERSION_NEW=$2
    PATH_VAR_UPGRADE_SCRIPT=$3

    if [ -f ${PATH_VAR_VERSION_CURR} ]; then
        . ${PATH_VAR_VERSION_CURR}
    else
        IMAGE_VAR_VERSION=1
    fi
    VAR_VERSION_CURR=${IMAGE_VAR_VERSION}

    if [ -f ${PATH_VAR_VERSION_NEW} ]; then
        . ${PATH_VAR_VERSION_NEW}
    else
        IMAGE_VAR_VERSION=1
    fi
    VAR_VERSION_NEW=${IMAGE_VAR_VERSION}
    unset IMAGE_VAR_VERSION

    if [ ${VAR_VERSION_NEW} -ne ${VAR_VERSION_CURR} ]; then
        logger "Image upgrade required from version ${VAR_VERSION_CURR} to version ${VAR_VERSION_NEW}"

        if [ ${VAR_VERSION_NEW} -lt ${VAR_VERSION_CURR} ]; then
            logger -p user.warn "Image upgrade failed: current version too recent"
            return 1
        fi

        # If there is no upgrade script, there's trouble, since by now we
        # have determined that we need to do an upgrade.
        if [ ! -f ${PATH_VAR_UPGRADE_SCRIPT} ]; then
            logger -p user.err "Image upgrade failed: upgrade script ${PATH_VAR_UPGRADE_SCRIPT} not found"
            return 1
        fi

        curr_version=${VAR_VERSION_CURR}

        error=0
        while [ $curr_version -lt ${VAR_VERSION_NEW} ]; do
            next_version=$(( $curr_version + 1 ))
            logger -p user.info "Image upgrade: version $curr_version to version $next_version"

            ugs="${curr_version}_${next_version}"

            # XXX It would be better to update /var/var_version.sh as we go

	    . ${PATH_VAR_UPGRADE_SCRIPT} ${ugs}

            curr_version=$next_version
        done

        if [ $error -eq 0 ]; then
            cp ${PATH_VAR_VERSION_NEW} ${PATH_VAR_VERSION_CURR}
            logger "Image upgrade complete."
        else
            logger -p user.err "Image upgrade failed."
        fi
        
    fi

}


do_image_upgrade ${PATH_VAR_VERSION_CURR_GENERIC} ${PATH_VAR_VERSION_NEW_GENERIC} ${PATH_VAR_UPGRADE_SCRIPT_GENERIC}

do_image_upgrade ${PATH_VAR_VERSION_CURR_CUSTOMER} ${PATH_VAR_VERSION_NEW_CUSTOMER} ${PATH_VAR_UPGRADE_SCRIPT_CUSTOMER}


# If there is no image layout settings file, generate one
LAYOUT_FILE=/etc/image_layout.sh
if [ ! -f "${LAYOUT_FILE}" ]; then
    BOOTED_ROOT_DEV=`/bin/mount | grep -w '^.* on / type .*$' | awk '{print $1}'`
    BOOTED_DEV=`echo ${BOOTED_ROOT_DEV} | sed 's/^\(.*[^0-9]*\)[0-9][0-9]*$/\1/'`
    touch ${LAYOUT_FILE}
    chmod 644 ${LAYOUT_FILE}

    echo "IL_LAYOUT=STD" >> ${LAYOUT_FILE}
    echo "export IL_LAYOUT" >> ${LAYOUT_FILE}
    echo "IL_LO_STD_TARGET_DISK1_DEV=${BOOTED_DEV}" >> ${LAYOUT_FILE}
    echo "export IL_LO_STD_TARGET_DISK1_DEV" >> ${LAYOUT_FILE}
fi


# XXXXXXXXXXXXXX call writeimage to make it remake the fstab, etc.
do_regen_grub_conf() {
    eval `/sbin/aiget.sh`
    if [ ! -z "${AIG_NEXT_BOOT_ID}" ]; then
        /sbin/aigen.py -i -l $AIG_NEXT_BOOT_ID 
    fi
}

do_regen_grub_conf

do_rsa1_keygen() {
        #XXX/evan: deal with upgrade case here
        if [ -s $RSA1_KEY_LN -a ! -L $RSA1_KEY_LN ]; then
	    mkdir -p /config/ssh/
	    mv $RSA1_KEY_LN $RSA1_KEY
	fi

	if [ ! -s $RSA1_KEY ]; then
		echo -n $"Generating SSH1 RSA host key: "
		if $KEYGEN -q -t rsa1 -f $RSA1_KEY -C '' -N '' >&/dev/null; then
			chmod 600 $RSA1_KEY
			chmod 644 $RSA1_KEY.pub
			success $"RSA1 key generation"
			echo
		else
			failure $"RSA1 key generation"
			echo
		fi
	fi
}

do_rsa_keygen() {
        #XXX/evan: deal with upgrade case here
        if [ -s $RSA_KEY_LN -a ! -L $RSA_KEY_LN ]; then
	    mkdir -p /config/ssh/
	    mv $RSA_KEY_LN $RSA_KEY
	fi

	if [ ! -s $RSA_KEY ]; then
		echo -n $"Generating SSH2 RSA host key: "
		if $KEYGEN -q -t rsa -f $RSA_KEY -C '' -N '' >&/dev/null; then
			chmod 600 $RSA_KEY
			chmod 644 $RSA_KEY.pub
			success $"RSA key generation"
			echo
		else
			failure $"RSA key generation"
			echo
		fi
	fi
}

do_dsa_keygen() {
        #XXX/evan: deal with upgrade case here
        if [ -s $DSA_KEY_LN -a ! -L $DSA_KEY_LN ]; then
	    mkdir -p /config/ssh/
	    mv $DSA_KEY_LN $DSA_KEY
	fi

	if [ ! -s $DSA_KEY ]; then
		echo -n $"Generating SSH2 DSA host key: "
		if $KEYGEN -q -t dsa -f $DSA_KEY -C '' -N '' >&/dev/null; then
			chmod 600 $DSA_KEY
			chmod 644 $DSA_KEY.pub
			success $"DSA key generation"
			echo
		else
			failure $"DSA key generation"
			echo
		fi
	fi
}

setup_config_links() {
    if [ -s $RSA1_KEY -a ! -L $RSA1_KEY_LN ]; then
	echo -n $"Creating RSA1 key link: "
	ln -s $RSA1_KEY $RSA1_KEY_LN >&/dev/null
	if [ $? -eq 0 ]; then 
	    success $"RSA1 key link creation"
	    echo
	else
	    failure $"RSA1 key link creation"
	    echo
	fi
    fi
    if [ -s $RSA1_KEY.pub -a ! -L $RSA1_KEY_LN.pub ]; then
	echo -n $"Creating RSA1 key pub link: "
	ln -s $RSA1_KEY.pub $RSA1_KEY_LN.pub >&/dev/null
	if [ $? -eq 0 ]; then 
	    success $"RSA1 pub key link creation"
	    echo
	else
	    failure $"RSA1 pub key link creation"
	    echo
	fi
    fi

    if [ -s $RSA_KEY -a ! -L $RSA_KEY_LN ]; then
	echo -n $"Creating RSA key link: "
	ln -s $RSA_KEY $RSA_KEY_LN >&/dev/null
	if [ $? -eq 0 ]; then 
	    success $"RSA key link creation"
	    echo
	else
	    failure $"RSA key link creation"
	    echo
	fi
    fi
    if [ -s $RSA_KEY.pub -a ! -L $RSA_KEY_LN.pub ]; then
	echo -n $"Creating RSA key pub link: "
	ln -s $RSA_KEY.pub $RSA_KEY_LN.pub >&/dev/null
	if [ $? -eq 0 ]; then 
	    success $"RSA pub key link creation"
	    echo
	else
	    failure $"RSA pub key link creation"
	    echo
	fi
    fi

    if [ -s $DSA_KEY -a ! -L $DSA_KEY_LN ]; then
	echo -n $"Creating DSA key link: "
	ln -s $DSA_KEY $DSA_KEY_LN >&/dev/null
	if [ $? -eq 0 ]; then 
	    success $"DSA key link creation"
	    echo
	else
	    failure $"DSA key link creation"
	    echo
	fi
    fi
    if [ -s $DSA_KEY.pub -a ! -L $DSA_KEY_LN.pub ]; then
	echo -n $"Creating DSA key pub link: "
	ln -s $DSA_KEY.pub $DSA_KEY_LN.pub >&/dev/null
	if [ $? -eq 0 ]; then 
	    success $"DSA pub key link creation"
	    echo
	else
	    failure $"DSA pub key link creation"
	    echo
	fi
    fi

}

# Different versions of the platform may have different MIBs,
# and so we need to cause the MIB cache to be regenerated.
do_clean_snmp_mib_cache() {
	rm -f /var/lib/net-snmp/*_index
}

# We might lack a valid /tmp if we upgraded from an older system.
if ! grep -w /tmp /etc/fstab > /dev/null; then
    cat >> /etc/fstab <<EOF
none            /tmp            tmpfs   size=16M        0 0
EOF
    mount /tmp
fi

# We might lack a valid passwd or group if we upgraded from an older system
if [ ! -e /etc/passwd -o ! -e /etc/group ]; then
    cp /etc/passwd_initial /etc/passwd
    cp /etc/group_initial /etc/group
fi

# We might lack a valid syslog.conf if we upgraded from an older system
if [ ! -e /etc/syslog.conf ]; then
    cp /etc/syslog.conf_initial /etc/syslog.conf
fi

if [ "$HAVE_FIRSTBOOT_GRAFT_2" = "y" ]; then
    firstboot_graft_2
fi

if [ -f ${SERVICE_DIR}/random ]; then
    chkconfig --add random
fi
chkconfig --add syslog
chkconfig --add mdinit
chkconfig --add shutdown_check
chkconfig --add internal_startup
chkconfig --add pm
chkconfig --add load-debug
chkconfig --add fwkinit
chkconfig --add iptables
chkconfig --add bob_reboot
chkconfig --add bob_shutdown
chkconfig --add net_linkwatch

if [ "$HAVE_HPBLADE_FIRSTBOOT_GRAFT" = "y" ]; then
    hpblade_firstboot_graft_1
fi

# Some customer-specific systems don't want SMART, and if they
# do, they worry about adding it themselves.
if [ "x$BUILD_PROD_FEATURE_SMARTD" = "x1" ]; then
    chkconfig --add smartd
fi

# Only use our interface renaming support if turned on
if [ "x$BUILD_PROD_FEATURE_RENAME_IFS" = "x1" ]; then
    chkconfig --add rename_ifs
fi

mkdir -p /config/ssh/

mkdir -p /config/local/

do_rsa1_keygen
do_rsa_keygen
do_dsa_keygen
setup_config_links
do_clean_snmp_mib_cache

if [ "$HAVE_FIRSTBOOT_GRAFT_3" = "y" ]; then
    firstboot_graft_3
fi

#
#Disable managment mode for Intel 82574
#The bits 5 and 6 of offset 0x1f on 82574 need to be 0 to dsisable mng mode
#

function disable_82574_mng() {
    magic=0x10d38086

    if [ ! -x $ETHTOOL ]; then
        echo "$ETHTOOL is missing"
        return 1
    fi

    if [ ! -x $EXPR ]; then
        echo "$EXPR is missing"
        return 1
    fi

    if [ -z $1 ]; then
        return 1
    fi

    eth=$(basename $1)

    mng=`$ETHTOOL -e $eth offset 0x1f length 1 | grep 1f | tr -d " \t"`
    start=`$EXPR ${#mng} - 1`
    mng=`$EXPR substr $mng $start 2`
    mng="0x${mng}"

    mng=`printf "%d" $mng`

    res=$(( mng & 0x60 ))
    if [ $res -ne 0 ]; then #MNG is enabled
        mng=$((mng & 0x9F))
        `$ETHTOOL -E $eth magic $magic offset 0x1f value $mng 2>/dev/null`
        if [ $? -eq 0 ]; then
            echo "Successfully disabled management mode of interface $eth."
        else
            echo "Failed to disable management mode of interface $eth!"
        fi
    fi
}


DIRS=/sys/class/net/*

for dir in $DIRS
do
    if [ -d "$dir" ] ; then
        if [ -e "$dir/device/device" ] ; then
            vendorID=`cat "$dir/device/vendor"`
            devID=`cat "$dir/device/device"`
            if [[ "x$vendorID" == "x0x8086" && "x$devID" == "x0x10d3" ]]
            then
                disable_82574_mng $dir
            fi
        fi
    fi
done


# This may reboot the system
do_firstboot_cleanup

if [ $READ_ONLY_ROOT -ne 0 ]; then 
    mount / -o remount,ro
fi
