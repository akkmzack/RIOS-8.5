#!/usr/bin/python
import os
import sys
import commands
from time import gmtime, strftime


# each platforms sensors information is an array of strings organized
# ListOfNames,ListOfSensorNodes,ListOfSensorParams,numberOfSensors

# Handy list indicies.
# NAME, index to list of sensor names to be used in header display
# NODES, index to list of sensor sysfs file names
# INV,  parameters used in process of computing temp
# COUNT, index to the number of sensors for a platform 
NAME=0
NODES=1
INV=2
COUNT=3


# defines for header spacing and, etc.
MAX_NAME_LEN = 12
MAX_DISPLAY_CHUNK = 13


# list of platform-specific sensors
# 

# Bluedell  425-0135
sens1name1="TCore0"
sens1name2="TCore1"
sens1names=sens1name1,sens1name2
sens1n1="/proc/core_temp/0", 0, 0
sens1n2="/proc/core_temp/1", 0, 0
sens1nodes=sens1n1,sens1n2
sens1inv=[0,0],[0,0]
sensor1count=2
BLUEDELL=sens1names,sens1nodes,sens1inv,sensor1count

# 1UABA 
# part_number="400-00100-01" Baramundi
sens2name1="TCPU0"
sens2name2="TCPU1"
sens2name3="TSB"
sens2name4="TMEM"
sens2name5="TLAN"
sens2name6="TMCH"
sens2name7="TBP1"
sens2name8="TBP2"
sens2name9="TPSU"
sens2name10="TSys"
sens2name11="TPS0"
sens2name12="TPS1"
sens2names=sens2name1,sens2name2,sens2name3,sens2name4,sens2name5, \
sens2name6,sens2name7,sens2name8,sens2name9,sens2name10,sens2name11,sens2name12
sens2n1="/sys/devices/platform/ipmi_si.0/bmc/temp12_input"
sens2n2="/sys/devices/platform/ipmi_si.0/bmc/temp11_input"
sens2n3="/sys/devices/platform/ipmi_si.0/bmc/temp10_input"
sens2n4="/sys/devices/platform/ipmi_si.0/bmc/temp9_input"
sens2n5="/sys/devices/platform/ipmi_si.0/bmc/temp8_input"
sens2n6="/sys/devices/platform/ipmi_si.0/bmc/temp7_input"
sens2n7="/sys/devices/platform/ipmi_si.0/bmc/temp6_input"
sens2n8="/sys/devices/platform/ipmi_si.0/bmc/temp5_input"
sens2n9="/sys/devices/platform/ipmi_si.0/bmc/temp4_input"
sens2n10="/sys/devices/platform/ipmi_si.0/bmc/temp3_input"
sens2n11="/sys/devices/platform/ipmi_si.0/bmc/temp2_input"
sens2n12="/sys/devices/platform/ipmi_si.0/bmc/temp1_input"
sens2nodes=sens2n1,sens2n2,sens2n3,sens2n4,sens2n5,sens2n6, \
sens2n7,sens2n8,sens2n9,sens2n10,sens2n11,sens2n12
sens2inv=[1,100],[1,100],[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],[0,0]
sensor2count=12
BARAMUNDI=sens2names,sens2nodes,sens2inv,sensor2count



