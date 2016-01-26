#!/bin/sh

# mine deployed systems for errors and warnings.
#
# install as an hourly system cronjob:
# 5 * * * * /sbin/minelog.sh

PATH=/usr/local/bin:/opt/tms/bin:/usr/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/X11R6/bin:/var/home/root/bin:/opt/tms/bin:/var/home/root/bin

cd /var/log

if [ ! -e "messages.1.gz" ]; then
  exit 0
fi

if [ -e "lastminedlog" ]; then
  ll=`cat lastminedlog`
  tl=`sha1sum messages.1.gz`
  if [ x"$tl" = x"$ll" ]; then
    # The log file has not been rotated
    howlong=`find /var/log/lastminedlog -cmin +1441`
    if [ x"$howlong" = x"/var/log/lastminedlog" ]; then
      # Not rotated within 24 hours, send out a status
      ( echo "To: logminer" &&                                    \
        echo "Subject: logs" &&                                   \
        echo &&                                                   \
        ( ( ( echo "show info" | cli ) &&                         \
            echo &&                                               \
            echo "WARN: no log rotation in a 24 hour period" )    \
          | gzip -c | uuencode - ) )                              \
      | ssmtp logminer@riverbed.com
      touch /var/log/lastminedlog
    fi
    exit 0
  fi
fi

sha1sum messages.1.gz > lastminedlog

( echo "To: logminer" &&                                    \
  echo "Subject: logs" &&                                   \
  echo &&                                                   \
  ( ( ( echo "show info" | cli ) &&                         \
      echo &&                                               \
      zgrep -e '\.ERR|\.WARN|\.CRIT' messages.1.gz )        \
    | gzip -c | uuencode - ) )                              \
| ssmtp logminer@riverbed.com

exit 0 

