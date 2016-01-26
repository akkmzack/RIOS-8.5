#!/usr/bin/env python

from sys import argv, exit
from os import popen, stat
from stat import S_ISCHR
from os.path import exists
from time import sleep
from fcntl import ioctl
from struct import unpack
from xml.dom import minidom
import xml
import re

#CONSTANTS

#found in jabil_led.c
JABIL_READ = 0x0
JABIL_WRITE = 0x1

class EntityType:
    def __init__(self):
        self.members = {}

class Entity:
    def __init__(self, methods):
        self.methods = methods

class Method:
    def __init__(self, xml_node):
        self.name = xml_node.getAttribute('name')
        self.type = xml_node.getAttribute('type')
        self.writes = make_boolean(xml_node.getAttribute('writes'))
        self.reads = make_boolean(xml_node.getAttribute('reads'))
        if self.reads == None:
            self.reads = True

class Jabil(Method):
    device = '/dev/jabil_led'
    def __init__(self, xml_node):
        temp = xml_node.getAttribute('turn_system_led_off')
        if temp == '':
            self.turn_system_led_off = False
        else:
            self.turn_system_led_off = make_boolean(temp)
        self.cmd = int(xml_node.getAttribute('cmd'),16)
        self.read_type = xml_node.getAttribute('read-type')
        self.read_state = xml_node.getAttribute('read-state')
    
    def turn_off_system_led(self):
        # The system LED is really a bunch of LEDs, one for each color.
        # Only one can be on at a time, but the only way to set the system
        # LED to off is to specifically turn off the LED that is on.  This
        # method just turns them all off.
        self.ioctl_write(0x2000)
        self.ioctl_write(0x2001)
        self.ioctl_write(0x2002)
        self.ioctl_write(0x2004)
    
    def ioctl_write(self, opcode):
        write_code = 0x1 # found in jabil_led.c as JABIL_WRITE
        try:
            if exists(self.device) and S_ISCHR(stat(self.device).st_mode):
                fd = open(self.device, 'w')
                foo = ioctl(fd, write_code, opcode)
                fd.close()
        except IOError:
            print 'ERROR: ioctl error when writing to "%s".' % self.device
    
    def ioctl_read(self):
        read_code = 0x0 # found in jabil_led.c as JABIL_READ
        string = "    "
        try:
            if exists(self.device) and S_ISCHR(stat(self.device).st_mode):
                fd = open(self.device, 'r')
                foo = ioctl(fd, read_code, string)
                fd.close()
            else:
                foo = 0
            return foo
        except IOError:
            print 'ERROR: ioctl error when reading from "%s".' % self.device
    
    def do(self):
        if self.turn_system_led_off:
            self.turn_off_system_led()
        self.ioctl_write(self.cmd)
    
    def state(self):
        tuple_state = unpack('cccc', self.ioctl_read())[::-1]
        
        num_state = 0
        for i in range(4):
            num_state += long(ord(tuple_state[i])) << i * 8
        
        c = to_binary_fixed_length(num_state, bitcount=32)
        if self.read_type == 'led':
            c = c[:16]
        else:
            c = c[16:]
        
        return binary_equality_extended(c, self.read_state)

class IpmiSdr(Method):
    command = 'ipmitool sdr'
    output = None
    cols = {0 : (0, 17),
            1 : (18, 37),
            2 : (38, 41)}
    
    def __init__(self, xml_node):
        Method.__init__(self, xml_node)
        self.string = xml_node.getAttribute('string')
        self.to_get = xml_node.getAttribute('to_get')
    
    def do(self):
        if not self.writes:
            return None
        return None
    
    def state(self):
        if not self.reads:
            return None
        if not IpmiSdr.output:
            IpmiSdr.output = popen(IpmiSdr.command).read().split("\n")
        
        for line in IpmiSdr.output:
            if line[IpmiSdr.cols[0][0]:IpmiSdr.cols[0][1]].strip() == self.string:
                if self.to_get == 'value':
                    return line[IpmiSdr.cols[1][0]:IpmiSdr.cols[1][1]].strip()
                elif self.to_get == 'status':
                    return make_boolean(line[IpmiSdr.cols[2][0]:IpmiSdr.cols[2][1]].strip())
        return None