# sturgeon 400-00300-01
sens3name1="TPS1"
sens3name2="TPS0"
sens3name3="TFP"
sens3name4="TPDB"
sens3name5="TBP4"
sens3name6="TBP3"
sens3name7="TBP2"
sens3name8="TBP1"
sens3name9="TLANPHY"
sens3name10="TCOMPORT"
sens3name11="TLSI"
sens3name12="TCENTER"
sens3name13="TIO55"
sens3name14="TMCP55"
sens3name15="TCPU1"
sens3name16="TCPU0"
sens3names=sens3name1,sens3name2,sens3name3,sens3name4, \
sens3name5,sens3name6,sens3name7,sens3name8,sens3name9, \
sens3name10,sens3name11,sens3name12,sens3name13, \
sens3name14,sens3name15,sens3name16
sens3n1="/sys/devices/platform/ipmi_bmc.1a11.32/temp1_input"
sens3n2="/sys/devices/platform/ipmi_bmc.1a11.32/temp2_input"
sens3n3="/sys/devices/platform/ipmi_bmc.1a11.32/temp3_input"
sens3n4="/sys/devices/platform/ipmi_bmc.1a11.32/temp4_input"
sens3n5="/sys/devices/platform/ipmi_bmc.1a11.32/temp5_input"
sens3n6="/sys/devices/platform/ipmi_bmc.1a11.32/temp6_input"
sens3n7="/sys/devices/platform/ipmi_bmc.1a11.32/temp7_input"
sens3n8="/sys/devices/platform/ipmi_bmc.1a11.32/temp8_input"
sens3n9="/sys/devices/platform/ipmi_bmc.1a11.32/temp9_input"
sens3n10="/sys/devices/platform/ipmi_bmc.1a11.32/temp10_input"
sens3n11="/sys/devices/platform/ipmi_bmc.1a11.32/temp11_input"
sens3n12="/sys/devices/platform/ipmi_bmc.1a11.32/temp12_input"
sens3n13="/sys/devices/platform/ipmi_bmc.1a11.32/temp13_input"
sens3n14="/sys/devices/platform/ipmi_bmc.1a11.32/temp14_input"
sens3n15="/sys/devices/platform/ipmi_bmc.1a11.32/temp15_input"
sens3n16="/sys/devices/platform/ipmi_bmc.1a11.32/temp16_input"
sens3nodes=sens3n1,sens3n2,sens3n3,sens3n4,sens3n5,sens3n6,sens3n7, \
sens3n8,sens3n9,sens3n10,sens3n11,sens3n12,sens3n13,sens3n14,sens3n15,sens3n16
sens3inv=[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],\
[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],[0,0],[0,0]
sensor3count=16
STURGEON=sens3names,sens3nodes,sens3inv,sensor3count

# HPBLADE AKA minnow 400-00099-01
sens4name1="TCore0"
sens4name2="TCore1"
sens4names=sens4name1,sens4name2
sens4n1="/sys/devices/platform/coretemp.0/temp1_input"
sens4n2="/sys/devices/platform/coretemp.1/temp1_input"
sens4nodes=sens4n1,sens4n2
sens4inv=[0,0],[0,0]
sensor4count=2
MINNOW=sens4names,sens4nodes,sens4inv,sensor4count

# Redfin sensors uses IPMI commands to read sensors
# short sensor names for header display
# 425-00140-01
sens5name1 = "TCPU0MOS"
sens5name2 = "TCPU1MOS"
sens5name3 = "TSR5690"
sens5name4 = "TAIRIN"
sens5name5 = "TCPU0"
sens5name6 = "TCPU1"
sens5name7 = "TCPU0DA0"
sens5name8 = "TCPU0DA1"
sens5name9 = "TCPU0DB0"
sens5name10 = "TCPU0DB1"
sens5name11 = "TCPU1DA0"
sens5name12 = "TCPU1DA1"
sens5name13 = "TCPU1DB0"
sens5name14 = "TCPU1DB1"
sens5name15 = "TAMBIENT"
sens5name16 = "THDD1"
sens5name17 = "THDD2"
sens5name18 = "THDD3"
sens5name19 = "THDD4"
sens5name20 = "TPSU0"
sens5name21 = "TPSU1"
sens5names=sens5name1,sens5name2,sens5name3,sens5name4,sens5name5,sens5name6,sens5name7,sens5name8, \
sens5name9,sens5name10,sens5name11,sens5name12,sens5name13,sens5name14,sens5name15,sens5name16,  \
sens5name17,sens5name18,sens5name19,sens5name20,sens5name21
sens5nodes=''
sens5inv=''
sensor5count=21
REDFIN=sens5names,sens5nodes,sens5inv,sensor5count


