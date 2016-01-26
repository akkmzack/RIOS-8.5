#!/usr/bin/python

from getopt import getopt, GetoptError
from sys import exit, argv
from hwtool_util import *
from hwconfig import *
from appliance_util import *
from hwtool_cpu import *
from hwtool_disk import *
from hwtool_nic import *
from hwtool_sh import *

debug_parse = False
gateway_naming = False
config_path = "/opt/tms/lib/hwtool/config/config.xml"
query = ""

enable_syslog ()
        
##############################################################
#run utils
def usage():

    print "Usage:", argv[0], "[options] <-q query> "
    print """  Options:
    -h ................. print this message
    -v ................. be verbose
    -o ................. use filer gateway naming convention
    -c [config_path] ... load config from [config_path]
    -m [modules_dir] ... load modules from [module_path]

  Queries:
    address_map=[addr_map_path] : Write the address map to stdout or [addr_map_path]
    bios=[info_type] : Print bios information
    cli=[] : Pretty-print device info for the CLI
    hal-path=[] : Ouput the path to the HAL program
    mactab=[mactab_path] : Write a mactab to stdout or [mactab_path]
    motherboard=[] : Output the motherboard's part number
    revision=[] : Output the hardware revision ID
    system=[] : Pretty-print all system information"""

def parse_opts(opts):
    global debug_parse, config_path, query, gateway_naming
    for o, a in opts:
	if o in ["-v", "-d"]:
	    debug_parse = True
	if o == "-o": 
	    gateway_naming = True 
	if o == "-c": 
	    config_path = a 
	if o == "-h":
	    usage()
	    exit(0)
        if o == "-m":
	    pass 
	if o == "-q":
	    query = a

def main():
    global config_path, query
    try:
        opts, ign = getopt(argv[1:], "q:c:m:hdov")
    except GetoptError:
        usage()
	exit(2)

    parse_opts(opts)

    if query == "":
	exit(0)

    parse_config(config_path)

    arg = ""
    try:
	query, arg = query.split('=')
    except ValueError:
	pass

    if query == "revision":
	get_rev()
    elif query == "address_map":
	get_address_map(gateway_naming, False, False)
    elif query == "bios":
	get_bios(arg)
    elif query == "cli":
	get_cli()
    elif query == "if_util":
	get_util(query, arg)
    elif query == "card_list":
        get_card_list()
    elif query == "has_card":
        get_has_card(arg)
    elif query == "if_block":
	get_util(query, arg)
    elif query == "ipmi":
        get_ipmi_support()
    elif query == "if_type":
	get_util(query, arg)
    elif query == "if_part_num":
	get_util(query, arg)
    elif query == "getniccard":
	get_nic_card()
    elif query == "hal-path":
	get_hal_path()
    elif query == "mactab":
	get_mactab(arg, gateway_naming)
    elif query == "motherboard":
	get_motherboard()
    elif query == "mobo-family":
	get_mobo_hint()
    elif query == "system":
	get_system()
    elif query == "raid":
        print_raid()
    elif query == "cpu":
	print_cpu(arg)
    elif query == "memory":
	print_memory(arg)
    elif query == "disk":
	get_disk(arg)
    elif query == "flash":
	print_flash()
    elif query == "licensed":
	print_licensed(True)
    elif query == "branding":
	get_branding()
    elif query == "group-info":
        get_groupinfo()
    elif query == "unlicensed-info":
        print_licensed(False)
    elif query == "disk-license":
        print_disk_license()
    elif query == "nic-license":
        print_nic_license()
    elif query == "flex-supported":
        print_flexl()
    elif query == "hwalarm-support":
        print_hwalarm()
    elif query == "kernel-opts":
       print_kernel_opts()
    elif query == "nic-valid-brand-string":
        NIC.valid_brand_string(arg)
    elif query == "physical-mobo":
       get_physical_motherboard()
    elif query == "mobo-type":
       get_motherboard_type()
    elif query == "who-checks-disk":
       get_disk_check()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception, (str) :
        print "Error:", str
        exit(1)
    else:
        exit(0)
