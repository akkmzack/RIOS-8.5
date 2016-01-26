#!/usr/bin/python

from getopt import getopt, GetoptError
from sys import exit, argv
from xml.dom.minidom import parse
from string import lower
import errno
import subprocess

from hwtool_util import *
from appliance_util import get_appliance_model
from rrdm_config import *
from rrdm_util import *

hwtool    = "/opt/hal/bin/hwtool.py"
flexypy   = "/opt/hal/bin/flexpy"
mddbreq   = "/opt/tms/bin/mddbreq"
spec_file = "/opt/hal/lib/specs/specs.xml"
mdreq     = "/opt/tms/bin/mdreq"

#Granite license node
granite_license = "/rbt/eva/main/config/licensed"
rsp55_license   = "/rbt/rsp2/config/license/multi/licensed"

SPECS = None

SPECIAL_MODELS = {
    'EX560L': {'granite': 16384},
    'EX560M': {'granite': 16384},
    'EX560H': {'granite': 16384},
    'EX1160L': {'granite': 20480},
    'EX1160M': {'granite': 20480},
    'EX1160H': {'granite': 20480},
}


##############################################################
#run utils
def usage():
    print "Usage: ./hardware_check.py"


# This will parse the specs.xml file and fill up the SPECS global variable
def parse_spec_file():
    global SPECS

    # read in the spec file and pass its contents to create a layout map
    # and spec list from the config file.
    spec_xml = parse(spec_file)
    disk_layouts = DiskLayoutMap(spec_xml)
    storage_map = parse_storage_configs(spec_xml, disk_layouts)
    SPECS = SpecMap(disk_layouts, spec_xml, storage_map)


# This function is used to call hwtool with some query
# It will return the output of the call back to the caller
def hwtool_call(query):
    if not exists(hwtool):
        return None

    hw = run_shell_cmd ('%s -q %s' % (hwtool, query), True)
    output = hw.strip()

    return output

# This function will query the MFDB to get the storage profile associated with
# this box
def get_storage_profile():
    if not exists (mddbreq):
        # we can't get the model.
        return None

    if not exists('/config/mfg/mfdb'):
        return None

    # grab the model from hald_model
    pf = run_shell_cmd ('%s -v /config/mfg/mfdb query get - /rbt/mfd/resman/profile' % \
                mddbreq, True)

    profile  = pf.strip()
    if profile == '':
        return None

    return profile

def check_license_present(node):
    if not exists(mdreq):
        return False

    # grab the node value from the config DB
    value = run_shell_cmd ('%s -v query get - %s' % (mdreq, node), True)

    if value =='':
        return False

    if lower(value) == 'false':
        return False
    elif lower(value) == 'true':
        return True
    else:
        return 'Unknown'


