#!/bin/sh

#
# (C) Copyright 2003-2005 Riverbed Technology, Inc.
# $Id: smb_backup.sh 6487 2005-07-01 20:45:28Z ltrac $
/usr/local/samba/bin/tdbbackup /usr/local/samba/var/locks/*.tdb
/usr/local/samba/bin/tdbbackup /usr/local/samba/private/*.tdb

exit 0
