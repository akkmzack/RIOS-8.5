# Copyright 2006, Riverbed Technology, Inc., All rights reserved.
##
## Host support for gui and xmldata.
## Author: Don Tillman

import re
import os
import sys
import time
import xml.dom
import NicFactory

import RVBDUtils
import FormUtils
import HostUtils
import Nodes
import SessionRBTStore
from RVBDUtils import isSH
from gclclient import NonZeroReturnCodeException
from PagePresentation import PagePresentation
from XMLContent import XMLContent
from JSONContent import JSONContent
from common import lc_ipv6addr_str_canonicalize as canonicalizeIpv6Addr
from common import ltc_encrypt_password_two_way

import OSUtils
import Logging
import WebUtils.FieldStorage as FieldStorage

# Adding a directory for temp files for software upgrades.
APP_UPGRADE_TMP_DIR = '/var/tmp/appUpgrades'
OSUtils.safeMkdir(APP_UPGRADE_TMP_DIR) # clear out any preexisting temp files.
FieldStorage.tempdirMap['applianceUpgradesTmpDir'] = APP_UPGRADE_TMP_DIR

_IMAGE_DIR_PATH = '/var/opt/tms/images'
_TEMP_IMAGE_DIR_PATH = '/var/opt/tms/image_version/.tmpdir'

## Return the pretty Status message and Name of a CSS Class to apply to a license
#
# The status and style (color) changes depending on whether the license
# is not yet active, expiring (2 weeks remaining to expire) or expired.
# Expected format of date params: YYYY/MM/DD HH:MM:SS
#
# @param starting
#   The start date of the license
# @param expiration
#   The expiry date of the license
# @param isActive
#   Indicates whether the license is currently active
def getPrettyStatusAndStyle(starting=None, expiration=None, isActive=False):
    expiringThreshold_sec = 2 * 7 * 24 * 60 * 60
    now = time.time()
    status = 'Invalid'
    expiry_style = ''

    if starting:
        starting_raw = time.mktime(time.strptime(starting, '%Y/%m/%d %H:%M:%S'))
    if expiration:
        expiration_raw = time.mktime(time.strptime(expiration, '%Y/%m/%d %H:%M:%S'))

    if isActive == True:
        status = 'Valid'
        if expiration:
            status += ' through ' + expiration.split()[0]
            # change style if license is expiring
            if now > expiration_raw - float(expiringThreshold_sec):
                expiry_style = 'statusWarning'
    # if it's not yet active, show when it starts
    elif starting and starting_raw > now:
        status = 'Valid starting ' + starting.split()[0]
        expiry_style = 'statusWarning'
    # if it has expired, show expiration date
    elif expiration and expiration_raw < now:
        status = 'Expired ' + expiration.split()[0]
        expiry_style = 'statusFailure'
    return status, expiry_style

