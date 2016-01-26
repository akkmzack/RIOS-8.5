#!/bin/bash

# $Id: sum-openssl-wrapper.sh 101347 2012-12-06 19:47:08Z timlee $
# $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/linux_rhel/6/image_files/sum-openssl-wrapper.sh $
# Copyright 2012 Riverbed Technology.  All rights reserved.
#
# This is a wrapper script to call openssl in place of
# md5sum, sha1sum, sha256sum, sha512sum.  It emulates the
# command line options and output of these programs from
# coreutils.

usage() {
    echo "usage: $0 [OPTION]... [FILE]..."
    exit 1
}

check=0
quiet=0
status=0
warn=0
count=0
failed=0
rc=0

parse=`/usr/bin/getopt -l 'binary,check,text,quiet,status,warn,help' -- 'bctw' "$@"`
eval set -- "$parse"
while true ; do
    case "$1" in
        --binary) shift ;;
        -b) shift ;;
        --text) shift ;;
        -t) shift ;;
        --check) check=1 ; shift ;;
        -c) check=1 ; shift ;;
        --quiet) quiet=1 ; shift ;;
        --status) status=1 ; shift ;;
        --warn) warn=1 ; shift ;;
        -w) warn=1 ; shift ;;
        --help) usage ;;
        --) shift; break ;;
        *) echo "$0: unrecognized option '$1'" ; exit 1 ;;
    esac
done

if [ $status -ne 0 ]; then
    warn=0
    quiet=1
fi

hash=`echo $0 | /bin/sed -e 's,.*/,,' -e 's/sum//'`

check_valid_sum() {
    len=`echo $1 | /usr/bin/wc -c`
    [ "$hash" = "sha512" -a "$len" = "129" ] && echo 1;
    [ "$hash" = "sha384" -a "$len" = "97" ] && echo 1;
    [ "$hash" = "sha256" -a "$len" = "65" ] && echo 1;
    [ "$hash" = "sha224" -a "$len" = "57" ] && echo 1;
    [ "$hash" = "sha1" -a "$len" = "41" ] && echo 1;
    [ "$hash" = "md5" -a "$len" = "33" ] && echo 1;
}

check_stdin() {
    line=0
    failed=0
    count=0
    while [ 1 = 1 ]; do
        line=`/usr/bin/expr $line + 1`
        read sum file_to_sum
        [ $? -ne 0 ] && break
        valid=`check_valid_sum $sum`
        if [ "x$file_to_sum" = "x" -o "x$valid" = "x" ]; then
            [ $warn -ne 0 ] && echo "$0: $f: $line: improperly formatted $hash checksum line"
            continue;
        fi
        test_sum=`/usr/bin/openssl dgst -$hash $file_to_sum | /bin/awk -F '[ ()=]*' '{ print $3"  "$2 }'`
        if [ "x$test_sum" = "x$sum  $file_to_sum" ]; then
            [ $quiet -eq 0 ] && echo "$file_to_sum: OK"
        else
            [ $quiet -eq 0 ] && echo "$file_to_sum: FAILED"
            failed=`/usr/bin/expr $failed + 1`
            rc=1
        fi
        count=`/usr/bin/expr $count + 1`
    done
}

check() {
    if [ "x$files" = x ]; then
        check_stdin
    else
        for f in $files ; do
            if [ -f $f ]; then
                check_stdin < $f
                if [ $failed -ne 0 ]; then
                    [ $status -eq 0 ] && echo "$0: WARNING: $failed of $count computed checksums did NOT match"
                    rc=1
                fi
            fi
        done
    fi
}

files=$@
if [ $check -ne 0 ]; then
    check $files
elif [ "x$files" = "x" ]; then
    output=`/usr/bin/openssl dgst -$hash`
    rc=$?
    echo -n "$output" | /bin/awk -F '[ ()=]*' '{ print $3"  -" }'
else
    for f in $files ; do
        [ "x$f" = "x-" ] && f=''
        output=`/usr/bin/openssl dgst -$hash $f`
        [ $? -ne 0 ] && rc=1
        echo -n "$output" | /bin/awk -F '[ ()=]*' '{ print $3"  "$2 }'
    done
fi
exit $rc