# IPMI commands to read sensors
sens5sdrcmd1 = '/usr/bin/ipmitool sensor reading "CPU0 MOS TEMP"'
sens5sdrcmd2 = '/usr/bin/ipmitool sensor reading "CPU1 MOS TEMP"'
sens5sdrcmd3 = '/usr/bin/ipmitool sensor reading "SR5690 TEMP"'
sens5sdrcmd4 = '/usr/bin/ipmitool sensor reading "MB Air Inlet"'
sens5sdrcmd5 = '/usr/bin/ipmitool sensor reading "CPU0_TEMP"'
sens5sdrcmd6 = '/usr/bin/ipmitool sensor reading "CPU1_TEMP"'
sens5sdrcmd7 = '/usr/bin/ipmitool sensor reading "CPU0 Dimm A0"'
sens5sdrcmd8 = '/usr/bin/ipmitool sensor reading "CPU0 Dimm A1"'
sens5sdrcmd9 = '/usr/bin/ipmitool sensor reading "CPU0 Dimm B0"'
sens5sdrcmd10 = '/usr/bin/ipmitool sensor reading "CPU0 Dimm B1"'
sens5sdrcmd11 = '/usr/bin/ipmitool sensor reading "CPU1 Dimm A0"'
sens5sdrcmd12 = '/usr/bin/ipmitool sensor reading "CPU1 Dimm A1"'
sens5sdrcmd13 = '/usr/bin/ipmitool sensor reading "CPU1 Dimm B0"'
sens5sdrcmd14 = '/usr/bin/ipmitool sensor reading "CPU1 Dimm B1"'
sens5sdrcmd15 = '/usr/bin/ipmitool sensor reading "Ambient"'
sens5sdrcmd16 = '/usr/bin/ipmitool sensor reading "Backplate HDD1"'
sens5sdrcmd17 = '/usr/bin/ipmitool sensor reading "Backplate HDD2"'
sens5sdrcmd18 = '/usr/bin/ipmitool sensor reading "Backplate HDD3"'
sens5sdrcmd19 = '/usr/bin/ipmitool sensor reading "Backplate HDD4"'
sens5sdrcmd20 = '/usr/bin/ipmitool sensor reading "PSU0 Temp"'
sens5sdrcmd21 = '/usr/bin/ipmitool sensor reading "PSU1 Temp"'
REDFIN_SDRCMDS = sens5sdrcmd1,sens5sdrcmd2,sens5sdrcmd3,sens5sdrcmd4,sens5sdrcmd5,sens5sdrcmd6,sens5sdrcmd7, \
sens5sdrcmd8,sens5sdrcmd9,sens5sdrcmd10,sens5sdrcmd11,sens5sdrcmd12,sens5sdrcmd13,sens5sdrcmd14,sens5sdrcmd15,  \
sens5sdrcmd16,sens5sdrcmd17,sens5sdrcmd18,sens5sdrcmd19,sens5sdrcmd20,sens5sdrcmd21
 

# YT 400-00400-01
sens6name1 = "TCPU0DTS"
sens6name2 = "TCPU1DTS"
sens6name3 = "TCPU2DTS"
sens6name4 = "TCPU3DTS"
sens6name5 = "TPCH"
sens6name6 = "TLANX540"
sens6name7 = "TSYSFAN1"
sens6name8 = "TSYSFAN2"
sens6name9 = "TSAS2X20_0"
sens6name10 = "TSAS2X20_1"
sens6name11 = "TSAS2X20_2"
sens6name12 = "TSAS2X20_3"
sens6name13 = "TCPU0DIMMA0"
sens6name14 = "TCPU0DIMMA1"
sens6name15 = "TCPU0DIMMB0"
sens6name16 = "TCPU0DIMMB1"
sens6name17 = "TCPU0DIMMC0"
sens6name18 = "TCPU0DIMMC1"
sens6name19 = "TCPU0DIMMD0"
sens6name20 = "TCPU0DIMMD1"
sens6name21 = "TCPU1DIMMA0"
sens6name22 = "TCPU1DIMMA1"
sens6name23 = "TCPU1DIMMB0"
sens6name24 = "TCPU1DIMMB1"
sens6name25 = "TCPU1DIMMC0"
sens6name26 = "TCPU1DIMMC1"
sens6name27 = "TCPU1DIMMD0"
sens6name28 = "TCPU1DIMMD1"
sens6name29 = "TCPU2DIMMA0"
sens6name30 = "TCPU2DIMMA1"
sens6name31 = "TCPU2DIMMB0"
sens6name32 = "TCPU2DIMMB1"
sens6name33 = "TCPU2DIMMC0"
sens6name34 = "TCPU2DIMMC1"
sens6name35 = "TCPU2DIMMD0"
sens6name36 = "TCPU2DIMMD1"
sens6name37 = "TCPU3DIMMA0"
sens6name38 = "TCPU3DIMMA1"
sens6name39 = "TCPU3DIMMB0"
sens6name40 = "TCPU3DIMMB1"
sens6name41 = "TCPU3DIMMC0"
sens6name42 = "TCPU3DIMMC1"
sens6name43 = "TCPU3DIMMD0"
sens6name44 = "TCPU3DIMMD1"
sens6names=sens6name1,sens6name2,sens6name3,sens6name4,sens6name5,sens6name6,sens6name7,sens6name8,sens6name9,sens6name10,  \
sens6name11,sens6name12,sens6name13,sens6name14,sens6name15,sens6name16,sens6name17,sens6name18,sens6name19,sens6name20, \
sens6name21,sens6name22,sens6name23,sens6name24,sens6name25,sens6name26,sens6name27,sens6name28,sens6name29,sens6name30, \
sens6name31,sens6name32,sens6name33,sens6name34,sens6name35,sens6name36,sens6name37,sens6name38,sens6name39,sens6name40, \
sens6name41,sens6name42,sens6name43,sens6name44
sens6nodes=''
sens6inv=''
sensor6count=44
YELLOWTAIL=sens6names,sens6nodes,sens6inv,sensor6count