class gui_Host(PagePresentation):
    # actions handled here
    actionList = ['setupHostSettings',
                  'setupHostDataInterfaces',
                  'setupHostInpath',
                  'setupHostInterfaces',
                  'setupHostInterfacesIPv6',
                  'setupHostInterfacesInpathCmc',
                  'setupHostInterfacesDataCmc',
                  'setupLicenses',
                  'setupFlexLicenses',
                  'setupVirtualKey',
                  'setupApplianceControl',
                  'setupApplianceConfig',
                  'setupApplianceUpgrade',
                  'setupCloudLicensing',
                  'setupDateTime']

    # Support for the Host Settings page:
    #     Hostname
    #     DNS Settings
    #     Host table
    #     Proxies
    #
    def setupHostSettings(self):
        fields = self.request().fields()
        mgmt = self.session().value('mgmt')
        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)
        if policyType:
            hosts_path = 'hosts/ipv4'
        else:
            hosts_path = 'hosts/ipaddr'

        if 'addHost' in fields:
            # add a host
            ip = canonicalizeIpv6Addr(fields['host_ip'])
            name = fields['host_name']
            if ip and name:
                path = '%s/%s/%s/host/%s' % (pathPrefix, hosts_path, ip, name)
                self.setNodes((path, 'hostname', name))
        elif 'removeHosts' in fields:
            # remove selected hosts
            base = '%s/%s' % (pathPrefix, hosts_path)
            FormUtils.deleteNodesFromConfigForm(mgmt, base, 'selectedHost_', fields)
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

    # Helper method for above; handle the proxy settings.
    def _setupHostSettings_proxy(self):
        # default, disabled values:
        host = '0.0.0.0'
        port = '1080'
        authUser = ''
        authPassword = ''
        authType = 'basic'
        fields = self.request().fields()
        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)

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
                if FormUtils.bogusPassword == authPassword and not policyType:
                    authPassword = self.sendAction(
                        '/web/proxy/actions/get_decrypted_password')['passwd']

        if policyType:
            # Set web proxy nodes for CMC
            base = self.cmcPolicyRetarget('/web/proxy')
            nodes = []
            if FormUtils.bogusPassword != authPassword:
                ltc_2_way = ltc_encrypt_password_two_way(authPassword)
                nodes = [('%s/passwd' % base, 'string', ltc_2_way)]
            nodes += [('%s/address' % base, 'hostname', host),
                     ('%s/port' % base, 'uint16', port),
                     ('%s/username' % base, 'string', authUser),
                     ('%s/authtype' % base, 'string', authType)]
            self.setNodes(*nodes)
        else:
            # This is for SH
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
            numPart =   iface[len('inpath'):]                   # e.g. '0_0' or '0_1'
            dhcp =      fields.get('inpath_dhcp', 'false')
            manIp =     (dhcp == 'false') and fields['inpath_manIp'] or ''
            manSubnet = (dhcp == 'false') and fields['inpath_manSubnet'] or ''
            gateway =   (dhcp == 'false') and fields['inpath_gateway'] or ''
            gatewayNodePath = '/rbt/route/config/%s/ipv4/prefix/0.0.0.0\\/0' % iface

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
                nodes.append((netConf + '/%s/addr/ipv4/static/1/mask_len' % iface, 'uint8',
                                str(FormUtils.ipv4ParseNetMask(manSubnet))))
            elif 'inpath_manIPv6Enable' in fields:
                # We're in IPv6-only mode so delete the IPv4 ip and subnet mask.
                nodes.append((netConf + '/%s/addr/ipv4/static/1' % iface, 'none', ''))

            # gateway is optional (even when not using dhcp)
            if gateway:
                nodes.append((gatewayNodePath + '/gw', 'ipv4addr', gateway))
            else:
                nodes.append((gatewayNodePath, 'none', ''))

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

            # IPv6 settings
            if ('inpath_manIPv6Addr' not in fields) or \
               (Nodes.present(mgmt, '/net/interface/config/%s/addr/ipv6/static/%s' % (iface, canonicalizeIpv6Addr(fields['inpath_manIPv6Addr']))) != canonicalizeIpv6Addr(fields['inpath_manIPv6Addr'])):
                # Only delete the nodes if a new address is being used. If the
                # same address is used and only the IPv6 gateway is being changed,
                # deleting these nodes will unnecessarily trigger a "restart the
                # optimization service" message because the address was deleted.
                self.deleteNodes('/net/interface/config/%s/addr/ipv6/static/*' % iface)
            gatewayNodePath = '/rbt/route/config/%s/ipv6/prefix/::\\/0' % iface

            ipv6Bindings = [(gatewayNodePath, 'none', '')]
            if 'inpath_manIPv6Enable' in fields:
                address = canonicalizeIpv6Addr(fields['inpath_manIPv6Addr'])
                prefix = self.fields['inpath_manIPv6Prefix']
                ipv6Bindings.append(('/net/interface/config/%s/addr/ipv6/static/%s/mask_len' % (iface, address),
                                    'uint8', prefix))

                gateway = self.fields['inpath_manIPv6Gateway']
                if gateway:
                    ipv6Bindings.append((gatewayNodePath + '/gw', 'ipv6addr', gateway))

            self.adjustInterface_subnetGateway()
            FormUtils.setNodesFromConfigForm(mgmt, fields, *ipv6Bindings)

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
        elif 'addRouteIPv6' in fields:
            inpath = fields.get('inpath_name')
            dest = canonicalizeIpv6Addr(fields['addRouteIPv6_destIPv6'])
            netmask = fields['addRouteIPv6_prefixIPv6']
            gw = fields['addRouteIPv6_gatewayIPv6']
            node = '%s/%s/ipv6/prefix/%s\\/%s/gw' % (base, inpath, dest, netmask)
            self.setNodes((node, 'ipv6addr', gw))
        elif 'removeRoutesIPv6' in fields:
            inpath = fields.get('inpath_name')
            prefix = '%s/%s/ipv6/prefix' % (base, inpath)
            FormUtils.deleteNodesFromConfigForm(mgmt, prefix, 'selectedRouteIPv6_', fields)

        elif 'apply' in fields:
            # Sets the "link state propagation" checkbox
            FormUtils.setNodesFromConfigForm(mgmt, fields)

    # Data Interfaces
    def setupHostDataInterfaces(self):
        fields = self.fields
        mgmt = self.mgmt
        base = self.cmcPolicyRetarget('/rbt/route/config')
        if 'editDataInterface' in fields:
            # changing one of the data interface's settings
            iface =     fields['data_name']
            numPart =   iface[len('eth'):] # e.g. '0_0' or '0_1'
            manIp =     fields['data_manIp'] or ''
            manSubnet = str(FormUtils.ipv4ParseNetMask(fields['data_manSubnet'])) or ''
            gateway =   fields['data_gateway'] or ''
            gatewayNodePath = '/rbt/route/config/%s/ipv4/prefix/0.0.0.0\\/0/gw' % iface

            # these don't apply to all interfaces
            speed =  fields.get('data_speed')
            duplex = fields.get('data_duplex')
            mtu =    fields.get('data_mtu')

            netConf =   '/net/interface/config'

            nodes = [(netConf + '/eth%s/type/ethernet/speed' % numPart,  'string',  speed),
                     (netConf + '/eth%s/type/ethernet/duplex' % numPart, 'string',  duplex),
                     (netConf + '/%s/mtu' % iface,                       'uint16',  mtu)]

            if manIp != '' and manSubnet != '':
                # not using dhcp, so set the ip and subnet nodes.
                nodes.append((netConf + '/%s/addr/ipv4/static/1/ip' % iface,       'ipv4addr', manIp))
                nodes.append((netConf + '/%s/addr/ipv4/static/1/mask_len' % iface, 'uint8',    manSubnet))

            # gateway is optional (even when not using dhcp)
            if gateway:
                nodes.append((gatewayNodePath, 'ipv4addr', gateway))

            # IPv6 settings
            if 'data_manIPv6Enable' in fields:
                address = canonicalizeIpv6Addr(fields['data_manIPv6Addr'])
                prefix = fields['data_manIPv6Prefix']

                # Delete the old ipv6 address and add the new one
                nodes.append(('/net/interface/config/%s/addr/ipv6/static/*' % iface, 'none', ''))
                nodes.append(('/net/interface/config/%s/addr/ipv6/static/%s/mask_len' % (iface, address), 'uint8', prefix))

                # Add the default gateway
                gateway = canonicalizeIpv6Addr(fields['data_manIPv6Gateway'])
                nodes.append(('/rbt/route/config/%s/ipv6/prefix/::\\/0/gw' % iface, 'ipv6addr', gateway))
            else:
                # Delete the IPv6 settings if 'Assign IPv6 Address' is un-checked
                nodes.append(('/net/interface/config/%s/addr/ipv6/static/*' % iface, 'none', ''))

            self.adjustInterface_subnetGateway()
            Nodes.set(mgmt, *Nodes.removeNullBindings(nodes))

        elif 'addRoute' in fields:
            data_name = fields.get('data_name')
            dest = fields.get('addRoute_dest')
            netmask = fields.get('addRoute_netmask')
            mask = FormUtils.ipv4ParseNetMask(netmask)
            gw = fields.get('addRoute_gateway')
            node = '%s/%s/ipv4/prefix/%s\\/%s/gw' % (base, data_name, dest, mask)
            self.setNodes((node, 'ipv4addr', gw))
        elif 'removeRoutes' in fields:
            data_name = fields.get('data_name')
            prefix = '%s/%s/ipv4/prefix' % (base, data_name)
            FormUtils.deleteNodesFromConfigForm(mgmt, prefix, 'selectedRoute_', fields)
        elif 'addRouteIPv6' in fields:
            data_name = fields.get('data_name')
            dest = canonicalizeIpv6Addr(fields['addRouteIPv6_destIPv6'])
            netmask = fields['addRouteIPv6_prefixIPv6']
            gw = fields['addRouteIPv6_gatewayIPv6']
            node = '%s/%s/ipv6/prefix/%s\\/%s/gw' % (base, data_name, dest, netmask)
            self.setNodes((node, 'ipv6addr', gw))
        elif 'removeRoutesIPv6' in fields:
            data_name = fields.get('data_name')
            prefix = '%s/%s/ipv6/prefix' % (base, data_name)
            FormUtils.deleteNodesFromConfigForm(mgmt, prefix, 'selectedRouteIPv6_', fields)
        elif 'apply' in fields:
            FormUtils.setNodesFromConfigForm(mgmt, fields)

    # Interfaces
    def setupHostInterfaces(self):
        fields = self.fields
        mgmt = self.mgmt
        prefix = self.cmcPolicyRetarget('/net/routes/config/ipv4/prefix')
        policyName, cmcPathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields);

        if 'apply' in fields:
            ipv6Bindings = []
            for iface in ('primary', 'aux'):
                ipv6Bindings.append(
                    (cmcPathPrefix +'/net/interface/config/%s/addr/ipv6/static/*' % iface,
                    'none', ''))
                if ('enable%sIpv6' % iface) in fields:
                    address  = canonicalizeIpv6Addr(fields['%s_manIPv6Addr' % iface])
                    prefix = self.fields['%s_manIPv6Prefix' % iface]
                    ipv6Bindings.append(
                        (cmcPathPrefix + '/net/interface/config/%s/addr/ipv6/static/%s/mask_len' %
                         (iface, address),
                         'uint8', prefix))

            self.adjustInterface_subnetGateway()
            FormUtils.setNodesFromConfigForm(mgmt, fields, *ipv6Bindings)

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
            dest = canonicalizeIpv6Addr(fields['addRouteIPv6_destIPv6'])
            ipPrefix = fields['addRouteIPv6_prefixIPv6']

            # Gateway can be optional (Gateway OR interface must be specified)
            gw = fields.get('addRouteIPv6_gatewayIPv6')
            gw = gw and canonicalizeIpv6Addr(gw) or '::'

            index = Nodes.arrayElementForAdd(
                mgmt,
                '%s/%s\\/%s/nh' % (prefix, dest, ipPrefix),
                'gw',
                gw)

            node = '%s/%s\\/%s/nh/%s' % (prefix, dest, ipPrefix, index)
            iface = fields['addRouteIPv6_interfaceIPv6']
            if iface == 'auto':
                self.setNodes(('%s/gw' % node, 'ipv6addr', gw))
            else:
                self.setNodes(('%s/gw' % node, 'ipv6addr', gw),
                              ('%s/interface' % node, 'string', iface))
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
        policyName, prefixPath, policyType = Nodes.cmcDecodeNodeMode(fields)
        applianceName, applianceProduct, applianceSerialNum = \
                Nodes.parseApplianceParam(policyName)
        ic_policy_page = (applianceProduct == "ib")
        bypassNodes = []
        ipv6Nodes = []

        for ifaceNum in Nodes.allInterfaceIndices:
            iface = "inpath" + ifaceNum
            if ic_policy_page:
                # delete inpathX_Y interfaces Enable Bypass nodes.
                # if the node is 'true' then enable bypass is disabled (unchecked) & vice-versa.
                # Hence, these enable nodes have to tbe deleted.
                bypassNodes.append((prefixPath + \
                 '/rbt/interface/config/inpath/%s/enable' % iface, 'none', ''))
                if '%s_inpathBypass' % iface in fields:
                    bypass = fields['%s_inpathBypass' % iface]
                    inpathEnable = bypass == 'true' and 'false' or 'true'
                    bypassNodes.append((prefixPath + '/rbt/interface/config/inpath/%s/enable' % iface, 'bool', inpathEnable))
            else :
                # Steelhead appliance specific policy page only. IC doesnt have ipv6 address.
                # delete inpathX_Y interfaces IPv6 address.
                ipv6Nodes.append((prefixPath + \
                 '/net/interface/config/%s/addr/ipv6/static/*' % iface,'none',''))
                ipv6Nodes.append((prefixPath + \
                 '/rbt/route/config/%s' % iface, 'none', ''))
                if 'enable%sIpv6'% iface in fields:
                    address = canonicalizeIpv6Addr(fields['%s_manIPv6Addr' % iface])
                    prefix = fields['%s_manIPv6Prefix' % iface]
                    if fields['%s_manIPv6Gateway' % iface]:
                        gateway = canonicalizeIpv6Addr(fields['%s_manIPv6Gateway' % iface])
                        ipv6Nodes.append((prefixPath + '/rbt/route/config/%s/ipv6/prefix/::\\/0/gw' % iface, 'ipv6addr', gateway))
                    ipv6Nodes.append((prefixPath + '/net/interface/config/%s/addr/ipv6/static/%s/mask_len' % (iface, address), 'uint8', prefix))

        if 'apply' in fields:
            self.adjustInterface_subnetGateway()
            FormUtils.setNodesFromConfigForm(self.mgmt, fields, *ipv6Nodes)
            FormUtils.setNodesFromConfigForm(self.mgmt, fields, *bypassNodes)

            # remove the nodes for interfaces not being included
            ifacePrefix = self.cmcPolicyRetarget('/net/interface/config')
            ifaces = Nodes.getMgmtLocalChildrenNames(self.mgmt, ifacePrefix)
            dels = []
            # these all have I_J appended to them
            delPrefixes = ['/net/interface/config/inpath',
                           '/net/interface/config/lan',
                           '/net/interface/config/wan',
                           '/rbt/route/config/inpath',
                           '/rbt/sport/intercept/config/ifaces/inpath/inpath']
            if ic_policy_page:
                delPrefixes.append('/rbt/wdt/config/interface/')

            for iface in ifaces:
                if iface.startswith('inpath'):
                    ifi = iface[len('inpath'):]
                    if ('cmcIface_inpath' + ifi) not in self.fields:
                        for delPref in delPrefixes:
                            dels.append(self.cmcPolicyRetarget(delPref + ifi))
            self.deleteNodes(*dels)

    # CMC Version of data ifaces
    def setupHostInterfacesDataCmc(self):
        fields = self.fields
        policyName, prefixPath, policyType = Nodes.cmcDecodeNodeMode(fields)
        ipv6Nodes = []

        for ifaceNum in Nodes.allDataInterfaceIndices:
            iface = "eth" + ifaceNum
            # EX appliance specific policy page only.
            # delete ethX_Y interfaces IPv6 address.
            ipv6Nodes.append((prefixPath + \
                 '/net/interface/config/%s/addr/ipv6/static/*' % iface,'none',''))
            if 'enable%sIpv6'% iface in fields:
                address = canonicalizeIpv6Addr(fields['%s_manIPv6Addr' % iface])
                prefix = fields['%s_manIPv6Prefix' % iface]
                gateway = canonicalizeIpv6Addr(fields['%s_manIPv6Gateway' % iface])
                ipv6Nodes.append((prefixPath + '/net/interface/config/%s/addr/ipv6/static/%s/mask_len' % (iface, address), 'uint8', prefix))
                ipv6Nodes.append((prefixPath + '/rbt/route/config/%s/ipv6/prefix/::\\/0/gw' % iface, 'ipv6addr', gateway))

        if 'apply' in fields:
            self.adjustInterface_subnetGateway()
            FormUtils.setNodesFromConfigForm(self.mgmt, fields, *ipv6Nodes)

            # remove the nodes for interfaces not being included
            ifacePrefix = prefixPath + '/net/interface/config'
            ifaces = Nodes.getMgmtLocalChildrenNames(self.mgmt, ifacePrefix)
            # the 'eth' interfaces have x_y appended to them, where 1 <= x <= 5, 0 <= y <= 3
            delPrefixes = ['/net/interface/config/eth',
                           '/rbt/route/config/eth']

            dels = []
            for iface in ifaces:
                if iface.startswith('eth'):
                    ifi = iface[len('eth'):]
                    if ('cmcEthIface_eth' + ifi) not in self.fields:
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

    # Handle licenses here, including CMC's managed
    # appliance licenses.
    def setupLicenses(self):
        fields = self.fields
        mgmt = self.mgmt
        app_sn, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)

        if 'addLicense' in fields:
            licenses_str = fields.get('licenses', '')
            licenses = licenses_str.split()
            for license in licenses:
                # Use the action for product licenses and CMC's
                # managed appliance licenses.
                self.sendAction(pathPrefix + '/license/action/add_license', \
                                    ('license_key', 'string', license))

        elif 'removeLicense' in fields:
            idList = FormUtils.getPrefixedFieldNames('selectedLicense_', fields)
            idList = [int(id) for id in idList]
            idList.sort()
            idList.reverse()

            # Handle a CMC's managed appliance licenses
            if policyType == 'editAppliancePolicy':
                basepath = self.cmcPolicyRetarget('/license/key')

                # List nodes attributes and their types
                nodeSpec= {'license_key': 'string',
                           'properties/install_time': 'uint32',
                           'properties/install_method': 'string'}

                # Remove license key from the appliance license array.
                Nodes.editNodeSequence(self.mgmt, basepath, nodeSpec, 'remove', idList)

            # Handle product licenses (including CMC'c own licenses)
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
        action = self.mgmt.get(
            '/rbt/sport/hardware/state/spec/all/%s/action_needed' % specName)
        self.sendAction('/rbt/sport/hardware/action/activate_spec', ('spec_id', 'string', specName))
        if action == "reboot" or action == "reboot-granite" :
            self.response().sendRedirect('/mgmt/logout?reason=reboot')
        elif action == "hardware-replace":
            self.response().sendRedirect('/mgmt/logout?reason=shutdown')
        else:
            for i in range(30):
                if self.mgmt.get(
                    '/rbt/sport/hardware/state/model_upgrade_running')=="false":
                    break
                time.sleep(1)

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
            if 'scheduleForLaterTime' in fields:
                date, time = fields['scheduleForLaterTime'].split(' ')
                command = ('applianceClean' in fields) and 'reload clean' or 'reload'

                Nodes.scheduleJob(self.mgmt,
                                  'Reboot',
                                  'Scheduled appliance reboot',
                                  date,
                                  time,
                                  [command])

                self.setActionMessage('Appliance reboot has been scheduled.')
            else:
                if 'applianceClean' in fields:
                    self.applianceControlCleanSegmentStore()
                args = 'esxiResponse' in fields and [('force', 'bool', 'true')] or []
                self.sendAction('/pm/actions/reboot', *args)
                self.response().sendRedirect('/mgmt/logout?reason=reboot')
        # shutdown
        elif 'applianceShutdown' in fields:
            if 'scheduleForLaterTime' in fields:
                date, time = fields['scheduleForLaterTime'].split(' ')
                command = ('applianceClean' in fields) and 'reload clean halt' or 'reload halt'

                Nodes.scheduleJob(self.mgmt,
                                  'Shutdown',
                                  'Scheduled appliance shutdown',
                                  date,
                                  time,
                                  [command])

                self.setActionMessage('Appliance shutdown has been scheduled.')
            else:
                if 'applianceClean' in fields:
                    self.applianceControlCleanSegmentStore()
                self.sendAction('/pm/actions/shutdown')
                self.response().sendRedirect('/mgmt/logout?reason=shutdown')

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
                # importId depends on the product
                # (explained in bugs 119025/49856)
                if RVBDUtils.isSH():
                    importId = 'rbt'
                elif RVBDUtils.isCMC():
                    importId = 'rbt_cmc'
                elif RVBDUtils.isGW():
                    importId = 'rbt_gw'
                elif RVBDUtils.isIB():
                    importId = 'rbt_ib'
                elif RVBDUtils.isWW():
                    importId = 'rbt_cb'
                elif RVBDUtils.isGraniteSupported():
                    importId = 'rbt_dva'
                else:
                    raise 'Configuration import is not supported.'

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
                                    ('import_id', 'string', importId))
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
                            ('location_id', 'uint32', otherPartition))
        elif 'cancelSwitch' in fields:
            # handle cancel
            self.sendAction('/image/boot_location/nextboot/set',
                            ('location_id', 'uint32', thisPartition))
        elif 'upgradeMeterSubmit' in fields:
            # handle install
            self.installUpgrade(thisPartition, otherPartition)

    # installUpgrade() is called by setupApplianceUpgrade(). This method is run after the upgrade image
    # file has been uploaded (for "from local file" upgrades) or after the form has been submitted (for
    # "from url" upgrades). The AJAX method that returns the status of the upload/upgrade is
    # upgradeMeterStatus().
    #
    def installUpgrade(self, thisPartition, otherPartition):
        upgradeState = self.session().value('upgradeState', None) # syntactic sugar

        def fromSupportSiteUpgrade():
            # Handle a differential upgrade from the remote support site.
            version = fields.get('targetUpgradeVersion', None)
            if not version:
                raise Exception
            baseName = 'support_image.img'

            self.session().setValue('upgradeState', ('support', baseName))

            # Delete the old image file
            self.sendAction('/image/delete',
                            ('image_name', 'string', baseName))

            # Immediately begin file transfer:
            if 'installUpgradeLater' not in fields:
                try:
                    self.sendAction('/image/fetch',
                                    ('version', 'string', version),
                                    ('image_name', 'string', baseName))
                except NonZeroReturnCodeException, info:
                    OSUtils.log(Logging.LOG_NOTICE,
                                'Failed to fetch image from support site.')
                    raise

            return baseName

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
            self.sendAction('/image/delete',
                            ('image_name', 'string', baseName))
            self.session().setValue('upgradeState', ('url', baseName))

            # immediately begin file transfer:
            if 'installUpgradeLater' not in fields:
                try:
                    self.sendAction('/image/fetch',
                                    ('remote_url', 'string', url),
                                    ('image_name', 'string', baseName))
                except NonZeroReturnCodeException, info:
                    # Most likely cause for error is a 404.
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
            FormUtils.handleLocalFileUpload(imageField, _IMAGE_DIR_PATH, baseName)

            if 'installUpgradeLater' not in fields:
                self.sendAction('/image/fetch',
                                ('remote_url', 'string', 'file://' + _IMAGE_DIR_PATH + '/' + baseName),
                                ('image_name', 'string', baseName))

            return baseName


        fields = self.fields

        if 'file' == fields.get('installUpgradeFrom', ''):
            baseName = fromLocalFileUpgrade()
        elif 'support' == fields.get('installUpgradeFrom'):
            try:
                baseName = fromSupportSiteUpgrade()
            except Exception:
                self.setFormError('Unable to connect to Riverbed support site.')
                return
        elif 'url' == fields.get('installUpgradeFrom'):
            try:
                # needs to be called after scheduling a "from url"
                # upgrade task, so we don't transfer the file twice.
                baseName = fromURLUpgrade()
            finally:
                if self.session().hasValue('upgradeState'):
                    self.session().delValue('upgradeState')
        else:
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
            elif 'support' == fields.get('installUpgradeFrom'):
                version = fields.get('targetUpgradeVersion', '').strip()
                sourceMsg = 'from Riverbed support site.'
                scheduledTasks = ['image fetch version %s %s' % (version, baseName),
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
                            ('image_name', 'string', baseName))
            self.sendAction('/image/boot_location/nextboot/set',
                            ('location_id', 'uint32', otherPartition))
        finally:
            if self.session().hasValue('upgradeState'):
                self.session().delValue('upgradeState')
        self.setActionMessage('Successfully installed upgrade image. Please <a href="/mgmt/gui?p=setupAppliance_shutdown">reboot the appliance</a> to complete the upgrade.', safe=True)

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

    # Support for Date Time page
    #
    def setupDateTime(self):
        fields = self.request().fields()
        mgmt = self.session().value('mgmt')
        if 'addNtpServer' in fields:
            # add an NTP server
            host = fields['ntpServer_host']
            version = fields['ntpServer_version']
            enable = fields['ntpServer_enable']
            # Get authentication key ID. '0' represents no authentication key.
            keyid = fields['ntpServer_keyid'] if fields['ntpServer_keyid'] else '0'
            base = self.cmcPolicyRetarget('/ntp/server/address')
            nodes = [('%s/%s/enable' % (base, host), 'bool', enable),
                     ('%s/%s/key' % (base, host), 'uint32', keyid),
                     ('%s/%s/version' % (base, host), 'uint32', version)]
            self.setNodes(*nodes)
        elif 'removeNtpServers' in fields:
            # remove NTP servers
            base = self.cmcPolicyRetarget('/ntp/server/address')
            FormUtils.deleteNodesFromConfigForm(mgmt, base, 'selectedNtpServer_', fields)
        elif 'addNtpAuth' in fields:
            # add an NTP authentication key
            key = fields['ntpAuth_keyid']
            keyType = fields['ntpAuth_keyType']
            secret = fields['ntpAuth_secret']

            # The secret text can be one of the following:
            # - A 1- to 16-character ASCII string for MD5
            # - A 40-character HEX string for MD5/SHA1
            # - A 44+ character base64 string for MD5/SHA1 (AKA "Hash")
            #   Use setNodes() to save a hash. No encryption necessary.
            isPlainText = len(secret) <= 40

            base = self.cmcPolicyRetarget('/ntp')
            policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)
            if isPlainText:
                if policyType:
                    # Encrypt secret manually for CMC
                    vals = self.sendAction('/ntp/action/encrypt_secret',
                                        ('secret', 'string', secret))
                    if vals:
                        secret = vals.get('secret')
                        isPlainText = False
                else:
                    try:
                        # We attempt to use an action to set the key. Errors can occur and if one
                        # particular error comes back we can safely downgrade it to a warning and
                        # complete the operation. Otherwise, we kick it upstairs.
                        self.sendAction('/ntp/action/add_key',
                                        ('secret', 'string', secret),
                                        ('type', 'string', keyType),
                                        ('key', 'uint32', key))
                    except NonZeroReturnCodeException, info:
                        if str(info).rstrip() == 'Authentication keys with type MD5 should not be used in FIPS mode.':
                            self.setActionMessage(info)
                        else:
                            raise

                    # Keys set via the UI are automatically trusted.
                    self.setNodes(('%s/trustedkeys/%s' % (base, key), 'uint32', key))

            # If the secret is a hash then we should set the nodes directly.
            if not isPlainText:
                self.setNodes(('%s/keys/%s' % (base, key), 'uint32', key),
                              ('%s/keys/%s/secret' % (base, key), 'string', secret),
                              ('%s/keys/%s/type' % (base, key), 'string', keyType),
                              ('%s/trustedkeys/%s' % (base, key), 'uint32', key))

        elif 'removeNtpAuths' in fields:
            # remove NTP authentication key
            base = self.cmcPolicyRetarget('/ntp/keys')
            FormUtils.deleteNodesFromConfigForm(mgmt, base, 'selectedNtpAuth_', fields)
            # remove NTP trusted key
            base = self.cmcPolicyRetarget('/ntp/trustedkeys')
            FormUtils.deleteNodesFromConfigForm(mgmt, base, 'selectedNtpAuth_', fields)
        elif 'apply' in fields:
            # Set the nodes. This has to happen before manually setting the time.
            FormUtils.setNodesFromConfigForm(mgmt, fields)
            # These 'target' variables are set to either None if that setting
            # doesn't need to be changed or the new setting.

            targetDate = None
            targetTime = None
            targetTimeZone = None

            # For cmc, timezone is in a separate policy page, and may not be in the fields.
            # Handling timezone last as this causes webasd to restart.
            if 'timezone' in fields and fields['timezone'] != mgmt.get('/time/zone'):
                targetTimeZone = fields['timezone']

            # Setting the time manually?
            ntpPath = 'b' + self.cmcPolicyRetarget('/ntp/enable')
            if ntpPath in fields and fields[ntpPath] == 'false':
                if 'changeDate' in fields and fields.get('date', None) != mgmt.get('/time/now/date'):
                    targetDate = fields.get('date', None)
                if 'changeTime' in fields and fields.get('time', None) != mgmt.get('/time/now/time'):
                    targetTime = fields.get('time', None)

            # There's an action for setting the time, date or datetime.
            # The one we invoke depends on what needs to be changed.
            # The gotcha is that a timezone change requires an immediate
            # and automatic webasd restart.
            if targetDate or targetTime:
                params = []
                if targetDate and targetTime:
                    action = 'datetime'
                    params.append(('datetime', 'datetime_sec', '%s %s' % (targetDate, targetTime)))
                elif targetTime:
                    action = 'time'
                    params.append(('time', 'time_sec', targetTime))
                else:
                    action = 'date'
                    params.append(('date', 'date', targetDate))
                if targetTimeZone:
                    params.append(('zone', 'string', targetTimeZone))
                    self.sendAction('/time/set/%s' % action, *params)
                else:
                    SessionRBTStore.SessionRBTStore.startTimeWarp()
                    self.sendAction('/time/set/%s' % action, *params)
                    SessionRBTStore.SessionRBTStore.endTimeWarp(self.transaction())
            elif targetTimeZone:
                self.setNodes((self.cmcPolicyRetarget('/time/zone'), 'string', targetTimeZone))
        else:
            # Handle submission for enabling NTP Servers
            host, enable = FormUtils.getPrefixedField('ntpServer_enable_', fields)
            if host:
                base = self.cmcPolicyRetarget('/ntp/server/address')
                self.setNodes(('%s/%s/enable' % (base, host), 'bool', enable))

            # Handle submission for enabling NTP Peers
            host, enable = FormUtils.getPrefixedField('ntpPeer_enable_', fields)
            if host:
                base = self.cmcPolicyRetarget('/ntp/peer/address')
                self.setNodes(('%s/%s/enable' % (base, host), 'bool', enable))

            # Handle submission for trusting NTP Authentication Keys
            key, trusted = FormUtils.getPrefixedField('ntpAuth_trusted_', fields)
            if key:
                base = self.cmcPolicyRetarget('/ntp')
                if trusted == 'true':
                    nodes = [('%s/trustedkeys/%s' % (base, key), 'uint32', key)]
                    self.setNodes(*nodes)
                else:
                    nodes = ['%s/trustedkeys/%s' % (base, key)]
                    self.deleteNodes(*nodes)

