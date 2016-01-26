#! /usr/bin/env python

# Copyright 2011 Riverbed Technology, Inc.
# All Rights Reserved. Confidential.


'''
This utility is used at virtual steelhead boot time to create a hierarchy of
small informational files based on the information from the Silicom ESX/ESXi
driver.  This is meant to look similar to /proc or /sys files.  Verification
is also performed on the information gathered, that only whole
control/slave bypass pairs have been mapped in, that any bypass pair
present has been Riverbed branded, and if a maximum bypass pair limit
is supplied, only that number of bypass pairs will be marked as
validated.

It creates these files by forking off simultaneous calls to the
vsh_bypass_ctrl binary on each supplied guest interface.  The
calls are made simultaneously so as not to slow down virtual steelhead
boot time on instances that don't have the Silicom driver installed.
(Where each instance will be going through the default 1 second timeout
waiting for a response to its probe.)

For illustration purposes, here's an example of what you'd see after
this is run on a virtual steelhead.  (The -> means "content of file is",
symlink-> means symlink to.)

/var/run/vsh_bypass/macs/00:0C:29:2C:8E:C0/type -> slave
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:C0/devnum -> 2
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:C0/esx_pci -> 0a:00.01
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:C0/esx_mac -> 00:0E:B6:86:5A:47
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:C0/esx_nic -> vmnic3
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:DE/type -> management
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:DE/driver_version -> 2.0.1.8
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:DE/device_count -> 4
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:B6/type -> control
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:B6/oem_data -> 23sdf24...
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:B6/slave -> 2
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:B6/devnum -> 1
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:B6/esx_pci -> 0a:00.00
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:B6/esx_mac -> 00:0E:B6:86:5A:46
/var/run/vsh_bypass/macs/00:0C:29:2C:8E:B6/esx_nic -> vmnic2
/var/run/vsh_bypass/validated/00:0C:29:2C:8E:B6 symlink-> /var/run/vsh_bypass/macs/00:0C:29:2C:8E:B6
/var/run/vsh_bypass/validated/00:0C:29:2C:8E:C0 symlink-> /var/run/vsh_bypass/macs/00:0C:29:2C:8E:C0
/var/run/vsh_bypass/macs/management symlink-> /var/run/vsh_bypass/macs/00:0C:29:2C:8E:DE

If a mac address doesn't appear in the macs directory, no response (or an
error) was received when running the control binary on that interface.

If a mac address doesn't appear in the validated directory, then that
bypass pair failed branding or went above the supplied bypass limit.

'''


import glob
import os
from optparse import OptionParser
import re
import shutil
import stat
import string
import subprocess
import sys
import tempfile