# This function will check if the specs and hardware match, if not it will 
# print out the information about disparities
def check_if_hardware_meets_spec(model, spec, granlicensestate, rsp55licensestate):
    hw_mem_size = int(hwtool_call('memory=size'))
    print "INFO: Memory installed on the system [%s]" % hw_mem_size

    hw_cpu_cores = int(hwtool_call('cpu=cores'))
    print "INFO: CPU cores count on the system [%s]" % hw_cpu_cores

    hw_cpu_speed = int(hwtool_call('cpu=speed'))
    print "INFO: CPU speed count on the system [%s]" % hw_cpu_speed

    hw_disk_map = {}
    hw_disk_size = hwtool_call('disk=size')
    for line in hw_disk_size.split('\n'):
        (dname, dsize) = line.split(' ')
        if dname[0:4] != 'disk':
            # Skip all non hard disk/SSD lines
            continue

        hw_disk_map[dname] = int(dsize)
        print "INFO: System [%s] size [%s]" % (dname, dsize)

    sp_memory = int(spec.get_memory_size())
    print "INFO: Spec Memory [%s]" % sp_memory

    sp_cpu_cores = int(spec.get_cores())
    print "INFO: Spec CPU cores [%s]" % sp_cpu_cores

    sp_cpu_speed = int(spec.get_core_speed())
    print "INFO: Spec CPU speed [%s]" % sp_cpu_speed

    sp_disk_map = {}
    # Get the disk information from specs
    for i in spec.get_disk_members():
        sp_disk_map['disk%s' % i] = int(spec.get_disk_size_by_id(i))
        print "INFO: Spec [disk%s] size [%s]" % (i, spec.get_disk_size_by_id(i))

    if rsp55licensestate:
        hw_mem_size = int(hw_mem_size) - 2048
        print "NOTICE: 2GB on system memory is reserved for RSP55 license, system memory now [%s]" % hw_mem_size

    # Check to make sure that the memory in the system is correct
    if hw_mem_size != sp_memory:
        if SPECIAL_MODELS.has_key(model):
            # If the granite license is present 
            if granlicensestate:
                sp_memory = SPECIAL_MODELS[model]['granite']

        if hw_mem_size > sp_memory:
            print "WARNING: There is [%s] of additional system memory, you may want to remove some DIMM's" % (hw_mem_size - sp_memory)
        else:
            print "ERROR: There is not enough memory in the system, you need [%s] addition memory for this model" % (sp_memory - hw_mem_size)

    print "INFO: The system memory and the spec memory values match"

    # Check to make sure there are enough cores in the system
    if hw_cpu_cores != sp_cpu_cores:
        if hw_cpu_cores > sp_cpu_cores:
            print "WARNING: There are [%s] additional cores in the system" % (hw_cpu_cores - sp_cpu_cores)
        else:
            print "ERROR: There are not enough cores in the system, you need [%s] additional cores for this model" % (sp_cpu_cores - hw_cpu_cores)

    print "INFO: The system CPU core count matches the spec values"

    # Check to make sure that the CPU speed is in the ball park figure
    if sp_cpu_speed < (hw_cpu_speed - (10 * hw_cpu_speed)/100):
        print "WARNING: The CPU seems to be clocking at a higher speed than the spec expects"

    if sp_cpu_speed > (hw_cpu_speed + (10 * hw_cpu_speed)/100):
        print "ERROR: The CPU seems to be clocking at a lower speed than the spec expects"

    print "INFO: The CPU speed matches the spec values"

    # Check to make sure the disk count matches
    if len(hw_disk_map) != len(sp_disk_map):
        if len(hw_disk_map) > len(sp_disk_map):
            print "WARNING: There seems to be additional drives in the system, expected drives [%s], currently has [%s]" % (len(sp_disk_map), len(hw_disk_map))
        else:
            print "ERROR: Not enough drives in the system, or a RAID mirror missing, expected drives [%s], currently has [%s]" % (len(sp_disk_map), len(hw_disk_map))

    print "INFO: The disk count in the system matches to what the spec expects"

    # Check to make sure all the disk sizes match
    for k in sp_disk_map.keys():
        if not hw_disk_map.has_key(k):
            print "ERROR: [%s] seems to be missing"

        if sp_disk_map[k] < (hw_disk_map[k] - (10 * hw_disk_map[k])/100):
            print "WARNING: The disk size for [%s] seems to be smaller than what the spec expects, expected [%s], current has [%s]" % (k, sp_disk_map[k], hw_disk_map[k])

        if sp_disk_map[k] > (hw_disk_map[k] + (10 * hw_disk_map[k])/100):
            print "ERROR: The disk size for [%s] seems to be bigger than what the spec expects, expected [%s], current has [%s]" % (k, sp_disk_map[k], hw_disk_map[k])

    print "INFO: The disk sizes in the system matches what the spec expects"


def main():
    # Get the appliance model name from teh MFDB
    model = get_appliance_model()
    print "INFO: Model name is [%s]" % model

    # parse the specs.xml to get the specs list
    parse_spec_file()

    # Get the spec object for this model from specs.xml
    curr_spec = SPECS.get_spec_by_name(model)

    # If the current spec is not present in specs.xml, we 
    # cannot help with this tool
    if not curr_spec:
        print "This tool is not supported on model [%s]" % model
        sys.exit(0)

    # Get the current storage profile this model is running
    # for pre xx55 and xx60 models we will get None
    sprof = get_storage_profile()
    if sprof != None:
        print "INFO: Current profile set to [%s]" % sprof
        # Set the profile view to associate it with the spec
        curr_spec.set_spec_profile_view(sprof)
    else:
        print "INFO: Model does not support profiles"
        

    granlicensestate    = check_license_present(granite_license)
    if granlicensestate:
        print "INFO: Granite license present on the system"
    else:
        print "INFO: Granite license not present on the system"

    rsp55licensestate   = check_license_present(rsp55_license)
    if rsp55licensestate:
        print "INFO: RSP55 license present on the system"
    else:
        print "INFO: RSP55 license not present on the system"

    check_if_hardware_meets_spec(model, curr_spec, granlicensestate, rsp55licensestate)


if __name__ == "__main__":
    main()
