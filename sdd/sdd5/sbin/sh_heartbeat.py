#!/usr/bin/python
#
# Revision:    $Revision
# Date:        $Date
# Author:      $Author
#
# Report various counters via heartbeat.
#
# (C) Copyright 2013 Riverbed Technology, Inc.
# All rights reserved.
#

from optparse import OptionParser
import sys, Mgmt

def initMgmt():
    Mgmt.open(gcl_provider='mgmtd')

def killMgmt():
    Mgmt.close()

def is_interceptor_in_cluster():
    RSI = '/rbt/sport/intercept'
    names = Mgmt.get_children(RSI + '/config/neighbor/name')[0]
    
    for name in names:
        is_interceptor = Mgmt.get_value(RSI + '/neighbor/' + \
		         name + '/is_interceptor') == 'true'
        if is_interceptor:
            return True
    
    return False;

def main():
    parser = OptionParser()
    parser.add_option( "--interceptor_in_cluster", action="store_true",
               help="indicates if an Interceptor is present in the cluster")
    (opts, args) = parser.parse_args()

    initMgmt()

    if opts.interceptor_in_cluster:
        print is_interceptor_in_cluster()
    else:
        print 0;

    killMgmt()

if __name__ == "__main__":
    sys.exit(main())