class BypassExc(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return 'vsh_bypass_init: ' + str(self.value)

class BypassDiscoveredInfo:
    def __init__(self):
        # info for each nic is put here, validation
        # comes once all are done
        self.raw_list = []
        self.raw_nics = dict()

        # The guest management interface
        self.mgmt_nic = None

        # control and slave interfaces
        self.by_mac = dict()  # by guest mac
        self.by_devnum = dict() # by bpvm reported device number

        # interfaces not connected to this guest
        self.unconnected = []

    def add_nic(self, nic):
        # If there's no 'type' field, assume that this
        # interface has no relevance to the bypass feature.
        # Will happen for primary, aux.
        if 'type' in nic:
            self.raw_list.append(nic)

    def no_nics(self):
        return len(self.raw_list) == 0

    def validate_iface_info(self, nic):
        if nic['type'] not in ('management', 'control', 'slave'):
            return False
        if nic['type'] == 'management':
            for i in ('driver_version','device_count'):
                if i not in nic:
                    return False
        if nic['type'] == 'control':
            for i in ('devnum','esx_nic','esx_mac','slave','oem_data'):
                if i not in nic:
                    return False
        if nic['type'] == 'slave':
            for i in ('devnum','esx_nic','esx_mac'):
                if i not in nic:
                    return False
        return True

    def basic_validate(self):
        for nic in self.raw_list:
            mac = nic['mac']
            name = nic['name']
            if mac in self.raw_nics:
                raise BypassExc('multiple interfaces discovered with the same guest mac %s, noticed while probing guest interface %s, verify ESX network config and driver version or contact support.' % (mac,name))
            elif not self.validate_iface_info(nic):
                raise BypassExc('Did not understand interface info data when probing guest nic %s mac %s, verify ESX driver version or contact support.' % (name, mac))
            else:
                self.raw_nics[mac] = nic

    def verify_management_maybe_rename(self, nameif):
        '''Find the management interface, rename it to bpvmX if asked.'''
        # Though its an error to have multiple management interfaces,
        # we want to be sure that we don't leave them named 'ethX'.
        # We only do this during pre_rename_init
        num = 0
        mgmts_found = []
        for (mac, nic) in self.raw_nics.iteritems():
            if nic['type'] == 'management':
                name = 'bpvm%d' % num
                num += 1
                if nameif:
                    rename_interface(nameif, mac, name)
                self.raw_nics[mac]['name'] = name
                mgmts_found.append(mac)
        if len(mgmts_found) == 0:
            raise BypassExc('the ESX bpvm interface is not connected to this guest, check ESX network config.')
        elif len(mgmts_found) == 1:
            mac = mgmts_found[0]
            self.mgmt_nic = self.raw_nics[mac]
            del self.raw_nics[mac]
        else:
            macstr = str([nic['mac'] for nic in mgmts_found])
            raise BypassExc('multiple guest interfaces are connected to the ESX bpvm interface, check ESX network config.  Guest interfaces with the following mac addresses are connected to the ESX bpvm interface: %s' % macstr)

    def prepare_guest_interfaces_info(self):
        '''Prep by_devnum and by_mac.'''
        for (mac, nic) in self.raw_nics.iteritems():
            if nic['devnum'] in self.by_devnum:
                dupl = self.by_devnum[nic['devnum']]
                raise BypassExc('multiple guest interfaces are mapped to the same hardware bypass interface; a hardware bypass interface must only have a single guest interface connected to it. Verify ESX network config. guest interface %s mac %s and interface %s mac %s both connect to ESX nic %s ESX mac %s' % (nic['name'], nic['mac'], dupl['name'], dupl['mac'], nic['esx_nic'], nic['esx_mac']))
            self.by_devnum[nic['devnum']] = nic
            # already verified mac uniqueness
            self.by_mac[nic['mac']] = nic

        if not self.by_mac:
            raise BypassExc('the ESX bpvm interface is connected, but no bypass interfaces are connected to this guest, check ESX network config.')

    def verify_branding(self, hwtool):
        for (mac, nic) in self.by_mac.iteritems():
            if nic['type'] == 'control':
                cmd = [hwtool,'-q','nic-valid-brand-string=%s' % nic['oem_data'] ]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                        shell=False, close_fds=True)
                (stdoutdata, stderrdata) = proc.communicate()
                if proc.returncode != 0:
                    raise BypassExc('verification method for branding failed, please contact support.')
                if stdoutdata.rstrip() != 'true':
                    raise BypassExc('unsupported non-Riverbed bypass interface ESX nic %s ESX mac %s connected to this guest (on guest interface %s mac %s ), hardware bypass functionality disabled.' % (nic['esx_nic'], nic['esx_mac'], nic['name'], nic['mac']))


    def read_unconnected_interfaces_info(self, topdir, bpctl):
        '''Get info on bypass interfaces that aren't attached to this guest.'''

        bpvm = self.mgmt_nic['name']
        devcount = int(self.mgmt_nic['device_count'])
        missing_devs = [ str(devn) for devn in range(1, devcount+1) 
                if str(devn) not in self.by_devnum ]

        if not missing_devs:
            return

        try:
            set_iface_up(bpvm)

            for dev in missing_devs:
                cmd = [bpctl, bpvm, '-d', dev, 'print_interface_info']

                proc = subprocess.Popen(cmd, close_fds=True, shell=False,
                                        stdout=subprocess.PIPE,
                                        stderr=open('/dev/null', 'w'))
                proc.wait()
                output = []
                for i in proc.stdout.readlines():
                    output.append(i.strip())

                if output:
                    nic = parse_iface_info(output)
                    if self.validate_iface_info(nic):
                        self.unconnected.append(nic)
                    else:
                        # if we don't understand the info back from the
                        # driver, just ignore it. We just use this info
                        # for logging purposes now, and this ensures
                        # that Silicom could make odd changes to their
                        # driver if they needed to, like introducing
                        # interfaces of type 'control_v2' or something.
                        pass
        finally:
            set_iface_down(bpvm)

        if not self.unconnected:
            return

        # For support/troubleshooting, record info
        # on the unconnected devices.
        udir = topdir + '/unconnected'
        if os.path.exists(udir):
            shutil.rmtree(udir)
        os.mkdir(udir)

        for nic in self.unconnected:
            nic_dir = udir + '/' + nic['devnum']
            record_iface_info(nic_dir, nic)

    def find_unconnected_control(self, slave_devnum):
        for nic in self.unconnected:
            if nic['type'] == 'control' and nic['slave'] == slave_devnum:
                return nic
        return None

    def find_unconnected_slave(self, slave_devnum):
        for nic in self.unconnected:
            if nic['type'] == 'slave' and nic['devnum'] == slave_devnum:
                return nic
        return None

    def missing_iface_string(self, nic, missing):
        if missing:
            return 'The guest interface %s mac %s is connected to ESX nic %s ESX mac %s . However, this guest does not have any interfaces connected to the other physical interface in the hardware bypass pair, which is ESX nic %s ESX mac %s .  Verify ESX network config and ensure that both of these ESX nics are connected to this guest.' % (nic['name'], nic['mac'], nic['esx_nic'], nic['esx_mac'], missing['esx_nic'], missing['esx_mac'])
        else:
            return 'The guest interface %s mac %s is connected to ESX nic %s ESX mac %s . However, this guest does not have any interfaces connected to the other physical interface in the hardware bypass pair, and an error occured while trying to determine which physical interface should be connected.  Verify ESX network config and ensure that both ESX nics in a hardware bypass pair are connected to this guest.' % (nic['name'], nic['mac'], nic['esx_nic'], nic['esx_mac'])

    def bad_pair_string(self, nic1, nic2):
        return 'hardware bypass pair consisting of ESX nic %s mac %s and ESX nic %s mac %s has been connected to mismatched guest interfaces %s mac %s and %s mac %s , which do not belong to the same inpath pair, check ESX network config.' % (nic1['esx_nic'], nic1['esx_mac'], nic2['esx_nic'], nic2['esx_mac'], nic1['name'], nic1['mac'], nic2['name'], nic2['mac'])

    def verify_pairs(self):
        '''Make sure that each lan/wan pair maps to a sane physical bypass pair.'''
        slave_macs = set([mac for mac in self.by_mac.keys() if self.by_mac[mac]['type'] == 'slave'])
        excstr = ''

        # make sure there are no control or slave orphans
        for (mac, nic) in self.by_mac.iteritems():
            if nic['type'] == 'control':
                if nic['slave'] not in self.by_devnum:
                    missing = self.find_unconnected_slave(nic['slave'])
                    excstr += self.missing_iface_string(nic, missing) + '\n'
                else:
                    slave_macs.remove(self.by_devnum[nic['slave']]['mac'])
        if slave_macs:
            for mac in slave_macs:
                nic = self.by_mac[mac]
                missing = self.find_unconnected_control(nic['devnum'])
                excstr += self.missing_iface_string(nic, missing) + '\n'
        if excstr:
            raise BypassExc(excstr)

        # make sure the inpath pairings make sense
        for (mac, nic) in self.by_mac.iteritems():
            if nic['type'] == 'control':
                snic = self.by_devnum[nic['slave']]
                c_name = nic['name']
                s_name = snic['name']
                c_xan = c_name[0:3]
                s_xan = s_name[0:3]
                c_slot_port = c_name[3:]
                s_slot_port = s_name[3:]
                if not ((c_xan == 'wan' or c_xan == 'lan') and 
                        (s_xan == 'wan' or s_xan == 'lan')):
                    raise BypassExc('unrecognized interface name pattern %s or %s , contact support.' % (c_name, s_name))
                if not ((c_xan == 'wan' and s_xan == 'lan') or
                        (c_xan == 'lan' and s_xan == 'wan')):
                    excstr += self.bad_pair_string(nic, snic) + '\n'
                    continue
                if c_slot_port != s_slot_port:
                    excstr += self.bad_pair_string(nic, snic) + '\n'
        if excstr:
            raise BypassExc(excstr)

    def lans_to_lowest_esx_mac(self, nameif):
        '''Ensure that all lan interfaces corresponds to lowest ESX mac to match physical steelhad behavior.'''
        # FIXME: bug#102499
        # this will give correct behavior for the 2 port and 4 port copper
        # cards that this feature is currently qualified with, but this will do
        # the wrong thing with 10gig cards.
        # must be run after verify_pairs ensures that we have sane lan/wan interfaces
        cmacs = [mac for mac in self.by_mac.keys() 
            if self.by_mac[mac]['type'] == 'control']

        for cmac in cmacs:
            nic1 = self.by_mac[cmac]
            nic2 = self.by_devnum[nic1['slave']]
            slot_port = nic1['name'][3:]
            if nic1['name'][0:3] == 'lan':
                old_lnic = nic1
                old_wnic = nic2
            else:
                old_lnic = nic2
                old_wnic = nic1

            if old_wnic['esx_mac'] < old_lnic['esx_mac']:
                rename_interface(nameif, old_wnic['mac'], 'bypasstemp')
                rename_interface(nameif, old_lnic['mac'], 'wan' + slot_port)
                rename_interface(nameif, old_wnic['mac'], 'lan' + slot_port)
                old_wnic['name'] = 'lan' + slot_port
                old_lnic['name'] = 'wan' + slot_port
                self.by_mac[old_wnic['mac']] = old_wnic
                self.by_mac[old_lnic['mac']] = old_lnic
                self.by_devnum[old_wnic['devnum']] = old_wnic
                self.by_devnum[old_lnic['devnum']] = old_lnic
                print >> sys.stderr, "vsh_bypass_init: NOTICE: guest interfaces in inpath%s (guest mac addresses %s and %s , connected to ESX nic %s ESX mac %s and ESX nic %s ESX mac %s ) had lan/wan mappings reversed and were swapped.  No administrative action is required, but to avoid this message in the future, shutdown this guest and then swap the ESX network connections for these two guest interfaces. " % (slot_port, nic1['mac'], nic2['mac'], nic1['esx_nic'], nic1['esx_mac'], nic2['esx_nic'], nic2['esx_mac'])

    def control_macs(self, limit):
        cmacs = [mac for mac in self.by_mac.keys() 
            if self.by_mac[mac]['type'] == 'control']

        if limit > 0:
            cdict = dict([(self.by_mac[mac]['esx_mac'],mac) for mac in cmacs])
            t = sorted(cdict.keys())

            allowed = [cdict[i] for i in t[:limit]]
            unallowed = [cdict[i] for i in t[limit:]]

            return (allowed, unallowed)

        return (cmacs, [])


