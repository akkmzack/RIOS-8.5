#!/usr/bin/python

from getopt import getopt, GetoptError
from optparse import OptionParser
import string, os
from os.path import exists
from appliance_util import *
from xml.dom.minidom import parse
from rrdm_config import *
from rrdm_util import *
from shutil import copy
from os import remove

###############################################################################
# Constants
#
###############################################################################
spec_file = "/opt/hal/lib/specs/specs.xml"
hwtool_path='/opt/hal/bin/hwtool.py'

###############################################################################
# Globals
#
###############################################################################
specs = None

##############################################
# Object definitions.
##############################################
class SystemMemMgrError(Exception):
    pass

###############################################################################
# cmd_get_sport_mem
#
# The cmem field from hald_model output. This field corresponds to the memory usage limit 
# of sport that when reached, sport would no longer optimize data traffic.  
#
###############################################################################

def cmd_get_sport_mem(option, spec, model):
    # This is the minimum amount of memory needed by the box to run sport/mgmt.
    # This is the value specified in the memory tag of the specs.xml file
    print get_appliance_base_memory()

def get_total_mem():
    # The total memory installed on the system.
    if not exists (hwtool_path):
        print 'Hwtool does not exist on this box. Exiting...'
        exit(1)

    cmd = '%s -q memory=size' % hwtool_path
    total_mem = run_shell_cmd(cmd, True)
    return int(total_mem)

###############################################################################
# cmd_get_total_mem
#
# Get total system memory as specified in specs.xml
#
###############################################################################

def cmd_get_total_mem(option, spec, model):
    total_mem = get_total_mem()
    print total_mem

###############################################################################
# cmd_get_overhead_mem
#
# Get WS8 overhead memory as specified for BOBv1
#
###############################################################################
def cmd_get_overhead_mem(option, spec, model):
    print int(get_esxivm_mem(spec) - get_vsp_memory(spec) + 1800)


###############################################################################
# cmd_get_esxivmws8_mem
#
# Get total system memory for WS8 + ESXi + VM in BOBv2
#
###############################################################################
def cmd_get_esxivmws8_mem(option, spec, model):
    print get_esxivm_mem(spec) + 1800


###############################################################################
# cmd_get_esxivm_mem
#
# Amount of memory that the BOBv2 ESXi stack will see
#
###############################################################################
def cmd_get_esxivm_mem(option, spec, model):
    print get_esxivm_mem(spec)


###############################################################################
# get_esxivm_mem
#
# Calculate the memory that will be given to ESXi BOBv2 based on VSP memory
#
###############################################################################
def get_esxivm_mem(spec):
    vsp_mem = get_vsp_memory(spec)
    return int(round(float(vsp_mem + 1908) / 0.956))


###############################################################################
# cmd_get_rsp_mem
#
# Amount of memory available for VSP VM's
#
###############################################################################

def cmd_get_rsp_mem(option, spec, model):
    rsp_mem = get_vsp_memory(spec)
    if rsp_mem > 0:
	print rsp_mem
    else:
	print 0


###############################################################################
# get_vsp_memory
#
# Caluculate the amount of memory available for VSP
#
###############################################################################
def get_vsp_memory(spec):
    # Get the default value for VSP
    # this is the minimum value for VSP VM's to be enabled on the box 
    (vsp_min, total_min) = (0, 0)
    min_val = spec.get_vsp_default()
    if min_val:
        (vsp_min, total_min) = min_val.split(',')
        vsp_min   = int(vsp_min)
        total_min = int(total_min)

    # Get the addon value for VSP
    # This is the maximum value we know about from PM specs
    (vsp_max, total_max) =  (0, 0)
    max_val = spec.get_vsp_addon()
    if max_val:
        (vsp_max, total_max) = max_val.split(',')
        vsp_max   = int(vsp_max)
        total_max = int(total_max)

    # Get the total memory installed on the system
    total_sys_mem = get_total_mem()

    if total_sys_mem == total_max:
        # Check to see if the total available memory in the system
        # is equal to the 'total_max' from specs, if so vsp memory available is
        # vsp_max. ADDON kit was added
        rsp_mem = vsp_max
    elif total_sys_mem == total_min:
        # Check to see if the total available memory in the system
        # is equal to the 'total_min' from specs, if so vsp memory available is
        # vsp_min. NO ADDON KIT in the system
        rsp_mem = vsp_min
    elif total_sys_mem < total_min:
        # If this is the case then there isn't enough memory in the system
        # to run vsp, set value to 0
        rsp_mem = 0
    elif total_sys_mem > total_max:
        # If the system has more memory than what the spec max expects
        #                 OR
        # If the customer added partial DIMM's from the addon kit
        # Here we will calculate the VSP memory
        # formula is ...
        # [((total - sport - edge - SAFETY) - 1800) * 0.956] - 1908
        # SAFETY = 500, its 500MB to give room to other processes
        rsp_mem = ((total_sys_mem - int(get_appliance_base_memory()) - get_edge_mem(spec) \
                  - 500 - 1800) * 0.956) - 1908

    return int(rsp_mem)


def parse_edge_mem_rule(spec, memory_rule):
    # Now parse the memory rule to see if granite mem size is 0 or should be fetched from mfdb
    # In specs.xml, Memory rule is of the form edge_mem_size="integer" where integer is the minimum
    # total system memory needed for edge/granite to be enabled on this appliance.

    if get_total_mem() < int(memory_rule):
	return False
    else:
	return True

