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
from raidctrl import raid_3ware, raid_sw, raid_lsi
from rrdm_util import rrdm_error

# use the raid packages for sw raided units.
#
from rrdm_util import run_shell_cmd

model     = '500'
card_type = 'lsi'
opt_test  = 1

def hal_init():
    """ Initializing global variables """

    global model
    global card_type

    db = MgmtDB.MgmtDB('/config/mfg/mfdb')
    model = db.get_value('/rbt/mfd/model')

    if (model == '3000' or model == '3010' or 
        model == '3020' or model == '3510' or
        model == '3520' or model == '5000' or
        model == '5010' or model == '5520' or
        model == '6020' or model == '9200'):
        card_type = 'lsi'
    elif (model == '6520' or model == '6120'):
        card_type = '3ware'
    else :
	try:
	    output = run_shell_cmd ('/opt/hal/bin/raid/rrdm_tool.py --uses-sw-raid', True)
	    if output == 'True':
		card_type = 'swraid'
	except rrdm_error:
            card_type = 'None'
	
    db.close()


def main(argv=None):
    """ Hal """

    global card_type
    global model

    if argv is None:
        argv = sys.argv
        try:
            opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
        except getopt.error, msg:
            print >> sys.stderr, err.msg
            print >> sys.stderr, "for help use --help"
            return 2

        for o, a in opts:
            if o in ("-h", "--help"):
                print __doc__
                sys.exit(0)

        hal_init()

        raid = None
        if (card_type == '3ware') :
            raid = raid_3ware()
        elif (card_type == 'lsi') :
            raid = raid_lsi()
	elif (card_type == 'swraid'):
	    raid = raid_sw()
        else :
            print 'Not supported on this hardware platform.'
            return 0

        for arg in args:
            if arg == "show_raid_config":
                raid.show_raid_config()
            elif arg == "show_raid_info":
                raid.show_raid_info()
            elif arg == "show_raid_physical":
                raid.show_raid_physical()
            elif arg == "show_raid_info_detail":
                raid.show_raid_info_detail()
            elif arg == "show_raid_config_detail":
                raid.show_raid_config_detail()
            elif arg == "raid_card_vendor":
                raid.show_card_type()
            elif arg == "test":
                raid.show_raid_status()
            else:
                print ""

if __name__ == "__main__":
    main()
