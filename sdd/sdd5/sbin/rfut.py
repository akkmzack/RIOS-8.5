#!/usr/bin/env python
from lxml import etree
import os
from os.path import exists
import sys
import subprocess
from subprocess import Popen
from subprocess import PIPE
from optparse import OptionParser
import syslog
import time
import fileinput
import datetime


DBG_NONE = 0
DBG_ERR = 1
DBG_WAR = 2
DBG_INF = 3
DBG_VBS = 4

DEFAULT_DBG_LEVEL = 1
CURRENT_DBG_LEVEL = DEFAULT_DBG_LEVEL
SAVED_PATH = None
SYSLOG_ENABLE = False

class Upgrade_result:
    Failed_no_file, Fail_cmds, Succeed_no_need_upgrade, Succeed_upgrade = range(4)
    
###############################################################################
#
# printd
#
# print out the messages if the debug level is high enough
#
###############################################################################

def printd(dbg_level, msg):
    global CURRENT_DBG_LEVEL
    if (dbg_level <= CURRENT_DBG_LEVEL):
        now = datetime.datetime.now()
        print "rfut: " + str(now) + " " + msg


###############################################################################
#
# run_cd_cmd
#
# execute a linux cd command. 
#
###############################################################################

def run_cd_cmd(cmdline):
    global SAVED_PATH
    
    if cmdline[3] == '-':
        if SAVED_PATH is not None: # switch back to previous path
            try:
                os.chdir(SAVED_PATH)
            except Exception, err:
                printd(DBG_WAR, "failed to switch to the old path. Error: %s" %str(err))
            return
        else: #no previous path. the cd command is cding to the working directory
            return
    
    try:        
        SAVED_PATH = os.getcwd()
        
        printd(DBG_VBS, " new dir is " + cmdline[3:])
        os.chdir(cmdline[3:])
    except Exception, err:
        printd(DBG_WAR, "failed to switch to another path. Error: %s" %str(err))


###############################################################################
#
# run_reboot_cmd
#
# handle reboot command
#
###############################################################################

def run_reboot_cmd():
    raise RebootException


###############################################################################
#
# run_shell_cmd
#
# execute a linux shell command. 
#
###############################################################################
    
def run_shell_cmd(cmdline):
    # special handling for "cd" command
    if (cmdline[0] == 'c' and cmdline[1] == 'd'
        and cmdline[2] == ' '):
        printd(DBG_VBS, " got a cd command")
        run_cd_cmd(cmdline)
        return

    if ( "reboot" in cmdline or "shutdown -r" in cmdline):
        run_reboot_cmd()
        
    pf = Popen(cmdline, shell=True, stdout=PIPE, stderr=PIPE)
    (output, errout) = pf.communicate()

    printd(DBG_VBS, "out is " + output)
    printd(DBG_VBS, "err is " + errout)

    if (pf.wait() == 0 and len(errout) == 0):
        return output
    else:
        raise Exception('Unable to run cmd %s, got following error %s %s' %
                           (cmdline, output, errout))


###############################################################################
#
# check_file
#
# check if a file exist and accessible. Return True if file exists.
#
###############################################################################

def check_file( path, report_warn=True ):
    if os.path.exists(path) and os.path.isfile(path) and os.access(path, os.R_OK):
        printd(DBG_VBS, path + " exists and is readable")
        return True
    elif ( report_warn ):
        printd(DBG_INF, "Either file is missing or is not readable, file: " + path )
        return False


###############################################################################
#
# compare_with_major_minor
#
# Split version strings to Major and minor number and compare them
#    the format of the version string should be like this "2.10" or "2.4"
# return false if the current version is >= the expected version
#    Otherwise, return true
#
###############################################################################

def compare_with_major_minor(expected_ver_str, cur_ver_str):
    [expected_major, expected_minor] = [int(x) for x in expected_ver_str.split('.')]
    [current_major, current_minor] = [int(x) for x in cur_ver_str.split('.')]
    
    if ( current_major > expected_major ):
        return False
    elif ( current_major == expected_major ):
        if ( current_minor >= expected_minor ):
            return False
    
    return True
    
###############################################################################
#
# RebootException
#
# Special reboot exception
#
###############################################################################

