#!/bin/bash

# $Id: hostname_lookup.sh 89860 2011-08-30 00:19:46Z timlee $
# $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/hostname_lookup.sh $
#
# Called from md_system.c with parameters which are candidates to
# yield a FQDN.
#
# Returns the FQDN of the first parameter which resolves using the
# /usr/bin/host command.
#

for addr in $*
do
    HOST_OUTPUT=`/usr/bin/host $addr | /bin/grep -E 'has address|has IPv6 address|domain name pointer'`

    # market.nbttech.com has address 10.32.137.23
    # -> market.nbttech.com
    OUTPUT=`echo $HOST_OUTPUT | /bin/awk '/has address/ {print $1; exit;}'`
    [ -n "$OUTPUT" ] && echo $OUTPUT && exit 0

    # lodgeit.lab.nbttech.com has IPv6 address 2600:809:200:481:250:56ff:fea7:1bff
    # -> lodgeit.lab.nbttech.com
    OUTPUT=`echo $HOST_OUTPUT | /bin/awk '/has IPv6 address/ {print $1; exit;}'`
    [ -n "$OUTPUT" ] && echo $OUTPUT && exit 0

    # 23.137.32.10.in-addr.arpa domain name pointer market.nbttech.com.
    # -> market.nbttech.com
    OUTPUT=`echo $HOST_OUTPUT | /bin/awk '/domain name pointer/ {print $5; exit;}' | /bin/sed -e 's,\.$,,'`
    [ -n "$OUTPUT" ] && echo $OUTPUT && exit 0
done

exit 1