def runcmd(argseq):
    proc = subprocess.Popen(argseq, close_fds=True, shell=False)
    proc.wait()
    return proc.returncode

def set_iface_up(ifname):
    runcmd(['/sbin/ifconfig', ifname, 'up'])

def set_iface_down(ifname):
    runcmd(['/sbin/ifconfig', ifname, 'down'])

def get_iface_mac(iface):
    mac= ''
    try:
        f = open('/sys/class/net/%s/address' % iface, 'r')
        _mac = f.read()
        mac = string.upper(_mac.strip())
        f.close()
    except EnvironmentError:
        pass
    return mac

def create_mac_to_iface_dict():
    idict = dict()
    for iface in os.listdir('/sys/class/net'):
        mac = get_iface_mac(iface)
        idict[mac] = iface
    return idict

def rename_interface(nameif, mac, newname):
    f = tempfile.NamedTemporaryFile()
    f.write('%s %s\n' % (newname, mac))
    f.flush()
    rc = runcmd([nameif, '-c', f.name])
    f.close()
    if rc != 0:
        raise BypassExc('failed to rename guest interface with mac %s to %s, please contact support' % (mac, newname))

def record_iface_info(dir, nic):
    if os.path.exists(dir):
        shutil.rmtree(dir)
    os.mkdir(dir)
    for (name, value) in nic.iteritems():
        fname = dir + '/' + name
        f = open(fname, 'w')
        f.write(value + '\n')
        f.close()

