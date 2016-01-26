#!/bin/sh
#
#  Filename:  $Source$
#  Revision:  $Revision: 64174 $
#  Date:      $Date: 2010-03-31 11:09:01 -0700 (Wed, 31 Mar 2010) $
#  Author:    $Author: amoghe $
# 
#  (C) Copyright 2002-2008 Riverbed Technology, Inc.
#  All rights reserved.
#
#  Script used to handle the web management interface's SSL certs/keys
#
######################################################################

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

######################################################################
#
# PATHS
#
######################################################################

GETOPT=/usr/bin/getopt
OPENSSL=/opt/rbt/bin/openssl
CONFIG=/var/tmp/newopenssl.cnf
SEED=/proc/apm:/proc/cpuinfo:/proc/dma:/proc/filesystems:/proc/interrupts:/proc/ioports:/proc/pci:/proc/rtc:/proc/uptime
WEB_HOST=/var/opt/tms/web/conf/server.hostname
WEB_KEY=/var/opt/tms/web/conf/server.key
WEB_CERT=/var/opt/tms/web/conf/server.crt
WEB_CUSTOM=/var/opt/tms/web/conf/server.custom
TMP_WEB_KEY=/var/opt/tms/web/conf/server.key.tmp
TMP_WEB_CERT=/var/opt/tms/web/conf/server.crt.tmp
TMP_WEB_KEY_OUT=/var/tmp/server.key.out

######################################################################
#
# Script
#
######################################################################

usage()
{
    echo "usage: $0 -m <check|generate|update> [-n hostname] [-t path-to-text-file]"
    exit 1
}

PARSE=`$GETOPT -- 'm:n:t:' "$@"`
if [ $? != 0 ] ; then
    usage
fi

eval set -- "$PARSE"
MODE=
OPT_HOSTNAME=0
VAL_HOSTNAME=
OPT_TEXT=0
VAL_TEXT=
while true ; do
    case "$1" in
        -m) MODE="$2"; shift 2;;
        -n) OPT_HOSTNAME=1; VAL_HOSTNAME="$2"; shift 2;;
        -t) OPT_TEXT=1; VAL_TEXT="$2"; shift 2;;
        --) shift; break;;
         *) usage;;
    esac
done

if [ "x$MODE" = "x" ]; then
    usage
fi

if [ "$OPT_HOSTNAME" = "1" ] ; then
	if [ "x$VAL_HOSTNAME" = "x" ]; then
        usage
    fi
fi

if [ "$MODE" != "check" -a "$MODE" != "update" -a "$MODE" != "generate" ]; then
    usage
fi

# There is a product specific component to self-signed cert generation
# so we need to load the values in if they exist.
if [ -f /etc/customer.sh ]; then
    . /etc/customer.sh
fi

# if hostname was not specified, we need to read in the hostname.
if [ "x$VAL_HOSTNAME" = "x" ]; then
    CUR_HOSTNAME=`hostname`
else
    CUR_HOSTNAME=$VAL_HOSTNAME
fi

# make sure we set the correct umask so any created files have the
# correct permissions set.
umask 022

# function to generate a new SSL key
generate_ssl_key() {
    rm -f $WEB_KEY
    rm -f $WEB_CUSTOM
    $OPENSSL genrsa -rand "$SEED" 1024 > $WEB_KEY 2> /dev/null
    if [ $? != 0 ]; then
        echo "Failed to generate key."
        exit 1
    fi
}

# function to generate a new self-signed SSL cert
generate_ssl_cert() {
    rm -f $WEB_CERT
    GEN_ARGS="req -new -key $WEB_KEY -x509 -days 365 -out $WEB_CERT"
    if [ -e $CONFIG ]; then
        GEN_ARGS=$GEN_ARGS" -config $CONFIG"
    fi
    cat << EOF | $OPENSSL $GEN_ARGS 2> /dev/null
--
$SSL_CERT_HEADER
$CUR_HOSTNAME
admin@$CUR_HOSTNAME
EOF
    if [ $? != 0 ]; then
        echo "Failed to generate certificate."
        exit 1
    fi
}

# function to check if a cert has expired
check_ssl_cert_expiry() {
    $OPENSSL verify $WEB_CERT | grep "error 10 " > /dev/null 2>&1
    if [ $? = 0 ]; then
        return 1
    fi
    return 0
}