class RebootException(Exception):
    pass

###############################################################################
#
# TeeLog
#
# New class to overload "print" statements to go to screen and logfile
# When this class is used, either -l option or -s option must be specified
#
###############################################################################
    
class TeeLog:
    def __init__(self, stdout, filename):
        global SYSLOG_ENABLE
        
        if ( not SYSLOG_ENABLE ) :
            self.stdout = stdout
            self.logfile = open(filename, 'w')
    
    def write(self, text):
        global SYSLOG_ENABLE
        
        if ( SYSLOG_ENABLE ) :
            syslog.syslog(syslog.LOG_ERR, text)
        else:
            self.stdout.write(text)
            self.logfile.write(text)
            
    def close(self):
        global SYSLOG_ENABLE
        
        if ( SYSLOG_ENABLE ) :
            syslog.closelog()
        else:
            self.stdout.close()
            self.logfile.close()
            
    def flush(self):
        global SYSLOG_ENABLE
        
        if ( SYSLOG_ENABLE ) :
            self.logfile.flush()
        else:
            self.stdout.flush()
            
###############################################################################
#
# Binary
#
# Check if a binary exist in the PATH. Return the path or None.
#
###############################################################################

class Binary:
    def __init__(self, program):
        self.program = program

    def whereis(self):
        return run_shell_cmd("which " + self.program)

###############################################################################
#
# Action
#
# Base class for all real actions.
#
###############################################################################

class Action:
    def add_action_name(self, action_name):
        pass
        
    def add_action(self, real_action):
        pass
        
    def do_it(self):
        pass

    def get_cur_fw_ver(self):
        pass

###############################################################################
#
# FWItem
#
# Class for each individual firmware upgrade item, such as BIOS, or BMC
#
###############################################################################
        