class IpmiOem(Method):
    command = 'ipmitool raw 0x3e'
    
    def __init__(self, xml_node):
        Method.__init__(self, xml_node)
        
        write_opcode = xml_node.getAttribute('write_opcode')
        if write_opcode:
            write_opcode = write_opcode + ' ' + hex(flip(int(write_opcode, 16),
                                                         range(8)))
        else:
            write_opcode = '0x80 0x7f'
        read_opcode = xml_node.getAttribute('read_opcode')
        if read_opcode:
            read_opcode = read_opcode + ' ' + hex(flip(int(read_opcode, 16),
                                                         range(8)))
        else:
            read_opcode = '0x0 0xff'
        
        cmd = xml_node.getAttribute('cmd')
        indicator0 = xml_node.getAttribute('indicator0')
        self.state0 = xml_node.getAttribute('state0')
        indicator1 = xml_node.getAttribute('indicator1')
        self.state1 = xml_node.getAttribute('state1')
        
        self.do_command = "%s %s %s" % (self.command, cmd, write_opcode)
        self.state_command = "%s %s %s" % (self.command, cmd, read_opcode)
        
        indicator0 = ready_byte(0, indicator0)
        self.state_command = "%s %s" % (self.state_command, indicator0)
        self.do_command = "%s %s %s" % (self.do_command, indicator0, ready_byte(0, self.state0))
        if indicator1 != '':
            indicator1 = ready_byte(0, indicator1)
            self.state_command = "%s %s" % (self.state_command, indicator1)
            self.do_command = "%s %s %s" % (self.do_command, indicator1, ready_byte(0, self.state1))
        
    def do(self):
        if not self.writes:
            return None
        popen(self.do_command + " >/dev/null 2>&1")
    
    def state(self):
        if not self.reads:
            return None
        state = popen(self.state_command + " 2>/dev/null").readline()[:-1].strip().split(' ')
        if state == '':
            print "Could not talk to i2c device."
            exit(1)
        if len(state) == 1:
            return binary_equality_extended(to_binary_fixed_length(int(state[0], 16)),
                                        self.state0)
        elif len(state) == 2:
            return binary_equality_extended(to_binary_fixed_length(int(state[0], 16)), self.state0) and \
                   binary_equality_extended(to_binary_fixed_length(int(state[1], 16)), self.state1)
        else:
            return None


class Redfin(Method):
    command = '/opt/tms/bin/redfin_led_ctl'

    def __init__(self, xml_node):
        Method.__init__(self, xml_node)

        self.cmd      = xml_node.getAttribute('cmd')
        non_decimal = re.compile(r'[^\d]+')
        self.mtype    = non_decimal.sub('', xml_node.getAttribute('mtype'))
        self.stateval = xml_node.getAttribute('state')
        self.slot     = xml_node.getAttribute('slot')
        self.led_state_command = "%s -s %s %s" % \
                             (self.command, self.mtype, self.slot)
        self.power_state_command = "%s -z %s %s" % \
                             (self.command, self.mtype, self.slot)

    def do(self):
        if not self.writes:
            return None

        self.do_command = "%s %s %s %s %s" %\
                          (self.command, self.cmd, self.mtype,
                           self.slot, self.stateval)
        popen(self.do_command + " >/dev/null 2>&1")

    def state(self):
        if not self.reads:
            return None

        if self.cmd == '-p':
            state = popen(self.power_state_command + " 2>/dev/null").readline()[:-1].strip()
        else:
            state = popen(self.led_state_command + " 2>/dev/null").readline()[:-1].strip()

        if state == '':
            print "Could not talk to i2c device."
            exit(1)

        if state == '1':
            # Revert the state for the inverted fault_led_off query
            # In Redfins we cannot query states as ON/OFF differently
            if self.name in ['fault_led_off', 'power_off']:
                return True
            else:
                return False
        else:
            # Revert the state for the inverted fault_led_off query
            # In Redfins we cannot query states as ON/OFF differently
            if self.name in  ['fault_led_off', 'power_off']:
                return False
            else:
                return True


