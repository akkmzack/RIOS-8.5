#!/usr/bin/env python
#
# Copyright (C) 2007 Riverbed Technology, Inc.
# All rights reserved world wide.
#

import getopt
import re
import sys
import socket
import time
import commands
import Mgmt
import MgmtDB

from sys import exit

TW_CLI_BIN = '/usr/sbin/tw_cli'
MEGARC_BIN = '/usr/sbin/megarc'

class raidConf:

    firmware  = ''
    bios      = ''
    memory    = ''
    numdrives = ''
    raidtype  = ''
    rebuild   = ''
    disktype  = ''
    serial    = ''
    stripesize  = ''
    stripes     = ''
    autorebuild = ''
    raidstatus = ''

    def __init__(self):
        return


class raid_3ware(raidConf):
    "Control info for 3ware raid card"

    value = { 'bios'          : ['bios',     ''],
              'driver'        : ['driver',   ''],
              'firmware'      : ['firmware', ''],
              'achip'         : ['achip',    ''],
              'memory'        : ['memory',   ''],
              'model'         : ['model',    ''],
              'monitor'       : ['monitor',  ''],
              'numdrives'     : ['numdrives',''],
              'numports'      : ['numports', ''],
              'numunits'      : ['numunits', ''],
              'serial_num'    : ['serial',   ''],
              'autorebuild'   : ['autorebuild', ''],
              }

    def __init__(self):
        for item, val in self.value.items():
            value = self.tw_cli_ctrl_show(val[0])
            if value and value[-1] == '\n':
                val[1] = value[:-1]

        self.raidtype  = 'Raid 10'
        self.stripesize = '64k'

        self.firmware  = self.value['firmware'][1]
        self.bios      = self.value['bios'][1]
        self.memory    = self.value['memory'][1]
        self.model     = self.value['model'][1]
        self.serial    = self.value['serial_num'][1]
        self.numdrives = self.value['numdrives'][1]
        self.disktype  = self.get_disk_type() 

        self.autorebuild = self.auto_rebuild()
        self.raidstatus = self.raid_status()
        
        return

    def get_disk_type(self):

        numofdrivers = self.numdrives

        vendors = {};
        for index in range(int(numofdrivers)):
            val = self.tw_cli_port_show('Model', 0, index)

            if (not val.has_key('Model')):
                continue

            disk_model = val['Model']

            if (disk_model[:2] == 'ST'):
                vendors['Seagate'] = 1
            elif (disk_model[:2] == 'WD'):
                vendors['WDC'] = 1
            else:
                vendors['Other'] = 1

        vendor_list = ''
        num_of_keys = 0
        for vendor in vendors.iterkeys():
            num_of_keys = num_of_keys + 1
            if (num_of_keys ==1):
                vendor_list = vendor_list + vendor
            else:
                vendor_list = vendor_list + '/' + vendor

        return vendor_list

    def auto_rebuild(self):
        val = self.value['autorebuild'][1]

        prog     = re.compile('on')
        matching = prog.match(val)

        if (matching):
            ret = 'Enabled'
        else:
            ret = 'Disabled'

        return ret

    def raid_status(self):
        val = self.tw_cli_unit_show('status')

        prog     = re.compile('DEGRADED|REBUILDING')
        matching = prog.match(val)

        ret = 'OK'

        if (matching):
            ret = 'DEGRADED'
        else:
            ret = 'OK'

        return ret

    def get_conf(self, key):
        print self.value[key][1]
        return

    def show(self):
        for key in self.value.keys():
            print '%-12s ==> %-12s' % (key, self.value[key][1])
        return

    def tw_cli_show(self, query_key):
        cmd = TW_CLI_BIN + ' show ' + query_key
        output = commands.getoutput(cmd)
        lines = output.splitlines()

        return output

    def tw_cli_ctrl_show(self, query_key, ctrl = 0):
        cmd = TW_CLI_BIN + ' /c' + str(ctrl) + ' show ' 
        output = commands.getoutput(cmd + query_key)

        prog     = re.compile('/c\d\s([\w+|\s*|-]+) = ([\S+\s*]+)')
        matching = prog.match(output)

        if (matching):
            ret = matching.group(2)
        else:
            ret = ''

        return ret

    def tw_cli_unit_show(self, query_key, ctrl = 0, unit = 0):
        cmd = TW_CLI_BIN + ' /c' + str(ctrl) +'/u' + str(unit) +  ' show '  
        output = commands.getoutput(cmd + query_key)
        prog     = re.compile('/c\d/u\d+\s([\w+\s*]+) = ([\S+\s*]+)')
        matching = prog.match(output)

        if (matching):
            ret = matching.group(2)
        else:
            ret = output

        return ret

    def tw_cli_port_show(self, query_key, ctrl = 0, port = 0):
        cmd = TW_CLI_BIN + ' /c' + str(ctrl) + '/p' + str(port) + ' show ' 
        output = commands.getoutput(cmd + query_key)
        lines = output.splitlines()

        prog     = re.compile('/c\d/p\d+\s([\w+\s*]+) = ([\S+\s*]+)')

        ret = {}

        for line in lines:

            matching = prog.match(line)

            if (matching):
                ret[matching.group(1)] = matching.group(2)

        return ret

    def show_raid_config(self):
        output = commands.getoutput(TW_CLI_BIN + ' /c0/u0 show')
        lines = output.splitlines()

        prog1     = re.compile('--------------------------')
        prog2     = re.compile('^Unit')
        prog3     = re.compile('^u\d+/v\d+\s+Volume')

        prog4     = re.compile('p(\d+)')

        for line in lines:

            matching1 = prog1.match(line)
            matching2 = prog2.match(line)
            matching3 = prog3.match(line)
            if (matching1):
                print '-------------------------------------------'
            elif (matching2):
                print 'UnitType     Status      Stripe       Size(GB)'
            elif (matching3):
                continue
            else:
                etry    = line.split()
                if (etry):
                    unittype   = etry[1]
                    status     = etry[2]
                    stripesize = etry[6]
                    disksize   = etry[7]
                    disknum    = -1

                    matching4 = prog4.match(etry[5])
                    if (matching4):
                        disknum    = int(matching4.group(1))

                    if (status == 'OK'):
                        status = 'ONLINE'

                    if (disknum == -1):
                        print '%-12s%-15s%-12s%-12s' % (etry[1], status, etry[6], etry[7])
                    else :
                        disknum = disknum + 1
                        print '%-4s %02d     %-15s%-12s%-12s' % (etry[1], int(disknum), status, etry[6], etry[7])

        return


    def show_raid_config_detail(self):
        output = commands.getoutput(TW_CLI_BIN + ' /c0 show | head -n4')
        print output

        output = commands.getoutput(TW_CLI_BIN + ' /c0/u0 show')
        print output

        return

    def show_raid_physical(self):
        numofdrivers = self.numdrives
        print

        for index in range(int(numofdrivers)):
            print "\t ------------------------------";
            print "\t Controller 0, Unit 0, Port " + str(index);
            print "\t ------------------------------";
            val = self.tw_cli_port_show('capacity', 0, index);
            if (val.has_key('Capacity')):
                capacity = val['Capacity']
            val = self.tw_cli_port_show('firmware', 0, index);
            if (val.has_key('Firmware Version')):
                firmware = val['Firmware Version']
            val = self.tw_cli_port_show('identify', 0, index);
            if (val.has_key('Identify Status')):
                identify = val['Identify Status']
            val = self.tw_cli_port_show('serial', 0, index);
            if (val.has_key('Serial')):
                serial = val['Serial']
            val = self.tw_cli_port_show('Status', 0, index);
            if (val.has_key('Status')):
                status = val['Status']
            val = self.tw_cli_port_show('lspeed', 0, index);
            if (val.has_key('SATA Link Speed Supported')):
                link_speed_supported = val['SATA Link Speed Supported']
            if (val.has_key('SATA Link Speed')):
                link_speed = val['SATA Link Speed']

            print "\t %-26s %-12s %-14s" % ('Type: Disk', 'Vendor: ', self.disktype)
            print "\t %-26s %-12s %-14s" % ('Firmware Version: ' + firmware, 'Serial: ', serial)
            print "\t %-26s %-26s" % ('Status: ' + status, 'Identify Status: ' + identify)
            print "\t %-26s " % ('Capacity: ' + capacity)
            print "\t %-26s " % ('SATA Link Speed Supported: '+ link_speed_supported )
            print "\t %-26s " % ('SATA Link Speed:           '+ link_speed )
            print
            print

        return

    def show_raid_info_detail(self):
        output = commands.getoutput(TW_CLI_BIN + ' /c0 show all')
        lines = output.splitlines()

        print
        for line in lines:
            if (line and line[0] == '/'):
                print line[1:]
            else:
                print line
        print

        return

    def show_raid_info(self):

        print 'Firmware           => ', self.firmware
        print 'Bios               => ', self.bios
        print 'Memory             => ', self.memory
        print 'Raid type          => ', self.raidtype
        print 'Auto rebuild       => ', self.autorebuild
        print 'Raid status        => ', self.raidstatus
        print 'Stripe size        => ', self.stripesize
        print 'Num of drives      => ', self.numdrives
        print 'Disk Vendor        => ', self.disktype
        print 'Serial Number      => ', self.serial

    def get_disk_status(self):

        numofdrivers = self.numdrives
        status = {}
 
        for index in range(int(numofdrivers)):
            val = self.tw_cli_port_show('status', 0, index)
            if (val.has_key('Status')):
                status[index] = val['Status']
            else:
                status[index] = 'Unknown';

        return status

    def show_raid_status(self):

        val = self.get_disk_status()

        for v, k in val.iteritems():
            print v, k

    def show_card_type(self):

        print "3ware"