class FWItem:
    def __init__(self, name):
        self.name = name
        self.cur_ver_nr = 0
        self.cur_ver_str = ""
        self.cur_ver_cmd_list = []

    def get_cur_ver(self):
        for cmd in self.cur_ver_cmd_list:
            cmd_output = run_shell_cmd( cmd )
            self.cur_ver_str = cmd_output.strip('\n')
            printd(DBG_VBS, "%s : cur ver is %s" %(self.category, self.cur_ver_str))
            
            try:
                cur_ver_nr = float(self.cur_ver_str)
            except ValueError:
                printd(DBG_VBS, "%s, cannot convert to fload, must be md5 hash." %(self.category))
                continue
            else:
                self.cur_ver_nr = cur_ver_nr
                return
            
        #It is OK that cur_ver_str cannot be convert to float for LSI components 
        if ("LSI" in self.category and len(self.cur_ver_str) == 32):
            return
        else:
            raise Exception ("%s, wrong format for version string" %self.category)

    def need_upgrade( self ):
        #compare two version strings. Return true if upgrading is needed. Otherwsie, return false
        printd(DBG_INF, "%s : cur ver %s, expected ver %s" %(self.category, 
                self.cur_ver_str, self.expected_ver_str))

        if ( self.expected_ver_str == self.cur_ver_str ):
            return False

        try:
            expected_ver_nr = float(self.expected_ver_str)
        except ValueError:
            printd(DBG_VBS, "%s, cannot convert to float, must be md5 hash." %(self.category))
            return True
        else:
            printd(DBG_VBS, "%s : cur ver %f, expected ver %f" %(self.category, 
                float(self.cur_ver_nr), float(self.expected_ver_str)))
        
        
        if ( expected_ver_nr == self.cur_ver_nr ):
            return False
        
        if (self.newer_ok == "yes" ):
            if ("BMC" in self.category): #need to splict to major and minor versions
                return compare_with_major_minor(self.expected_ver_str, self.cur_ver_str)
            else :
                if (self.cur_ver_nr >= expected_ver_nr ):
                    return False
            
        return True

    def upgrade(self, retry_times):
        """upgrade the firmware
        return value: Upgrade_result.Failed_no_file: upgrade failed because files do not exist
        return value: Upgrade_result.Fail_cmds: upgrade failed because cmds failed
        return value: Upgrade_result.Succeed_no_need_upgrade: no need to upgrade
        return value: Upgrade_result.Succeed_upgrade : upgrade succeed ..."""
    
        printd(DBG_VBS, "in upgrade")
        
        if ( not self.need_upgrade() ):
            printd(DBG_INF, "No need to upgrade, cur ver %s" %self.cur_ver_str)
            return Upgrade_result.Succeed_no_need_upgrade

        printd(DBG_VBS, "Need to upgrade")
        
        if ( not (check_file(self.expected_img) ) ):
            printd(DBG_ERR, "Error: cannot find expected image file " + self.expected_img)
            return Upgrade_result.Failed_no_file
        
        if ( not ( self.expected_img in self.upgrade_cmd_opt ) ):
            printd(DBG_ERR, "Error: Expected image file not in the command line option")
            return Upgrade_result.Failed_no_file

        for  i in range(int(retry_times) + 1) :
            try:
                full_cmd = self.upgrade_cmd + self.upgrade_cmd_opt
                printd(DBG_VBS, "Need to upgrade, cmd " + full_cmd)
                printd(DBG_INF, "upgrading %s... this may take several minutes, please wait." %self.category)
                run_shell_cmd(full_cmd)
            except Exception, err:
                printd(DBG_WAR, "upgrade %s failed, cmd %s, error %s" %(self.category, full_cmd, err))
            else:
                printd(DBG_INF, "upgrade %s succeed" %self.category )
                return Upgrade_result.Succeed_upgrade 
        
        return Upgrade_result.Fail_cmds
        
        
    def fall_back(self):
        if ( not check_file(self.fallback_img) ):
            return False

        printd(DBG_INF, "%s : cur ver %s, fall back ver %s" %(self.category, 
            self.cur_ver_str, self.fallback_ver_str))

        try:
            fallback_ver_nr = float(self.fallback_ver_str)
        except ValueError:
            printd(DBG_VBS, "%s, cannot convert fall back ver to float, must be md5 hash." %(self.category))
        else:
            printd(DBG_VBS, "%s : cur ver %f, fall back ver %f" %(self.category, 
                float(self.cur_ver_nr), float(self.fallback_ver_str)))
        
        
        if ( (self.fallback_ver_str != self.cur_ver_str) and (fallback_ver_nr != self.cur_ver_nr) ):
            printd(DBG_WAR, "%s : cur ver %s is different from fall back ver %s" %(self.category, 
                self.cur_ver_str, self.fallback_ver_str))
            
        try:
            printd(DBG_INF, "falling back to old image %s... this may take several minutes, please wait." %self.category)
            run_shell_cmd(self.upgrade_cmd + self.fallback_cmd_opt)
        except Exception, err:
            printd(DBG_ERR, "Error: %s: failed to fall back image %s, err msg %s" %(self.category, self.fallback_img, err))
            return False
        else:
            printd(DBG_INF, "%s: fallback to old image %s finished" %(self.category,self.fallback_img))
            return True
        
    def to_string(self):
        tmpstr = ( "\n" + "name " + self.name + "\n" +
        "cur_ver " + self.cur_ver_str + "\n" +
        "expected_ver_str " + str(self.expected_ver_str) + "\n"+
        "expected_img " + self.expected_img + "\n"+
        "upgrade_cmd " + self.upgrade_cmd + "\n"+
        "upgrade_cmd_opt " + self.upgrade_cmd_opt + "\n"+
        "fallback_img " + self.fallback_img + "\n"+
        "fallback_cmd_opt " + self.fallback_cmd_opt )
        for cc in self.cur_ver_cmd_list:
            tmpstr += cc
            tmpstr += "\n"

        return tmpstr
        
###############################################################################
#
# FWTransaction
#
# Class for firmware transactions. Each transaction may contain mulitple FWItem
# For example, LSI controller BIOS and FW could be in one transaction
# 
###############################################################################
    
