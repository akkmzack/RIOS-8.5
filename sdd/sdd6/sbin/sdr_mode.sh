#!/bin/sh
#
# determine the SDR mode by querying various mutually exclusive config nodes.
#
LEGACY=`/opt/tms/bin/mdreq -v query get - /rbt/sport/datastore/config/autolz`
ADVANCED=`/opt/tms/bin/mdreq -v query get - /rbt/sport/datastore/config/sdr_advanced`
SDRM=`/opt/tms/bin/mdreq -v query get - /rbt/sport/datastore/config/memonly`

if [ x${LEGACY} = xtrue ]; then
  echo "legacy"
elif [ x${ADVANCED} = xtrue ]; then
  echo "advanced"
elif [ x${SDRM} = xtrue ]; then
  echo "sdrm"
else
  echo "default"
fi