sens6cmd1 = '/usr/bin/ipmitool sensor reading "CPU0_DTS_Temp"'
sens6cmd2 = '/usr/bin/ipmitool sensor reading "CPU1_DTS_Temp"'
sens6cmd3 = '/usr/bin/ipmitool sensor reading "CPU2_DTS_Temp"'
sens6cmd4 = '/usr/bin/ipmitool sensor reading "CPU3_DTS_Temp"'
sens6cmd5 = '/usr/bin/ipmitool sensor reading "PCH_Area_Temp"'
sens6cmd6 = '/usr/bin/ipmitool sensor reading "LAN_X540_Temp"'
sens6cmd7 = '/usr/bin/ipmitool sensor reading "SYS_Fan_Inlet_1"'
sens6cmd8 = '/usr/bin/ipmitool sensor reading "SYS_Fan_Inlet_2"'
sens6cmd9 = '/usr/bin/ipmitool sensor reading "SAS2X20_area_0"'
sens6cmd10 = '/usr/bin/ipmitool sensor reading "SAS2X20_area_1"'
sens6cmd11 = '/usr/bin/ipmitool sensor reading "SAS2X20_area_2"'
sens6cmd12 = '/usr/bin/ipmitool sensor reading "SAS2X20_area_3"'
sens6cmd13 = '/usr/bin/ipmitool sensor reading "CPU0_DIMM_A0"'
sens6cmd14 = '/usr/bin/ipmitool sensor reading "CPU0_DIMM_A1"'
sens6cmd15 = '/usr/bin/ipmitool sensor reading "CPU0_DIMM_B0"'
sens6cmd16 = '/usr/bin/ipmitool sensor reading "CPU0_DIMM_B1"'
sens6cmd17 = '/usr/bin/ipmitool sensor reading "CPU0_DIMM_C0"'
sens6cmd18 = '/usr/bin/ipmitool sensor reading "CPU0_DIMM_C1"'
sens6cmd19 = '/usr/bin/ipmitool sensor reading "CPU0_DIMM_D0"'
sens6cmd20 = '/usr/bin/ipmitool sensor reading "CPU0_DIMM_D1"'
sens6cmd21 = '/usr/bin/ipmitool sensor reading "CPU1_DIMM_A0"'
sens6cmd22 = '/usr/bin/ipmitool sensor reading "CPU1_DIMM_A1"'
sens6cmd23 = '/usr/bin/ipmitool sensor reading "CPU1_DIMM_B0"'
sens6cmd24 = '/usr/bin/ipmitool sensor reading "CPU1_DIMM_B1"'
sens6cmd25 = '/usr/bin/ipmitool sensor reading "CPU1_DIMM_C0"'
sens6cmd26 = '/usr/bin/ipmitool sensor reading "CPU1_DIMM_C1"'
sens6cmd27 = '/usr/bin/ipmitool sensor reading "CPU1_DIMM_D0"'
sens6cmd28 = '/usr/bin/ipmitool sensor reading "CPU1_DIMM_D1"'
sens6cmd29 = '/usr/bin/ipmitool sensor reading "CPU2_DIMM_A0"'
sens6cmd30 = '/usr/bin/ipmitool sensor reading "CPU2_DIMM_A1"'
sens6cmd31 = '/usr/bin/ipmitool sensor reading "CPU2_DIMM_B0"'
sens6cmd32 = '/usr/bin/ipmitool sensor reading "CPU2_DIMM_B1"'
sens6cmd33 = '/usr/bin/ipmitool sensor reading "CPU2_DIMM_C0"'
sens6cmd34 = '/usr/bin/ipmitool sensor reading "CPU2_DIMM_C1"'
sens6cmd35 = '/usr/bin/ipmitool sensor reading "CPU2_DIMM_D0"'
sens6cmd36 = '/usr/bin/ipmitool sensor reading "CPU2_DIMM_D1"'
sens6cmd37 = '/usr/bin/ipmitool sensor reading "CPU3_DIMM_A0"'
sens6cmd38 = '/usr/bin/ipmitool sensor reading "CPU3_DIMM_A1"'
sens6cmd39 = '/usr/bin/ipmitool sensor reading "CPU3_DIMM_B0"'
sens6cmd40 = '/usr/bin/ipmitool sensor reading "CPU3_DIMM_B1"'
sens6cmd41 = '/usr/bin/ipmitool sensor reading "CPU3_DIMM_C0"'
sens6cmd42 = '/usr/bin/ipmitool sensor reading "CPU3_DIMM_C1"'
sens6cmd43 = '/usr/bin/ipmitool sensor reading "CPU3_DIMM_D0"'
sens6cmd44 = '/usr/bin/ipmitool sensor reading "CPU3_DIMM_D1"'
YELLOWTAIL_SDRCMDS=sens6cmd1,sens6cmd2,sens6cmd3,sens6cmd4,sens6cmd5,sens6cmd6,sens6cmd7,sens6cmd8,sens6cmd9,sens6cmd10, \
sens6cmd11,sens6cmd12,sens6cmd13,sens6cmd14,sens6cmd15,sens6cmd16,sens6cmd17,sens6cmd18,sens6cmd19,sens6cmd20, \
sens6cmd21,sens6cmd22,sens6cmd23,sens6cmd24,sens6cmd25,sens6cmd26,sens6cmd27,sens6cmd28,sens6cmd29,sens6cmd30, \
sens6cmd31,sens6cmd32,sens6cmd33,sens6cmd34,sens6cmd35,sens6cmd36,sens6cmd37,sens6cmd38,sens6cmd39, \
sens6cmd40,sens6cmd41,sens6cmd42,sens6cmd43,sens6cmd44

