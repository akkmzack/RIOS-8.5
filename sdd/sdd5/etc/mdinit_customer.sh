#
#  Filename:  $Source$
#  Revision:  $Revision: 107328 $
#  Date:      $Date: 2012-07-02 09:47:59 -0700 (Mon, 02 Jul 2012) $
#  Author:    $Author: kguragain $
#
#  (C) Copyright 2012 Riverbed Technology, Inc.
#  All rights reserved.
#
MODEL=`/opt/tms/bin/hald_model -m`

HAVE_UPGRADE_REVERT_GRAFT=y
upgrade_revert()
{
	if [ "${MODEL}" = "rvbd_ex" ]; then
		touch /esxi/.upgradeorrevert
	fi
}