class raid_lsi(raidConf):
    "Control info for lsi raid card"

    rebuild_rate = ''

    value = { 'bios'          : ['BIOS Version',     ''],
              'firmware'      : ['Firmware Version', ''],
              'rebuild_rate'  : ['Rebuild Rate', ''],
              'memory'        : ['DRAM',   ''],
              'rebuild'       : ['Auto Rebuild',''],
              'serial_num'    : ['Board SN',''],
              }

    def __init__(self):

        self.megarc_ctrl_show()

        self.raidtype  = 'Raid 10'
        self.stripesize = '64K'

        self.rbld_rate = self.value['rebuild_rate'][1]
        self.firmware  = self.value['firmware'][1]
        self.bios      = self.value['bios'][1]
        self.memory    = self.value['memory'][1]
        self.serial    = self.value['serial_num'][1]
        self.numdrives = self.get_num_drives()
        self.disktype  = self.get_disk_type()
        
        self.autorebuild = self.auto_rebuild()

        return

    def megarc_ctrl_show(self):
        cmd = MEGARC_BIN + ' -ctlrInfo  -nolog -a0 | tail -n 12'
        output = commands.getoutput(cmd)

        tokens = {};
        lines = output.splitlines()

        pat1 = re.compile('([\w+\s*]+) : (.+)')
        pat2 = re.compile('([\w+\s*]+): (.+)')

        for line in lines:
            t = line.split('\t')

            for ele in t:
                m1 = pat1.match(ele)
                m2 = pat2.match(ele)
                if (m1):
                    tokens[m1.group(1)] = m1.group(2)
                elif (m2):
                    tokens[m2.group(1)] = m2.group(2)

        for item, val in self.value.items():
            val[1] = tokens[val[0]]

        return

    def get_num_drives(self):
        cmd = MEGARC_BIN + ' -phys -nolog -a0 -ch0 -idAll | grep \'Target ID\''
        output = commands.getoutput(cmd)

        lines = output.splitlines()

        return len(lines)

    def get_disk_type(self):
        cmd = MEGARC_BIN + ' -phys -nolog -a0 -ch0 -idAll | grep Vendor'
        output = commands.getoutput(cmd)

        lines = output.splitlines()

        pat1 = re.compile('.*(Vendor)\s+ : (.+)')

        vendors = {};
        for line in lines:
            m = pat1.match(line)
            if (m):
                 vendor = m.group(2)
                 vendors[vendor] = 1

        vendor_list = ''
        num_of_keys = 0
        for vendor in vendors.iterkeys():
            num_of_keys = num_of_keys + 1
            if (num_of_keys ==1):
                vendor_list = vendor_list + vendor
            else:
                vendor_list = vendor_list + '/' + vendor

        return vendor_list

    def auto_rebuild(self):
        val = self.value['rebuild'][1]

        prog     = re.compile('Enabled')
        matching = prog.match(val)

        if (matching):
            ret = 'Enabled'
        else:
            ret = 'Disabled'

        return ret

    def show(self):
        for key in self.value.keys():
            print '%-12s ==> %-12s' % (key, self.value[key][1])
        return

    def show_raid_info(self):

        print 'Firmware           => ', self.firmware
        print 'Bios               => ', self.bios
        print 'Memory             => ', self.memory
        print 'Raid type          => ', self.raidtype
        print 'Auto rebuild       => ', self.autorebuild
        print 'Raid status        => ', self.raid_status()
        print 'Stripe size        => ', self.stripesize
        print 'Num of drives      => ', self.numdrives
        print 'Disk Vendor        => ', self.disktype
        print 'Serial Number      => ', self.serial


    def show_raid_config(self):
        output = commands.getoutput(MEGARC_BIN + ' -dispCfg -nolog -a0')
        lines = output.splitlines()

        prog = re.compile('\tLogical Drive (\d+) : SpanLevel_(\d+) Disks')

        prog1 = re.compile('\tSpanDepth :(\d+)\s+RaidLevel:\s(\d+)')
        prog2 = re.compile('\s+StripSz\s+:(\d+\w+)\s+Stripes.+')
        prog3 = re.compile('\s+\d+\s+(\d+)\s+(0x\d+)\s+(0x\w+)\s+(\w+)')

        disksize   = {}
        diskstatus = {}
        raidtype   = 'RAID-10'
        raidstatus = ''
        stripesize = ''
        totalsize  = 0.0

        groups = []
        array  = []
        group_start = 0

        for line in lines:
            matching  = prog.match(line)
            matching1 = prog1.match(line)
            matching2 = prog2.match(line)
            matching3 = prog3.match(line)
            if (matching):
                if (group_start):
                    groups.append(array)
                    array = []
                    group_start = 0
            elif (matching1):
                continue
            elif (matching2):
                stripesize = matching2.group(1)
            elif (matching3):
                group_start = 1
                array.append(matching3.group(1))
                size = int(matching3.group(3), 16)/2.0/1024/1024
                totalsize += size
                disksize[matching3.group(1)] = size
                if (matching3.group(4) == 'ONLINE'):
                    status = 'ONLINE'
                elif (matching3.group(4) == 'RBLD'):
                    status     = 'FAILED'
                else:
                    status = 'FAILED'

                diskstatus[matching3.group(1)]   = status
            else:
                continue

        groups.append(array)

        raidstatus = 'ONLINE'

        for gp in groups:
            groupstatus = 'ONLINE'
            num_failures = 0
            for port in gp:
                if (diskstatus[port] != 'ONLINE'):
                    num_failures += 1

            if (num_failures >1):
                groupstatus = 'FAILED'

            if (groupstatus == 'FAILED'):
                raidstatus = FAILED
                break

        print 'UnitType  Status      Stripe       Size(GB)'
        print '-------------------------------------------'
        print '%-12s%-12s%-12s%-10.2f' % (raidtype, raidstatus, stripesize, totalsize) 

        for gp in groups:
            groupstatus = 'ONLINE'
            num_failures = 0
            for port in gp:
                if (diskstatus[port] != 'ONLINE'):
                    num_failures += 1

            if (num_failures >1):
                groupstatus = 'FAILED'

            print '%-12s%-15s%-12s%-12s' % ('RAID-1', groupstatus, '-', '-')

            for port in gp:
                disknum = int(port) + 1
                print '%-4s %02d     %-15s%-10s%-10.2f' % ('DISK', disknum, diskstatus[port], '-', int(disksize[port]))


        return 


    def show_raid_config_detail(self):
        output = commands.getoutput(MEGARC_BIN + ' -dispCfg -nolog -a0')
        lines = output.splitlines()

        prog     = re.compile('\t\s*Logical Drive : \d.*')

        start = 0
        for line in lines:
            matching = prog.match(line)
            if (matching):
                start = 1
            if (start > 0):
                print line

        return

    def show_raid_info_detail(self):
        output = commands.getoutput(MEGARC_BIN + ' -ctlrInfo -nolog -a0 | tail -n12')
        print output

        return

    def show_raid_physical(self):

        numofdrivers = self.numdrives
        print

        for index in range(int(numofdrivers)):
            print "\t----------------------------------";
            print "\tAdapter 0, Channel 0, Target ID " + str(index);
            print "\t----------------------------------";
            cmd = ' -phys -nolog -a0 -chAll -id%d | tail -n6' % index
            output = commands.getoutput(MEGARC_BIN + cmd)
            print output
            print

        return


    def get_disk_status(self):
        output = commands.getoutput(MEGARC_BIN + ' -dispCfg -nolog -a0')
        lines = output.splitlines()

        status = { }

        prog = re.compile('\s+\d+\s+(\d+)\s+(0x\d+)\s+(0x\w+)\s+(\w+)')

        for line in lines:
            matching = prog.match(line)
            if (matching):
                status[int(matching.group(1))] = matching.group(4)

        return status

    def raid_status(self):

        val = self.get_disk_status()

        online  = re.compile('ONLINE')
        failed  = re.compile('FAILED')
        rebuild = re.compile('RBLD')

        for v, k in val.iteritems():

            matching = failed.match(k)
            if (matching):
                return "Degraded"

            matching = rebuild.match(k)
            if (matching):
                return "Degraded"

        return "OK"

    def show_raid_status(self):

        val = self.get_disk_status()

        for v, k in val.iteritems():
            print v, k

    def show_card_type(self):

        print "lsi"

from rrdm_util import run_shell_cmd
rrdm_tool_py = '/opt/hal/bin/raid/rrdm_tool.py'

def exec_rrdm_tool(command):
    global rrdm_tool_py
    try:
	output = run_shell_cmd ('%s %s' % (rrdm_tool_py, command), True)
    except rrdm_error, what:
	print 'Failed to execute command %s' % command
	exit(1)

    return output
    

class raid_sw(raidConf):
    "Control info for sw raid "
        
    rebuild_rate = ''
            
    def __init__(self):
    
        return

    def show_raid_config(self):
	output = exec_rrdm_tool('--get-raid-configuration')
	print output
    
    def show_raid_config_detail(self):
	print 'Detailed info is not available for appliances that use software RAID.'

    def show_raid_info_detail(self):
	print 'Detailed info is not available for appliances that use software RAID.'

    def show_raid_info(self):
	output = exec_rrdm_tool('--raid-info')
	print output
    
    def show_raid_physical(self):
	output = exec_rrdm_tool('--get-physical')
	print output
    

    def show_card_type(self):
	print 'swraid'
	

    def show_card_type(self):
	print 'swraid'