class Guppy(Method):
    i2cset = "/usr/sbin/i2cset -y 0"
    i2cget = "/usr/sbin/i2cget -y 0"
    sensors = "/usr/bin/sensors"

    def __init__(self, xml_node):
        Method.__init__(self, xml_node)

        self.devaddr  = xml_node.getAttribute('devaddr')
        self.regbank  = xml_node.getAttribute('regbank')
        self.regaddr  = xml_node.getAttribute('regaddr')
        self.regaddr2 = xml_node.getAttribute('regaddr2')
        self.pattern  = xml_node.getAttribute('pattern')

    def do(self):
        if not self.writes:
            return None

        # LED write
        if self.devaddr == '0x23':
            self.read_cmd = "%s %s %s 2>/dev/null" %\
                            (self.i2cget, self.devaddr, self.regaddr)
            state = popen(self.read_cmd).readline()[:-1].strip()
            check_i2c_return(state)

            value = int(state, 16)
            new_v = ready_byte(value, self.pattern)
            self.write_cmd = "%s %s %s %s >/dev/null 2>&1" %\
                             (self.i2cset, self.devaddr, self.regaddr, new_v)
            popen(self.write_cmd)

    def state(self):
        if not self.reads:
            return None

        # LED read
        if self.devaddr == '0x23':
            self.read_cmd = "%s %s %s 2>/dev/null" %\
                            (self.i2cget, self.devaddr, self.regaddr)
            state = popen(self.read_cmd).readline()[:-1].strip()
            check_i2c_return(state)

            value = bin(int(state, 16))[2:].zfill(8)
            return binary_equality_extended(value, self.pattern)

        # Nuvoton read
        elif self.devaddr == '0x2D':
            self.read_cmd = "%s | grep %s | awk '{print $%s}' 2>/dev/null" %\
                            (self.sensors, self.regaddr, self.regbank)
            state = popen(self.read_cmd).readline()[:-1].strip()
            value = int(state)
            return value

class Yellowtail(Method):
    command = '/opt/tms/bin/yt_led_ctl'

    def __init__(self, xml_node):
        Method.__init__(self, xml_node)

        self.cmd = xml_node.getAttribute('cmd')
        non_decimal = re.compile(r'[^\d]+')
        self.mtype = non_decimal.sub('', xml_node.getAttribute('mtype'))
        self.stateval = xml_node.getAttribute('state')
        self.slot = xml_node.getAttribute('slot')
        self.led_state_command = "%s -s %s %s" % \
                             (self.command, self.mtype, self.slot)
        self.power_state_command = "%s -z %s %s" % \
                             (self.command, self.mtype, self.slot)
        self.system_led_state_command = "%s -t" % \
                             (self.command)

    def do(self):
        if not self.writes:
            return None

	
        self.do_command = "%s %s %s %s %s" %\
                          (self.command, self.cmd, self.mtype,
                           self.slot, self.stateval)
        popen(self.do_command + " >/dev/null 2>&1")

    def state(self):
        if not self.reads:
            return None

        if self.cmd == '-p':
            state = popen(self.power_state_command + " 2>/dev/null").readline()[:-1].strip()
        elif self.cmd == '-l':
            state = popen(self.led_state_command + " 2>/dev/null").readline()[:-1].strip()
        elif self.cmd == '-u':
            state = popen(self.system_led_state_command + " 2>/dev/null").readline()[:-1].strip()
            if state == '0':
                return self.name == 'degraded'
            elif state == '1':
                return self.name == 'normal'
            elif state == '2':
                return self.name == 'critical'
            else:
                print "Unknown LED state"
                exit(1)

        if state == '':
            print "Could not talk to i2c device."
            exit(1)

        if state == '1':
            if self.name in ['fault_led_off', 'power_off']:
                return True
            else:
                return False
        else:
            if self.name in  ['fault_led_off', 'power_off']:
                return False
            else:
                return True

