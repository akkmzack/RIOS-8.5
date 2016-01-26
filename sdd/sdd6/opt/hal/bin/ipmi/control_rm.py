#!/usr/bin/python

# Script controls the remote management port, including IP address, 
# bitrate, and passwords
#
# Usage:
# control_rm.py enable
# control_rm.py disable
# control_rm.py get-ip
# control_rm.py dhcp
# control_rm.py <ip=xxx> <netmask=xxx> <gateway=xxx> <mac=xxx>
# control_rm.py get-bitrate
# control_rm.py set-bitrate=x.x
# control_rm.py set-password=xxxxxx
#
# enable enables the remote port
# disable disables the remote port
# get-ip returns all IP address related info
# dhcp sets the remote management port to get IP info via dhcp
# ip= set the remote management port to the specified IP address
# netmask= set to the specified netmask
# gateway= set to the specified gateway
# mac= change the MAC address to the one specified
# get-bitrate returns the current bit-rate used for SOL
# set-bitrate sets the SOL bit-rate
# set-password= sets all remote management port user passwords, leave blank to clear the passwords

import re
from os import popen
import time
import sys

IP_INFO_ERROR = 5

def check_bluedell():
    # check motherboard
    mb = popen('/opt/hal/bin/hwtool.py -q motherboard')
    output = mb.read()
    match = re.search(r"425-00135-01", output)
    if match: # means bluedell
        checkroot = popen('ipmitool user list 1')
	checkoutput = checkroot.read()
        match = re.search(r"2\s+root\s+\w+", checkoutput)
        if match: # means we need to change the root account to ""
            setnull = popen('ipmitool user set name 2 ""')
            nullcode = setnull.close()
            if nullcode != None:
                print("error changing account name on bmc")
    code = mb.close()
    if code != None:
        print("error checking motherboard")

def get_ip_info(mode):
    ip = ""
    netmask = ""
    dhcp = 0
    gateway = ""
    mac = ""
    error = 0
    
    ipmitool = popen('ipmitool lan print')
    for l in ipmitool.readlines():
        match = re.match(r"IP\sAddress\sSource\s+:\s(\w+)", l)
        if match:
            if (match.group(1) == "DHCP"):
                dhcp = 1
        match = re.match(r"MAC\sAddress\s+:\s(\w\w:\w\w:\w\w:\w\w:\w\w:\w\w)", l)
        if match:
            mac = match.group(1)
        match = re.match(r"IP\sAddress\s+:\s(\d+\.\d+\.\d+\.\d+)", l)
        if match:
            ip = match.group(1)
        match = re.match(r"Subnet\sMask\s+:\s(\d+\.\d+\.\d+\.\d+)", l)
        if match:
            netmask = match.group(1)
        match = re.match(r"Default\sGateway\sIP\s+:\s(\d+\.\d+\.\d+\.\d+)", l)
        if match:
            gateway = match.group(1)

    code = ipmitool.close()
    if code != None:
        error = 1
    else:
        if (ip == "") or (netmask == "") or (gateway == ""):
            error = 1 # will signal that we need a 2nd try
        else:
            if (mode == "print"):
                dcounter = 0
	        ipmitool = popen('ipmitool channel info 1')
                for l in ipmitool.readlines():
                    match = re.match(r"\s\s\s\sAccess\sMode\s+:\sdisabled", l)
                    if match:
                        dcounter = dcounter + 1
                code = ipmitool.close()
                if (dcounter == 2):
                    print "Remote Access: Disabled"
                else:
                    print "Remote Access: Enabled"
                if code != None:
                    error = 1
                if (dhcp == 1):
                    print "DHCP:          Enabled"
                else:
                    print "DHCP:          Disabled"
                print "IP Address:    " + ip
                print "Netmask:       " + netmask
                print "Gateway:       " + gateway
                print "MAC Address:   " + mac
    return [dhcp, ip, netmask, gateway, mac, error]

def enable_dhcp():
    check_bluedell()
    ipmitool = popen('ipmitool lan set 1 ipsrc dhcp')
    code = ipmitool.close()
    if code != None:
        print("Error setting DHCP")
	sys.exit(1)

def remote_enable():
    ipmitool = popen('ipmitool lan set 1 access on')
    code = ipmitool.close()
    if code != None:
        print("error enabling remote port access")

def remote_disable():
    ipmitool = popen('ipmitool lan set 1 access off')
    code = ipmitool.close()
    if code != None:
        print("error disabling remote port access")
		    
def set_ip_info(data):
    check_bluedell()

    string = "ipmitool lan set 1"
    if (data[0] != ""): # ip address
        string = string + " ipaddr " + data[0]
    if (data[1] != ""): # netmask
        string = string + " netmask " + data[1]
    if (data[2] != ""): # gateway
        string = string + " defgw ipaddr " + data[2]
    if (data[3] != ""): # MAC address
        string = string + " macaddr " + data[3]

    ipmitool = popen('ipmitool lan set 1 ipsrc static')
    code = ipmitool.close()
    if code != None:
        # wait a couple seconds and try again
	# ipmitool can error out with channel 1 not a lan channel so retry
	time.sleep(2)
	ipmitool = popen('ipmitool lan set 1 ipsrc static')
	code = ipmitool.close()
	if code != None:
            print("Error setting address type to static")

    ipmitool = popen(string)
    # the rest of this function is all error checking
    output = ipmitool.read()
    match = re.search(r"Invalid\sIP\saddress", output)
    if match: # means ipmitool returned an error about the ip addr
        print("IP address not valid")
	sys.exit(1)
    code = ipmitool.close()
    if code != None:
        print("Error setting IP or MAC settings")
	sys.exit(1)
    time.sleep(1)
    ip_info = get_ip_info("")
    if (ip_info[IP_INFO_ERROR] == 1): # means there was a problem running ipmitool
        # wait a couple seconds and try again
        time.sleep(2)
        ip_info = get_ip_info("")
        if (ip_info[IP_INFO_ERROR] == 1):
            print("Error accessing current IP settings")
            sys.exit(1)
    if (data[0] != "") and (data[0] != ip_info[1]): # ip
        print("Ip address did not set correctly")
        sys.exit(1)
    if (data[1] != "") and (data[1] != ip_info[2]): # netmask
        print("Netmask did not set correctly")
        sys.exit(1)
    if (data[2] != "") and (data[2] != ip_info[3]): # gateway
        print("Default-gateway address did not set correctly")
        sys.exit(1)