class xml_Host(XMLContent):
    dispatchList = ['dynamicStatus',
                    'dataInterfaces',
                    'dnsHosts',
                    'hostConfigs',
                    'inpathInterfaces',
                    'inpathRoutes',
                    'inpathRoutesIPv6',
                    'mainRoutes',
                    'mainRoutesIPv6',
                    'ntpServers',
                    'ntpActivePeers',
                    'ntpPeers',
                    'ntpAuths',
                    'licenses',
                    'licensesUpdateStatus',
                    'upgradeMeterStatus',
                    'saveConfig',
                    'domainTestControl',
                    'cloudLicenseServers']
    dogKickerList = ['saveConfig',
                     'licensesUpdateStatus',
                     'upgradeMeterStatus']

    gatewayRE = re.compile("nh/(\d+)$")

    # Used for the dynamic header status.
    # Calls back into the headerDynamic psp file and xmlizes that.
    def dynamicStatus(self):
        # Recursively builds out xml based off nested dictionaries.
        def attributesFromDict(element, items):
            for key, value in items.iteritems():
                if isinstance(value, dict):
                    child = self.doc.createElement(key)
                    element.appendChild(child)
                    attributesFromDict(child, value)
                else:
                    element.setAttribute(key, value)

        # Record the current time as the last time we saw a dynamic status
        # request for this session.  See bug 121169 for more details.
        self.session().setValue('lastDynamicStatus', time.time())

        status = self.application().callMethodOfServlet(self.transaction(),
                                                        '/Templates/headerDynamic',
                                                        'getDynamicStatus')
        result = self.doc.createElement('status')
        attributesFromDict(result, status)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupHostSettings.psp, setupHostSettingsCMC.psp:
    #
    # The dnsHosts command.
    #
    # Result is of the form:
    # <hosts>
    #   <host ipaddr="22.22.22.22">
    #     <hostname name="skeezer"/>
    #     <hostname name="gleep"/>
    #   </host>
    # </hosts>
    #
    def dnsHosts(self):
        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(self.fields)
        path = '/hosts/ipaddr'
        if policyType:
            path = '%s/hosts/ipv4' % pathPrefix
        hostsDict = Nodes.getMgmtSetEntriesDeep(self.mgmt, path)
        hostIPs = hostsDict.keys()
        hostIPs.sort(FormUtils.alphanumericCompare)
        result = self.doc.createElement('hosts')
        for ip in hostIPs:
            hostElement = self.doc.createElement('host')
            hostElement.setAttribute('ipaddr', ip)

            # We blank out the 'id' for the loopback addresses
            # so those entries can't be selected for deletion
            if ip != "127.0.0.1" and ip != "::1":
                hostElement.setAttribute('id', ip)

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

    # for setupHostInterfacesData.psp:
    #
    # <interfaces>
    #   <interface name=""
    #              dhcp=""
    #              ip=""
    #              subnet=""
    #              dataInterface=""
    #              manIp=""
    #              manSubnet=""
    #              gateway=""
    #              speed=""
    #              duplex=""
    #              negoSpeed=""
    #              negoDuplex=""
    #              speedOptions=""
    #              duplexOptions=""
    #              mtu="">
    #   ...
    # </interfaces>
    def dataInterfaces(self):
        result = self.doc.createElement('interfaces')
        mgmt = self.mgmt # syntactic sugar
        netState  = '/net/interface/state'
        netConf   = '/net/interface/config'

        dataInterfaces = [x for x in
                          Nodes.getMgmtLocalChildrenNames(mgmt,
                                                          self.cmcPolicyRetarget(netState))
                          if x.startswith('eth')]
        dataInterfaces = FormUtils.sortInterfacesByName(dataInterfaces)
        for iface in dataInterfaces:
            numPart = iface[len('eth'):] # e.g. '0_0' or '0_1'

            dhcp          = Nodes.present(mgmt, '%s/%s/addr/ipv4/dhcp' % (netConf, iface), 'false')
            manIp         = Nodes.present(mgmt, '%s/%s/addr/ipv4/static/1/ip' % (netConf, iface))
            manSubnet     = FormUtils.ipv4NetMask(Nodes.present(mgmt, '%s/%s/addr/ipv4/static/1/mask_len' % (netConf, iface)))
            ip            = Nodes.present(mgmt, '%s/%s/addr/ipv4/1/ip' % (netState, iface))
            subnetShort   = Nodes.present(mgmt, '%s/%s/addr/ipv4/1/mask_len' % (netState, iface))
            subnet        = FormUtils.ipv4NetMask(subnetShort)

            if ip and subnetShort:
                dataInterface = ip + '/' + subnetShort
            else:
                dataInterface = '--'

            ipv6Info = Nodes.getTreeifiedSubtree(mgmt, '/net/interface/config/%s/addr/ipv6/static' % iface)
            ipv6Enable = 'false'
            ipv6Addr = ''
            ipv6Prefix = ''
            ipv6Gateway = ''
            if len(ipv6Info) == 1:
                ipv6Enable = 'true'
                ipv6Addr = ipv6Info.keys()[0]
                ipv6Prefix = ipv6Info[ipv6Addr]['mask_len']
                ipv6Gateway = Nodes.present(mgmt, '/rbt/route/config/%s/ipv6/prefix/::\\/0/gw' % iface)
                dataInterface += ';%s/%s' % (ipv6Addr,ipv6Prefix)

            gateway       = Nodes.present(mgmt, '/rbt/route/config/%s/ipv4/prefix/0.0.0.0\\/0/gw' % iface)
            speed      = Nodes.present(mgmt, '%s/eth%s/type/ethernet/speed'  % (netConf, numPart))
            duplex     = Nodes.present(mgmt, '%s/eth%s/type/ethernet/duplex' % (netConf, numPart))
            mtu           = Nodes.present(mgmt, '%s/%s/mtu'  % (netState, iface))
            negoSpeed  = Nodes.present(mgmt, '%s/eth%s/type/ethernet/speed'  % (netState, numPart))
            negoDuplex = Nodes.present(mgmt, '%s/eth%s/type/ethernet/duplex' % (netState, numPart))
            speedOptions  = NicFactory.getNativeSpeedOptions(mgmt,  'eth%s' % numPart)
            duplexOptions = NicFactory.getNativeDuplexOptions(mgmt, 'eth%s' % numPart)

            ifaceEl = self.doc.createElement('interface')
            for optname, opts in (('speedOptions', speedOptions),
                                  ('duplexOptions', duplexOptions)):
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
                               ('ip', ip), ('subnet', subnet), ('dataInterface', dataInterface),
                               ('ipv6Enable', ipv6Enable), ('ipv6Addr', ipv6Addr),
                               ('ipv6Gateway', ipv6Gateway), ('ipv6Prefix', ipv6Prefix),
                               ('speed', speed), ('duplex', duplex),
                               ('negoSpeed', negoSpeed), ('negoDuplex', negoDuplex),
                               ('mtu', mtu)):
                ifaceEl.setAttribute(key, value)

            result.appendChild(ifaceEl)

        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

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
    #              ipv6Enable=""
    #              ipv6Addr=""
    #              ipv6Prefix=""
    #              ipv6Gateway=""
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

        inpathInterfaces = [x for x in Nodes.getMgmtLocalChildrenNames(mgmt,
            self.cmcPolicyRetarget(netState))
            if x.startswith('inpath')]

        inpathInterfaces = FormUtils.sortInterfacesByName(inpathInterfaces)
        for iface in inpathInterfaces:
            numPart = iface[len('inpath'):] # e.g. '0_0' or '0_1'

            dhcp          = '%s/%s/addr/ipv4/dhcp' % (netConf, iface)
            manIp         = '%s/%s/addr/ipv4/static/1/ip' % (netConf, iface)
            manSubnet     = '%s/%s/addr/ipv4/static/1/mask_len' % (netConf, iface)
            ip            = '%s/%s/addr/ipv4/1/ip' % (netState, iface)
            subnetShort   = '%s/%s/addr/ipv4/1/mask_len' % (netState, iface)
            gateway       = '/rbt/route/config/%s/ipv4/prefix/0.0.0.0\\/0/gw' % iface
            lanSpeed      = '%s/lan%s/type/ethernet/speed'  % (netConf, numPart)
            lanDuplex     = '%s/lan%s/type/ethernet/duplex' % (netConf, numPart)
            wanSpeed      = '%s/wan%s/type/ethernet/speed'  % (netConf, numPart)
            wanDuplex     = '%s/wan%s/type/ethernet/duplex' % (netConf, numPart)
            mtu           = '%s/%s/mtu'  % (netState, iface)
            vlan          = '%s/%s/vlan' % (sportConf, iface)
            negoLanSpeed  = '%s/lan%s/type/ethernet/speed'  % (netState, numPart)
            negoWanSpeed  = '%s/wan%s/type/ethernet/speed'  % (netState, numPart)
            negoLanDuplex = '%s/lan%s/type/ethernet/duplex' % (netState, numPart)
            negoWanDuplex = '%s/wan%s/type/ethernet/duplex' % (netState, numPart)

            # gather nic nodes
            nicNodes = self.mgmt.getMultiple(dhcp, manIp, manSubnet, ip,
                subnetShort, gateway, lanSpeed, lanDuplex,
                wanSpeed, wanDuplex, mtu, vlan,
                negoLanSpeed, negoWanSpeed, negoLanDuplex, negoWanDuplex)

            stateSubnet = FormUtils.ipv4NetMask(nicNodes.get(subnetShort))
            manSubnetValue = FormUtils.ipv4NetMask(nicNodes.get(manSubnet, ""))

            if nicNodes.get(ip) and nicNodes.get(subnetShort):
                optInterface = nicNodes.get(ip) + '/' + nicNodes.get(subnetShort)
            else:
                optInterface = ''

            lanSpeedOptions  = NicFactory.getNativeSpeedOptions(mgmt,  'lan%s' % numPart)
            wanSpeedOptions  = NicFactory.getNativeSpeedOptions(mgmt,  'wan%s' % numPart)
            lanDuplexOptions = NicFactory.getNativeDuplexOptions(mgmt, 'lan%s' % numPart)
            wanDuplexOptions = NicFactory.getNativeDuplexOptions(mgmt, 'wan%s' % numPart)

            ipv6Info = Nodes.getTreeifiedSubtree(mgmt, '/net/interface/config/%s/addr/ipv6/static' % iface)
            ipv6Enable = 'false'
            ipv6Addr = ''
            ipv6Prefix = ''
            ipv6Gateway = ''
            if len(ipv6Info) == 1:
                ipv6Enable = 'true'
                ipv6Addr = ipv6Info.keys()[0]
                ipv6Prefix = ipv6Info[ipv6Addr]['mask_len']
                ipv6Gateway = Nodes.present(mgmt, '/rbt/route/config/%s/ipv6/prefix/::\\/0/gw' % iface)
                optInterface += (optInterface and ';' or '') + ipv6Addr + '/' + ipv6Prefix

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

            for key, value in  (('name', iface),
                                ('dhcp', nicNodes.get(dhcp, 'false')),
                                ('manIp', nicNodes.get(manIp)),
                                ('manSubnet', manSubnetValue),
                                ('gateway', nicNodes.get(gateway)),
                                ('ip', nicNodes.get(ip)),
                                ('subnet', stateSubnet),
                                ('optInterface', optInterface),
                                ('ipv6Enable', ipv6Enable),
                                ('ipv6Addr', ipv6Addr),
                                ('ipv6Gateway', ipv6Gateway),
                                ('ipv6Prefix', ipv6Prefix),
                                ('lanSpeed', nicNodes.get(lanSpeed)),
                                ('lanDuplex', nicNodes.get(lanDuplex)),
                                ('wanSpeed', nicNodes.get(wanSpeed)),
                                ('wanDuplex', nicNodes.get(wanDuplex)),
                                ('negoLanSpeed', nicNodes.get(negoLanSpeed)),
                                ('negoLanDuplex', nicNodes.get(negoLanDuplex)),
                                ('negoWanSpeed', nicNodes.get(negoWanSpeed)),
                                ('negoWanDuplex', nicNodes.get(negoWanDuplex)),
                                ('mtu', nicNodes.get(mtu)),
                                ('vlan', nicNodes.get(vlan))):
                ifaceEl.setAttribute(key, value or '')

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
    def inpathRoutesIPv6(self):
        iface = self.request().fields().get('iface')
        dynamicRoutePrefix = self.cmcPolicyRetarget('/rbt/route/state/%s/ipv6/prefix' % iface)
        configRoutePrefix = self.cmcPolicyRetarget('/rbt/route/config/%s/ipv6/prefix' % iface)
        dynamicRoutes = Nodes.getMgmtSetEntriesDeep(self.mgmt, dynamicRoutePrefix)
        configRoutes = Nodes.getMgmtSetEntriesDeep(self.mgmt, configRoutePrefix)

        routes = configRoutes.copy()
        routes.update(dynamicRoutes)
        defaultRoute = None

        result = self.doc.createElement('routes')
        for routeID in routes.keys():
            routeEl = self.doc.createElement('route')

            ip, mask = routeID.split('\\/')
            if '::' == ip and 0 == int(mask):
                ip = 'default'

            id = ''
            status = 'dynamic'
            if routeID in configRoutes:
                id = routeID
                if routeID in dynamicRoutes:
                    status = 'configured'
                else:
                    status = 'down'

            statusPretty = {'down': 'User Configured / Inactive',
                            'configured': 'User Configured',
                            'dynamic': ''}

            routeEl.setAttribute('id', id)
            routeEl.setAttribute('destination', ip)
            routeEl.setAttribute('prefix', mask)
            routeEl.setAttribute('gateway', routes[routeID].get('gw'))
            routeEl.setAttribute('status', statusPretty.get(status))

            # Add the route to the result collection.
            # If it's the default route, save it to add last.
            if 'default' == ip and 0 == int(mask):
                defaultRoute = routeEl
            else:
                result.appendChild(routeEl)

        # If the default route was found, add it last.
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
        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(self.fields)
        statusPretty = {'down': 'User Configured / Inactive',
                        'configured': 'User Configured',
                        'dynamic': ''}
        dynamicRoutePrefix = pathPrefix + '/net/routes/state/ipv4/prefix'
        configRoutePrefix = pathPrefix + '/net/routes/config/ipv4/prefix'
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
                interface = route.get('nh/%d/interface' % gw, '')
                if interface == '':
                    interface = 'Auto'
                routeEl.setAttribute('interface', interface)
                if not policyType:
                    # On CMC policy page we do not display the status column
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

    # for setupDateTime.psp, setupHostSettingsCMC.psp:
    #
    # ntpServers
    #
    # <ntpservers>
    #   <ntpserver host="" enable="" prefer="" version="" key="" />
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
            keyid = server.get('key', '')
            if keyid == '0':
                # There is no Authentication Key when key=='0'
                keyid = ''
            if keyid:
                # Mark Trusted Key IDs
                trustedBase = self.cmcPolicyRetarget('/ntp/trustedkeys')
                trusted = Nodes.present(self.mgmt, '%s/%s' % (trustedBase, keyid), None)
                if not trusted:
                    keyid = '%s (Untrusted)' % keyid
            serverEl = self.doc.createElement('ntpserver')
            serverEl.setAttribute('host', serverId)
            statePrefix = '/ntp/state/remote/%s' % serverId
            serverEl.setAttribute('enable', server.get('enable', ''))
            serverEl.setAttribute('prefer', server.get('prefer', ''))
            serverEl.setAttribute('version', server.get('version', ''))
            serverEl.setAttribute('key', keyid)
            result.appendChild(serverEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupDateTime.psp:
    #
    # ntpActivePeers
    #
    # <ntpActivePeers>
    #   <activePeer server="" active="" server="" auth="" keyid="" refid="" />
    # </ntpActivePeers>
    #
    def ntpActivePeers(self):
        activePeers = Nodes.getTreeifiedSubtree(self.mgmt, '/ntp/state/remote')

        serverIds = activePeers.keys()
        serverIds.sort(FormUtils.alphanumericCompare)

        # Bubble the active server, if more than one then we can handle that too,
        # to the top of the list.

        inactive = []
        active = []
        for serverId in serverIds:
            server = activePeers[serverId]
            if server.get('active_sync', 'false') == 'false':
                inactive.append(serverId)
            else:
                active.append(serverId)
        serverIds = active + inactive

        result = self.doc.createElement('ntpActivePeers')
        for serverId in serverIds:
            server = activePeers[serverId]
            serverEl = self.doc.createElement('activePeer')
            result.appendChild(serverEl)

            key = server.get('key', 'false')
            if key == '0':
                authPretty = 'None'
                keyPretty = ''
            else:
                authPretty = server.get('auth', 'false') == 'false' and 'Bad' or 'Ok'
                keyPretty = key

            activePretty = server.get('active_sync', 'false') == 'true' and 'Yes' or ''

            serverEl.setAttribute('active', activePretty)
            serverEl.setAttribute('server', serverId)
            serverEl.setAttribute('auth', authPretty)
            serverEl.setAttribute('keyid', keyPretty)
            serverEl.setAttribute('refid', server.get('refid', 'false'))

        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupDateTime.psp, setupHostSettingsCMC.psp:
    #
    # ntpAuths
    #
    # <ntpauths>
    #   <ntpauth key="" type="" secret="" trusted=""/>
    # </ntpauths>
    #
    def ntpAuths(self):
        # Get NTP Authentication Keys
        authKeyBase = self.cmcPolicyRetarget('/ntp/keys')
        authKeys = Nodes.getMgmtSetEntriesDeep(self.mgmt, authKeyBase)
        authKeyIds = authKeys.keys()
        authKeyIds.sort(FormUtils.alphanumericCompare)
        # Get List of NTP Trusted Keys
        trustedKeyBase = self.cmcPolicyRetarget('/ntp/trustedkeys')
        trustedKeys = Nodes.getMgmtSetEntriesDeep(self.mgmt, trustedKeyBase)
        trustedKeyIds = trustedKeys.keys()
        trustedKeyIds.sort(FormUtils.alphanumericCompare)
        result = self.doc.createElement('ntpauths')
        for authKeyId in authKeyIds:
            authKey = authKeys[authKeyId]
            trusted = (authKeyId in trustedKeyIds) and 'true' or 'false'
            authKeyEl = self.doc.createElement('ntpauth')
            authKeyEl.setAttribute('key', authKeyId)
            authKeyEl.setAttribute('type', authKey.get('type', ''))
            authKeyEl.setAttribute('secret', authKey.get('secret', ''))
            authKeyEl.setAttribute('trusted', trusted)
            result.appendChild(authKeyEl)
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
    #         uploading from file            ('file', '<filename>')
    #         transferring from url          ('url', '<filename>')
    #         transferring from support site ('support', '<filename>')
    #         while installing               'installing'
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
                if fields.get('installUpgradeFrom') == 'url' or fields.get('installUpgradeFrom') == 'support':
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
                    if upgradeState[0] == 'url' or upgradeState[0] == 'support':
                        baseName = upgradeState[1]
                        if not os.path.exists(os.path.join(_TEMP_IMAGE_DIR_PATH, baseName)):
                            # This clause could potentially happen if an AJAX status request occurs between the
                            # setting of upgradeState and the file from the transfer actually being
                            # created. This is uncommon, but does happen. In this case, the file size
                            # info will not be available, so we display a generic description.
                            desc = 'Starting the transfer.'
                        else:
                            bytesTransferredSoFar = os.stat(os.path.join(_TEMP_IMAGE_DIR_PATH, baseName)).st_size
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
    #   <license id="" key="" desc="" status="" expiry_style="" installDateTime="" installMethod=""/>
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
            expiry_style = ''
            if licenseNodes[id].get('properties/valid') == 'true':
                starting = licenseNodes[id].get('properties/start_date')
                expiration = licenseNodes[id].get('properties/end_date')
                isActive = licenseNodes[id].get('properties/active')
                status, expiry_style = getPrettyStatusAndStyle(starting, expiration, isActive=='true')
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
                           expiry_style=expiry_style,
                           installDateTime=installDateTime,
                           installMethod=installMethod)

        # On Steelheads, show an empty row when there's no MSPEC license.
        # If there are multiple missing features, show the MSPEC first.
        if isSH():
            if Nodes.present(self.mgmt, '/license/state/model/current/licensed', '') != 'true':
                missingFeatures.insert(0, 'MSPEC' + Nodes.present(self.mgmt, '/hw/hal/spec/state/current/name', ''))

        # handle licenses that come from a license server
        # these cannot be removed by the user
        licenseFromServerNodes = Nodes.getMgmtSetEntriesDeep(self.mgmt, '/license/client/state/feature')
        for id in licenseFromServerNodes:
            license_name = licenseFromServerNodes[id].get('name')
            license_class = licenseFromServerNodes[id].get('class')
            license_active = licenseFromServerNodes[id].get('active')
            license_is_perpetual = \
                licenseFromServerNodes[id].get('is_perpetual')
            license_start = licenseFromServerNodes[id].get('start_datetime')
            license_end = licenseFromServerNodes[id].get('end_datetime')
            license_status = 'Invalid'
            license_style = ''
            if license_is_perpetual == 'true':
                license_status = 'Perpetual'
            else:
                license_status, license_style = getPrettyStatusAndStyle(
                                                        license_start, license_end, license_active=='true')

            license_info = self.licenseFromServerDesc(license_name, license_class)
            for license in license_info:
                table.addEntry(id='',
                               key=license_name,
                               desc=license[1],
                               status=license_status,
                               expiry_style=license_style,
                               installDateTime='--',
                               installMethod='--')
                if license[0] in missingFeatures:
                    missingFeatures.remove(license[0])

        licensesFromBase = Nodes.getMgmtLocalChildrenNames(self.mgmt, '/rbt/virtual/state/base_licensed_features')
        for featureName in licensesFromBase:
            if featureName in missingFeatures:
                missingFeatures.remove(featureName)
            table.addEntry(id='',
                           key='Included from base license',
                           desc=self.licenseDesc(featureName, ' -- '),
                           status='Valid',
                           installDateTime='--',
                           installMethod='Included from base license')

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


    def domainTestControl(self):
        fields = self.fields
        BASE = '/rbt/sport/domain_auth/action/domaind'

        reply = ''
        try:
            if 'testName' in self.fields:
                testName = self.fields['testName']

                if 'testjoin' == testName:
                    reply = self.sendAction('%s/testjoin' % BASE)

                elif 'testdns' == testName:
                    realm = fields['realm']
                    reply = self.sendAction('%s/testdns' % BASE,
                                            ('realm', 'string', realm))

                elif 'delegtest' == testName:
                    realm = fields['realm']
                    server = fields['server']
                    serverIP = fields['server-ip']
                    service = fields['service']
                    params = [('realm', 'string', realm),
                              ('server', 'string', server),
                              ('server-ip', 'string', serverIP),
                              ('service', 'string', service)]
                    enduser = fields['enduser']
                    if enduser:
                        params.append(('enduser', 'string', enduser))
                    reply = self.sendAction('%s/%s' % (BASE, testName), *params)

                elif 'delegtest2' == testName:
                    realm = fields['realm']
                    dc = fields['dc']
                    reply = self.sendAction('%s/delegtest2' % BASE,
                                            ('realm', 'string', realm),
                                            ('dc', 'string', dc))

                elif 'authtest' == testName:
                    user = fields['user']
                    password = fields['password']
                    params = [('user', 'string', user),
                              ('password', 'string', password)]
                    domain = fields.get('domain')
                    if domain:
                        params.append(('domain', 'string', domain))
                    shortdom = fields.get('shortdom')
                    if shortdom:
                        params.append(('shortdom', 'string', shortdom))
                    reply = self.sendAction('%s/%s' % (BASE, testName), *params)

                elif 'repltest' == testName:
                    realm = fields['realm']
                    shortDOM = fields['shortdom']
                    rServer = fields['rserver']
                    reply = self.sendAction('%s/repltest' % BASE,
                                            ('realm', 'string', realm),
                                            ('shortdom', 'string', shortDOM),
                                            ('rserver', 'string', rServer))

                elif 'replprptest' == testName:
                    realm = fields['realm']
                    dc = fields['dc']
                    rServer = fields['rserver']
                    reply = self.sendAction('%s/replprptest' % BASE,
                                            ('realm', 'string', realm),
                                            ('dc', 'string', dc),
                                            ('rserver', 'string', rServer))

                elif testName in ['confdeleg', 'confrepl']:
                    admin = fields['admin']
                    adminpass = fields['adminpass']
                    realm = fields['realm']
                    dc = fields['dc']
                    reply = self.sendAction('%s/%s' % (BASE, testName),
                                            ('admin', 'string', admin),
                                            ('adminpass', 'string', adminpass),
                                            ('realm', 'string', realm),
                                            ('dc', 'string', dc))

                elif testName in ['confdelegaddserver', 'confdelegdelserver']:
                    admin = self.fields.get('admin')
                    adminpass = self.fields.get('adminpass')
                    realm = fields['realm']
                    dc = fields['dc']
                    service = fields['service']
                    serverlist = fields['serverlist']
                    params = [('realm', 'string', realm),
                              ('dc', 'string', dc),
                              ('service', 'string', service),
                              ('serverlist', 'string', serverlist)]
                    if admin and adminpass:
                        params.append(('admin', 'string', admin))
                        params.append(('adminpass', 'string', adminpass))
                    reply = self.sendAction('%s/%s' % (BASE, testName), *params)

                elif 'easy_auth' == testName:
                    admin = fields['admin']
                    adminpass = fields['adminpass']
                    realm = fields['realm']
                    dc = fields['dc']
                    confType = []
                    # Backend expects these parameters in this specific order.
                    if fields['emapi'] == 'true':
                        confType.append('emapi')
                    if fields['smb2signing'] == 'true':
                        confType.append('smb2signing')
                    if fields['smb3signing'] == 'true':
                        confType.append('smb3signing')
                    if fields['smbsigning'] == 'true':
                        confType.append('smbsigning')
                    if confType == []:
                        reply = 'Please enable at least one optimization type.'
                        result = self.doc.createElement('error')
                        result.appendChild(self.doc.createTextNode(reply))
                        self.doc.documentElement.appendChild(result)
                        self.writeXmlDoc()
                        return
                    else:
                        confString = ','.join(confType)
                    joinType = fields['join_type']
                    params = [('admin', 'string', admin),
                              ('adminpass', 'string', adminpass),
                              ('realm', 'string', realm),
                              ('dc', 'string', dc),
                              ('conf_type', 'string', confString),
                              ('join_type', 'string', joinType)]
                    shortDOM = fields['shortdom']
                    if shortDOM:
                        params.append(('shortdom', 'string', shortDOM))
                    reply = self.sendAction('%s/%s' % (BASE, testName), *params)

        except Exception, info:
            result = self.doc.createElement('error')
            result.appendChild(self.doc.createTextNode(str(info.args[0])))
            self.doc.documentElement.appendChild(result)
            self.writeXmlDoc()
            return
        result = self.doc.createElement('okay')
        if reply:
            result.appendChild(self.doc.createTextNode(str(reply)))
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()


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


