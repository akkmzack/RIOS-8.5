#!/bin/sh

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

usage()
{
    echo "usage: $0 -s \"Subject\"  -t \"addr@example.com\" \
        -c \"cc@example.com\" -i inline.txt [-h htmlmime] [-S sendmail_opts] \
        [-P preamble.txt] [-m mime type] \
        [-o outputfile] [-a]"
    echo ""
    exit 1
}

PARSE=`/usr/bin/getopt -s sh 's:t:c:i:h:S:P:m:o:a' "$@"`

if [ $? != 0 ] ; then
    usage
fi

eval set -- "$PARSE"
    
MAIL_SUBJECT="No subject"
ADDR_TO=
ADDR_CC=
INLINE_FILE=
HTML=
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
        -h) HTML=$2; shift 2 ;;
        -S) SENDMAIL_OPTS=$2; shift 2 ;;
        -P) PREAMBLE_FILE=$2; shift 2 ;;
        -m) MIME_TYPE=$2; shift 2 ;;
        -o) DO_MAIL=0; OUTPUT_FILE=$2; shift 2 ;;
        -a) GEN_CID=1; shift ;;
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
echo ${B64CONV_2}

MIME_BOUNDARY="`dd if=/dev/urandom bs=15 count=1 2> /dev/null | ${B64CONV_1} | ${B64CONV_2}`"

echo "To: ${ADDR_TO}" >> ${OUTPUT_FILE}
if [ ! -z "${ADDR_CC}" ]; then
    echo "Cc: ${ADDR_CC}"  >> ${OUTPUT_FILE}
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
    if [ ! -z "${HTML}" ]; then
        echo "Content-Type: ${HTML}; charset=us-ascii" >> ${OUTPUT_FILE}
    else    
        echo "Content-Type: text/plain; charset=us-ascii" >> ${OUTPUT_FILE}
    fi
    echo "Content-Disposition: inline" >> ${OUTPUT_FILE}
    echo "" >> ${OUTPUT_FILE}
    echo "`cat ${INLINE_FILE}`" >> ${OUTPUT_FILE}
fi

# Attachments
for attach in ${ATTACH_FILES}; do
    attach_base=`basename $attach`
    echo "" >> ${OUTPUT_FILE}
    echo "--${MIME_BOUNDARY}" >> ${OUTPUT_FILE}
    echo "Content-Type: ${MIME_TYPE}; name=$attach_base" >> ${OUTPUT_FILE}
    if [ "${GEN_CID}" != "" ]; then
        echo "Content-ID: <$attach_base>" >> ${OUTPUT_FILE}
        echo "Content-Disposition: inline; filename=\"$attach_base\"" >> ${OUTPUT_FILE}
    else
        echo "Content-Disposition: attachment; filename=\"$attach_base\"" >> ${OUTPUT_FILE}
    fi
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
