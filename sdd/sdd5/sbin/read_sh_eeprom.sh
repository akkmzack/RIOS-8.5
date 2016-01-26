#!/bin/sh

EEP_CACHE=/var/tmp/eeprom_cache

# Function to parse the minnow eeprom
parse_minnow_eeprom() {
	local FILE_EEPROM=$1
	local FILE=/var/tmp/eeprom.bin
	rm -f $FILE 
	if [ -e $FILE_EEPROM ]; then
		cat $FILE_EEPROM > $FILE
		echo >>${EEP_CACHE} "`awk '{print $1}' $FILE` : `awk '{print $3}' $FILE`"
		echo >>${EEP_CACHE} "`awk '{print $4 " " $5}' $FILE` : `awk '{print $7 " " $8}' $FILE`"
		echo >>${EEP_CACHE} "`awk '{print $9 " " $10}' $FILE` : `awk '{print $12}' $FILE`"
		echo >>${EEP_CACHE} "`awk '{print $14 " " $15}' $FILE` : `awk '{print $17 " " $18 " " $19}' $FILE`"
	else
		echo "Minnow eeprom file not found!"
		exit 1
	fi
}

# Function to parse the barramundi & sturgeon eeprom
parse_1u3u_eeprom() {
	local FILE=$1
	if [ -e $FILE ]; then
		echo >>${EEP_CACHE} "`awk '{print $1}' $FILE` : `awk '{print $3}' $FILE`"
		echo >>${EEP_CACHE} "`awk '{print $4 " " $5}' $FILE` : `awk '{print $7}' $FILE`"
		echo >>${EEP_CACHE} "`awk '{print $8 " " $9}' $FILE` : `awk '{print $11}' $FILE`"
		echo >>${EEP_CACHE} "`awk '{print $12 " " $13 " " $14}' $FILE` : `awk '{print $16 " " $17}' $FILE`"
		local RVBD_SERIAL=`/sbin/read_eeprom_serial.py`
		echo >>${EEP_CACHE} "Riverbed Serial : $RVBD_SERIAL"
	else
		echo "1U / 3U eeprom file not found!"
		exit 1
	fi
}

# Check board type and invoke the function to 
check_board_parse_eeprom() {
    local MOBO=`/opt/tms/bin/hwtool -q motherboard | awk -F- '{ print $1"-"$2}'`
    case ${MOBO} in
        "400-00100"|"400-00300")
		# =============== BARRAMUNDI & STURGEON===============
		local EEPROM_FILE="/var/tmp/5.bin"
		rm -f $EEPROM_FILE > /dev/null 2>&1
		ipmitool fru read 5 $EEPROM_FILE > /dev/null
		if [ $? -eq 0 ]; then
			parse_1u3u_eeprom $EEPROM_FILE
		else
			echo "Cannot read eeprom file"
			exit 1
		fi
        ;;
        "400-00099"|"400-00098")
		# ============== MINNOW ===============================
		parse_minnow_eeprom /sys/bus/i2c/devices/0-0051/eeprom
        ;;
	*)
		# =========== Other MOBO ===============================
		rm -f ${EEP_CACHE}
		echo "Unsupported Motherboard"
		exit 0
        ;;
    esac
}

main_function() {
	if [ ! -f ${EEP_CACHE} ]; then
		check_board_parse_eeprom
	fi
	if [ ! -f ${EEP_CACHE} ]; then
		echo "Could not create eeprom cache file"
		exit 1
	else
		cat ${EEP_CACHE}
	fi
}

main_function