class IpmiOemGar(Method):
    command = 'ipmitool raw 0x6 0x52 0x7'

    def __init__(self, xml_node):
        Method.__init__(self, xml_node)

        self.write_opcode = '0x0 0x1'

        self.read_opcode = xml_node.getAttribute('read_opcode')
        self.cmd = xml_node.getAttribute('cmd')
        self._state = xml_node.getAttribute('state')

        self.state_command = "%s %s %s" %\
                             (self.command, self.cmd, self.read_opcode)

    def do(self):
        if not self.writes:
            return None
        self.do_command = "%s %s %s" %\
                          (self.command, self.cmd, self.write_opcode)
        current_state = int(popen(self.state_command +\
                                  " 2>/dev/null").readline()[:-1].strip(),
                            16)
        self.do_command = "%s %s" % (self.do_command,
                                     ready_byte(current_state, self._state))
        popen(self.do_command + " >/dev/null 2>&1")

    def state(self):
        if not self.reads:
            return None
        state = popen(self.state_command + " 2>/dev/null").readline()[:-1].strip()
        if state == '':
            print "Could not talk to i2c device."
            exit(1)
        return binary_equality_extended(to_binary_fixed_length(int(state, 16)),
                                        self._state)

class IpmiRaw(Method):
    def __init__(self, xml_node):
        Method.__init__(self, xml_node)
        self.addr = xml_node.getAttribute('addr')
        self.comm = xml_node.getAttribute('comm')
    
    def do(self):
        "Decodes method's command, changing addr byte it in the process."
        if not self.writes:
            return None
        curr = read_byte(self.addr)
        pos = 0
        for c in reverse_string(self.comm):
            if c == '1':
                curr = turn_on(curr, pos)
            elif c == '0':
                curr = turn_off(curr, pos)
            elif c == 'f':
                curr = flip(curr, pos)
            pos += 1
        write_byte(self.addr, curr)
    
    def state(self):
        "Returns whether or not method is 'on'."
        if not self.reads:
            return None
        return binary_equality_extended(to_binary_fixed_length(read_byte(self.addr)),
                                        self.comm)

class Ioctl(Method):
    def __init__(self, xml_node):
        self.ival = xml_node.getAttribute('ival')
        self.dev = xml_node.getAttribute('dev')
        self.wdioc = xml_node.getAttribute('wdioc')
        self.write = make_boolean(xml_node.getAttribute('write'))
        self.flush = make_boolean(xml_node.getAttribute('flush'))
    
    def do(self):
        # TODO: Figure out if Evan's wdt_disable needs to do ipmi stuff.
        # TODO: Figure out if wdt_enable and wdt_disable can be closer.
        if not self.writes:
            return None
        fd = open(dev, 'w')
        foo = ioctl(fd, wdioc, struct.pack('I',ival))
        if self.write:
            fd.write('V')
        if self.flush:
            fd.flush()
        fd.close()
    
    def state(self):
        if not self.reads:
            return None
        return None

# GLOBALS and CONSTANTS

ipmi_cmd = '/sbin/ipmitool raw 0x6 0x52 0x7 '
cli = '/opt/tms/bin/cli '
hwtool = '/opt/hal/bin/hwtool.py '
config = 'hw_ctl.xml'
config_loc = '/opt/hal/bin/hw_ctl.xml'

entities = {}
to_write = {}
only_read = {}

method_classes = { 'ipmi-raw' : IpmiRaw,
                   'ipmi-sdr' : IpmiSdr,
                   'ipmi-oem' : IpmiOem,
                   'ipmi-oem-gar' : IpmiOemGar,
                   'classic-redfin' : Redfin,
                   'yellowtail' : Yellowtail,
                   'guppy' : Guppy,
                   'jabil' : Jabil}

class MotherboardNotPresentError(Exception):
    def __init__(self, name):
        self.name = name
    
    def __str__(self):
        return self.name

