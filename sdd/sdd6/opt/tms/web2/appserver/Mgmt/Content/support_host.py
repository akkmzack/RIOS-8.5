# Copyright 2006, Riverbed Technology, Inc., All rights reserved.
##
## Host support for gui and xmldata.
## Author: Don Tillman

import re
import os
import sys
import time
import xml.dom
import interfacewidget

import RVBDUtils
import FormUtils
import HostUtils
import Nodes
from gclclient import NonZeroReturnCodeException
from PagePresentation import PagePresentation
from XMLContent import XMLContent
import common

import OSUtils
import Logging
import WebUtils.FieldStorage as FieldStorage

# Adding a directory for temp files for software upgrades.
APP_UPGRADE_TMP_DIR = '/var/tmp/appUpgrades'
OSUtils.safeMkdir(APP_UPGRADE_TMP_DIR) # clear out any preexisting temp files.
FieldStorage.tempdirMap['applianceUpgradesTmpDir'] = APP_UPGRADE_TMP_DIR

IMAGE_DIR_PATH = '/var/opt/tms/images'

class gui_Host(PagePresentation):
    # actions handled here
    actionList = ['setupHostSettings',
                  'setupHostInpath',
                  'setupHostInterfaces',
                  'setupHostInterfacesIPv6',
                  'setupHostInterfacesInpathCmc',
                  'setupLicenses',
                  'setupFlexLicenses',
                  'setupVirtualKey',
                  'setupApplianceControl',
                  'setupApplianceConfig',
                  'setupApplianceUpgrade',
                  'setupDiskManagement',
                  'setupCloudLicensing',
                  'setupHypervisorLicense']

    # Support for the Host Settings page:
    #     Hostname
    #     IQN (BOB only)
    #     DNS Settings
    #     Host table
    #     Proxies
    #     Date and Time
    #
    # All but Date and Time are CMC ready.
    def setupHostSettings(self):
        fields = self.request().fields()
        mgmt = self.session().value('mgmt')
        if 'addHost' in fields:
            # add a host
            ip = fields.get('host_ip')
            name = fields.get('host_name')
            if ip and name:
                path = self.cmcPolicyRetarget('/hosts/ipv4/%s/host/%s' % (ip, name))
                self.setNodes((path, 'hostname', name))
        elif 'removeHosts' in fields:
            # remove selected hosts
            base = self.cmcPolicyRetarget('/hosts/ipv4')
            FormUtils.deleteNodesFromConfigForm(mgmt, base, 'selectedHost_', fields)
        elif 'addNtpServer' in fields:
            # add an NTP server
            host = fields.get('ntpServer_host')
            version = fields.get('ntpServer_version')
            enable = fields.get('ntpServer_enable')
            base = self.cmcPolicyRetarget('/ntp/server/address')
            nodes = [('%s/%s/enable' % (base, host), 'bool', enable)]

            # If version doesn't exist, then we're on a BOB appliance, which
            # means we don't set the version node.
            if version:
                nodes.append(('%s/%s/version' % (base, host), 'uint32', version))

            self.setNodes(*nodes)
        elif 'removeNtpServers' in fields:
            # remove NTP servers
            base = self.cmcPolicyRetarget('/ntp/server/address')
            FormUtils.deleteNodesFromConfigForm(mgmt, base, 'selectedNtpServer_', fields)
        elif 'apply' in fields:
            # Set the nodes. This has to happen before manually setting the time.
            FormUtils.setNodesFromConfigForm(mgmt, fields)

            # proxy settings
            self._setupHostSettings_proxy()


            # The DNS address nodes look like this:
            #
            #   /resolver/nameserver/1/address
            #
            # (This gets retargeted for a CMC policy, of course.)
            # When we set this node, /resolver/nameserver/1 gets
            # created automatically.  Similarly, if we set the address
            # to '', /resolver/nameserver/1 and
            # /resolver/nameserver/1/address both get deleted.
            #
            # This doesn't happen on a CMC policy though so we need to
            # delete /resolver/nameserver/1 explicitly.  The following
            # code applies only to CMC policies, which contain
            # dnsServer_* fields.
            dnsPath = self.cmcPolicyRetarget('/resolver/nameserver')
            for i in FormUtils.getPrefixedFieldNames('dnsServer_', fields):
                addr = fields['dnsServer_' + i]
                if addr:
                    self.setNodes(
                        ('%s/%s/address' % (dnsPath, i), 'ipv4addr', addr))
                else:
                    Nodes.delete(mgmt, '%s/%s' % (dnsPath, i))

            HostUtils.setDomainList(
                mgmt, fields['dnsDomainList'], self)
            # If NTP is disabled, manually set the time
            # (check that the fields exist because of cmc policies)
            if ('date' in fields) and ('time' in fields):
                # set the date with an action call
                currentDate = mgmt.get('/time/now/date')
                newDate = fields.get('date', None)
                if newDate != currentDate:
                    val = self.sendAction('/time/set/date', ('date', 'date', newDate))
                # set the time with an action call
                currentTime = mgmt.get('/time/now/time')
                newTime = fields.get('time', None)
                if newTime != currentTime:
                    self.sendAction('/time/set/time', ('time', 'time_sec', newTime))

            # IQN for BOB
            if RVBDUtils.isBOB():
                currentIQN = Nodes.present(mgmt, '/rbt/rsp3/state/host_initiator_iqn')
                newIQN = fields['iqn']
                if currentIQN != newIQN:
                    self.sendAction('/rbt/rsp3/action/iscsi/update_name',
                                    ('iqn', 'string', newIQN))

            # Handling timezone last as this causes webasd to restart
            self.setNodes(('/time/zone', 'string', fields['timezone']))
        else:
            host, enable = FormUtils.getPrefixedField('ntpServer_enable_', fields)
            if host:
                base = self.cmcPolicyRetarget('/ntp/server/address')
                self.setNodes(('%s/%s/enable' % (base, host), 'bool', enable))

    # Helper method for above; handle the proxy settings.
    # NOTE: not CMC-worthy yet 
    def _setupHostSettings_proxy(self):
        # default, disabled values:
        host = '0.0.0.0'
        port = '1080'
        authUser = ''
        authPassword = ''
        authType = 'basic'

        if 'proxy_enable' in self.fields:
            host = self.fields['proxy_host']
            port = self.fields['proxy_port']

            if 'proxy_authEnable' in self.fields:
                authUser = self.fields['proxy_authUser']
                authPassword = self.fields['proxy_authPassword']
                authType = self.fields['proxy_authType']

                # The action's API doesn't allow us to leave a password  alone,
                # so we need to replace an unedited password with the decripted
                # current password.
                if FormUtils.bogusPassword == authPassword:
                    authPassword = self.sendAction(
                        '/web/proxy/actions/get_decrypted_password')['passwd']
        
        self.sendAction('/web/proxy/actions/set_web_proxy',
                        ('address', 'hostname', host),
                        ('port', 'uint16', port),
                        ('username', 'string', authUser),
                        ('passwd', 'string', authPassword),
                        ('authtype', 'string', authType))

    # Inpath
    def setupHostInpath(self):
        fields = self.fields
        mgmt = self.mgmt
        base = self.cmcPolicyRetarget('/rbt/route/config')
        if 'editInpathInterface' in fields:
            # changing one of the In-Path interface's settings
            iface =     fields['inpath_name']
            numPart =   iface[len('inpath'):] # e.g. '0_0' or '0_1'
            dhcp =      fields['inpath_dhcp']
            manIp =     (dhcp == 'false') and fields['inpath_manIp'] or ''
            manSubnet = (dhcp == 'false') and str(FormUtils.ipv4ParseNetMask(fields['inpath_manSubnet'])) or ''
            gateway =   (dhcp == 'false') and fields['inpath_gateway'] or ''
            gatewayNodePath = '/rbt/route/config/%s/ipv4/prefix/0.0.0.0\\/0/gw' % iface
            if gateway == '': # ipv4addr type cannot be blank, set gateway to 0.0.0.0 instead.
                gateway = '0.0.0.0'

            # these don't apply to all interfaces
            lanSpeed =  fields.get('inpath_lanSpeed')
            lanDuplex = fields.get('inpath_lanDuplex')
            wanSpeed =  fields.get('inpath_wanSpeed')
            wanDuplex = fields.get('inpath_wanDuplex')
            mtu =       fields.get('inpath_mtu')
            vlan =      fields.get('inpath_vlan')

            sportConf = '/rbt/sport/intercept/config/ifaces/inpath'
            netConf =   '/net/interface/config'

            nodes = [(netConf + '/%s/addr/ipv4/dhcp' % iface,            'bool',     dhcp),
                     (netConf + '/lan%s/type/ethernet/speed' % numPart,  'string',  lanSpeed),
                     (netConf + '/lan%s/type/ethernet/duplex' % numPart, 'string',  lanDuplex),
                     (netConf + '/wan%s/type/ethernet/speed' % numPart,  'string',  wanSpeed),
                     (netConf + '/wan%s/type/ethernet/duplex' % numPart, 'string',  wanDuplex),
                     (netConf + '/%s/mtu' % iface,                       'uint16',  mtu),
                     (sportConf + '/%s/vlan' % iface,                    'uint16',  vlan)]

            if manIp != '' and manSubnet != '':
                # not using dhcp, so set the ip and subnet nodes.
                nodes.append((netConf + '/%s/addr/ipv4/static/1/ip' % iface,       'ipv4addr', manIp))
                nodes.append((netConf + '/%s/addr/ipv4/static/1/mask_len' % iface, 'uint8',    manSubnet))

            # gateway is optional (even when not using dhcp)
            nodes.append((gatewayNodePath, 'ipv4addr', gateway))

            if 'mgmt_enable' in fields:
                # Set all the mgmt interface settings if mgmt_enable is checked
                mgmtEnable = fields['mgmt_enable']
                mgmtIp =     fields['mgmt_manIp']
                mgmtSubnet = str(FormUtils.ipv4ParseNetMask(fields['mgmt_manSubnet']))
                mgmtVlan =   fields['mgmt_vlan']
                nodes.extend([(sportConf + '/inpath%s/mgmt/enable' % numPart,             'bool',     mgmtEnable),
                              (sportConf + '/inpath%s/mgmt/addr/ipv4/ip' % numPart,       'ipv4addr', mgmtIp),
                              (sportConf + '/inpath%s/mgmt/addr/ipv4/mask_len' % numPart, 'uint8',    mgmtSubnet),
                              (sportConf + '/inpath%s/mgmt/vlan' % numPart,               'uint16',   mgmtVlan),
                              ])
            elif FormUtils.isFieldUnchecked('mgmt_enable', fields):
                nodes.append((sportConf + '/inpath%s/mgmt/enable' % numPart, 'bool', 'false'))

            Nodes.set(mgmt, *Nodes.removeNullBindings(nodes))

        elif 'addRoute' in fields:
            inpath = fields.get('inpath_name')
            dest = fields.get('addRoute_dest')
            netmask = fields.get('addRoute_netmask')
            mask = FormUtils.ipv4ParseNetMask(netmask)
            gw = fields.get('addRoute_gateway')
            node = '%s/%s/ipv4/prefix/%s\\/%s/gw' % (base, inpath, dest, mask)
            self.setNodes((node, 'ipv4addr', gw))
        elif 'removeRoutes' in fields:
            inpath = fields.get('inpath_name')
            prefix = '%s/%s/ipv4/prefix' % (base, inpath)
            FormUtils.deleteNodesFromConfigForm(mgmt, prefix, 'selectedRoute_', fields)
        elif 'apply' in fields:
            # Sets the "link state propagation" checkbox
            FormUtils.setNodesFromConfigForm(mgmt, fields)

    # Interfaces
    def setupHostInterfaces(self):
        fields = self.fields
        mgmt = self.mgmt
        prefix = self.cmcPolicyRetarget('/net/routes/config/ipv4/prefix')
        if 'apply' in fields:
            # If IPv6 isn't enabled, delete the config nodes.
            # TODO:  Be less destructive by doing nothing if the
            # address is set to ::.
            if 'enablePrimaryIpv6' not in fields:
                Nodes.delete(mgmt, self.cmcPolicyRetarget(
                    '/net/interface/config/primary/addr/ipv6/static/1'))
            if 'enableAuxIpv6' not in fields:
                Nodes.delete(mgmt, self.cmcPolicyRetarget(
                    '/net/interface/config/aux/addr/ipv6/static/1'))
            self.adjustInterface_subnetGateway()
            FormUtils.setNodesFromConfigForm(mgmt, fields)

            if 'IPv6 settings change requires a reboot.' in self.actionMessages:
                self.removeActionMessage()
                self.setActionMessage('''IPv6 settings change requires a
                                      <a href="/mgmt/gui?p=setupAppliance_shutdown">reboot</a>.''',
                                      safe=True)
        elif 'addRoute' in fields:
            dest = fields.get('addRoute_dest')
            netmask = fields.get('addRoute_netmask')
            mask = FormUtils.ipv4ParseNetMask(netmask)
            gw = fields.get('addRoute_gateway') or '0.0.0.0'
            iface = fields.get('addRoute_interface')

            # the backend uses an empty string to say that an interface is not
            # specified but the UI page uses 'auto' due to the way dropdown menus
            # should be used. this does the conversion.
            if iface == 'auto':
                iface = ''
            
            index = Nodes.arrayElementForAdd(mgmt,
                                             '%s/%s\\/%s/nh' % (prefix, dest, mask),
                                             'gw',
                                             gw)
            node = '%s/%s\\/%s/nh/%s' % (prefix, dest, mask, index)
            self.setNodes(('%s/gw' % node, 'ipv4addr', gw),
                          ('%s/interface' % node, 'string', iface))
        elif 'removeRoutes' in fields:
            selectPaths = []
            selecteds = FormUtils.getPrefixedFieldNames('selectedRoute_', fields)
            for selected in selecteds:
                destmask, gw = selected.split('_')
                selectPaths.append('%s/%s/nh/%s' % (prefix, destmask, gw))
            self.deleteNodes(*selectPaths)

    def setupHostInterfacesIPv6(self):
        fields = self.fields
        mgmt = self.mgmt
        prefix = self.cmcPolicyRetarget('/net/routes/config/ipv6/prefix')
        if 'addRouteIPv6' in fields:
            # IPv6 addresses in node paths must be must be in canonicalized format
            dest = common.lc_ipv6addr_str_canonicalize(fields['addRouteIPv6_destIPv6'])
            ipPrefix = fields['addRouteIPv6_prefixIPv6']
            gw = common.lc_ipv6addr_str_canonicalize(fields['addRouteIPv6_gatewayIPv6'])
            index = Nodes.arrayElementForAdd(
                mgmt,
                '%s/%s\\/%s/nh' % (prefix, dest, ipPrefix),
                'gw',
                gw)
            node = '%s/%s\\/%s/nh/%s/gw' % (prefix, dest, ipPrefix, index)
            self.setNodes((node, 'ipv6addr', gw))
        elif 'removeRoutesIPv6' in fields:
            selectPaths = []
            selecteds = FormUtils.getPrefixedFieldNames('selectedRouteIPv6_', fields)
            for selected in selecteds:
                destmask, gw = selected.split('_')
                selectPaths.append('%s/%s' % (prefix, destmask))
            self.deleteNodes(*selectPaths)

    # CMC Version of inpaths
    def setupHostInterfacesInpathCmc(self):
        fields = self.fields
        if 'apply' in fields:
            self.adjustInterface_subnetGateway()
            FormUtils.setNodesFromConfigForm(self.mgmt, fields)

            # remove the nodes for interfaces not being included
            ifacePrefix = self.cmcPolicyRetarget('/net/interface/config')
            ifaces = Nodes.getMgmtLocalChildrenNames(self.mgmt, ifacePrefix)
            dels = []
            # these all have I_J appended to them
            delPrefixes = ('/net/interface/config/inpath',
                           '/net/interface/config/lan',
                           '/net/interface/config/wan',
                           '/rbt/route/config/inpath',
                           '/rbt/sport/intercept/config/ifaces/inpath/inpath')
            for iface in ifaces:
                if iface.startswith('inpath'):
                    ifi = iface[len('inpath'):]
                    if ('cmcIface_inpath' + ifi) not in self.fields:
                        for delPref in delPrefixes:
                            dels.append(self.cmcPolicyRetarget(delPref + ifi))
            self.deleteNodes(*dels)

    # Helper for above; make adjustments to the values of subnet masks
    # and gateway ip's in the fields.
    def adjustInterface_subnetGateway(self):
        for fn, fv in self.fields.items():
            fv = fv.strip()
            # convert ipv4 subnet masks
            if fn.startswith('u8/') and fn.endswith('/mask_len') and \
                    (fn.find('ipv4') != -1):
                self.fields[fn] = str(FormUtils.ipv4ParseNetMask(fv))
            # handle empty gateway
            elif fn.startswith('ipv4/') and fn.endswith('/gw'):
                if not fv:
                    self.fields[fn] = '0.0.0.0'

    # Handle licenses here, set policy nodes directly for managed
    # appliance licenses.
    def setupLicenses(self):
        fields = self.fields
        mgmt = self.mgmt
        appliance, appliance_productType, appliance_serialNumber  = Nodes.parseApplianceParam(fields.get('editAppliancePolicy'))

        if 'addLicense' in fields:
            licenses_str = fields.get('licenses', '')
            licenses = licenses_str.split()
            for license in licenses:

                if appliance_serialNumber:
                    # Add this license key to the appliance license array.
                    nodes= {'license_key' : license}
                    basepath = \
                        ('/cmc/policy/config/sh/appliance/%s/node/license/key' \
                        % appliance_serialNumber)

                    value = self.editNodeSequence(basepath, {}, 'add', -1,
                                                  nodes, allow_dups=False)
                    if value == 'Duplicate':
                        self.setActionMessage('Duplicate licenses are not allowed')
                        return

                else:
                    self.sendAction('/license/action/add_license', \
                                    ('license_key', 'string', license))
        elif 'removeLicense' in fields:
            idList = FormUtils.getPrefixedFieldNames('selectedLicense_', fields)
            idList = [int(id) for id in idList]
            idList.sort()
            idList.reverse()

            if appliance_serialNumber:
                basepath = \
                        ('/cmc/policy/config/sh/appliance/%s/node/license/key' \
                        % appliance_serialNumber)
                # Pop it like it's hot.
                self.editNodeSequence(basepath, {}, 'remove', idList)

            else:
                idList = [str(id) for id in idList]
                for id in idList:
                    if id > 0:
                        self.sendAction('/license/action/delete_license', \
                                        ('idx', 'uint32', id))
        elif 'upgradeHardware' in fields:
            # hardware upgrade on licenses page
            self.sendAction('/rbt/manufacture/action/hw_upgrade')

    # handle flexible licenses here
    def setupFlexLicenses(self):
        specName = self.fields.get('/hw/hal/spec/state/current/name', '')
        self.sendAction('/hw/hal/spec/action/set', ('spec_id', 'string', specName))
        self.sendAction('/rbt/sport/status/action/rewrite_config')

    # Generate a new virtual model upgrade license request key from the token
    def setupVirtualKey(self):
        self.setFormNodes()
        requestKey = Nodes.present(self.mgmt, '/rbt/virtual/state/key')
        self.setActionMessage('Your model upgrade license request key is %s' %
                              requestKey)

    # For the setupApplianceControl page.
    #
    # Handles these operations:
    #    start/stop/restart service
    #    reboot appliance
    #    shutdown appliance
    #
    # Hasn't been tested.  Could still use some more work.
    def setupApplianceControl(self):
        fields = self.fields
        # start:
        if 'serviceStart' in fields:
            if 'serviceClean' in fields:
                self.cleanSegmentStore()
            self.sendAction('/rbt/sport/status/action/unset_restart_needed')
            self.sendAction('/pm/actions/restart_process', ('process_name', 'string', 'sport'))
        # stop:
        elif 'serviceStop' in fields:
            if 'serviceClean' in fields:
                self.cleanSegmentStore()
            self.sendAction('/rbt/sport/status/action/unset_restart_needed')
            self.sendAction('/pm/actions/terminate_process', ('process_name', 'string', 'sport'))
        # restart
        elif 'serviceRestart' in fields:
            if 'serviceClean' in fields:
                self.cleanSegmentStore()
            self.sendAction('/rbt/sport/status/action/unset_restart_needed')
            self.sendAction('/pm/actions/restart_process', ('process_name', 'string', 'sport'))
        # reboot
        elif 'applianceReboot' in fields:
            if 'applianceClean' in fields:
                self.applianceControlCleanSegmentStore()
            self.sendAction('/pm/actions/reboot')
            self.response().sendRedirect('/mgmt/logout?reason=Machine+rebooting...')
        # shutdown
        elif 'applianceShutdown' in fields:
            if 'applianceClean' in fields:
                self.applianceControlCleanSegmentStore()
            self.sendAction('/pm/actions/shutdown')
            self.response().sendRedirect('/mgmt/logout?reason=Machine+shutting+down...')

    # Used by the above
    #
    # To leave a note to clean the segment store on startup, make
    # sure that this file exists.
    def applianceControlCleanSegmentStore(self):
        rbtSegmentStoreCleanPath = '/var/opt/rbt/.clean'
        f = file(rbtSegmentStoreCleanPath, 'w+')
        f.close()

    # Implements the configuration manager
    #
    def setupApplianceConfig(self):
        fields = self.fields
        mgmt = self.mgmt
        if 'removeConfigs' in fields:
            for name in FormUtils.getPrefixedFieldNames('selectedConfig_', fields):
                self.sendAction('/mgmtd/db/delete', ('db_name', 'string', name))
        elif 'saveCurrentConfig' in fields:
            self.sendAction('/mgmtd/db/save')
        elif 'saveCurrentConfigAs' in fields:
            self.sendAction('/mgmtd/db/save_as',
                             ('db_name', 'string', fields['saveAsName']),
                             ('switch_to', 'bool', 'true'))
        elif 'revertCurrentConfig' in fields:
            self.sendAction('/mgmtd/db/revert')
        elif 'importConfig' in fields:
            host = fields.get('import_host')
            password = fields.get('import_password', '')
            remoteName = fields.get('import_remoteName')
            name = fields.get('import_name')
            sharedData = fields.get('import_sharedData')
            if not (host and remoteName and name):
                return
            url = 'scp://admin:%s@%s/config/db/%s' % (password, host, remoteName)
            if sharedData:
                # get temp name
                i = 0
                while True:
                    tempName = '%s_%d' % (name, i)
                    if not Nodes.present(mgmt, '/mgmtd/db/info/saved/%s' % tempName):
                        break
                    i += 1
                # save name of current active db
                activeDB = mgmt.get('/mgmtd/db/info/running/db_name')
                # save current configuration under new config name
                self.sendAction('/mgmtd/db/save_as',
                                ('db_name', 'string', name),
                                ('switch_to', 'bool', 'true'))
                try:
                    # fetch
                    self.sendAction('/mgmtd/db/download',
                                    ('remote_url', 'string', url),
                                    ('db_name', 'string', tempName))
                    # import
                    self.sendAction('/mgmtd/db/import',
                                    ('db_name', 'string', tempName),
                                    ('import_id', 'string', 'generic'))
                except:
                    # if failed, switch to previous active db and delete download
                    self.sendAction('/mgmtd/db/switch_to', ('db_name', 'string', activeDB))
                    self.sendAction('/mgmtd/db/delete', ('db_name', 'string', name))
                # save the new db
                self.sendAction('/mgmtd/db/save')
                # delete temp
                self.sendAction('/mgmtd/db/delete', ('db_name', 'string', tempName))
            else:
                # fetch
                self.sendAction('/mgmtd/db/download',
                                ('remote_url', 'string', url),
                                ('db_name', 'string', name))
        elif 'activateConfig' in fields:
            newConfig = fields['activateConfig']
            self.sendAction('/mgmtd/db/switch_to', ('db_name', 'string', newConfig))

    # implements the appliance upgrade page
    #
    def setupApplianceUpgrade(self):
        fields = self.fields
        thisPartition = self.mgmt.get('/image/boot_location/booted/location_id')
        otherPartition = ('1' == thisPartition) and '2' or '1'
        if 'switch' in fields:
            # handle switch
            self.sendAction('/image/boot_location/nextboot/set',
                            ('location_id', 'uint32', otherPartition),
                            ('device_name', 'string', ''))
        elif 'cancelSwitch' in fields:
            # handle cancel
            self.sendAction('/image/boot_location/nextboot/set',
                            ('location_id', 'uint32', thisPartition),
                            ('device_name', 'string', ''))
        elif 'upgradeMeterSubmit' in fields:
            # handle install
            self.installUpgrade(thisPartition, otherPartition)

    # installUpgrade() is called by setupApplianceUpgrade(). This method is run after the upgrade image
    # file has been uploaded (for "from local file" upgrades) or after the form has been submitted (for
    # "from url" upgrades). The AJAX method that returns the status of the upload/upgrade is
    # upgradeMeterStatus().
    #
    # There are four cases of software upgrade:
    #     From file upload or from url, and install now or install later
    def installUpgrade(self, thisPartition, otherPartition):
        upgradeState = self.session().value('upgradeState', None) # syntactic sugar

        def fromURLUpgrade():
            # Handle an upgrade image from a url.
            url = fields.get('installUpgradeUrl', '').strip()
            assert url, "installUpgrade() called with no field named installUpgradeUrl (or installUpgradeUrl has a blank value)."

            baseName = RVBDUtils.getSafeBasenameFromUrl(url, 'webimage.tbz')

            # Download the file from the URL:

            # Going to delete the file first, even though /file/transfer/download will overwrite it.
            # This is because we want to delete the file before switching the state to
            # ('url','<filename>') so that if an AJAX status request occurs between the next two lines (unlikely but possible),
            # immediate url upgrade
            # it will brief show the file size as the full size of the old file. (This only
            # happens if there is an image uploaded that has the same name as the image currently
            # being uploaded.)
            self.sendAction('/file/delete',
                            ('local_dir', 'string', IMAGE_DIR_PATH),
                            ('local_filename', 'string', baseName))
            self.session().setValue('upgradeState', ('url', baseName))

            # immediately begin file transfer:
            if 'installUpgradeLater' not in fields:
                try:
                    self.sendAction('/file/transfer/download',
                                    ('remote_url', 'string', url),
                                    ('local_dir', 'string', IMAGE_DIR_PATH),
                                    ('local_filename', 'string', baseName),
                                    ('allow_overwrite', 'bool', 'true'),
                                    ('mode', 'uint16', str(0600)))
                except NonZeroReturnCodeException, info:
                    # Most likely cause for error is a 404.
                    OSUtils.log(Logging.LOG_NOTICE,
                                'Software upgrade fetch of "%s" failed. %s' % (url, info))
                    raise
            return baseName


        def fromLocalFileUpgrade():
            # Handle an upgrade image is from file upload:
            assert type(upgradeState) == type( () ) or upgradeState is None, \
                'Session variable upgradeState is in the wrong state to begin a "from file" transfer: %s' % \
                (upgradeState)
            imageField = self.fields.get(FormUtils.makeUploadFieldName(
                                            'applianceUpgradesTmpDir', 'installUpgradeFile'))
            baseName = FormUtils.fileBaseName(imageField)
            baseName = re.sub(r'[^\w.]', '_', baseName) # replace any funny characters
            FormUtils.handleLocalFileUpload(imageField, IMAGE_DIR_PATH, baseName)
            return baseName


        fields = self.fields

        if 'file' == fields.get('installUpgradeFrom', ''):
            baseName = fromLocalFileUpgrade()
        elif 'url' == fields.get('installUpgradeFrom'):
            try:
                # needs to be called after scheduling a "from url"
                # upgrade task, so we don't transfer the file twice.
                baseName = fromURLUpgrade()
            finally:
                self.session().delValue('upgradeState')
        else:
            # Note: There is no "install from previously uploaded images" option for software upgrades.
            # There is only installing from a file upload or from a current url.
            raise AssertionError, "Invalid value for the installUpgradeFrom field passed in installUpgrade(): %s" % (fields.get('installUpgradeFrom'))

        if 'installUpgradeLater' in fields:
            # Schedule the upgrade for later:
            if 'url' == fields.get('installUpgradeFrom'):
                url = fields.get('installUpgradeUrl', '').strip()
                sourceMsg = 'from url.'
                scheduledTasks = ['image fetch %s %s' % (url, baseName),
                                  'image install %s %s' % (baseName, otherPartition),
                                  'image boot %s' % otherPartition,
                                  'reload']
            elif 'file' == fields.get('installUpgradeFrom'):
                sourceMsg = 'from image file.'
                scheduledTasks = ['image install %s %s' % (baseName, otherPartition),
                                  'image boot %s' % otherPartition,
                                  'reload']

            Nodes.scheduleJob(self.mgmt,
                              'Software Upgrade',
                              'Scheduled software upgrade ' + sourceMsg,
                              fields.get('installUpgradeDate'),
                              fields.get('installUpgradeTime'),
                              scheduledTasks)
            return


        # Perform an immediate "from url" or "from file upload" upgrade:
        self.session().setValue('upgradeState', 'installing')
        try:
            self.sendAction('/image/install',
                            ('image_name', 'string', baseName),
                            ('target_location_id', 'uint32', otherPartition),
                            ('target_device_name', 'string', ''),
                            ('install_bootmgr', 'bool', 'false'),
                            ('use_tmpfs', 'bool', 'false'))
            self.sendAction('/image/boot_location/nextboot/set',
                            ('location_id', 'uint32', otherPartition),
                            ('device_name', 'string', ''))
        finally:
            self.session().delValue('upgradeState')
        self.setActionMessage('Successfully installed upgrade image. Please <a href="/mgmt/gui?p=setupAppliance_shutdown">reboot the appliance</a> to complete the upgrade.', safe=True)

    # Change the disk layout.
    def setupDiskManagement(self):
        if 'diskLayout' in self.fields:
            self.sendAction('/rbt/disk_config/action/switch_config',
                            ('disk_config', 'string', self.fields['diskLayout']))
            self.response().sendRedirect('/mgmt/logout?reason=Machine+rebooting...')

    def setupCloudLicensing(self):
        fields = self.fields
        mgmt = self.mgmt
        if 'initClient' in fields:
            cshToken = fields['cshToken']
            self.sendAction('/license/action/init_client',
                            ('token_string', 'string', cshToken))
        elif 'reInitClient' in fields:
            cshToken = fields['cshToken']
            self.sendAction('/license/action/cleanup_client')
            self.sendAction('/license/action/init_client',
                            ('token_string', 'string', cshToken))
        elif 'removeLicense' in fields:
            self.sendAction('/license/action/cleanup_client')
        elif 'refreshLicense' in fields:
            self.sendAction('/license/action/client_fetch_now')
        elif 'addLicenseServer' in fields:
            name = fields['add_cloudLicenseServer_name']
            port = fields['add_cloudLicenseServer_port']
            priority = fields['add_cloudLicenseServer_priority']

            base = self.cmcPolicyRetarget('/license/server/config/')
            self.setNodes((base + name, 'string', name),
                          (base + name + '/port', 'uint16', port),
                          (base + name + '/priority', 'uint32', priority))
        elif 'editLicenseServer' in fields:
            name = fields['edit_cloudLicenseServer_name']
            port = fields['edit_cloudLicenseServer_port']
            priority = fields['edit_cloudLicenseServer_priority']

            base = self.cmcPolicyRetarget('/license/server/config/')
            self.setNodes((base + name, 'string', name),
                          (base + name + '/port', 'uint16', port),
                          (base + name + '/priority', 'uint32', priority))
        elif 'removeLicenseServer' in fields:
            base = self.cmcPolicyRetarget('/license/server/config')
            FormUtils.deleteNodesFromConfigForm(mgmt, base, 'selectedServer_', fields)

    # Change the hypervisor (ESXi) license.
    def setupHypervisorLicense(self):
        fields = self.fields
        if 'update' in fields:
            self.sendAction('/rbt/rsp3/action/host_license_change',
                            ('license', 'string', fields['hypervisorLicense']))
        elif 'reset' in fields:
            self.sendAction('/rbt/rsp3/action/host_license_reset',
                            ('confirm', 'bool', 'true'))