def parse_iface_info(bpctl_output):
    iface_info = dict()

    if len(bpctl_output):
        for line in bpctl_output:
            match = re.search('^(.*?)=(.*)', line)
            if not match:
                raise BypassExc('malformed bpctl output during probing, please contact support: %s' % line)
            name = match.group(1)
            value = match.group(2)

            iface_info[name] = value

    return iface_info

def run_bpctl(bpctl, iface_list):
    nics = BypassDiscoveredInfo()

    try:
        jobboard = {}

        for iface in iface_list:
            if not os.path.exists('/sys/class/net/%s' % iface):
                print >> sys.stderr, 'Unknown iface %s skipped' % iface
                continue

            set_iface_up(iface)

            cmd = [bpctl, iface, 'print_interface_info']
            proc = subprocess.Popen(cmd, close_fds=True, shell=False,
                                    stdout=subprocess.PIPE,
                                    stderr=open('/dev/null', 'w'))
            jobboard[iface] = proc

        for iface in jobboard.keys():
            proc = jobboard[iface]
            proc.wait()

            output = []
            for i in proc.stdout.readlines():
                output.append(i.strip())
            if output:
                iface_info = parse_iface_info(output)
                iface_info['mac'] = get_iface_mac(iface)
                iface_info['name'] = iface

                nics.add_nic(iface_info)
    finally:
        for iface in iface_list:
            set_iface_down(iface)

    return nics



