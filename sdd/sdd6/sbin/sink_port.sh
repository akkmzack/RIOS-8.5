#!/bin/bash
#
# Use socat to listen to the specified TCP port.  Read 
# any data off of the socket and dump it into /dev/null.
# The idea is that the connection is routed between a pair
# of appliances, and that transferring data in this way will
# "warm" the segment store on each of them.
#

SOCAT=/usr/bin/socat
PORT=8777

if [ "$1" != "" ]; then
    PORT=$1
fi

exec ${SOCAT} -u TCP4-LISTEN:${PORT},reuseaddr,fork OPEN:/dev/null
