#!/usr/bin/env python
#
# Filename:  $Source$
# Revision:  $Revision: 103119 $
# Date:      $Date: 2013-02-22 11:02:56 -0800 (Fri, 22 Feb 2013) $
# Author:    $Author: cscuderi $
# URL:       $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/host_resolve.py $
# 
# (C) Copyright 2012 Riverbed Technology, Inc.
# All rights reserved.
"""!
This script is used by the host-labels mgmtd module.
It is responsible for resolving a list of domain names
and returning the ip addresses
"""

import socket
import sys
import syslog
import os

syslog.openlog("host_resolve[%s]" % os.getpid())

filePath = ' '.join(sys.argv[1:])
with open(filePath, 'r') as f:
    domain_list = f.read().split()

# Remove any duplicate domain names
domain_list = dict.fromkeys(domain_list).keys()

for domain in domain_list:
    try:
        resolved = set()
        # Build the list of IPv4 addresses, remove duplicates
        for item in socket.getaddrinfo(domain, None, 2):
            family, socktype, proto, canonname, addr = item      
            resolved.add(addr[0])
    except socket.error, msg:
        syslog.syslog("[host_resolve.ERR] %s: %s" % (domain, msg))
      
    # Print the results to stdout
    print domain,
    for addr in resolved:
        print addr,
    
    print '\n'
 