# we need to key off the mode now.
# check - the check mode is basically to run a sanity check to make
# sure that a certificate/key pair exist and that they have not
# expired. the expiry check is only done against self-signed certs
# as we don't want to purge any user added ones automatically.
# generate - the generate mode overwrites any existing cert/key pair
# and replaces them with a new key and a self-signed cert.
# update - the update mode works differently depending on what type
# of cert/key pair exist. if it's a self-signed cert, the cert will
# be updated. if it's a user uploaded cert/key pair, then an action
# will only be taken if the '-t' text option was specified.
case "$MODE" in
    check)
        # if the web key doesn't exist, generate one.
        KEY_GENERATED=0
        if [ ! -f $WEB_KEY ]; then
            generate_ssl_key
            KEY_GENERATED=1
        fi

        # if the cert doesn't exist or the key was regenerated, generate one.
        if [ ! -f $WEB_CERT -o KEY_GENERATED = 1 ]; then
            generate_ssl_cert
        else
            if [ ! -f $WEB_CUSTOM ]; then
                OLD_HOSTNAME=old_$CUR_HOSTNAME
                if [ -f $WEB_HOST ]; then
                    OLD_HOSTNAME=`cat $WEB_HOST`
                fi

                check_ssl_cert_expiry
                CERT_EXPIRED=$?
                if [ $CERT_EXPIRED = 1 -o $CUR_HOSTNAME != $OLD_HOSTNAME ]; then
                    generate_ssl_cert
                fi
            fi
        fi
        ;;

    generate)
        generate_ssl_key
        generate_ssl_cert
        ;;

    update)
        if [ $OPT_TEXT = 1 ]; then

            # parse out the certificate and it's ok if there isn't one.
            $OPENSSL x509 -in $VAL_TEXT -out $TMP_WEB_CERT > /dev/null 2>&1
            CERT_RESULT=$?

            # parse out the key and it's ok if there isn't one.
            # but if there is one, we can only take unencrypted keys.
            $OPENSSL rsa -in $VAL_TEXT -out $TMP_WEB_KEY -passin pass:"" > $TMP_WEB_KEY_OUT 2>&1
            KEY_RESULT=$?

            grep "bad password" $TMP_WEB_KEY_OUT > /dev/null 2>&1
            NO_PASSWORD=$?
            rm -f $TMP_WEB_KEY_OUT

            if [ $NO_PASSWORD = 0 ]; then
                echo "Cannot use encrypted keys."
                exit 1
            fi

            # determine which cert to use, the existing one or the new one.
            CHECK_WEB_CERT=$WEB_CERT
            if [ $CERT_RESULT = 0 ]; then
                CHECK_WEB_CERT=$TMP_WEB_CERT
            fi

            # determine which key to use, the existing one or the new one.
            CHECK_WEB_KEY=$WEB_KEY
            if [ $KEY_RESULT = 0 ]; then
                CHECK_WEB_KEY=$TMP_WEB_KEY
            fi

            # compute modulus on web cert
            MODULUS_CERT=`$OPENSSL x509 -in $CHECK_WEB_CERT -noout -modulus`
            if [ $? != 0 ]; then
                echo "Failed to parse certificate."
                rm -f $TMP_WEB_KEY
                rm -f $TMP_WEB_CERT
                exit 1
            fi

            # compute modulus on web key
            MODULUS_KEY=`$OPENSSL rsa -in $CHECK_WEB_KEY -noout -modulus`
            if [ $? != 0 ]; then
                echo "Failed to parse key."
                rm -f $TMP_WEB_KEY
                rm -f $TMP_WEB_CERT
                exit 1
            fi

            # compare and error if we have a mismatch.
            if [ "x$MODULUS_CERT" != "x$MODULUS_KEY" ]; then
                echo "Certificate and key do not match."
                rm -f $TMP_WEB_KEY
                rm -f $TMP_WEB_CERT
                exit 1
            fi

            if [ $CERT_RESULT = 0 ]; then
                rm -f $WEB_CERT
                mv $TMP_WEB_CERT $WEB_CERT
            fi

            if [ $KEY_RESULT = 0 ]; then
                rm -f $WEB_KEY
                mv $TMP_WEB_KEY $WEB_KEY
            fi

            touch $WEB_CUSTOM
        else
            if [ ! -f $WEB_CUSTOM ]; then
                generate_ssl_cert
            fi
        fi
        ;;
esac

# update the hostname file
rm -f $WEB_HOST
echo $CUR_HOSTNAME > $WEB_HOST
exit 0