def set_bitrate(rate):
    set = popen('ipmitool sol set volatile-bit-rate ' + str(rate) + " 1")
    code = set.close()
    if code != None:
        print("Error setting volatile bit rate")
	sys.exit(1)
    time.sleep(1)
    set = popen('ipmitool sol set non-volatile-bit-rate ' + str(rate) + " 1")
    code = set.close()
    if code != None:
        print("Error setting non-volatile bit rate")
        sys.exit(1)

def get_bitrate():
    getrate = popen('ipmitool sol info 1 2>/dev/null')
    for l in getrate.readlines():
        match = re.match(r"Volatile\s.+\s\(kbps\)\s+:\s+(\d+\.?\d*)", l)
        if match:
            print "Volatile:     " + str(match.group(1)) + " kbps"
        match = re.match(r"Non-Volatile\s.+\s\(kbps\)\s+:\s+(\d+\.?\d*)", l)
        if match:
            print "Non-Volatile: " + str(match.group(1)) + " kbps"
    code = getrate.close()
    if code != None:
        print("Error checking bit rate")
	sys.exit(1)

def set_password(password):
    import subprocess
    match = re.match(r"(\w*)", password)
    if match == None or match.group(1) != password:
        print >>sys.stderr,"Invalid character in password. Alphanumeric or '_' expected."
        sys.exit(1)
    looper = 1
    while (looper != 6):
        child_proc = subprocess.Popen(
            ['ipmitool', 'user', 'set', 'password', str(looper), password],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE)
        looper += 1
        (child_stdout_text, child_stderr_text) = child_proc.communicate()
	if child_proc.returncode:
            print >>sys.stderr, child_stderr_text,
	    sys.exit(1)

# check for remote port support
check_ipmi = popen('/opt/hal/bin/hwtool.py -q ipmi')
output = check_ipmi.read()
code = check_ipmi.close()
if code != None:
    print("Error checking for feature support")
    sys.exit(1)
match = re.search(r"False", output)
if match:
    print("This model does not support the remote management port feature")
    sys.exit(0)

ip = ""
netmask = ""
gateway = ""
mac = ""
password = ""
# parse commandline options and execute
no_valid_cli_option = 1
# if no_valid_cli_option == 1 at the end of the script, that means
# no option was provided to the script that matched any regex
for i in sys.argv:
    if i == "enable":
        no_valid_cli_option = 0
        remote_enable()
        sys.exit(0)
    if i == "disable":
        no_valid_cli_option = 0
        remote_disable()
        sys.exit(0)
    if i == "get-ip":
        no_valid_cli_option = 0
        ip_info = get_ip_info("print")
        if (ip_info[IP_INFO_ERROR] == 1): # means there was a problem running ipmitool
            # wait a couple seconds and try again
            time.sleep(2)
            ip_info = get_ip_info("print")
            if (ip_info[IP_INFO_ERROR] == 1):
                print("Error accessing current IP settings")
                sys.exit(1)
        sys.exit(0)
    if i == "dhcp":
        no_valid_cli_option = 0
        enable_dhcp()
        sys.exit(0)
    if i == "get-bitrate":
        no_valid_cli_option = 0
        get_bitrate()
        sys.exit(0)
    match = re.match(r"set-bitrate=(\d+\.?\d*)", i)
    if match:
        no_valid_cli_option = 0
        set_bitrate(match.group(1))
        sys.exit(0)
    match = re.match(r"set-password=(.*)", i)
    if match:
        no_valid_cli_option = 0
        password = match.group(1)
        set_password(password)
        sys.exit(0)
    match = re.match(r"ip=(\d+\.\d+\.\d+\.\d+)", i)
    if match:
        no_valid_cli_option = 0
        ip = match.group(1)
    match = re.match(r"netmask=(\d+\.\d+\.\d+\.\d+)", i)
    if match:
        no_valid_cli_option = 0
        netmask = match.group(1)
    match = re.match(r"gateway=(\d+\.\d+\.\d+\.\d+)", i)
    if match:
        no_valid_cli_option = 0
        gateway = match.group(1)
    match = re.match(r"mac=([0-9|a-f|A-F]{2}:[0-9|a-f|A-F]{2}:[0-9|a-f|A-F]{2}:[0-9|a-f|A-F]{2}:[0-9|a-f|A-F]{2}:[0-9|a-f|A-F]{2})", i)
    if match:
        no_valid_cli_option = 0
        mac = match.group(1)

if (ip != "") or (netmask != "") or (gateway != "") or (mac != ""):
    set_ip_info([ip, netmask, gateway, mac])

if (no_valid_cli_option == 1):
    print("No valid options or values were specified")