class json_Host(JSONContent):
    alwaysKeepAliveList = []

    neverKeepAliveList = [
        'dbDirty',
        'domainActionStatus',
        'checkHWUpgradeWarning'
    ]

    autoRefreshList = []

    # returns JSON of the following form:
    # { "dirty": True | False }
    def dbDirty(self):
        def internal():
            dirty = self.mgmt.get('/mgmtd/db/info/running/unsaved_changes')
            return {'dirty': dirty == 'true'}
        self.rpcWrapper(internal)


    # returns JSON that looks like this:
    #     {
    #         "status": "SUCCESS",
    #          "log": "<tr><td class=\"logTimestamp\">[Aug 20 18:38:12 NOTICE]</td> ...",
    #          "timestamp": 1345513092,
    #          "result": "",
    #          "resultLines": 0,
    #          "logLines": 17,
    #          "lastRunParams": "realm=VCS86DOM.COM",
    #          "name": "testdns",
    #     },

    def domainActionStatus(self):
        import logDomainHealth

        def internal(actionName):
            BASE = '/rbt/sport/domain_auth/state/domaind'
            data = {}

            data['name'] = actionName
            data['timestamp'] = int(Nodes.present(self.mgmt, '%s/timestamp/%s' % (BASE, actionName), '0'))

            status = Nodes.present(self.mgmt, '%s/status/%s' % (BASE, actionName))
            data['status'] = status

            # Special case for test DNS at the beginning of time.

            if status == 'NOT STARTED' and actionName == 'testdns':
                mgmt = self.session().value('mgmt')
                data['lastRunParams'] = 'realm=%s' % Nodes.present(mgmt, '/rbt/rcu/domain/config/realm')
            else:
                data['lastRunParams'] = Nodes.present(self.mgmt, '%s/params/%s' % (BASE, actionName))

            result = Nodes.present(self.mgmt, '%s/result/%s' % (BASE, actionName))
            if result:
                data['result'] = logDomainHealth.getLogDomainHealth(result.split('\n'))
            else:
                data['result'] = ''
            data['resultLines'] = result.count('\n')

            log = Nodes.present(self.mgmt, '%s/verbose/%s' % (BASE, actionName))
            if log:
                data['log'] = logDomainHealth.getLogDomainHealth(log.split('\n'))
            else:
                data['log'] = ''
            data['logLines'] = log.count('\n')

            return data

        self.rpcWrapper(internal)

    def checkHWUpgradeWarning(self):

        def internal(specName):
            return self.mgmt.get('/rbt/sport/hardware/state/spec/all/%s/action_needed' % specName)

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
