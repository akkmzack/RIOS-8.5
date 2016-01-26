#!/bin/sh

#
# (C) Copyright 2003-2005 Riverbed Technology, Inc.
# $Id: smb_check_restore.sh 6536 2005-07-07 18:14:39Z ltrac $

FILENAME="/usr/local/samba/var/locks/netsamlogon_cache.tdb /usr/local/samba/var/locks/account_policy.tdb /usr/local/samba/var/locks/brlock.tdb /usr/local/samba/var/locks/connections.tdb /usr/local/samba/var/locks/gencache.tdb /usr/local/samba/var/locks/group_mapping.tdb /usr/local/samba/var/locks/locking.tdb /usr/local/samba/var/locks/messages.tdb /usr/local/samba/var/locks/winbindd_cache.tdb /usr/local/samba/var/locks/ntdrivers.tdb /usr/local/samba/var/locks/ntforms.tdb /usr/local/samba/var/locks/ntprinters.tdb /usr/local/samba/var/locks/registry.tdb /usr/local/samba/var/locks/sessionid.tdb /usr/local/samba/var/locks/share_info.tdb /usr/local/samba/var/locks/winbindd_idmap.tdb /usr/local/samba/private/secrets.tdb"

for each_file in $FILENAME; do
    if [ -r $each_file ] ; then
        /usr/local/samba/bin/tdbbackup -c $each_file
        if [ "$?" != "0" ]; then
            /usr/local/samba/bin/tdbbackup -v $each_file
            if [ "$?" != "0" ]; then
                /usr/local/samba/bin/tdbbackup -c $each_file
                if [ "$?" != "0" ]; then
                    exit 1
                fi
            fi
        fi
    fi
done

exit 0
