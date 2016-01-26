#!/bin/sh
#
# raid_diagram.sh
#
# $Id: raid_diagram.sh 12295 2006-05-16 23:26:26Z phamson $

FAILED=$2
REBUILD=$3
MISSING=$4
seperator="------------------------------------"
legend="O = online; S = spare;\nF = failed; R = rebuild; M = missing"

echo_drive()
{
    for i in $FAILED
    do
      if [ "$i" = "$1" ]
	  then 
	  echo "$1(F)"
	  return 0
      fi
    done

    for i in $REBUILD
    do
      if [ "$i" = "$1" ]
	  then 
	  echo "$1(R)"
	  return 0
      fi
    done

    for i in $MISSING
    do
      if [ "$i" = "$1" ]
	  then 
	  echo "$1(M)"
	  return 0
      fi
    done

    echo "$1(O)"
}

echo $1

case $1 in
    "6020")

        row1="[=======][=======][=======][=======]\n"'[  '`echo_drive 1`' ]''[  '`echo_drive 2`' ]''[  '`echo_drive 3`' ]''[  '`echo_drive 4`' ]'"\n[=======][=======][=======][=======]"
        row2="[=======][=======][=======][=======]\n"'[  '`echo_drive 5`' ]''[  '`echo_drive 6`' ]''[  '`echo_drive 7`' ]''[  '`echo_drive 8`' ]'"\n[=======][=======][=======][=======]"
        row3="[=======][=======][=======][=======]\n"'[  N/A  ]''[  N/A  ]''[  N/A  ]''[   S   ]'"\n[=======][=======][=======][=======]"

        echo -e "$row3"
        echo -e "$seperator"
        echo -e "$row2"
        echo -e "$seperator"
        echo -e "$row1"
        echo -e "$seperator"
	echo -e "$legend"
        ;;
    "5000" | "5520")

        row1="[=======][=======][=======][=======]\n"'[  '`echo_drive 1`' ]''[  '`echo_drive 2`' ]''[  '`echo_drive 3`' ]''[  '`echo_drive 4`' ]'"\n[=======][=======][=======][=======]"
        row2="[=======][=======][=======][=======]\n"'[  '`echo_drive 5`' ]''[  '`echo_drive 6`' ]''[  N/A  ]''[  N/A  ]'"\n[=======][=======][=======][=======]"
        row3="[=======][=======][=======][=======]\n"'[  N/A  ]''[  N/A  ]''[  N/A  ]''[   S   ]'"\n[=======][=======][=======][=======]"

        echo -e "$row3"
        echo -e "$seperator"
        echo -e "$row2"
        echo -e "$seperator"
        echo -e "$row1"
        echo -e "$seperator"
	echo -e "$legend"
        ;;
    "3000" | "3020" | "3520")

        row1="[=======][=======][=======][=======]\n"'[  '`echo_drive 1`' ]''[  '`echo_drive 2`' ]''[  '`echo_drive 3`' ]''[  '`echo_drive 4`' ]'"\n[=======][=======][=======][=======]"
        row2="[=======][=======][=======][=======]\n"'[  N/A  ]''[  N/A  ]''[  N/A  ]''[  N/A  ]'"\n[=======][=======][=======][=======]"
        row3="[=======][=======][=======][=======]\n"'[  N/A  ]''[  N/A  ]''[  N/A  ]''[   S   ]'"\n[=======][=======][=======][=======]"

        echo -e "$row3"
        echo -e "$seperator"
        echo -e "$row2"
        echo -e "$seperator"
        echo -e "$row1"
        echo -e "$seperator"
	echo -e "$legend"

        ;;
        *)
        echo "Please see physical label on appliance"
        ;;
esac