def populate_entities(config):
    "Reads the config.xml file, fleshing out the entities found within."
    motherboard_name = get_mobo()
    # By default getAttribute will return an empty string if the elment isn't present
    mobo_type        = get_mobo_type()

    try:
        xml_file = minidom.parse(config)
        motherboards = xml_file.getElementsByTagName('motherboard')
        motherboard = None
        for mobo in motherboards:
            if mobo.getAttribute('name') == motherboard_name:
                if motherboard_name == '425-00205-01':
                    if mobo_type == mobo.getAttribute('mtype'):
                        motherboard = mobo
                        break
                else:
                    motherboard = mobo
                    break
        if not motherboard:
            raise MotherboardNotPresentError, motherboard_name
        for type in motherboard.getElementsByTagName('type'):
            for entity in type.getElementsByTagName('entity'):
                add_entity(type.getAttribute('name'), entity)
    except xml.parsers.expat.ExpatError, e:
        print "ERROR: %s is malformed at line %s column %s with code %s." %\
              (config, e.lineno, e.offset, e.code)
    except MotherboardNotPresentError, e:
        print "ERROR: Motherboard %s is not present in %s." % (e, config)
    # Occurs in add_entity when an entity type does not exist.
    except KeyError:
        print "ERROR: %s is malformed in that expected elements or attributes are not present." % config
    
def add_entity(type_name, entity):
    "Adds ipmi entities from xml entities."
    ensure_entity_type(type_name)
    methods = {}
    for method in entity.getElementsByTagName('method'):
        name = method.getAttribute('name')
        type = method.getAttribute('type')
        methods[name] = method_classes[type](method)
    entities[type_name].members[entity.getAttribute('name')] = Entity(methods)

def ensure_entity_type(name):
    "Makes sure that EntityType exists and makes it if it does not."
    if not name in entities:
        entities[name] = EntityType()

def write_byte(addr, byte):
    if addr in only_read:
        del only_read[addr]
    to_write[addr] = byte

def read_byte(addr):
    """If command has been read before, use that.  Else, read from device.
    This ensures that, at the end, all writes to a byte occur at once."""
    global only_read
    
    if addr in to_write:
        return to_write[addr]
    elif addr in only_read:
        return only_read[addr]
    else:
        return get_curr(addr)

def get_bit(byte, loc):
    "Returns bit at location in byte."
    if (byte & turn_on(0x0, loc)) == 0x0:
        return 0
    else:
        return 1

def turn_on(orig, nums):
    "Sets, to 1, single bits in orig at positions in nums."
    nums = ensure_listness(nums)
    return reduce(lambda x,y: x | (0x01 << y), nums, orig)

def turn_off(orig, nums):
    "Sets, to 0, single bits in orig at positions in nums."
    nums = ensure_listness(nums)
    return orig & (orig ^ turn_on(0x00, nums))

def flip(orig, nums):
    "Flips single bits in orig at positions in nums."
    nums = ensure_listness(nums)
    for num in nums:
        orig = ~(~orig ^ turn_on(0x0, num))
    return orig

#def set_default(val):
#    # TODO: Ask Evan what he was doing, exactly.
#    #       This code /should/ equal to Evan's for curr >= 0xf8.
#    #       
#    rest = get_curr(0x30)
#    curr = get_curr(0x32)
#    
#    if val == 'disc':
#        set_val(turn_off(curr, [4,5]), 0x32)
#        set_val(turn_off(curr, 6), 0x32)
#        set_val(turn_on(curr, 6), 0x32)
#        curr = get_curr(0x32)
#        set_val(turn_off(curr, [4,5]), 0x30)
#        set_val(rest, 0x30)
#    elif val == 'bypass':
#        set_val(turn_on(curr, range(7)), 0x32)
#        set_val(turn_off(curr, 6), 0x32)
#        set_val(turn_on(curr, 6), 0x32)
#        curr = get_curr(0x32)
#        set_val(0xff, 0x30)
#        set_val(rest, 0x30)
#    else:
#        raise Exception('unknown default state')

def get_curr(reg):
    "Returns byte at register."
    curr = popen("%s %s 0x1 0x0 2> /dev/null" % (ipmi_cmd, reg)).readline()[:-1]
    if curr == '':
        print "Could not talk to i2c device."
        exit(1)
    return int(curr.strip(), 16)