class FWTransaction(Action):
    def __init__(self, name):
        self.name = name
        self.action_name_list = []
        self.action_list = []
        self.post_action_name_list = []
        self.post_action_list = []
        self.changed = False
        self.need_reboot = "no"
        self.reboot_now = "no"
    
    def add_action_name(self, action_name):
        self.action_name_list.append(action_name)
    
    def add_action(self, real_action):
        self.action_list.append(real_action)

    def add_post_action_name(self, action_name):
        self.post_action_name_list.append(action_name)
    
    def add_post_action(self, real_action):
        self.post_action_list.append(real_action)
            
    def do_it(self):
        printd(DBG_VBS, "tr: in do_it")

        finished = 0
        failed = False
        fall_back_failed = False
        
        global G_alarm_file_path
        
        ret_list = []
        for item in self.action_list:
            try:
                item.get_cur_ver()
            except Exception, err:
                printd(DBG_ERR, "Failed to get current version, error %s" %err)
                return
            
            ret = item.upgrade(self.retry_times)

            if ( ret >= Upgrade_result.Succeed_no_need_upgrade):
                finished += 1
                if ( ret == Upgrade_result.Succeed_upgrade) :
                    self.changed = True
            else:
                failed = True
                break
                
        if ( failed and (self.if_fall_back == "yes")):
            i = 0
            for item in self.action_list:
                if ( finished == 0 and (ret == Upgrade_result.Failed_no_file) ):
                    # no need to fall back in this case
                    break;
                    
                if i <= finished :
                    ret = item.fall_back()
                    if ( not ret ):
                        fall_back_failed = True
                    else:
                        self.changed = True
                    i += 1
                else:
                    break
                    
        if ( fall_back_failed and self.trigger_alarm == "yes" ):
            try:
                f = open(G_alarm_file_path, 'w')
            except Exception, err:
                printd(DBG_ERR, "Failed to open file %s, err %s" %(G_alarm_file_path, err))
            else:
                try:
                    f.write(self.name)
                    f.write(" failed to fall_back to the old image\n")
                except Exception, err:
                    printd(DBG_ERR, "Failed to write to file %s, err %s" %(G_alarm_file_path, err))
                finally:
                    f.close()
        elif ( failed and self.trigger_alarm == "yes" ):
            try:
                f = open(G_alarm_file_path, 'w')
            except Exception, err:
                printd(DBG_ERR, "Failed to open file %s, err %s" %(G_alarm_file_path, err))
            else:
                try: 
                    f.write(self.name)
                    f.write(" failed to upgrade to new image, fell back to old image\n")
                except Exception, err:
                    printd(DBG_ERR, "Failed to write to file %s, err %s" %(G_alarm_file_path, err))
                finally:
                    f.close()
        
        if ( self.changed  and self.need_reboot == "yes" ):
            if ( self.reboot_now == "yes" ):
                raise RebootException
            else: 
                global G_NEED_REBOOT
                G_NEED_REBOOT = True
        
        if ( self.changed ):
            for item in self.post_action_list:
                item.do_it()
        
        
    def get_cur_fw_ver(self):
        printd(DBG_VBS, "in fwtrancation.get_cur_fw_ver")

        for item in self.action_list:
            item.get_cur_ver()
            print("rfut: %s : cur ver is %s" %(item.category, item.cur_ver_str))
            
    def to_string(self):
        tmpstr = ( "\n" + "name " + self.name + "\n" +
        "action_name_list " + str(self.action_name_list) + "\n" +
        "retry_times " + str(self.retry_times) + "\n" + 
        "trigger_alarm " + self.trigger_alarm + "\n" + 
        "if_fall_back " + self.if_fall_back + "\n" )
        
        return tmpstr
                
###############################################################################
#
# CmdItem
#
# Class for each general shell cmds, such as cp rom files etc.
#
###############################################################################

class CmdItem:
    def __init__(self, name):
        self.name = name
        self.cmd_list = []
        
    def add_cmd(self, cmd):
        self.cmd_list.append(cmd)
    
    def do_it(self):
        printd(DBG_VBS, "cmd: in do_it")
        for cc in self.cmd_list:
            run_shell_cmd(cc)

    def to_string(self):
        tmpstr = ( "\n" + "name " + self.name + "\n")
        for cc in self.cmd_list:
            tmpstr += cc
            tmpstr += "\n"
        return tmpstr

###############################################################################
#
# CmdAction
#
# Class for general shell cmd actions, each action may contain mulitple cmds
#
###############################################################################
        