class xml_Host(XMLContent):
    dispatchList = ['dynamicStatus',
                    'dnsHosts',
                    'hostConfigs',
                    'dbDirty',
                    'inpathInterfaces',
                    'inpathRoutes',
                    'mainRoutes',
                    'mainRoutesIPv6',
                    'ntpServers',
                    'licenses',
                    'licensesUpdateStatus',
                    'upgradeMeterStatus',
                    'saveConfig',
                    'cloudLicenseServers',
                    'rpcTest']
    dogKickerList = ['saveConfig',
                     'licensesUpdateStatus',
                     'upgradeMeterStatus']

    gatewayRE = re.compile("nh/(\d+)$")

    # Used for the dynamic header status.
    # Calls back into the headerDynamic psp file and xmlizes that.
    def dynamicStatus(self):
        status = self.application().callMethodOfServlet(self.transaction(),
                                                        '/Templates/headerDynamic',
                                                        'getDynamicStatus')
        result = self.doc.createElement('status')
        for key, value in status.iteritems():
            result.setAttribute(key, value)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupHostSettings.psp, setupHostSettingsCMC.psp:
    #
    # The dnsHosts command.
    #
    # Result is of the form:
    # <hosts>
    #   <host ipv4="22.22.22.22">
    #     <hostname name="skeezer"/>
    #     <hostname name="gleep"/>
    #   </host>
    # </hosts>
    #
    def dnsHosts(self):
        path = self.cmcPolicyRetarget('/hosts/ipv4')
        hostsDict = Nodes.getMgmtSetEntriesDeep(self.mgmt, path)
        hostIPs = hostsDict.keys()
        hostIPs.sort(FormUtils.compareIpv4)
        result = self.doc.createElement('hosts')
        for ip in hostIPs:
            hostElement = self.doc.createElement('host')
            hostElement.setAttribute('ipv4', ip)
            host = hostsDict[ip]
            for eachKey in host.keys():
                nameElement = self.doc.createElement('hostname')
                nameElement.setAttribute('name', host[eachKey])
                hostElement.appendChild(nameElement)
            result.appendChild(hostElement)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupConfig.psp:
    #
    # <configs>
    #    <config name="" />
    #    ...
    # </configs>
    def hostConfigs(self):
        activeConfig = self.mgmt.get('/mgmtd/db/info/running/db_name')
        configNames = Nodes.getMgmtLocalChildrenNames(self.mgmt, '/mgmtd/db/info/saved')
        configNames.sort()
        result = self.doc.createElement('configs')
        for configName in configNames:
            configEl = self.doc.createElement('config')
            configEl.setAttribute('name', configName)
            if configName == activeConfig:
                configEl.setAttribute('prettyName', configName + ' (active)')
            else:
                configEl.setAttribute('prettyName', configName)
            mtime = Nodes.present(self.mgmt, '/mgmtd/db/info/saved/%s/mtime' % configName)
            configEl.setAttribute('mtime', mtime)
            result.appendChild(configEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # setupConfig.psp:
    #
    # returns JSON of the following form:
    # { "dirty": True | False }
    def dbDirty(self):
        def internal():
            dirty = self.mgmt.get('/mgmtd/db/info/running/unsaved_changes')
            return {'dirty': dirty == 'true'}
        self.rpcWrapper(internal)

    # for setupHostInterfacesInpath.psp:
    #
    # <interfaces>
    #   <interface name=""
    #              dhcp=""
    #              ip=""
    #              subnet=""
    #              optInterface=""
    #              manIp=""
    #              manSubnet=""
    #              gateway=""
    #              lanSpeed=""
    #              lanDuplex=""
    #              wanSpeed=""
    #              wanDuplex=""
    #              negoLanSpeed=""
    #              negoWanSpeed=""
    #              negoLanDuplex=""
    #              negoWanDuplex=""
    #              lanSpeedOptions=""
    #              wanSpeedOptions=""
    #              lanDuplexOptions=""
    #              wanDuplexOptions=""
    #              mtu=""
    #              vlan=""
    #              mgmtEnabled=""
    #              mgmtIp=""
    #              mgmtSubnet=""
    #              mgmtVlan=""
    #              mgmtInterface="">
    #   ...
    # </interfaces>
    def inpathInterfaces(self):
        result = self.doc.createElement('interfaces')
        mgmt = self.mgmt # syntactic sugar
        netState  = '/net/interface/state'
        netConf   = '/net/interface/config'
        sportConf = '/rbt/sport/intercept/config/ifaces/inpath'

        inpathInterfaces = [x for x in
                            Nodes.getMgmtLocalChildrenNames(mgmt,
                                                            self.cmcPolicyRetarget(netState))
                            if x.startswith('inpath')]
        inpathInterfaces = FormUtils.sortInterfacesByName(inpathInterfaces)
        for iface in inpathInterfaces:
            numPart = iface[len('inpath'):] # e.g. '0_0' or '0_1'

            dhcp          = Nodes.present(mgmt, '%s/%s/addr/ipv4/dhcp' % (netConf, iface), 'false')
            manIp         = Nodes.present(mgmt, '%s/%s/addr/ipv4/static/1/ip' % (netConf, iface))
            manSubnet     = FormUtils.ipv4NetMask(Nodes.present(mgmt, '%s/%s/addr/ipv4/static/1/mask_len' % (netConf, iface)))
            ip            = Nodes.present(mgmt, '%s/%s/addr/ipv4/1/ip' % (netState, iface))
            subnetShort   = Nodes.present(mgmt, '%s/%s/addr/ipv4/1/mask_len' % (netState, iface))
            subnet        = FormUtils.ipv4NetMask(subnetShort)

            if ip and subnetShort:
                optInterface = ip + '/' + subnetShort
            else:
                optInterface = '--'

            gateway       = Nodes.present(mgmt, '/rbt/route/config/%s/ipv4/prefix/0.0.0.0\\/0/gw' % iface)
            lanSpeed      = Nodes.present(mgmt, '%s/lan%s/type/ethernet/speed'  % (netConf, numPart))
            lanDuplex     = Nodes.present(mgmt, '%s/lan%s/type/ethernet/duplex' % (netConf, numPart))
            wanSpeed      = Nodes.present(mgmt, '%s/wan%s/type/ethernet/speed'  % (netConf, numPart))
            wanDuplex     = Nodes.present(mgmt, '%s/wan%s/type/ethernet/duplex' % (netConf, numPart))
            mtu           = Nodes.present(mgmt, '%s/%s/mtu'  % (netState, iface))
            vlan          = Nodes.present(mgmt, '%s/%s/vlan' % (sportConf, iface))
            negoLanSpeed  = Nodes.present(mgmt, '%s/lan%s/type/ethernet/speed'  % (netState, numPart))
            negoWanSpeed  = Nodes.present(mgmt, '%s/wan%s/type/ethernet/speed'  % (netState, numPart))
            negoLanDuplex = Nodes.present(mgmt, '%s/lan%s/type/ethernet/duplex' % (netState, numPart))
            negoWanDuplex = Nodes.present(mgmt, '%s/wan%s/type/ethernet/duplex' % (netState, numPart))
            lanSpeedOptions  = interfacewidget.getNativeSpeedOptions(mgmt,  'lan%s' % numPart)
            wanSpeedOptions  = interfacewidget.getNativeSpeedOptions(mgmt,  'wan%s' % numPart)
            lanDuplexOptions = interfacewidget.getNativeDuplexOptions(mgmt, 'lan%s' % numPart)
            wanDuplexOptions = interfacewidget.getNativeDuplexOptions(mgmt, 'wan%s' % numPart)

            ifaceEl = self.doc.createElement('interface')
            for optname, opts in (('lanSpeedOptions', lanSpeedOptions),
                                  ('wanSpeedOptions', wanSpeedOptions),
                                  ('lanDuplexOptions', lanDuplexOptions),
                                  ('wanDuplexOptions', wanDuplexOptions)):
                optsGroupEl = self.doc.createElement(optname)
                for i in range(len(opts)):
                    optEl = self.doc.createElement('option')
                    # items in opts are either a string (of the option) or a
                    # tuple of strings (of (option, prettyOption) )
                    if type(opts[i]) == type(str()):
                        optEl.setAttribute('name', opts[i])
                        optEl.setAttribute('value', opts[i])
                    elif type(opts[i]) == type(tuple()):
                        optEl.setAttribute('name', opts[i][1])
                        optEl.setAttribute('value', opts[i][0])
                    optsGroupEl.appendChild(optEl)
                ifaceEl.appendChild(optsGroupEl)

            for key, value in (('name', iface), ('dhcp', dhcp), ('manIp', manIp),
                               ('manSubnet', manSubnet), ('gateway', gateway),
                               ('ip', ip), ('subnet', subnet), ('optInterface', optInterface),
                               ('lanSpeed', lanSpeed), ('lanDuplex', lanDuplex),
                               ('wanSpeed', wanSpeed), ('wanDuplex', wanDuplex),
                               ('negoLanSpeed', negoLanSpeed), ('negoLanDuplex', negoLanDuplex),
                               ('negoWanSpeed', negoWanSpeed), ('negoWanDuplex', negoWanDuplex),
                               ('mtu', mtu), ('vlan', vlan)):
                ifaceEl.setAttribute(key, value)

            # If in-path management is supported, include those details too.
            if Nodes.present(mgmt, '/rbt/model_capability/inpath_mgmt') == 'true':
                mgmtEnable      = Nodes.present(mgmt, sportConf + '/inpath%s/mgmt/enable' % numPart)
                mgmtIp          = Nodes.present(mgmt, sportConf + '/inpath%s/mgmt/addr/ipv4/ip' % numPart)
                mgmtSubnetShort = Nodes.present(mgmt, sportConf + '/inpath%s/mgmt/addr/ipv4/mask_len' % numPart)
                mgmtSubnet      = FormUtils.ipv4NetMask(mgmtSubnetShort)
                mgmtVlan        = Nodes.present(mgmt, sportConf + '/inpath%s/mgmt/vlan' % numPart)
                mgmtInterface   = mgmtEnable == 'true' and mgmtIp + '/' + mgmtSubnetShort or '--'

                for key, value in (('mgmtEnable', mgmtEnable), ('mgmtIp', mgmtIp),
                                   ('mgmtSubnet', mgmtSubnet), ('mgmtVlan', mgmtVlan),
                                   ('mgmtInterface', mgmtInterface)):
                    ifaceEl.setAttribute(key, value)

            result.appendChild(ifaceEl)

        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupHostInterfacesInpath.psp:
    #
    # <routes>
    #   <route id=""
    #          destination=""
    #          gateway=""
    #          mask=""
    #          status="" />
    # ...
    # </routes>
    def inpathRoutes(self):
        statusPretty = {'down': 'User Configured / Inactive',
                        'configured': 'User Configured',
                        'dynamic': ''}
        iface = self.request().fields().get('iface')
        dynamicRoutePrefix = self.cmcPolicyRetarget('/rbt/route/state/%s/ipv4/prefix' % iface)
        configRoutePrefix = self.cmcPolicyRetarget('/rbt/route/config/%s/ipv4/prefix' % iface)
        dynamicRoutes = Nodes.getMgmtSetEntriesDeep(self.mgmt, dynamicRoutePrefix)
        configRoutes = Nodes.getMgmtSetEntriesDeep(self.mgmt, configRoutePrefix)
        routes = configRoutes.copy()
        routes.update(dynamicRoutes)
        routeIDs = routes.keys()
        routeIDs.sort(compareRoutes)
        result = self.doc.createElement('routes')
        defaultRoute = None # There is only one default route (i.e. ip of 0.0.0.0 & maskInt of 0)
        for routeID in routeIDs:
            route = routes[routeID]
            ip, mask = routeID.split('\\/')
            maskInt = int(mask)
            mask = FormUtils.ipv4NetMask(maskInt)
            id = ''
            status = 'dynamic'
            if routeID in configRoutes:
                id = routeID
                if routeID in dynamicRoutes:
                    status = 'configured'
                else:
                    status = 'down'
            routeEl = self.doc.createElement('route')
            routeEl.setAttribute('id', id)
            if '0.0.0.0' == ip:
                ip = 'default'
            routeEl.setAttribute('destination', ip)
            routeEl.setAttribute('mask', mask)
            routeEl.setAttribute('gateway', route.get('gw'))
            routeEl.setAttribute('status', statusPretty.get(status))
            if 'default' == ip and 0 == maskInt:
                defaultRoute = routeEl # save this route for later, add it at the end
            else:
                result.appendChild(routeEl)
        if defaultRoute is not None:
            result.appendChild(defaultRoute)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupHostInterfaces.psp:
    #
    # <routes>
    #   <route id=""
    #          destination=""
    #          gateway=""
    #          mask=""
    #          status="" />
    # ...
    # </routes>
    def mainRoutes(self):
        statusPretty = {'down': 'User Configured / Inactive',
                        'configured': 'User Configured',
                        'dynamic': ''}
        dynamicRoutePrefix = self.cmcPolicyRetarget('/net/routes/state/ipv4/prefix')
        configRoutePrefix = self.cmcPolicyRetarget('/net/routes/config/ipv4/prefix')
        dynamicRoutes = Nodes.getMgmtSetEntriesDeep(self.mgmt, dynamicRoutePrefix)
        configRoutes = Nodes.getMgmtSetEntriesDeep(self.mgmt, configRoutePrefix)
        routes = configRoutes.copy()
        routes.update(dynamicRoutes)
        routeIDs = routes.keys()
        routeIDs.sort(compareRoutes)
        result = self.doc.createElement('routes')
        for routeID in routeIDs:
            route = routes[routeID]
            ip, mask = routeID.split('\\/')
            maskInt = int(mask)
            mask = FormUtils.ipv4NetMask(maskInt)
            id = ''
            status = 'dynamic'
            if routeID in configRoutes:
                id = routeID
                if routeID in dynamicRoutes:
                    status = 'configured'
                else:
                    status = 'down'
            gateways = []
            for key in route:
                match = self.gatewayRE.match(key)
                if match:
                    gateways.append(int(match.group(1)))
            gateways.sort()
            for gw in gateways:
                idgw = ''
                if id:
                    idgw = '%s_%d' % (id, gw)
                routeEl = self.doc.createElement('route')
                routeEl.setAttribute('id', idgw)
                if '0.0.0.0' == ip and 0 == maskInt:
                    ip = 'default'
                routeEl.setAttribute('destination', ip)
                routeEl.setAttribute('mask', mask)
                routeEl.setAttribute('gateway', route.get('nh/%d/gw' % gw))
                routeEl.setAttribute('interface', route.get('nh/%d/interface' % gw, ''))
                routeEl.setAttribute('status', statusPretty.get(status))
                result.appendChild(routeEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupHostInterfaces.psp:
    #
    # <routes>
    #   <route id=""
    #          destination=""
    #          prefix=""
    #          gateway=""
    #          interface=""
    #          status="" />
    # ...
    # </routes>
    def mainRoutesIPv6(self):
        statusPretty = {'down': 'User Configured / Inactive',
                        'configured': 'User Configured',
                        'dynamic': ''}
        dynamicRoutePrefix = self.cmcPolicyRetarget('/net/routes/state/ipv6/prefix')
        configRoutePrefix = self.cmcPolicyRetarget('/net/routes/config/ipv6/prefix')
        dynamicRoutes = Nodes.getMgmtSetEntriesDeep(self.mgmt, dynamicRoutePrefix)
        configRoutes = Nodes.getMgmtSetEntriesDeep(self.mgmt, configRoutePrefix)
        routes = configRoutes.copy()
        routes.update(dynamicRoutes)
        routeIDs = routes.keys()
        # TODO: Instead of sorting, the sort order should be
        #       provided from the mgmt side.
        # routeIDs.sort(compareRoutes)
        result = self.doc.createElement('routes')
        for routeID in routeIDs:
            route = routes[routeID]
            ip, mask = routeID.split('\\/')
            id = ''
            status = 'dynamic'
            if routeID in configRoutes:
                id = routeID
                if routeID in dynamicRoutes:
                    status = 'configured'
                else:
                    status = 'down'
            gateways = []
            for key in route:
                match = self.gatewayRE.match(key)
                if match:
                    gateways.append(int(match.group(1)))
            gateways.sort()
            for gw in gateways:
                idgw = ''
                if id:
                    idgw = '%s_%d' % (id, gw)
                routeEl = self.doc.createElement('route')
                routeEl.setAttribute('id', idgw)
                # TODO : Need a proper IPv6 comparator to handle IPv6 Comparison
                if '::' == ip and 0 == int(mask):
                    ip = 'default'
                routeEl.setAttribute('destination', ip)
                routeEl.setAttribute('prefix', mask)
                routeEl.setAttribute('gateway', route.get('nh/%d/gw' % gw))
                routeEl.setAttribute('interface', route.get('nh/%d/interface' % gw, ''))
                routeEl.setAttribute('status', statusPretty.get(status))
                result.appendChild(routeEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupHostSettings.psp, setupHostSettingsCMC.psp:
    #
    # ntpServers
    #
    # <ntpservers>
    #   <ntpserver host="" enable="" prefer="" version="" />
    # </ntpservers>
    #
    def ntpServers(self):
        base = self.cmcPolicyRetarget('/ntp/server/address')
        servers = Nodes.getMgmtSetEntriesDeep(self.mgmt, base)
        serverIds = servers.keys()
        serverIds.sort(FormUtils.alphanumericCompare)
        result = self.doc.createElement('ntpservers')
        for serverId in serverIds:
            server = servers[serverId]
            serverEl = self.doc.createElement('ntpserver')
            serverEl.setAttribute('host', serverId)
            for key in ('enable', 'prefer', 'version'):
                serverEl.setAttribute(key, server.get(key, ''))
            result.appendChild(serverEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # For setupAppliance_upgrade.psp:
    #
    # Software upgrade's progress meter info.
    #
    # <upgradeProgress state="" description=""/>
    #
    # Returns information to Meter.py's progress meter objects about the status
    # of the upload. The description is displayed on the web ui, while a state of
    # "done" tells the meter object to stop polling.
    # This method is the AJAX status method. installUpgrade() is the method that
    # is run after the upgrade image file has been acquired.
    #
    # The session variable upgradeState tracks any software upgrade uploading/installing.
    # It has the following values during these phases:
    #         uploading from file   ('file', '<filename>')
    #         transferring from url ('url', '<filename>')
    #         while installing      'installing'
    # (<filename> is the full path and filename of the file being transferred. This info
    # can be used to get the file's size and (for local file uploads) the full size of the file.
    #
    # Process for "from local file" software upgrades:
    #     1) user clicks submit, 2) AJAX requests are made to upgradeMeterStatus()
    #     while the file uploads 3) gui action (installUpgrade()) is run which begins
    #     the install and sets the upgradeState session variable, 4) done.
    # Process for "from url" software upgrades:
    #     1) user clicks submit, 2) the gui action (installUpgrade()) runs and begins
    #     the transfer. The upgradeState session variable is set to the
    #     ('url', '<basename>') transferring state, 3) upgradeState is set to 'installing'
    #     in installUpgrade() when the transferring is finished, 4) done.
    def upgradeMeterStatus(self):
        # syntactic sugar:
        fields = self.fields
        upgradeState = self.session().value('upgradeState', None)

        if fields.get('upgradeMeterSubmit', None) is None:
            # This is the inital probe AJAX request sent by the meter code. We always reply with
            # a "done" state to this because we are not safeguarding against simultaneous upgrades.
            desc = ''
            state = 'done'
        else:
            if fields.get('clientState', None) == 'start':
                # Delete any files in the temp directory that are older than 15 seconds.
                # This takes care of the case where file uploads are interrupted by closing
                # the browser, which leaves behind partial files in the tmp directory.
                # Without this code, we may display the file size of the leftover file
                # instead of the currently uploading file.
                # The "older than 15 seconds" precondition is there because upgradeMeterStatus
                # is called via an AJAX request just after the file upload form is submitted,
                # which means the uploading file is in the temp directory. We want to delete
                # all other files (though we don't know the randomly generated temp file name,
                # so we rely instead of the timestamp).
                fileField = fields.get(FormUtils.makeUploadFieldName(
                                                      'applianceUpgradesTmpDir', 'installUpgradeFile'))
                baseName = FormUtils.fileBaseName(fileField)
                for fi in os.listdir(APP_UPGRADE_TMP_DIR):
                    if os.stat( os.path.join(APP_UPGRADE_TMP_DIR, fi) ).st_mtime < (time.time() - 15):
                        self.sendAction('/file/delete', \
                            ('local_dir', 'string', APP_UPGRADE_TMP_DIR), \
                            ('local_filename', 'string', fi))

                # The user has clicked the submit button.
                if fields.get('installUpgradeFrom') == 'url':
                    desc = 'Initializing...' # This generic message works for "from url" and "file upload" upgrades.
                    state = 'waitingToStart'
                    # At this point, installUpgrade() will be called and the HTTP transfer
                    # will begin. The browser will continue to request upgradeMeterStatus() for
                    # updates.
                    # The upgradeState session variable change to ('url','<filename>') occurs
                    # in installUpgrade(), not here. This is because there may be a race condition
                    # between upgradeMeterStatus() and installUpgrade()
                    # The state is set for "from file" upgrades in upgradeMeterStatus() instead because
                    # installUpgrade() is not run until after the image file was finished uploading,
                    # providing enough time for upgradeMeterStatus() to set the new state before
                    # installUpgrade() runs.
                elif fields.get('installUpgradeFrom') == 'file':
                    # Get the uploaded file's base (original) name and the temp file's name.
                    fileField = fields.get(FormUtils.makeUploadFieldName(
                                                      'applianceUpgradesTmpDir', 'installUpgradeFile'))
                    baseName = FormUtils.fileBaseName(fileField)
                    self.session().setValue('upgradeState', ('file', baseName))
                    desc  = 'Waiting to begin upload.'
                    state = 'waitingToStart'
                    # At this point, the file upload from the browser will start. The browser
                    # will continue to request upgradeMeterStatus() for status, and then
                    # setupApplianceUpgrade() will be called after the upload is complete.
                else:
                    raise AssertionError, "upgradeMeterStatus() passed an invalid value for " \
                    "the installUpgradeFrom field: %s" % (fields.get('installUpgradeFrom'))
            else:
                # This is a regular request for the current status of the upgrade process, and not
                # a request to initiate an upgrade.
                if upgradeState is None:
                    desc = 'Done.'
                    state = 'done'
                elif type(upgradeState) == type( () ):
                    # Value of session var upgradeState is ('url'|'file', '<filename>')
                    if upgradeState[0] == 'url':
                        baseName = upgradeState[1]
                        if not os.path.exists(os.path.join(IMAGE_DIR_PATH, baseName)):
                            # This clause could potentially happen if an AJAX status request occurs between the
                            # setting of upgradeState and the file from the transfer actually being
                            # created. This is uncommon, but does happen. In this case, the file size
                            # info will not be available, so we display a generic description.
                            desc = 'Starting the transfer.'
                        else:
                            bytesTransferredSoFar = os.stat(os.path.join(IMAGE_DIR_PATH, baseName)).st_size
                            desc = 'Transferring: ' + FormUtils.prettyFileSize(bytesTransferredSoFar)
                        state = 'transferring'
                    elif upgradeState[0] == 'file':
                        baseName = upgradeState[1]
                        tempName = FormUtils.findTempFileName(APP_UPGRADE_TMP_DIR, baseName)
                        tempFileSize = FormUtils.getFileSize(APP_UPGRADE_TMP_DIR, tempName)
                        desc  = FormUtils.getProgressText(tempName, tempFileSize)
                        state = 'transferring'
                    else:
                        raise AssertionError, "Invalid value for self.session().value('upgradeState')[0] detected: %s" % (upgradeState[0])
                elif upgradeState == 'installing':
                    # There is no specific progress information for the installing phase, so we just
                    # send back the description "Installing upgrade image."
                    state = 'installing'
                    desc  = 'Installing upgrade image.'
                else:
                    raise AssertionError, "Session variable upgradeState has an invalid value: %s" % (upgradeState)

        result = self.doc.createElement('upgradeProgress')
        result.setAttribute('state', state)
        result.setAttribute('description', desc)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupAppliance_license.psp:
    #
    # licenses
    #
    # <licenses>
    #   <license id="" key="" desc="" status="" installDateTime="" installMethod=""/>
    # </licenses>
    #
    # There's some data manipulation here.  First output the features,
    # then the remaining licenses.
    #
    # The parent xmldata class is responsible for supplying
    # licenseFeatures() and licenseDesc(), because those are product
    # specific and the parent xmldata class is closely linked with the
    # product.
    #
    def licenses(self):
        licenseNodes = Nodes.getMgmtSetEntriesDeep(self.mgmt, '/license/key')
        table = self.getXmlTable(False, tagNames=('licenses', 'license'))
        table.open(self.request())

        missingFeatures = []
        for f in self.licenseFeatures(): #XXX/TDS should rename that function
            missingFeatures.append(f)    # to "distinguishedLicenseFeatures()".
        for id in licenseNodes:   # Numbers: 1, 2, 3,...
            fullkey = licenseNodes[id].get('license_key')
            status = 'Invalid'
            if licenseNodes[id].get('properties/valid') == 'true':
                expiration = licenseNodes[id].get('properties/end_date')
                if licenseNodes[id].get('properties/active') == 'true':
                    status = 'Valid'
                    if expiration:
                        status += ' through'
                else:
                    status = 'Expired'
                if expiration:
                    status += ' ' + expiration.split()[0]
            feature = licenseNodes[id].get('properties/feature')
            if feature in missingFeatures:
                missingFeatures.remove(feature)

            if feature:
                description = self.licenseDesc(feature, fullkey)
            else:
                # feature is None if license doesn't start with LK1- or LK2-.
                description = 'Unknown'
            if fullkey.startswith('LK2-') and description != 'Unknown':
                description = 'Evaluation ' + description
            installTime = licenseNodes[id]['properties/install_time']
            installDateTime = RVBDUtils.formatDateTimeInterval(installTime)
            installMethod = licenseNodes[id]['properties/install_method']
            table.addEntry(id=id,
                           key=fullkey,
                           desc=description,
                           status=status,
                           installDateTime=installDateTime,
                           installMethod=installMethod)

        # handle licenses that come from a license server
        # these cannot be removed by the user
        licenseFromServerNodes = Nodes.getMgmtSetEntriesDeep(self.mgmt, '/license/client/state/feature')
        for id in licenseFromServerNodes:
            license_name = licenseFromServerNodes[id].get('name')
            license_class = licenseFromServerNodes[id].get('class')
            license_active = licenseFromServerNodes[id].get('active')
            license_is_perpetual = \
                licenseFromServerNodes[id].get('is_perpetual')
            license_end = licenseFromServerNodes[id].get('end_datetime')
            if license_active == 'false':
                license_status = 'Invalid'
            elif license_is_perpetual == 'true':
                license_status = 'Perpetual'
            else:
                license_status = 'Valid through %s' % license_end
            license_info = self.licenseFromServerDesc(license_name, license_class)
            for license in license_info:
                table.addEntry(id='',
                               key=license_name,
                               desc=license[1],
                               status=license_status,
                               installDateTime='--',
                               installMethod='--')
                if license[0] in missingFeatures:
                    missingFeatures.remove(license[0])

        for f in missingFeatures:
            table.addEntry(id='',
                           key=' -- ',
                           desc=self.licenseDesc(f, ' -- '),
                           status='Not installed',
                           installDateTime='--',
                           installMethod='--')

        # Included feature licenses
        includedFeatures = self.includedLicenseFeatures()
        for feature in includedFeatures:
            table.addEntry(id='',
                           key='Included',
                           desc=feature,
                           status='Valid',
                           installDateTime='--',
                           installMethod='Included')
        table.close()

    # for setupAppliance_license.psp:
    #
    # licenses update status
    #
    # <licenses-update-status>
    #   <status success="" when="" message="" />
    # </licenses-update-status>
    #
    # Attempts a fetch action, then queries fetch status nodes
    #
    def licensesUpdateStatus(self):
        table = self.getXmlTable(False, tagNames=('licenses-update-status', 'status'))
        table.open(self.request())

        # Do the fetch.
        try:
            self.sendAction('/license/action/init_autolicense')

            # Get the results
            success = Nodes.present(self.mgmt, '/license/autolicense/state/last_attempt_success')
            message = Nodes.present(self.mgmt, '/license/autolicense/state/last_attempt_result')
            seconds = Nodes.present(self.mgmt, '/license/autolicense/state/last_attempt_time')
            when    = RVBDUtils.formatDateTimeInterval(seconds)
        except Exception, info:
            success = 'false'
            message = info
            when = ''

        table.addEntry(success=success, when=when, message=message)
        table.close()

    def saveConfig(self):
        def internal(responseEl):
            try:
                self.sendAction('/mgmtd/db/save')
            except NonZeroReturnCodeException, e:
                responseEl.setAttribute('errorMsg', str(e))
        self.remoteCallWrapper(internal)

    # <servers>
    #   <server name="22.22.22.22" port="80" priority="1">
    # </servers>
    def cloudLicenseServers(self):
        path = self.cmcPolicyRetarget('/license/server/config')
        servers = Nodes.getMgmtSetEntries(self.mgmt, path)
        result = self.doc.createElement('servers')

        serverList = []
        for server, attribs in servers.iteritems():
            serverEl = self.doc.createElement('server')
            serverEl.setAttribute('name', server)
            serverEl.setAttribute('port', attribs['port'])
            serverEl.setAttribute('priority', attribs['priority'])
            serverList.append(serverEl)
        serverList.sort(key=lambda x: x.getAttribute('priority'))
        for serverEl in serverList:
            result.appendChild(serverEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    ## For RPC functional testing.
    #
    # This returns a JSON object via XMLContent.rpcWrapper() for the
    # purpose of testing the RPC mechanism.  There is one required
    # field, @c action, that determines what it returns:
    #
    # - @c echo - @c success is @c true and @c response is an object
    #   containing all of the fields that were sent to the server.
    # - @c timeout - Sleep for 2 seconds.  @c success is @c true and
    #   @c response is an object containing all of the fields that
    #   were sent to the server.
    # - @c error - @c success is @c false and @c errorMsg is
    #   "foobarbaz".
    # - @c echo - @c success is @c true and @c response the first 100
    #   characters from the file that was passed in the @c file field.
    #
    # @sa XMLContent.rpcWrapper() for the format of the JSON response.
    def rpcTest(self):

        def internal(**kw):

            if kw['action'] == 'echo':
                return kw

            elif kw['action'] == 'timeout':
                time.sleep(2)
                return kw

            elif kw['action'] == 'error':
                assert False, 'foobarbaz'

            elif kw['action'] == 'file':
                return kw['file'].value[:100]

        self.rpcWrapper(internal)

def compareRoutes(r1, r2):
    ip1, m1 = r1.split('\\/')
    ip2, m2 = r2.split('\\/')
    c = FormUtils.compareIpv4(ip1, ip2)
    if 0 == c:
        return cmp(m1, m2)
    return c

# Return the total size of all the upload files, in bytes.
def uploadSize():
    base = '/var/tmp'
    prefix = 'tmp_upload_'
    bytes = 0
    for name in os.listdir(base):
        if name.startswith(prefix):
            bytes += os.path.getsize('%s/%s' % (base, name))
    return bytes