def set_val(new, reg):
    "Sets byte at register."
    popen("%s %s 0x0 0x1 %s 2> /dev/null" % (ipmi_cmd, reg, hex(new)))

def print_state(type, name, method, state):
    "Properly formats printing an entity's method's 'on' state."
    if state == None:
        state = 'Unknowable'
    print "%s(%s).%s = %s" % (name, type, method, str(state))

def print_usage():
    print "%s command arguments" % argv[0]
    print """\
    -w type entity method
        do method
    -bb register [bit state]
        bit is 0-7
        state is on|off
    -r type entity method
        get method's 'on' status
    -R type entity
        same as -r only all methods
    -RR type
        same as -R only all entities
        no guaranteee of ordering
    -Rr type method
        same as -RR, but only specified method
    -c
        commit writes
        occurs automatically at end
    -t seconds
        commits then waits
        calls python's time.sleep(), so might not be thread-safe
    -f filename
        treat contents of file as args
        no protection against infinite recursion
    -h
        prints this message"""

def main():
    if len(argv) == 1:
        print_usage()
    else:
	config_path = config;
	if exists (config_path) == False:
	    config_path = config_loc
	    if exists (config_path) == False:
		print 'Unable to find configuration file'
		exit(1)

        populate_entities(config_path)
        process(argv[1:])
        commit_writes()

def process(args):
    "Calls functions based on args, as seen in print_usage()."
    try:
        pos = 0
        args_len = len(args)
        while pos < args_len:
            if args[pos] == '-w': # do method aka write
                type = args[pos+1]
                entity_name = args[pos+2]
                method_name = args[pos+3]
                try:
                    entities[type].members[entity_name].methods[method_name].do()
                except KeyError:
                    print "Bad input.  Check %s." % config
                pos += 3
            elif args[pos] == '-bb': # bit_bash
                register = args[pos+1]
                changes = []
                valid_bit_places = map(lambda x:str(x), range(8))
                valid_bit_states = ['on', 'off', 'flip']
                while True:
                    if pos+3 >= args_len:
                        break
                    if args[pos+2] in valid_bit_places and args[pos+3] in valid_bit_states:
                        changes.append((args[pos+2], args[pos+3]))
                        pos += 2
                    else:
                        break
                bit_bash(register, changes)
                pos += 1
            elif args[pos] == '-r': # get method's state
                type = args[pos+1]
                entity_name = args[pos+2]
                method_name = args[pos+3]
                try:
                    state = entities[type].members[entity_name].methods[method_name].state()
                    print_state(type, entity_name, method_name, state)
                except KeyError:
                    print "Bad input.  Check %s." % config
                pos += 3
            elif args[pos] == '-R': # get methods' states
                type = args[pos+1]
                entity_name = args[pos+2]
                try:
                    for method_name,method in entities[type].members[entity_name].methods.iteritems():
                        print_state(type, entity_name, method_name, method.state())
                except KeyError:
                        print "Bad input.  Check %s." % config
                pos += 2
            elif args[pos] == '-RR': # get entities' methods' states
                type = args[pos+1]
                try:
                    for entity_name,entity in entities[type].members.iteritems():
                        for method_name,method in entity.methods.iteritems():
                            print_state(type, entity_name, method_name, method.state())
                except KeyError:
                    print "Bad input.  Check %s." % config
                pos += 1
            elif args[pos] == '-Rr':
                type = args[pos+1]
                method_name = args[pos+2]
                try:
                    for entity_name,entity in entities[type].members.iteritems():
                        state = entity.methods[method_name].state()
                        print_state(type, entity_name, method_name, state)
                except KeyError:
                    print "Bad input.  Check %s." % config
                pos += 2
            elif args[pos] == '-c': # commit writes
                commit_writes()
            elif args[pos] == '-t':
                commit_writes()
                sleep(int(args[pos+1]))
                pos += 1
            elif args[pos] == '-f': # use file
                use_file(args[pos+1])
                pos += 1
            elif args[pos] == '-h': # print help
                print_usage()
            else:
                print "Bad argument given."
                print_usage()
                break
            pos += 1
    except IndexError:
        print 'ERROR: Not enough arguments given.'
        print_usage()