# Guppy - 425-00120-01
sens7name1 = "TCore0"
sens7names=sens7name1
sens7n1="/sys/devices/platform/coretemp.0/temp1_input"
sens7nodes=sens7n1
sens7inv=[0,0]
sensor7count=1
GUPPY=sens7names,sens7nodes,sens7inv,sensor7count

PLATFORMS=BLUEDELL,BARAMUNDI,STURGEON,MINNOW,REDFIN,YELLOWTAIL,GUPPY
OUR_PLATFORM=[]
OUR_PLATFORM_SDRCMDS=[]
print_header=0


def do_minnow():
    global OUR_PLATFORM

    OUR_PLATFORM=MINNOW
    if print_header > 0:
        HEADER=''
        build_header(HEADER)
    show_temps()

def do_sturgeon():
    global OUR_PLATFORM

    OUR_PLATFORM=STURGEON
    if print_header > 0:
        HEADER=''
        build_header(HEADER)
    show_temps()

def do_barramundi():
    global OUR_PLATFORM

    OUR_PLATFORM=BARAMUNDI
    if print_header > 0:
        HEADER=''
        build_header(HEADER)
    show_temps()

def do_bluedell():
    global OUR_PLATFORM

    OUR_PLATFORM=BLUEDELL
    if print_header > 0:
        HEADER=''
        build_header(HEADER)
    show_temps()

def do_guppy():
    global OUR_PLATFORM

    OUR_PLATFORM=GUPPY
    if print_header > 0:
        HEADER=''
        build_header(HEADER)
    show_temps()

