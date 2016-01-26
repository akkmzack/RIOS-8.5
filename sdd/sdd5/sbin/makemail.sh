#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 93812 $
#  Date:      $Date: 2011-11-02 09:43:16 -0700 (Wed, 02 Nov 2011) $
#  Author:    $Author: kguragain $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#


PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

usage()
{
    echo "usage: $0 -s \"Subject\"  -t \"addr@example.com\" \
        -c \"cc@example.com\" -i inline.txt [-S sendmail_opts] \
        [-P preamble.txt] [-m mime type] \
        [-o outputfile]"
    echo ""
    exit 1
}

PARSE=`/usr/bin/getopt -s sh 's:t:c:i:S:P:m:o:r:' "$@"`

if [ $? != 0 ] ; then
    usage
fi

eval set -- "$PARSE"
    
MAIL_SUBJECT="No subject"
ADDR_TO=
ADDR_CC=
REPLY_TO=
INLINE_FILE=
SENDMAIL_OPTS=
PREAMBLE_FILE=
PREAMBLE_STRING="This is a multi-part message in MIME format."
MIME_TYPE=application/octet-stream
DO_MAIL=1
DO_STDOUT=0
OUTPUT_FILE=

while true ; do
    case "$1" in
        -s) MAIL_SUBJECT=$2; shift 2 ;;
        -t) ADDR_TO=$2; shift 2 ;;
        -c) ADDR_CC=$2; shift 2 ;;
        -i) INLINE_FILE=$2; shift 2 ;;
        -S) SENDMAIL_OPTS=$2; shift 2 ;;
        -P) PREAMBLE_FILE=$2; shift 2 ;;
        -m) MIME_TYPE=$2; shift 2 ;;
        -o) DO_MAIL=0; OUTPUT_FILE=$2; shift 2 ;;
        -r) REPLY_TO=$2; shift 2 ;;
        --) shift ; break ;;
        *) echo "makemail.sh: parse failure: $1" >&2 ; usage ;;
    esac
done

ATTACH_FILES="$*"

if [ -z "${ATTACH_FILES}" -a -z "${INLINE_FILE}" ] ; then
    usage
fi

if [ -z "${ADDR_TO}" ]; then
    usage
fi

if [ ${DO_MAIL} -eq 0 ]; then
    if [ "${OUTPUT_FILE}" = "-" ]; then
        DO_STDOUT=1
        OUTPUT_FILE=
    fi
fi

if [ -z "${OUTPUT_FILE}" ]; then
    OUTPUT_FILE=/var/tmp/mm-temp-$$
    rm -f ${OUTPUT_FILE}
    touch ${OUTPUT_FILE}
    chmod 600 ${OUTPUT_FILE}
fi

# gnu uuencode wants to print a header and footer we don't want
B64CONV_1="uuencode -m -"
B64CONV_2="sed -e 1d -e \$d"

MIME_BOUNDARY="`dd if=/dev/urandom bs=15 count=1 2> /dev/null | ${B64CONV_1} | ${B64CONV_2}`"

echo "To: ${ADDR_TO}" >> ${OUTPUT_FILE}
if [ ! -z "${ADDR_CC}" ]; then
    echo "Cc: ${ADDR_CC}"  >> ${OUTPUT_FILE}
fi
if [ ! -z "${REPLY_TO}" ]; then
    echo "Reply-To: ${REPLY_TO}"  >> ${OUTPUT_FILE}
fi
echo "Subject: ${MAIL_SUBJECT}"  >> ${OUTPUT_FILE}
echo "Mime-Version: 1.0"  >> ${OUTPUT_FILE}
echo "Content-Type: multipart/mixed; boundary=\"${MIME_BOUNDARY}\""  >> ${OUTPUT_FILE}
if [ ! -z "${INLINE_FILE}" ]; then
    echo "Content-Disposition: inline"  >> ${OUTPUT_FILE}
fi
echo "User-Agent: tmsmakemail/1.0"  >> ${OUTPUT_FILE}
echo "" >> ${OUTPUT_FILE}

if [ ! -z "${PREAMBLE_FILE}" ]; then
    echo "`cat ${PREAMBLE_FILE}`" >> ${OUTPUT_FILE}
elif [ ! -z "${PREAMBLE_STRING}" ]; then
    echo "${PREAMBLE_STRING}" >> ${OUTPUT_FILE}
fi

# Inline text
if [ ! -z "${INLINE_FILE}" ]; then
    echo "" >> ${OUTPUT_FILE}
    echo "--${MIME_BOUNDARY}" >> ${OUTPUT_FILE}
    echo "Content-Type: text/plain; charset=us-ascii" >> ${OUTPUT_FILE}
    echo "Content-Disposition: inline" >> ${OUTPUT_FILE}
    echo "" >> ${OUTPUT_FILE}
    echo "`cat ${INLINE_FILE}`" >> ${OUTPUT_FILE}
fi

# Attachments
for attach in ${ATTACH_FILES}; do
    attach_base=`basename $attach`
    echo "" >> ${OUTPUT_FILE}
    echo "--${MIME_BOUNDARY}" >> ${OUTPUT_FILE}
    echo "Content-Type: ${MIME_TYPE}" >> ${OUTPUT_FILE}
    echo "Content-Disposition: attachment; filename=\"$attach_base\"" >> ${OUTPUT_FILE}
    echo "Content-Transfer-Encoding: base64" >> ${OUTPUT_FILE}
    echo "" >> ${OUTPUT_FILE}
    echo "`cat ${attach} | ${B64CONV_1} | ${B64CONV_2}`" >> ${OUTPUT_FILE}
done

echo "" >> ${OUTPUT_FILE}
echo "--${MIME_BOUNDARY}--" >> ${OUTPUT_FILE}
echo "" >> ${OUTPUT_FILE}

if [ ${DO_MAIL} -eq 1 ]; then
    cat ${OUTPUT_FILE} | /usr/lib/sendmail ${SENDMAIL_OPTS} -t
    rm ${OUTPUT_FILE}
fi

if [ ${DO_STDOUT} -eq 1 ]; then
    cat ${OUTPUT_FILE}
    rm ${OUTPUT_FILE}
fi

exit 0