class CmdAction(Action):
    def __init__(self, name):
        self.name = name
        self.action_name_list = []
        self.action_list = []
        self.post_action_name_list = []
        self.post_action_list = []

    
    def add_action_name(self, action_name):
        self.action_name_list.append(action_name)
    
    def add_action(self, real_action):
        self.action_list.append(real_action)
            
    def do_it(self):
        printd(DBG_VBS, "in cmd.do_it()")
        for item in self.action_list:
            item.do_it()
        
    def to_string(self):
        tmpstr = ( "\n" + "name " + self.name + "\n"
            + str(self.action_name_list) + "\n")
        return tmpstr

###############################################################################
#
# get_motherboard
#
# call into hwtool to find out what platform we're running on.
#
###############################################################################

def get_motherboard():
    cmdline1     = '/opt/tms/bin/hwtool -q motherboard'
    cmdline2     = '/opt/tms/bin/hwtool -q mobo-type'

    if ( not check_file("/opt/tms/bin/hwtool") ):
        raise Exception ('Unable to find hwtool executable')

    out1 = run_shell_cmd(cmdline1)

    out2 = run_shell_cmd(cmdline2)
    
    return (out1.strip('\n'), out2.strip('\n'))


###############################################################################
#
# populate_cmd_item
#
# set CmdItem members as specified in the xml file. Don't run any cmd here.
#
###############################################################################

def populate_cmd_item(element):
    
    tmpCmd = CmdItem(element.attrib["name"])
    
    for child in element:
        if child.tag == "one_cmd":
            tmpCmd.cmd_list.append(child.attrib["cmd"])
    return tmpCmd

###############################################################################
#
# populate_FW_item
#
# set FWItem members as specified in the xml file. Don't run any cmd here.
#
###############################################################################

def populate_FW_item(element):
    
    tmpFW = FWItem(element.attrib["name"])
    
    tmpFW.category = element.attrib["category"]
    
    for child in element:
        if child.tag == "cur_ver":
            nrOfCmd = child.attrib["possible_cmds"]
            for i in range (int(nrOfCmd)):
                cmdAttr = "cmd" + str(i)
                tmpFW.cur_ver_cmd_list.append(child.attrib[cmdAttr])
        
        if child.tag == "expected_image":
            tmpFW.expected_ver_str = child.attrib["ver"]
            tmpFW.expected_img = child.attrib["image_file"]
            if "LSI" not in tmpFW.category:
                tmpFW.newer_ok = child.attrib["newer_ok"]
        
        if child.tag == "upgrade_cmd":
            tmpFW.upgrade_cmd = child.attrib["cmd"]
            upgrade_cmd_opt = child.attrib["cmd_option"]
            if (len(upgrade_cmd_opt) >=1 and upgrade_cmd_opt[0] is not " "):
                tmpFW.upgrade_cmd_opt = " " + upgrade_cmd_opt
            else:
                tmpFW.upgrade_cmd_opt = upgrade_cmd_opt
        
        if child.tag == "fall_back":
            tmpFW.fallback_ver_str = child.attrib["ver"]
            tmpFW.fallback_img = child.attrib["image"]
            tmpFW.fallback_cmd_opt = child.attrib["cmd_option"]
        
    printd(DBG_VBS, "done with FWItem population")
    return tmpFW
        

###############################################################################
#
# populate_transaction
#
# set FWTransaction members as specified in the xml file. Don't run any cmd here.
#
###############################################################################

def populate_transaction(element):
    tmpTr = FWTransaction(element.attrib["name"])
    tmpTr.retry_times = element.attrib["retry_times"]
    tmpTr.trigger_alarm = element.attrib["alarm_if_fails"]
    tmpTr.if_fall_back = element.attrib["fall_back_to_old_image"]
    tmpTr.need_reboot = element.attrib["need_reboot"]
    if ( tmpTr.need_reboot == "yes" ):
        tmpTr.reboot_now = element.attrib["reboot_now"]
    
    len = 0
    
    for child in element:
        if child.tag == "item":
            tmpTr.add_action_name( child.attrib["name"] )
            len += 1
        if child.tag == "after_upgrade_action":
            tmpTr.add_post_action_name( child.attrib["name"] )
        
    printd(DBG_VBS, "tot item is %d" %len)
    
    return tmpTr


###############################################################################
#
# populate_cmds
#
# set FWTransaction members as specified in the xml file. Don't run any cmd here.
#
###############################################################################