def ready_byte(curr, string):
    """
* Alters the given integer 'curr' by manipulating its bits.
* The 'string' argument contains zero or more of '0', '1', and 'x'.
* For each 0 or 1, the corresponding bit in 'curr' is set thus.
* All x's (or indeed anything not a 0 or 1) are ignored.
Input: start byte (integer)
       string of 1's, 0's, and x's.
Output: string with hexadecimal representation of 'curr'."""
    pos = 0
    for c in reverse_string(string):
        if c == '1':
            curr = turn_on(curr, pos)
        elif c == '0':
            curr = turn_off(curr, pos)
        pos += 1
    return hex(curr)

def commit_writes():
    "Performs commands, with only one write per register."
    global to_write
    global only_read
    write = ' 0x0 0x1 '
    for key, value in to_write.iteritems():
        popen(ipmi_cmd + key + write + hex(value) + ' 2>/dev/null')
        only_read[key] = value
    to_write = {}

def bit_bash(reg, bashes):
    "Takes a list of bit locations and new states and applies them to register."
    curr = read_byte(reg)
    to_on = map(lambda x:int(x[0]),
                 filter(lambda x:x[1] == 'on', bashes))
    to_off = map(lambda x:int(x[0]),
                 filter(lambda x:x[1] == 'off', bashes))
    to_flip = map(lambda x:int(x[0]),
                 filter(lambda x:x[1] == 'flip', bashes))
    curr = turn_on(curr, to_on)
    curr = turn_off(curr, to_off)
    curr = flip(curr, to_flip)
    write_byte(reg, curr)

def use_file(filename):
    "Reads in a file as if it were arguments passed in the command-line."
    file = open(filename,'r')
    while True:
        line = file.readline().strip("\n").split(' ')
        if line == ['']:
            break
        process(line)

def make_boolean(string):
    if string.lower() in ['true', 't', 'ok', 'good', 'yes', 'y', '+', 'success', 'pass']:
        return True
    elif string.lower() in ['false', 'f', 'cr', 'bad', 'no', 'n', '-', 'failure', 'fail', 'error']:
        return False
    else:
        return None

def binary_equality_extended(current, ideal):
    "Checks if 2 strings containing [0,1,f,x] are equal."
    # NOTE: Treats f's and x's, which might be confusing.
    return reduce(lambda x,y: x and y,
                  map(lambda bit,comm: comm in ['x','f',bit],
                      current, ideal))

def to_binary_fixed_length(n, bitcount=8):
    "Converts number to binary string of certain length."
    return pad_string_left(to_binary(n), bitcount, pad='0')

def to_binary(n):
    "Converts non-negative integer to its binary string representation."
    # Taken from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/219300
    return n>0 and to_binary(n>>1).lstrip('0') + str(n&1) or '0'

def pad_string_left(str, min_len, pad=' '):
    if len(str) < min_len:
        for i in range(min_len - len(str)):
            str = pad + str
    return str

def reverse_string(string):
    "Reverses characters in string."
    # Python strings are immutable!
    new_string = ''
    array = []
    for c in string:
        array.append(c)
    array.reverse()
    for e in array:
        new_string += e
    return new_string

def get_mobo():
    output = popen(hwtool + ' -q motherboard').read().strip()
    if output == '':
        raise Exception, 'hwtool is not present'
    else:
        return output

def get_phy_mobo():
    return popen(hwtool + ' -q physical-mobo').read().strip()

def get_mobo_type():
    return popen(hwtool + ' -q mobo-type').read().strip()

def ensure_listness(maybe):
    "Simply turns atom into one-element list containing atom."
    if not type(maybe) == type([]):
        return [maybe]
    return maybe

def check_i2c_return(state):
    if state == '':
        print "Could not talk to i2c device."
        exit(1)

if __name__ == '__main__':
    main()
