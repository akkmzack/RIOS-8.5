#!/bin/sh

#
#  Filename:  $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/firstboot.sh $
#  Revision:  $Revision: 104699 $
#  Date:      $Date: 2013-04-19 15:14:23 -0700 (Fri, 19 Apr 2013) $
#  Author:    $Author: timlee $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  (C) Copyright 2003-2013 Riverbed Technology, Inc.  
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
ECDSA_KEY=/config/ssh/ssh_host_ecdsa_key
RSA1_KEY_LN=/var/lib/ssh/ssh_host_key
RSA_KEY_LN=/var/lib/ssh/ssh_host_rsa_key
DSA_KEY_LN=/var/lib/ssh/ssh_host_dsa_key
ECDSA_KEY_LN=/var/lib/ssh/ssh_host_ecdsa_key
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

            reboot
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

VAR_HAL_PATH=/var/opt/tms/hal
SPECS_STOR_PROF_PATH=/opt/hal/lib/specs/specs_storage_profiles
write_specs_stor_prof_file() {
    eval `/sbin/aiget.sh`
    # this gives us the current and next boot partitions
    if [ ! -d "${VAR_HAL_PATH}" ]; then
        # create the directory
        mkdir "${VAR_HAL_PATH}"
    fi

    if [ ! -d "${VAR_HAL_PATH}/${AIG_THIS_BOOT_ID}" ]; then
        mkdir "${VAR_HAL_PATH}/${AIG_THIS_BOOT_ID}"
    fi

    # Now the directory exists. copy the specs_storage_profiles file out there.
    if [ -f "${SPECS_STOR_PROF_PATH}" ]; then
        cp "${SPECS_STOR_PROF_PATH}" "${VAR_HAL_PATH}/${AIG_THIS_BOOT_ID}"
    else
        echo "Specs storage profiles path not present on this box"
    fi
}

write_specs_stor_prof_file

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

do_keygen() {
        local TYPE=$1
        local KEY_LN=$2
        local KEY=$3
        #XXX/evan: deal with upgrade case here
        if [ -s $KEY_LN -a ! -L $KEY_LN ]; then
	    mkdir -p /config/ssh/
	    mv $KEY_LN $KEY
	fi

	if [ ! -s $KEY ]; then
		echo -n $"Generating SSH2 $TYPE host key: "
		if $KEYGEN -q -t $TYPE -f $KEY -C '' -N '' >&/dev/null; then
			chmod 600 $KEY
			chmod 644 $KEY.pub
			success $"$TYPE key generation"
			echo
		else
			failure $"$TYPE key generation"
			echo
		fi
	fi
}

setup_config_link() {
    local TYPE=$1
    local KEY_LN=$2
    local KEY=$3
    if [ -s $KEY -a ! -L $KEY_LN ]; then
	echo -n $"Creating $TYPE key link: "
	ln -s $KEY $KEY_LN >&/dev/null
	if [ $? -eq 0 ]; then 
	    success $"$TYPE key link creation"
	    echo
	else
	    failure $"$TYPE key link creation"
	    echo
	fi
    fi
    if [ -s $KEY.pub -a ! -L $KEY_LN.pub ]; then
	echo -n $"Creating $TYPE key pub link: "
	ln -s $KEY.pub $KEY_LN.pub >&/dev/null
	if [ $? -eq 0 ]; then 
	    success $"$TYPE pub key link creation"
	    echo
	else
	    failure $"$TYPE pub key link creation"
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
    cat /etc/passwd_initial > /etc/passwd
    cat /etc/group_initial > /etc/group
fi

# We might lack a valid syslog.conf if we upgraded from an older system
if [ ! -e /etc/rsyslog.conf ]; then
    cat /etc/rsyslog.conf_initial > /etc/rsyslog.conf
fi

if [ "$HAVE_FIRSTBOOT_GRAFT_2" = "y" ]; then
    firstboot_graft_2
fi

if [ -f ${SERVICE_DIR}/random ]; then
    chkconfig --add random
fi
chkconfig --del syslog
chkconfig --add rsyslog
chkconfig --add mdinit
chkconfig --add shutdown_check
chkconfig --add internal_startup
chkconfig --add pm
chkconfig --add load-debug
chkconfig --add fwkinit
chkconfig --add iptables
chkconfig --add net_linkwatch

mkdir -p /config/ssh/

mkdir -p /config/local/

do_keygen rsa1 $RSA1_KEY_LN $RSA1_KEY
do_keygen rsa $RSA_KEY_LN $RSA_KEY
do_keygen dsa $DSA_KEY_LN $DSA_KEY
do_keygen ecdsa $ECDSA_KEY_LN $ECDSA_KEY
setup_config_link rsa1 $RSA1_KEY_LN $RSA1_KEY
setup_config_link rsa $RSA_KEY_LN $RSA_KEY
setup_config_link dsa $DSA_KEY_LN $DSA_KEY
setup_config_link ecdsa $ECDSA_KEY_LN $ECDSA_KEY
do_clean_snmp_mib_cache

if [ "$HAVE_FIRSTBOOT_GRAFT_3" = "y" ]; then
    firstboot_graft_3
fi

DIRS=/sys/class/net/*

for dir in $DIRS
do
    if [ -d "$dir" ] ; then
        if [ -e "$dir/device/device" ] ; then
            vendorID=`cat "$dir/device/vendor"`
            devID=`cat "$dir/device/device"`
            if [[ "x$vendorID" == "x0x8086" && "x$devID" == "x0x10d3" ]]
            then
                if [ "$HAVE_FIRSTBOOT_GRAFT_4" = "y" ]; then
                    firstboot_graft_4
                fi
            fi
        fi
    fi
done


# This may reboot the system
do_firstboot_cleanup

if [ $READ_ONLY_ROOT -ne 0 ]; then 
    mount / -o remount,ro
fi