def populate_cmds(element):
    tmpCmdAct = CmdAction(element.attrib["name"])
    tmpCmdAct.add_action_name(element.attrib["name"])
    return tmpCmdAct

    
###############################################################################
#
# main function
#
# do actual checking and upgrading and falling back
#
###############################################################################

def main():

    # Set up command line args
    parser = OptionParser(version="%prog Version 0.2")

    # command line parser options
    parser.add_option("-d", "--debug", action="store", type="int",
                      dest="debug", default="3",
                      help="Set debug level, 0 - 4, 0 is none, 4 is showing all msgs")
    parser.add_option("-l", "--logfile", action="store", type="string",
                      dest="logfile", default="",
                      help="Log stdout to this file (like Unix tee command)")
    parser.add_option("-s", "--sys-log", action="store_true", 
                      dest="syslog_enable", default=False,
                      help="Log stdout to syslog. Disabled by default")
    parser.add_option("-c", "--configfile", action="store", type="string",
                      dest="configfile", default="/opt/rbt/etc/fwspec.xml",
                      help="specify the config file to use, default is /opt/rbt/etc/fwspec.xml")
    parser.add_option("-g", "--get-current-ver", action="store_true", 
                    dest="only_get_cur", default=False,
                    help="only show current fimware versions, do not upgrade anything")
    parser.add_option("-r", "--remove_state_file", action="store_true", 
                    dest="remove_state_file", default=False,
                    help="delete all the state files related to rfut. This will let the rfut to do upgrade again.")
                      
    (options, args) = parser.parse_args()
    
    global SYSLOG_ENABLE
    SYSLOG_ENABLE = options.syslog_enable
    
    # log stdout like tee
    if (options.logfile != ""):
        tee = TeeLog(sys.stdout, options.logfile)
        sys.stdout = tee
    elif (options.syslog_enable):
        tee = TeeLog(sys.stdout, "")
        sys.stdout = tee
        
    # set global debug level
    global CURRENT_DBG_LEVEL
    CURRENT_DBG_LEVEL = options.debug
    
    global G_NEED_REBOOT
    G_NEED_REBOOT = False
    
    global G_alarm_file_path
    G_alarm_file_path = "/boot/.rfut_alarm"
        
    
    # check if .upgrade_complete file exist or not. exit if it exists
    done_file_path = "/boot/.rfut_upgrade_finished"
    state_file_path = "/boot/.rfut_cur_state"
    
    if (options.remove_state_file):
        try:
            os.remove(done_file_path)
        except OSError, err:
            printd(DBG_ERR, "Error: Failed to delete state file, error %s" %err )

        try:
            os.remove(state_file_path)
        except OSError, err:
            printd(DBG_ERR, "Error: Failed to delete state file, error %s" %err )
            
        try:
            os.remove(G_alarm_file_path)
        except OSError, err:
            printd(DBG_ERR, "Error: Failed to delete alarm file, error %s" %err )
            
        return
    
    
    if ( check_file( done_file_path, False ) and (not options.only_get_cur)):
        printd(DBG_INF, "Firmware Upgrade completed")
        sys.exit( 0 )

    # read current state from file
    done_act_dict = {}
    
    
    if ( check_file( state_file_path, False ) ):
        printd(DBG_VBS, "Firmware state file exist")
        f = open(state_file_path, 'r')
        for line in f:
            (date, time, key, val) = line.split()
            done_act_dict[key] = val
        f.close()
    
    # read in xml configuration file
    xml_file = os.path.abspath(__file__)
    xml_file = os.path.dirname(xml_file)
    xml_file = os.path.join(xml_file, options.configfile)

    # get current mother board type
    (part, type) =  get_motherboard()
    
    printd(DBG_VBS, "motherboard is" + part + " " + type)
    
    # parse the xml file
    try:
        tree = etree.parse(xml_file)
    except Exception, inst:
        printd(DBG_ERR, "Error: Unexpected error opening %s: %s" % (xml_file, inst))
        raise

    root = tree.getroot()

    full_act_dict = {}
    real_act_list = []
    

    for element in root.iter("*"):
        if element.tag:
            printd(DBG_VBS, "tag ---" + element.tag)

        if (element.tag == "binaries"):
            printd(DBG_VBS, "found binaries")
            for child in element:
                if child.tag == "cmd":
                    printd(DBG_VBS, "found cmds " + child.attrib["name"])
                    tmpBin = Binary(child.attrib["name"])
                    if tmpBin.whereis() is None:
                        raise Exception ('Unable to find executable ' + child.attrib["name"])
        
        if (element.tag == "cmds"):
            printd(DBG_VBS, "found cmds nodes")
            tmpCmd = populate_cmd_item(element)
            printd(DBG_VBS, "cmds item" + tmpCmd.to_string())
            full_act_dict[tmpCmd.name] = tmpCmd
        
        if (element.tag == "FW_item"):
            printd(DBG_VBS, "found FW_item")
            tmpFW = populate_FW_item(element)
            printd(DBG_VBS, "fw item" + tmpFW.to_string())
            full_act_dict[tmpFW.name] = tmpFW
                               
        
        if (element.tag == "motherboard" 
            and element.attrib["part"] == part  
            and element.attrib['mobo_type'] == type):

            for child in element:
                if child.tag == "upgrade":
                    printd(DBG_VBS, "upgrade len is " + str(len(child)))
                    
                    for items in child:
                        if (items.tag == "transaction"):
                            printd(DBG_VBS, "found transaction")
                            tmpTr = populate_transaction(items)
                            printd(DBG_VBS, "transaction is " + tmpTr.to_string())
                            real_act_list.append( tmpTr )
                            
                        if (items.tag == "run_cmd"):
                            printd(DBG_VBS, "found run_cmds")
                            tmpCmdAct = populate_cmds(items)
                            printd(DBG_VBS, "cmds is " + tmpCmdAct.to_string())
                            real_act_list.append( tmpCmdAct )
            
    for tr in real_act_list:
        printd(DBG_VBS, "action list is " + tr.to_string())

    if ( options.only_get_cur ):
        for tr in real_act_list:
                
            for act in tr.action_name_list:
                tr.add_action(full_act_dict[act])
            try:
                tr.get_cur_fw_ver()
            except Exception, err:
                printd(DBG_ERR, "Failed to get current firmware version, err %s" %err)
        return
    
    # perform upgrade
    for tr in real_act_list:
        if ( tr.name in done_act_dict):
            printd(DBG_VBS, "%s is already done, skip it" %tr.name)
            continue
            
        for act in tr.action_name_list:
            tr.add_action(full_act_dict[act])
        for act in tr.post_action_name_list:
            tr.add_post_action(full_act_dict[act])
        try:
            tr.do_it()
        except RebootException:
            now = datetime.datetime.now()
            try: 
                f = open(state_file_path, 'a')
            except Exception, err:
                printd(DBG_ERR, "Failed to open file %s, err %s" %(state_file_path, err))
            else:
                try:
                    f.write( str(now) )
                    f.write(" ")
                    f.write(tr.name)
                    f.write(" done\n")
                except Exception, err:
                    printd(DBG_ERR, "Failed to write to file %s, err %s" %(state_file_path, err))
                finally:
                    f.close()
            printd(DBG_INF, "rebooting....")
            sys.exit( 0xff ) #the caller should check the exit value and reboot.

        #write to state file
        now = datetime.datetime.now()
        try:
            f = open(state_file_path, 'a')
        except Exception, err:
            printd(DBG_ERR, "Failed to open file %s, err %s" %(state_file_path, err))
        else:
            try:
                f.write( str(now) )
                f.write(" ")
                f.write(tr.name)
                f.write(" done\n")
            except Exception, err:
                printd(DBG_ERR, "Failed to write to file %s, err %s" %(state_file_path, err))
            finally:
                f.close()
        
    # create hidden complete file so that we do not repeat ourselves
    try:
        finish_file = open(done_file_path, 'w')
    except IOError:
        printd(DBG_ERR, "Error: Failed to create log file" )
        sys.exit ( 1 )


    finish_file.close()

    if (G_NEED_REBOOT):
        printd(DBG_INF, "rebooting....")
        sys.exit( 0xff ) #the caller should check the exit value and reboot.

if __name__ == "__main__":
    main()