# Redfin and Yellowtail use use of ipmitool
def do_redfin():
    global OUR_PLATFORM
    global OUR_PLATFORM_SDRCMDS

    OUR_PLATFORM = REDFIN
    OUR_PLATFORM_SDRCMDS = REDFIN_SDRCMDS

    if print_header > 0:
        HEADER=''
        build_header(HEADER)
    show_sdrs()

def do_yellowtail():
    global OUR_PLATFORM
    global OUR_PLATFORM_SDRCMDS

    OUR_PLATFORM = YELLOWTAIL
    OUR_PLATFORM_SDRCMDS = YELLOWTAIL_SDRCMDS

    if print_header > 0:
        HEADER=''
        build_header(HEADER)
    show_sdrs()



do_map = {
'400-00099-01' : do_minnow,
'400-00300-01' : do_sturgeon,
'400-00100-01' : do_barramundi,
'425-00120-01' : do_guppy,
'425-00140-01' : do_redfin,
'425-00135-01' : do_bluedell,
'400-00400-01' : do_yellowtail}


def do_mobo():
    sts, val = commands.getstatusoutput('hwtool -q motherboard')
    if sts != 0:
        print "mobo query failed: %d" % sts
        return -1

    do_map[val]()
    return 0


# build and display header
def build_header(hdr):
    global OUR_PLATFORM

    hdr += 'Time                   '
    for n in range(0, OUR_PLATFORM[COUNT]):
        if OUR_PLATFORM[COUNT] > 1:
            l = len(OUR_PLATFORM[NAME][n])
            hdr += str(OUR_PLATFORM[NAME][n])
        else:
            l = len(OUR_PLATFORM[NAME])
            hdr += str(OUR_PLATFORM[NAME])
        while (l < MAX_NAME_LEN):
            hdr += ' '
            l += 1
        while (l < MAX_DISPLAY_CHUNK):
            hdr += ' '
            l += 1
    print hdr



# read and print temp sensors
def show_temps():
    global OUR_PLATFORM

    output = strftime("%Y-%m-%d %H:%M:%S", gmtime())
    l = len(output)

    while (l < 23):
        output += ' '
        l += 1

    num_nodes = OUR_PLATFORM[COUNT]
    node = 0
    for n in range(0, num_nodes):
        if OUR_PLATFORM[COUNT] > 1:
            name = OUR_PLATFORM[NODES][n]
            inv = OUR_PLATFORM[INV][n]
            inv_reading = inv[0]
            inv_max = inv[1]
        else:
            name = OUR_PLATFORM[NODES]
            inv = OUR_PLATFORM[INV]
            inv_reading = inv[0]
            inv_max = inv[1]
        try:
            F = open(name, 'r')
        except IOError:
           continue
        temp = int(F.read(), 10)
        if inv_reading > 0:
            temp = inv_max - temp
        temp = temp / 1000
        output += str(temp)
        rem = MAX_DISPLAY_CHUNK - len(str(temp))
        while (rem > 0):
            output += ' '
            rem -= 1

    print output


# for platforms that use ipmitool
ipmi_cmd_sts = 0

def run_ipmi_cmd(cmd):
    ipmi_cmd_sts, val = commands.getstatusoutput(cmd)
    if val == '':
        return 'na'
    else:
        return val
 
def show_sdrs():
    output = strftime("%Y-%m-%d %H:%M:%S", gmtime())
    l = len(output)
    while (l < 23):
        output += ' '
        l += 1

    for n in range(0, len(OUR_PLATFORM_SDRCMDS)):
        namelen = len(OUR_PLATFORM[NAME][n])
        val = run_ipmi_cmd(OUR_PLATFORM_SDRCMDS[n])
        if ipmi_cmd_sts != 0:
            continue
        else:
            ss = val[-2:]
            output += ss
            rem = MAX_DISPLAY_CHUNK - len(ss)
            while (rem > 0):
                output += ' '
                rem -= 1

    print output


if __name__ == "__main__":
    if sys.argv[1:]:
        if sys.argv[1] == "--header":
		print_header=1

    HEADER=''

    res = do_mobo()
    if res != 0:
        print "unable to determine mobo"