def pre_rename_init(options, args):

    macdir = options.topdir + '/macs'
    valdir = options.topdir + '/validated'
    udir = options.topdir + '/unconnected'

    # Clear any old information
    if os.path.exists(macdir):
        shutil.rmtree(macdir)
    if os.path.exists(valdir):
        shutil.rmtree(valdir)
    if os.path.exists(options.topdir + '/management'):
        os.unlink(options.topdir + '/management')
    if os.path.exists(udir):
        shutil.rmtree(udir)

    # Use bpctl to load in raw nic info
    nics = run_bpctl(options.bpctl, args)

    if nics.no_nics():
        # This is the ultra common case, bpctl returned
        # zero information; this vsh isn't using hardware bypass.
        raise BypassExc('no hardware bypass capable interfaces connected to this guest')

    # Peform validation on the raw info we read from
    # the bpctl program. If we detect
    # an error here, it's likely that the wrong
    # driver or something really strange is going
    # on, and there's not much we can do or helpful
    # info we can report.
    nics.basic_validate()

    # in order to make sure that we don't
    # interfere with the interface rename operations
    # that happen in rbtkmod, we need to make sure
    # that we rename any management interfaces to 'bpvm'
    # so that they aren't considered as potential
    # inpath members
    nics.verify_management_maybe_rename(options.nameif)

    # note that we record all the info we
    # gathered at system startup time, even
    # interfaces that arent branded, and the
    # original 'ethX' names (except for management).
    if not os.path.exists(options.topdir):
        os.makedirs(options.topdir)
    os.makedirs(macdir)
    for nic in [ nics.mgmt_nic ] + nics.raw_nics.values():
        nic['name_pre_rename'] = nic['name']
        del nic['name']
        nic_dir = macdir + '/' + nic['mac']
        record_iface_info(nic_dir, nic)

    # Done, will finish all other validation and marking
    # in post_rename_init (called after rbtkmod runs the
    # hwtool -q mactab & interface renaming actions)


def model_overage_strings(nics, allowed, unallowed):
    bypass_str = 'bypass pair: %s mac %s ESX nic %s ESX mac %s with %s mac %s ESX nic %s ESX mac %s'
    plist = []
    for mac in allowed:
        c = nics.by_mac[mac]
        s = nics.by_devnum[c['slave']]
        plist.append(bypass_str % (c['name'], c['mac'], c['esx_nic'], c['esx_mac'], s['name'], s['mac'], s['esx_nic'], s['esx_mac']))
    allowed_str = str(plist)
    plist = []
    for mac in unallowed:
        c = nics.by_mac[mac]
        s = nics.by_devnum[c['slave']]
        plist.append(bypass_str % (c['name'], c['mac'], c['esx_nic'], c['esx_mac'], s['name'], s['mac'], s['esx_nic'], s['esx_mac']))
    unallowed_str = str(plist)
    return (allowed_str, unallowed_str)