def get_edge_mem(spec):
    if get_appliance_uses_granite() == 'true':
        # Granite *can* run on this model.
        # Check the memory rule, compare it to the minimum system mem, as specified in specs.xml
        # to compute memory used by edge

        memory_rule = spec.get_edge_mem_size()
        if memory_rule != '':
	    # There exists a memory rule. Parse this memory rule and compare it with total system memory
            if parse_edge_mem_rule(spec, memory_rule) == False:
                # Total system Memory not sufficient for edge
	        return 0
            else:
                # Total system mem sufficient to support edge. Get edge mem value from mfdb
                edge_mem_node = '/rbt/mfd/edge_totalmem_mb'
                edge_mem = get_mfdb_val(edge_mem_node)
	        if edge_mem != '':
	            return int(edge_mem)
   	        else:
		    print 'MFDB returned null for edge mem. Exiting...'
		    exit(1)
        else:
	    # No memory rule for this model in specs.xml. Assuming that Granite is ON by default
	    # Return edge mem value from mfdb
	    edge_mem_node = '/rbt/mfd/edge_totalmem_mb'
            edge_mem = get_mfdb_val(edge_mem_node)
            return int(edge_mem)
    else:
	# Granite is disabled on this model
	return 0

###############################################################################
# cmd_get_edge_mem
#
# Amount of memory available for edge/granite. Depends on if the model supports granite
# If the model does, then the amount of edge memory depends on the memory rule specified 
# in specs.xml. This memory rule is a function of total system memory.
#
###############################################################################

def cmd_get_edge_mem(option, spec, model):
    if get_appliance_uses_granite() == 'true':
	edge_mem = get_edge_mem(spec)
	print edge_mem
    else:
	print 'Edge/Granite is not supported on this model [%s]' % model

###############################################################################
# cmd_get_excess_mem
#
# Legacy value, all memory not used by sport/mgmt
#
###############################################################################

def cmd_get_excess_mem(option, spec, model):
    print get_total_mem()-spec.get_memory_size()

###############################################################################
# List of command handlers indexed by optparse option string.
#
# When adding new command line options that result in an action,
# add a new handler here.
#
# optparse appends each argument together with a /.  So a command
# with a short option -s and a long option -- status gets '-s/--status'
# as the key
#
###############################################################################
cmd_handlers = { '--total-memory'     : cmd_get_total_mem,
                 '--rsp-memory'       : cmd_get_rsp_mem,
                 '--edge-memory'      : cmd_get_edge_mem,
		 '--sport-memory'     : cmd_get_sport_mem,
		 '--esxivm-memory'    : cmd_get_esxivm_mem,
		 '--overhead-memory'  : cmd_get_overhead_mem,
		 '--vmesxiws8-memory' : cmd_get_esxivmws8_mem,
                 '--excess-memory'    : cmd_get_excess_mem}

def sys_mem_mgr_cmd_callback(option, opt_str, value, parser, *args, **kwargs):
    setattr(parser.values, 'command', option)

def setup_parser():
    global cmd_handlers, specs
    parser = OptionParser()

    # command line option flags
    #
    parser.add_option ("--total-memory",  action="callback", callback=sys_mem_mgr_cmd_callback,
                        dest="total_memory", default=False, help="List total memory installed on the system")
    parser.add_option ("--rsp-memory",  action="callback", callback=sys_mem_mgr_cmd_callback,
                        dest="rsp_memory", default=False, help="Memory left over [if any] for RSP packages")
    parser.add_option ("--edge-memory",  action="callback", callback=sys_mem_mgr_cmd_callback,
                        dest="edge_memory", default=False, help="Memory assigned [if any] for edge")
    parser.add_option ("--excess-memory",  action="callback", callback=sys_mem_mgr_cmd_callback,
                        dest="excess_memory", default=False, help="Legacy value, all memory not used by sport/mgmt")
    parser.add_option ("--esxivm-memory",  action="callback", callback=sys_mem_mgr_cmd_callback,
                        dest="esxivm-memory", default=False, help="Amount of memory needed for ESXi/WS8 + VM's")
    parser.add_option ("--overhead-memory",  action="callback", callback=sys_mem_mgr_cmd_callback,
                        dest="overhead-memory", default=False, help="Amount of memory overhead for WS8 + ESXi")
    parser.add_option ("--vmesxiws8-memory",  action="callback", callback=sys_mem_mgr_cmd_callback,
                        dest="vmesxiws8-memory", default=False, help="Amount of memory overhead for WS8 + ESXi + VM in BOBv2")
    parser.add_option ("--sport-memory",  action="callback", callback=sys_mem_mgr_cmd_callback,
                        dest="sport_memory", default=False, help="Amount of memory needed by sport and mgmt. This is the value specified in specs.xml")

    (options, args) = parser.parse_args()

    try:
        os.stat(spec_file)
    except OSError:
        raise SystemMemMgrError("spec file missing.")

    if specs == None:
        spec_xml = parse(spec_file)
        disk_layouts = DiskLayoutMap(spec_xml)
        storage_map = parse_storage_configs(spec_xml, disk_layouts)
        specs = SpecMap(disk_layouts, spec_xml, storage_map)

    # check if the model was passed on the cmdline, if not fetch it from
    # the mfdb
    #
    model = get_model()
    if not model:
        print "Could not determine model, exiting"
        exit(1)

    spec = None
    try:
        spec = specs.get_spec_by_name(model)
    except rrdm_error:
        rlog_debug ('Specification not found for model %s' % model)

    cmd='%s' % options.command
    try:
        cmd_handlers[cmd](options, spec, model)
    except KeyError:
        print 'No command handler registered for cmd %s' % cmd
        exit (1)

def main():
    setup_parser ()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        sys.exit(0)

 
