#!/bin/bash

#
#
# Copyright 2008 Riverbed Technology, Inc. 
# All Rights Reserved. Confidential.
#
#

function usage
{
    echo "Usage: $(basename $0) -u user -p password -s servername -r realm"
    echo "-u user               User account with delegation privileges."
    echo "-p password           User's password. If not given, shall be "
    echo "                      prompted for during the run."
    echo "-s servername         Windows CIFS/Exchange server. "
    echo "-v service            Service name [cifs|exchangeMDB]. Default: cifs"
    echo "-r realm              Realm/Domain."
}

function to_upper
{
    echo $1 | tr  "[:lower:]" "[:upper:]"
}


function accept_input
{
    while getopts  u:p:s:v:r:h option
    do
        case $option in
            u) user=$OPTARG;;
            p) password=$OPTARG;;
            s) server=$OPTARG;;
            v) service=$OPTARG;;
            r) realm=$OPTARG;;
            h) usage;; 
            \?) usage
                exit 1;;
        esac
    done

    if [ "foo$user" = "foo" -o "foo$server" = "foo" -o "foo$realm" = "foo" ]; then
        usage
        exit 1
    fi

    if [ "foo$service" = "foo" ]; then
        service="cifs"
    fi

    #Read in password if not provided
    if [ "foo$password" = "foo" ]; then
        echo -n "Enter password for $user: "
        oldmodes=`stty -g`
        stty -echo
        read password
        stty $oldmodes
    fi

    # be sure to uppercase realm
    realm=`to_upper $realm`
}

function test_constrained_delegation
{
    if [ "foo$HEIM_TOOLS_BIN" = "foo" ]; then
        export HEIM_TOOLS_BIN=/usr/heimdal/bin
    fi
    tmpdir=`mktemp -d -t ".krbcdtmpXXXX"`
    echo $password > $tmpdir/pass
    fuser=$user\@$realm
    fserver=$server\.$realm\@$realm
    echo "Testing constrained delegation for "
    echo "User: $fuser"
    echo "Server: $fserver"
    echo "Service: $service"
    echo ""
    $HEIM_TOOLS_BIN/kinit --forwardable --cache=$tmpdir/user_cc --password-file=$tmpdir/pass  $fuser
    if [ $? != 0 ]; then
        echo "Error in kinit."
        rm -rf $tmpdir
        return 2
    fi
    $HEIM_TOOLS_BIN/kgetcred --cache=$tmpdir/user_cc --impersonate=$fuser --out-cache=$tmpdir/impersonate_cc --forwardable $fuser
    if [ $? != 0 ]; then
        echo -e "Error in obtaining impersonation ticket.\\n"
        echo "Delegate user's CC:"
        $HEIM_TOOLS_BIN/klist -c $tmpdir/user_cc
        rm -rf $tmpdir
        return 2
    fi
    $HEIM_TOOLS_BIN/kgetcred --cache=$tmpdir/user_cc --delegation-credential-cache=$tmpdir/impersonate_cc --forwardable --out-cache=$tmpdir/service_cc $service/$fserver
    if [ $? != 0 ]; then
        echo -e "Error in obtaining service ticket for $service/$server.\\n"
        echo "Delegate user's CC:"
        $HEIM_TOOLS_BIN/klist -c $tmpdir/user_cc
        echo -e "\\nImpersonated user's CC:"
        $HEIM_TOOLS_BIN/klist -c $tmpdir/impersonate_cc
        rm -rf $tmpdir
        return 2
    fi
    rm -rf $tmpdir
}


#MAIN

export user
export password
export server
export service
export realm
accept_input $*
test_constrained_delegation
if [ $? == 0 ]; then
    echo -e "\\nConstrained delegation settings are fine."
else
    echo -e "\\nConstrained delegation settings are broken."
fi
