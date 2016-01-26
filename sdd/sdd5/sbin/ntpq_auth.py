#!/usr/bin/env python
#
# Revision:  $Revision: 102205 $
# Date:      $Date: 2013-01-18 17:32:06 -0800 (Fri, 18 Jan 2013) $
# Author:    $Author: cscuderi $
# URL:       $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/ntpq_auth.py $
# 
# (C) Copyright 2012 Riverbed Technology, Inc.
# All rights reserved.
"""!
This script is used by the ntp state node path
/ntp/state/remote/* to build a list of active peers, 
key id per peer, and the current status of the 
authentication.
"""
import subprocess
import re

# Get the list of association IDs
asso = subprocess.Popen(['ntpq', '-c', 'asso'], stdout=subprocess.PIPE)

# Sample output of ntpq -c asso:
#
# ind assID status  conf reach auth condition  last_event cnt
# ===========================================================
#   1 15641  9414   yes   yes  none  candidat   reachable  1
#   2 15642  9414   yes   yes  none  candidat   reachable  1
#   3 15643  9314   yes   yes  none   outlyer   reachable  1
#   4 15644  9314   yes   yes  none   outlyer   reachable  1
#   5 15645  9614   yes   yes  none  sys.peer   reachable  1
#   6 15646  f314   yes   yes   ok    outlyer   reachable  1
#
for line in asso.stdout:
    if not re.search('\s*\d+\s*\d+', line):
        continue

    # Was this peer configured or learned?
    if line.split()[3] == 'yes':
        conf_status = True
    else:
        conf_status = False

    # Pull status from "association" output
    if line.split()[5] == 'ok':
        auth_status = True
    else:
        auth_status = False

    # Is this the peer we are getting time info from?
    if line.split()[6] == 'sys.peer':
        active_sync = True
    else:
        active_sync = False

    # Find key and hostname
    peer = line.split()[1]
    rv = subprocess.Popen(['ntpq', '-c', 'rv ' + peer], 
                          stdout=subprocess.PIPE)
    rv_output = rv.stdout.read()
    rv.wait()

    # Sample output of ntpq -c rv assID:
    #
    # assID=15641 status=9414 reach, conf, sel_candidat, 1 event, event_reach,
    # srcadr=mirror, srcport=123, dstadr=10.5.16.66, dstport=123, leap=00,
    # stratum=2, precision=-20, rootdelay=2.548, rootdispersion=40.726,
    # refid=204.9.54.119, reach=377, unreach=0, hmode=3, pmode=4, hpoll=10,
    # ppoll=10, flash=00 ok, keyid=0, ttl=0, offset=-2.173, delay=152.725,
    # dispersion=15.079, jitter=2.380,
    # reftime=d4a46ac7.df6d848d  Fri, Jan 18 2013 16:43:51.872,
    # org=d4a46f7b.7861c30d  Fri, Jan 18 2013 17:03:55.470,
    # rec=d4a46f7b.8cce809b  Fri, Jan 18 2013 17:03:55.550,
    # xmt=d4a46f7b.63d8322f  Fri, Jan 18 2013 17:03:55.390,
    # filtdelay=   159.98  152.72  153.26  154.86  154.50  150.89  161.34  165.88,
    # filtoffset=    0.21   -2.17   -1.95   -1.45   -2.26   -4.61    1.07    2.90,
    # filtdisp=      0.00   15.38   23.06   30.77   38.48   46.14   53.81   61.50
    # 
    #
    # Parse 'rv' command output for the peer
    keymatch = re.search('keyid=(.*?),', rv_output)
    srcmatch = re.search('srcadr=(.*?),', rv_output)
    refmatch = re.search('refid=(.*?),', rv_output)

    # refid of AUTH indicates an authentication failure
    # overwrite the previous auth status
    if refmatch.group(1) == 'AUTH':
        auth_status = False

    print '%s,%s,%s,%s,%s,%s' % (srcmatch.group(1), refmatch.group(1), active_sync, conf_status, auth_status, keymatch.group(1))
       
asso.wait()