def post_rename_init(options):

    macdir = options.topdir + '/macs'
    valdir = options.topdir + '/validated'

    nics = BypassDiscoveredInfo()

    mac_iface_dict = create_mac_to_iface_dict()

    for mac in os.listdir(macdir):
        nic = dict()
        for name in os.listdir(macdir + '/' + mac):
            fpath = macdir + '/' + mac + '/' + name
            f = open(fpath, 'r')
            raw = f.read()
            value = raw.strip()
            f.close()
            nic[name] = value
        if nic['mac'] not in mac_iface_dict:
            raise BypassExc('recorded info for mac %s references an interface that no longer exists, contact support.' % nic['mac'])
        nic['name'] = mac_iface_dict[nic['mac']]
        nics.add_nic(nic)

    # For safety and simplicity's sake, we'll just redo 
    # all the validation already done in pre_rename_init
    if nics.no_nics():
        raise BypassExc('no hardware bypass capable interfaces connected to this guest')
    nics.basic_validate()
    nics.verify_management_maybe_rename(nameif=None)

    # prepare control/slave data structures
    nics.prepare_guest_interfaces_info()

    # only Riverbed branded cards accepted
    nics.verify_branding(options.hwtool)

    # load info on Silicom hardware interfaces
    # that aren't connected to this guest so
    # that we can have better logging messages
    # in verify_pairs.
    nics.read_unconnected_interfaces_info(options.topdir, options.bpctl)

    # verify control/slave and lan/wan pairings
    nics.verify_pairs()

    # For consistency with physical steelheads, make sure that the
    # lan interface in an inpath has the lowest ESX mac address, swapping
    # the interfaces around if needed. Doing this will help anyone installing
    # or troubleshooting the cards.
    nics.lans_to_lowest_esx_mac(options.nameif)

    # Handle model limitation of # of bypass pairs,
    # we'll use the first N bypass pairs, ordered 
    # by lowest ESX mac address of their control iface
    (allowed, unallowed) = nics.control_macs(int(options.max_bypass_pairs))
    if unallowed:
        (allowed_str, unallowed_str) = model_overage_strings(nics, allowed, unallowed)
        # print warning, but do not exit with error,
        # so that any valid interfaces can be used
        print >> sys.stderr, 'vsh_bypass_init: WARNING: There are %d bypass pairs mapped to this guest, but the maximum for this steelhead model is %s. Only the first %s bypass pairs with the lowest control interface ESX mac addresses will be activated.  The following interfaces will be activated: %s .  The following interfaces will NOT be activated: %s .' % (len(allowed) + len(unallowed), options.max_bypass_pairs, options.max_bypass_pairs, allowed_str, unallowed_str)

    # yay, all validation done!
    if allowed:
        os.makedirs(valdir)
        for mac in allowed:
            nic = nics.by_mac[mac]
            slave = nics.by_devnum[nic['slave']]
            os.symlink(macdir + '/' + mac, valdir + '/' + mac)
            smac = slave['mac']
            os.symlink(macdir + '/' + smac, valdir + '/' + smac)

        # leave bpvm0 interface up
        set_iface_up(nics.mgmt_nic['name'])

        # This symlink is used and checked in the hal code to see
        # if initialization was successful
        os.symlink(macdir + '/' + nics.mgmt_nic['mac'], options.topdir + '/management')


def main():
    usage = "usage: %prog [options] iface-list"
    parser = OptionParser(usage)
    parser.add_option('--bpctl', default='/opt/hal/bin/vsh_bypass_ctrl', help='The path of the bypass control program that communicates to the Silicom ESX driver')
    parser.add_option('--hwtool', default='/opt/hal/bin/hwtool.py', help='The path of the hwtool.py script, needed for branding verification')
    parser.add_option('--topdir', default='/var/run/vsh_bypass', help='The top directory to hold discovered and computed bypass related info.')
    parser.add_option('--max_bypass_pairs', default='0', help='Maximum allowed bypass pairs, 0 for unlimited')
    parser.add_option('--nameif', default='/sbin/nameif', help='The path of the nameif utility, needed to rename management interfaces.')
    parser.add_option('--stage', help='which init stage, either pre_rename or post_rename')

    (options, args) = parser.parse_args()

    try:
        if not os.path.exists(options.bpctl):
            raise BypassExc('bypass control %s not found or not given' % options.bpctl)

        if not os.path.exists(options.hwtool):
            raise BypassExc('hwtool %s not found or not given' % options.hwtool)

        if not os.path.exists(options.nameif):
            raise BypassExc('nameif %s not found or not given' % options.nameif)

        if options.stage == 'pre_rename':
            pre_rename_init(options, args)
        elif options.stage == 'post_rename':
            post_rename_init(options)
        else:
            raise BypassExc('unknown init stage %s' % options.stage)

        sys.exit(0)


    except BypassExc, be:
        print >> sys.stderr, be
        sys.exit(1)

if __name__ == '__main__':
    main()
    sys.exit(0)

