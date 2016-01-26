#!/usr/bin/python

import sys
import socket

if len(sys.argv) != 4:
    exit(1)

username = sys.argv[1]
userhost = sys.argv[2]
should_allow = sys.argv[3]
thishost = socket.gethostname()

# if username is rcud, and localhost, then always allow.
# if username is rcud, and not localhost, always deny. simple, eh?
if username == "rcud":
    # always allow if this host, do caseless comparison
    if userhost.lower() == thishost.lower():
        exit(0)
    else:
        exit(1)

#if not sharing, then don't allow anyone (already did RCUD check above)
if should_allow == "no":
    exit(1)

exit(0)
