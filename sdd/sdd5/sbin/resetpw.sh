#! /bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 5137 $
#  Date:      $Date: 2004-12-31 01:58:56 -0800 (Fri, 31 Dec 2004) $
#  Author:    $Author: gregs $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

PW_BINDING=/auth/passwd/user/admin/password
CONFIG_DIR=/config/db
ACTIVE_DB=${CONFIG_DIR}/active
INITIAL_DB=${CONFIG_DIR}/initial
IEXT="restore"

# This should only be run in single user mode
grep -q single /proc/cmdline
if [ $? != 0 ] ; then
    echo "$0 should only be run in single user mode."
    exit 1
fi

# If there is no 'active' db file, then make sure if there is an 'initial'
# db, we move it out of the way and force the system to create a clean db.
if [ ! -f ${ACTIVE_DB} ]; then
    if [ -f ${INITIAL_DB} ]; then
        mv -f ${INITIAL_DB} ${INITIAL_DB}.${IEXT}
        echo "No active db found, moving db '${INITIAL_DB}' to"
	echo "'${INITIAL_DB}.${IEXT}'. System will restore configuration"
	echo "state to initial values on restart."
    else
	echo "No active or initial db found.  System will restore"
        echo "configuration state to initial values on restart."
    fi
    exit 1
fi

ACTIVE_FN=${CONFIG_DIR}/`cat ${ACTIVE_DB}`

# Now check to make sure the db that active points to exists. If it
# doesn't, remove 'active'.
if [ ! -f "${ACTIVE_FN}" ]; then
    echo "Active db reference '${ACTIVE_FN}' does not exist."
    echo "The system will remove this reference and will restore"
    echo "configuration state to initial values on restart."
    rm -f ${ACTIVE_DB}

    if [ -f ${INITIAL_DB} ]; then
        mv -f ${INITIAL_DB} ${INITIAL_DB}.${IEXT}
        echo "Saving '${INITIAL_DB}' to '${INITIAL_DB}.${IEXT}'"
    fi
    exit 1
fi

# Now know that active exists and references a valid file, try to
# reset the password for admin. If this fails, save the active db
# and 'initial' if it exists out of the way

/opt/tms/bin/mddbreq "${ACTIVE_FN}" set modify "" ${PW_BINDING} string ""

if [ $? != 0 ] ; then
    echo "Password reset failed. Saving any old configuration dbs"

    rm -f ${ACTIVE_DB}
    mv -f "${ACTIVE_FN}" "${ACTIVE_FN}".${IEXT}
    echo "Saving '${ACTIVE_FN}' to '${ACTIVE_FN}.${IEXT}'"

    if [ -f ${INITIAL_DB} ]; then
        mv -f ${INITIAL_DB} ${INITIAL_DB}.${IEXT}
        echo "Saving '${INITIAL_DB}' to '${INITIAL_DB}.${IEXT}'"
    fi
    exit 1
fi

echo "Admin password reset successful."
exit 0
