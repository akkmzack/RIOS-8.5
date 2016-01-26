## Copyright 2006, Riverbed Technology, Inc., All rights reserved.
##
## Advanced networking support for gui and xmldata.
## Author: Don Tillman

import re
import FormUtils
import GraphUtils
import Nodes
import RVBDUtils
import Reports2
import Reports2Math

from PagePresentation import PagePresentation
from XMLContent import XMLContent
from JSONContent import JSONContent
from gclclient import NonZeroReturnCodeException

class gui_AdvancedNetworking(PagePresentation):
    # actions handled here
    actionList = ['setupAsymmetricRouting',
                  'setupConnectionForwarding',
                  'setupNetworkAuth',
                  'setupNetworkNetflow',
                  'setupServicePeering',
                  'setupServicePorts',
                  'setupSubnetSide',
                  'setupServiceWccp',
                  'setupHWAssistRules',
                  'setupPortLabels',
                  'setupHostLabels']

    # Asymmetric routing page
    def setupAsymmetricRouting(self):
        if 'removeAsymmetricRoutes' in self.fields:
            routes = FormUtils.getPrefixedFieldNames('selectedRoute_', self.fields)
            for route in routes:
                ip1, ip2 = route.split('_')
                self.sendAction('/rbt/sport/intercept/action/asym_routing/delete_entry_pair',
                                ('ip_pair', 'string', '%s-%s' % (ip1, ip2)))
        else:
            FormUtils.setNodesFromConfigForm(self.mgmt, self.fields)

    # Connection Forwarding pagelet
    def setupConnectionForwarding(self):
        base = self.cmcPolicyRetarget('/rbt/sport/intercept/config/neighbor/name')
        if 'addNeighbor' in self.fields:
            name = self.fields.get('addNeighbor_name')
            ip = self.fields.get('addNeighbor_ip')
            ips = self.fields.get('addNeighbor_ips')
            port = self.fields.get('addNeighbor_port')

            # base nodes that need to be set
            nodes = [('%s/%s' % (base, name), 'hostname', name),
                     ('%s/%s/main_address' % (base, name), 'ipv4addr', ip),
                     ('%s/%s/port' % (base, name), 'uint16', port)]

            # now handle any additional addresses
            if ips:
                addrs = ips.split(',')
                for addr in addrs:
                    addr = addr.strip()
                    nodes.append(('%s/%s/additional_address/%s' % (base, name, addr), 'ipv4addr', addr))

            self.setNodes(*nodes)
        elif 'editNeighbor' in self.fields:
            name = self.fields.get('editNeighbor_name')
            ip = self.fields.get('editNeighbor_ip')
            ips = self.fields.get('editNeighbor_ips')
            port = self.fields.get('editNeighbor_port')

            # base nodes that need to be set
            nodes = [('%s/%s/main_address' % (base, name), 'ipv4addr', ip),
                     ('%s/%s/port' % (base, name), 'uint16', port)]

            # now handle any additional addresses
            old_ips = self.mgmt.getChildren('%s/%s/additional_address' % (base, name))
            del_ips = []
            set_ips = []
            new_ips = []
            if ips:
                ips = ips.split(',')
                for ip in ips:
                    ip = ip.strip()
                    new_ips.append(ip)

            for ip in old_ips:
                try:
                    new_ips.index(ip)
                except:
                    del_ips.append('%s/%s/additional_address/%s' % (base, name, ip))

            for ip in new_ips:
                try:
                    old_ips.index(ip)
                except:
                    nodes.append(('%s/%s/additional_address/%s' % (base, name, ip), 'ipv4addr', ip))
                    set_ips.append(ip)

            self.setNodes(*nodes)
            self.deleteNodes(*del_ips)
        elif 'removeNeighbors' in self.fields:
            FormUtils.deleteNodesFromConfigForm(self.mgmt,
                                                base,
                                                'selectedNeighbor_',
                                                self.fields)

    # Encryption pagelet
    def setupNetworkAuth(self):
        base = self.cmcPolicyRetarget('/rbt/auth/config')
        if 'apply' in self.fields:
            secret = self.fields.get('secret')
            if secret and (secret != FormUtils.bogusPassword):
                self.setNodes((base + '/secret', 'string', secret))
            FormUtils.setNodesFromConfigForm(self.mgmt, self.fields)
        elif 'addSecurePeer' in self.fields:
            secureIP = self.fields.get('addSecurePeer_peerIp', "")
            self.setNodes(('%s/peers/%s' % (base, secureIP), 'ipv4addr', secureIP))
        elif 'removeSecurePeer' in self.fields:
            FormUtils.deleteNodesFromConfigForm(self.mgmt, '%s/peers' % base, 'selectedPeer_', self.fields)

    # NetFlow pagelet
    def setupNetworkNetflow(self):
        cmcEditPolicy = 'editPolicy' in self.fields
        base = self.cmcPolicyRetarget('/rbt/sport/netflow/config/collector/address')
        if 'apply' in self.fields:
            if 'b/rbt/sport/netflow/config/enable' in \
               self.fields.get('unchecked', '') \
            and 'true' == Nodes.present(self.mgmt,
                '/rbt/sport/netflow/config/top_talkers/enable'):
                Nodes.set(self.mgmt,
                    ('/rbt/sport/netflow/config/top_talkers/enable',
                     'bool', 'false'))
            FormUtils.setNodesFromConfigForm(self.mgmt, self.fields)
        elif 'addCollector' in self.fields:
            ip = self.fields.get('addCollector_ip')
            port = self.fields.get('addCollector_port')
            path = '%s/%s/port/%s' % (base, ip, port)

            # remove any previous
            if Nodes.present(self.mgmt, path):
                self.deleteNodes(path)

            version = self.fields.get('addCollector_version')
            v9 = version.startswith('9')
            export = self.fields.get('addCollector_export')
            # note that a v9 collector should always have spoof set to
            # true (bug 51101)
            spoof = v9 and 'true' or \
                self.fields.get('addCollector_spoof', 'false')
            nodes = [(path + '/version', 'string', version),
                     (path + '/export_if', 'string', export),
                     (path + '/spoof', 'bool', spoof)]
            # interfaces
            ifs = FormUtils.getPrefixedFieldNames('addCollector_if_', self.fields)
            for i in ifs:
                val = self.fields.get('addCollector_if_%s' % i)
                if val:
                    nodes.append(('%s/interface/%s/capture' % (path, i), 'string', val))
            self.setNodes(*nodes)

            if v9:
                filterEnable = self.fields.get('addCollector_filterEnable', 'false')
                filters = self.parseV9Filters(self.fields.get('addCollector_filters'))
                if cmcEditPolicy:
                    # CMC: do these nodes
                    nodes = [('%s/filter_enable' % path, 'bool', filterEnable)]
                    index = 0
                    for filt in filters:
                        for fn, ft, fv in filt:
                            node = '%s/filter/%d/%s' % (path, index, fn)
                            nodes.append((node, ft, fv))
                        index += 1
                    self.setNodes(*nodes)
                else:
                    # SH: use these actions
                    self.sendAction('/rbt/sport/netflow/action/enable_filters',
                                    ('ip', 'ipv4addr', ip),
                                    ('port', 'uint16', port),
                                    ('filter_enable', 'bool', filterEnable))
                    for filt in filters:
                        self.sendAction('/rbt/sport/netflow/action/add_filter',
                                        ('ip', 'ipv4addr', ip),
                                        ('port', 'uint16', port),
                                        *filt)
        elif 'editCollector' in self.fields:
            ip, port = self.fields.get('editCollector_id', '').split(':')
            path = '%s/%s/port/%s' % (base, ip, port)
            version = self.fields.get('editCollector_version')
            v9 = version.startswith('9')
            export = self.fields.get('editCollector_export')
            # note that a v9 collector should always have spoof set to
            # true (bug 51101)
            spoof = v9 and 'true' or \
                self.fields.get('editCollector_spoof', 'false')
            nodes = [(path + '/version', 'string', version),
                     (path + '/export_if', 'string', export),
                     (path + '/spoof', 'bool', spoof)]

            # Remember the old interfaces so that they can be deleted
            # later.  We used to delete all of the interfaces first
            # and repopulate them but that actually causes the entire
            # collector to be temporarily removed.  This would
            # normally not be a problem since we put it back right
            # afterwards, but there are options that are configurable
            # via CLI but not web and removing the collector clobbers
            # those settings.  See bug 53655.
            oldInterfaces = Nodes.getMgmtLocalChildrenNames(
                self.mgmt, path + '/interface')

            # Add nodes to set all of the configured interfaces.
            ifs = FormUtils.getPrefixedFieldNames('editCollector_if_', self.fields)
            for i in ifs:
                val = self.fields.get('editCollector_if_%s' % i)
                if val:
                    nodes.append(('%s/interface/%s/capture' % (path, i), 'string', val))
            self.setNodes(*nodes)

            # If any interface is in the old list but not the new one,
            # delete its nodes.  Note that there might not be a field
            # for a configured interface at all (see bug 56026).  This
            # could happen if a physical interface is removed.
            for oldIface in oldInterfaces:
                if self.fields.get('editCollector_if_%s' % oldIface, '') == '':
                    self.deleteNodes('%s/interface/%s' % (path, oldIface))

            # remove old filters
            oldFilts = Nodes.getMgmtLocalChildrenNames(self.mgmt, path + '/filter')
            oldFilts.sort(key=int, reverse=True)
            if cmcEditPolicy:
                # CMC deletes nodes
                self.deleteNodes(*['%s/filter/%s' % (path, f)
                                   for f in oldFilts])
            else:
                # SH sends actions
                for f in oldFilts:
                    self.sendAction('/rbt/sport/netflow/action/delete_filter',
                                    ('ip', 'ipv4addr', ip),
                                    ('port', 'uint16', port),
                                    ('num', 'uint32', f))
            if v9:
                filterEnable = self.fields.get('editCollector_filterEnable', 'false')
                filters = self.parseV9Filters(self.fields.get('editCollector_filters'))
                if cmcEditPolicy:
                    # CMC: do these nodes
                    nodes = [('%s/filter_enable' % path, 'bool', filterEnable)]
                    index = 0
                    for filt in filters:
                        for fn, ft, fv in filt:
                            node = '%s/filter/%d/%s' % (path, index, fn)
                            nodes.append((node, ft, fv))
                        index += 1
                    self.setNodes(*nodes)
                else:
                    # SH: use these actions
                    self.sendAction('/rbt/sport/netflow/action/enable_filters',
                                    ('ip', 'ipv4addr', ip),
                                    ('port', 'uint16', port),
                                    ('filter_enable', 'bool', filterEnable))
                    for filt in filters:
                        self.sendAction('/rbt/sport/netflow/action/add_filter',
                                        ('ip', 'ipv4addr', ip),
                                        ('port', 'uint16', port),
                                        *filt)

        elif 'removeCollectors' in self.fields:
            # handle remove
            selecteds = FormUtils.getPrefixedFieldNames('selectedCollector_', self.fields)
            dels = []
            for each in selecteds:
                eachIp, eachPort = each.split(':')
                dels.append('%s/%s/port/%s' % (base, eachIp, eachPort))
            self.deleteNodes(*dels)


    # ipv4addr/maskbits
    RE_netflowCollectorFilter_mask = re.compile(r'^(\d+.\d+.\d+.\d+)/(\d+)$')
    # ipv4addr:port
    RE_netflowCollectorFilter_port = re.compile(r'^(\d+.\d+.\d+.\d+):(\d+)$')

    # Helper for above.  Given a string, the textarea full of filter
    # specs, one filter per line, either of the form "ip/mask" or
    # "ip:port", parse them out, and create a list of action args to
    # be sent out.
    def parseV9Filters(self, filtersString):
        result = []
        for filt in filtersString.split():
            # ipv4addr/maskbits
            filterMatch = self.__class__.RE_netflowCollectorFilter_mask.match(filt)
            if filterMatch:
                filterIp, filterMask = filterMatch.groups()
                result.append((('filter_ip', 'ipv4addr', filterIp),
                               ('filter_netmask', 'uint8', filterMask),
                               ('filter_port', 'uint16', '0')))
            # ipv4addr:port
            filterMatch = self.__class__.RE_netflowCollectorFilter_port.match(filt)
            if filterMatch:
                filterIp, filterPort = filterMatch.groups()
                result.append((('filter_ip', 'ipv4addr', filterIp),
                               ('filter_netmask', 'uint8', '0'),
                               ('filter_port', 'uint16', filterPort)))
        return result

    subnetSpec = {'lan': 'bool',
                  'network_prefix': 'ipv4prefix'}

    # Configure > Networking > Subnet Side pagelet
    #
    # Add, remove, and move a subnet side map.
    def setupSubnetSide(self):
        fields = self.fields
        base = self.cmcPolicyRetarget('/rbt/subnet/config/side/rule')
        cmc = ('editPolicy' in fields) or ('editAppliancePolicy' in fields)

        # LAN/WAN side
        if FormUtils.prefixedKey(fields, 'changeSubnetSide_'):
            index, newSide = FormUtils.getPrefixedField('changeSubnetSide_',
                                                        fields)
            if cmc:
                self.setNodes(('%s/%s/lan' % (base, index), 'bool', newSide))
            else: #SH
                netPrefix = Nodes.present(self.mgmt,
                    '%s/%s/network_prefix' % (base, index))
                if not netPrefix:
                    self.setFormError(
                        'Please select a valid rule. There is no rule number %s.' % index
                        )
                else:
                    self.sendAction('/rbt/subnet/action/side/rule/delete',
                                    ('idx', 'uint32', index))
                    self.sendAction('/rbt/subnet/action/side/rule/add',
                        ('idx', 'uint32', index),
                        ('network_prefix', 'ipv4prefix', netPrefix),
                        ('lan', 'bool', newSide))
        # add subnet
        elif 'addSubnet' in self.fields:
            index = self.fields.get('addSubnet_index')
            network = self.fields.get('addSubnet_source')
            lan = self.fields.get('addSubnet_side')
            if cmc:
                subnet = {'lan': lan, 'network_prefix': network}
                Nodes.editNodeSequence(self.mgmt, base, self.subnetSpec, 'add',
                        int(index), subnet)
            else: #SH
                self.sendAction('/rbt/subnet/action/side/rule/add',
                    ('idx', 'uint32', index),
                    ('network_prefix', 'ipv4prefix', network),
                    ('lan', 'bool', lan))
        # remove subnet
        elif 'removeSubnet' in self.fields:
            indices = FormUtils.getPrefixedFieldNames('selectedSubnetMap_', fields)
            indices.sort(FormUtils.alphanumericCompare)
            indices.reverse()
            for idx in indices:
                if cmc:
                    Nodes.editNodeSequence(self.mgmt, base, self.subnetSpec,
                            'remove', int(idx))
                else: #SH
                    self.sendAction('/rbt/subnet/action/side/rule/delete',
                            ('idx', 'uint32', idx))
        # move subnet
        else:
            reorderEntries = self.reorderEntries('selectedSubnetMap_',
                'moveToSubnetMap_', '/rbt/subnet/config/side/rule')
            for fromIdx, toIdx in reorderEntries:
                if cmc:
                    Nodes.editNodeSequence(self.mgmt, base, self.subnetSpec, 'move',
                            fromIdx, moveto=toIdx)
                else: #SH
                    self.sendAction('/rbt/subnet/action/side/rule/move',
                                    ('from_idx', 'uint32', fromIdx),
                                    ('to_idx', 'uint32', toIdx))

    # Peering pagelet
    def setupServicePeering(self):
        fields = self.fields
        mgmt = self.mgmt
        base = self.cmcPolicyRetarget('/rbt/sport/peering/config/rule')
        saasSupported = Nodes.present(mgmt, '/rbt/akam/state/supported') == 'true'
        peeringRuleSpec = {'action': 'string',
                           'description': 'string',
                           'dst/network': 'ipv6prefix',
                           'dst/port_label': 'string',
                           'peer/addr': 'ipv4addr',
                           'src/network': 'ipv6prefix',
                           'ssl_cap': 'string',
                           'saas_action': 'string'}
        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)

        if 'addPeeringRule' in fields:
            # handle add rule
            idx = fields.get('addRule_idx')

            # Handle CMC's edit policy page
            if policyType:
                # Make a rule dict, and edit it in
                rule = dict([(k, self.fields.get('addRule_' + k, ''))
                             for k,t in peeringRuleSpec.iteritems()])
                # Handle the special case port value of 'All'
                if 'all' == rule['dst/port_label'].lower():
                    rule['dst/port_label'] = '0'
                # Handle the special case peer value of 'All-IPv4'
                if 'all-ipv4' == rule['peer/addr'].lower():
                    rule['peer/addr'] = '0.0.0.0'
                # Handle the special case src/dst value of 'All-IP'
                rule['dst/network'] = RVBDUtils.mappedToIpv4v6Subnet(rule['dst/network'])
                rule['src/network'] = RVBDUtils.mappedToIpv4v6Subnet(rule['src/network'])
                Nodes.editNodeSequence(self.mgmt, base, peeringRuleSpec, 'add', int(idx), rule)
            else:  # Handle SH
                action = fields.get('addRule_action')
                description = fields.get('addRule_description', '')
                dst = RVBDUtils.mappedToIpv4v6Subnet(fields.get('addRule_dst/network'))
                port = fields.get('addRule_dst/port_label').lower()
                if port == 'all':
                    port = '0'
                peer = fields.get('addRule_peer/addr').lower()
                if peer == 'all-ipv4':
                    peer = '0.0.0.0'
                src = RVBDUtils.mappedToIpv4v6Subnet(fields.get('addRule_src/network'))
                ssl_cap = fields.get('addRule_ssl_cap')
                params = [('action', 'string', action),
                          ('description', 'string', description),
                          ('dst/network', 'ipv6prefix', dst),
                          ('dst/port_label', 'string', port),
                          ('peer/addr', 'ipv4addr', peer),
                          ('src/network', 'ipv6prefix', src),
                          ('ssl_cap', 'string', ssl_cap),
                          ('idx', 'uint16', idx)]

                if saasSupported:
                    saas_action = fields.get('addRule_saas_action')
                    params.append(('saas_action', 'string', saas_action))

                self.sendAction('/rbt/sport/peering/action/add_rule', *params)


        elif 'editPeeringRule' in fields:
            # handle edit rule
            index = fields.get('editRule_index')

            # Handle CMC's edit policy page
            if policyType:
                # Make a rule dict, and edit it in
                rule = dict([(k, self.fields.get('editRule_' + k, ''))
                             for k,t in peeringRuleSpec.iteritems()])
                # Handle the special case port value of 'All'
                if 'all' == rule['dst/port_label'].lower():
                    rule['dst/port_label'] = '0'
                # Handle the special case peer value of 'All-IPv4'
                if 'all-ipv4' == rule['peer/addr'].lower():
                    rule['peer/addr'] = '0.0.0.0'
                Nodes.editNodeSequence(self.mgmt, base, peeringRuleSpec, 'edit', int(index), rule)
            else:  # Handle SH
                action = fields.get('editRule_action')
                description = fields.get('editRule_description', '')
                dst = RVBDUtils.mappedToIpv4v6Subnet(fields.get('editRule_dst/network'))
                port = fields.get('editRule_dst/port_label').lower()
                if port == 'all':
                    port = '0'
                peer = fields.get('editRule_peer/addr').lower()
                if peer == 'all-ipv4':
                    peer = '0.0.0.0'
                src = RVBDUtils.mappedToIpv4v6Subnet(fields.get('editRule_src/network'))
                ssl_cap = fields.get('editRule_ssl_cap')

                params = [('action', 'string', action),
                          ('description', 'string', description),
                          ('dst/network', 'ipv6prefix', dst),
                          ('dst/port_label', 'string', port),
                          ('peer/addr', 'ipv4addr', peer),
                          ('src/network', 'ipv6prefix', src),
                          ('ssl_cap', 'string', ssl_cap),
                          ('idx', 'uint16', index)]

                if saasSupported:
                    saas_action = fields.get('editRule_saas_action')
                    params.append(('saas_action', 'string', saas_action))

                self.sendAction('/rbt/sport/peering/action/edit_rule', *params)

        elif 'removeRules' in self.fields:
            ruleIds = FormUtils.getPrefixedFieldNames('moveFromPeeringRule_',
                                                      self.fields)
            ruleIds.sort(FormUtils.compareStringInts)
            ruleIds.reverse()
            for eachRuleId in ruleIds:
                if policyType:
                    # Handle CMC's edit policy page
                    Nodes.editNodeSequence(self.mgmt, base, peeringRuleSpec, 'remove', int(eachRuleId))
                else:
                    # Handle SH
                    self.sendAction('/rbt/sport/peering/action/remove_rule',
                                    ('idx', 'uint16', eachRuleId))
        else:
            for fromIdx, toIdx in self.reorderEntries('moveFromPeeringRule_',
                                                      'moveToPeeringRule_',
                                                      '/rbt/sport/peering/config/rule'):
                if policyType:
                    # Handle CMC's edit policy page
                    Nodes.editNodeSequence(self.mgmt, base, peeringRuleSpec, 'move',
                                          fromIdx, moveto=toIdx)
                else:
                    # Handle SH
                    self.sendAction('/rbt/sport/peering/action/move_rule',
                                    ('from_idx', 'uint16', str(fromIdx)),
                                    ('to_idx', 'uint16', str(toIdx)))

    # Service Ports pagelet
    def setupServicePorts(self):
        portPrefix = self.cmcPolicyRetarget('/rbt/sport/inner/config/port')
        mapPrefix = self.cmcPolicyRetarget('/rbt/sport/inner/config/map')
        if 'apply' in self.fields:
            # handle regular settings, then the service ports list
            FormUtils.setNodesFromConfigForm(self.mgmt, self.fields)
            newPorts = self.fields.get('ports')
            Nodes.setWordList(self.mgmt, portPrefix, newPorts, 'uint16')
        elif 'addPortMapping' in self.fields:
            # handle add port mapping
            destPort = self.fields.get('addPortMapping_destinationPort')
            servPort = self.fields.get('addPortMapping_servicePort')
            self.setNodes(('%s/%s/port' % (mapPrefix, destPort), 'uint16', servPort))
        elif 'removePortMapping' in self.fields:
            # handle remove port mappings
            FormUtils.deleteNodesFromConfigForm(self.mgmt,
                                                mapPrefix,
                                                'selectedPort_',
                                                self.fields)


    def setupServiceWccp(self):
        fields = self.fields
        base = self.cmcPolicyRetarget('/rbt/sport/wccp/config')
        cmcPolicy = 'editPolicy' in fields
        if 'addWccp' in fields:
            idd = fields.get('addWccp_id')
            interface = fields.get('addWccp_interface')
            wbase = '%s/interface/%s/group/%s' % (base, interface, idd)
            protocol = fields.get('addWccp_protocol')
            password = fields.get('addWccp_password')
            priority = fields.get('addWccp_priority')
            weight = fields.get('addWccp_weight')
            encap = fields.get('addWccp_encap')
            assign = fields.get('addWccp_assign')
            srcIpMask = fields.get('addWccp_srcIpMask')
            srcPortMask = fields.get('addWccp_srcPortMask')
            dstIpMask = fields.get('addWccp_dstIpMask')
            dstPortMask = fields.get('addWccp_dstPortMask')
            portsMode = fields.get('addWccp_portsMode')
            flags = (int(portsMode) << 4) & 0x30
            if fields.get('addWccp_srcIpHash'):
                flags |= 0x1
            if fields.get('addWccp_dstIpHash'):
                flags |= 0x2
            if fields.get('addWccp_srcPortHash'):
                flags |= 0x4
            if fields.get('addWccp_dstPortHash'):
                flags |= 0x8
            ports = fields.get('addWccp_ports')
            routerIps = FormUtils.splitSeparators(fields.get('addWccp_routerIps', ''))

            nodeList = [(wbase + '/encap_scheme', 'string', encap),
                        (wbase + '/assign_scheme', 'string', assign)]
            if assign != 'hash':
                nodeList += [(wbase + '/src_ip_mask', 'string', srcIpMask),
                            (wbase + '/dst_ip_mask', 'string', dstIpMask),
                            (wbase + '/src_port_mask', 'string', srcPortMask),
                            (wbase + '/dst_port_mask', 'string', dstPortMask)]
            nodeList += [(wbase + '/flags', 'uint32', str(flags)),
                         (wbase + '/protocol', 'uint16', protocol),
                         (wbase + '/password', 'string', password),
                         (wbase + '/priority', 'uint16', priority),
                         (wbase + '/weight', 'uint16', weight)]
            for ip in routerIps:
                nodeList.append ((wbase + '/router/' + ip, 'ipv4addr', ip))

            self.setNodes(*nodeList)
            Nodes.setWordList(self.mgmt, wbase + '/port', ports, 'uint16')

        elif 'removeWccpGroups' in fields:
            # Similar to FormUtils.deleteNodesFromConfigForm, but modified slightly:
            names = FormUtils.getPrefixedFieldNames('selectedWccp_', fields)
            if names:
                Nodes.delete(self.mgmt, \
                             *['%s/interface/%s/group/%s' % \
                             (base, name.split('&&&')[0], name.split('&&&')[1]) \
                             for name in names])
        elif 'editWccpApply' in fields:
            idd = fields.get('editWccp_id')
            interface = fields.get('editWccp_interface')
            wbase = '%s/interface/%s/group/%s' % (base, interface, idd)
            protocol = fields.get('editWccp_protocol')
            encap = fields.get('editWccp_encap')
            assign = fields.get('editWccp_assign')
            srcIpMask = fields.get('editWccp_srcIpMask')
            dstIpMask = fields.get('editWccp_dstIpMask')
            srcPortMask = fields.get('editWccp_srcPortMask')
            dstPortMask = fields.get('editWccp_dstPortMask')
            password = fields.get('editWccp_password', '')
            priority = fields.get('editWccp_priority')
            weight = fields.get('editWccp_weight')
            portsMode = fields.get('editWccp_portsMode')
            flags = (int(portsMode) << 4) & 0x30
            if 'mask' == assign:
                hashFlags = int(Nodes.present(self.mgmt, wbase + '/flags')) \
                            & 0xf
                flags |= hashFlags
            else:
                if fields.get('editWccp_srcIpHash'):
                    flags |= 0x1
                if fields.get('editWccp_dstIpHash'):
                    flags |= 0x2
                if fields.get('editWccp_srcPortHash'):
                    flags |= 0x4
                if fields.get('editWccp_dstPortHash'):
                    flags |= 0x8
            ports = fields.get('editWccp_ports')

            if cmcPolicy:
                # cmc sets a list of router ips
                routerIps = fields.get('editWccp_routerIps', '')
                Nodes.setWordList(self.mgmt, wbase + '/router', routerIps, 'ipv4addr')
            Nodes.setWordList(self.mgmt, wbase + '/port', ports, 'uint16')

            nodeList = [(wbase + '/encap_scheme', 'string', encap),
                        (wbase + '/assign_scheme', 'string', assign)]
            if assign != 'hash':
                nodeList += [(wbase + '/src_ip_mask', 'string', srcIpMask),
                            (wbase + '/dst_ip_mask', 'string', dstIpMask),
                            (wbase + '/src_port_mask', 'string', srcPortMask),
                            (wbase + '/dst_port_mask', 'string', dstPortMask)]
            nodeList += [(wbase + '/protocol', 'uint16', protocol),
                         (wbase + '/flags', 'uint32', str(flags)),
                         (wbase + '/priority', 'uint16', priority),
                         (wbase + '/weight', 'uint16', weight)]

            if password != FormUtils.bogusPassword:
                nodeList.append((wbase + '/password', 'string', password))
            self.setNodes(*nodeList)

        elif 'addWccpRouter' in fields:
            wccpId = fields.get('editWccp_id')
            wccpInterface = fields.get('editWccp_interface')
            ip = fields.get('addWccpRouter_ip')
            self.setNodes(('%s/interface/%s/group/%s/router/%s' % (base, wccpInterface, wccpId, ip), 'ipv4addr', ip))
        elif 'removeWccpRouter' in fields:
            wccpId = fields.get('editWccp_id')
            wccpInterface = fields.get('editWccp_interface')
            FormUtils.deleteNodesFromConfigForm(self.mgmt, '%s/interface/%s/group/%s/router' % (base, wccpInterface, wccpId),
                                                'selectedWccpRouter_',
                                                fields)


    hwAssistRuleSpec = {'action': 'string',
                        'description': 'string',
                        'subnet_a/network': 'ipv4prefix',
                        'subnet_b/network': 'ipv4prefix',
                        'vlan': 'int16'}

    # Hardware Assist Rules page
    def setupHWAssistRules(self):
        fields = self.fields
        cmcPolicy = fields.get('editPolicy')
        default_vlan = Nodes.present(self.mgmt, '/rbt/hwassist/config/nic_def_vlan_id', '1')
        base = self.cmcPolicyRetarget('/rbt/hwassist/config/rule')
        if 'addHWAssistRule' in fields:
            index = fields.get('addHWAssist_idx')
            # retrieve the fields as a batch from the rulespec above
            # rule is a dict of key, value pairs
            rule = dict([(k, fields.get('addHWAssist_' + k, ''))
                         for k in gui_AdvancedNetworking.hwAssistRuleSpec.iterkeys()])
            # adjust the vlan value
            rule['vlan'] = RVBDUtils.translateVlanInput(rule['vlan'], untaggedValue=default_vlan)

            if cmcPolicy:
                # CMC
                Nodes.editNodeSequence(self.mgmt, base, gui_AdvancedNetworking.hwAssistRuleSpec, 'add',
                                      int(index), rule)
            else:
                # SH
                self.sendAction('/rbt/hwassist/action/add_rule',
                                ('idx', 'uint16', index),
                                *[(k, gui_AdvancedNetworking.hwAssistRuleSpec[k], v)
                                  for k, v in rule.iteritems()])

        elif 'editHWAssistRule' in fields:
            index = fields.get('editHWAssist_idx')
            rule = dict([(k, fields.get('editHWAssist_' + k, ''))
                         for k in gui_AdvancedNetworking.hwAssistRuleSpec.iterkeys()])
            rule['vlan'] = RVBDUtils.translateVlanInput(rule['vlan'], untaggedValue=default_vlan)
            if cmcPolicy:
                # CMC
                Nodes.editNodeSequence(self.mgmt, base, gui_AdvancedNetworking.hwAssistRuleSpec, 'edit',
                                      int(index), rule)
            else:
                # SH
                # Avoiding the edit_rule mgmt action. It doesn't work.
                self.sendAction('/rbt/hwassist/action/remove_rule',
                                ('idx', 'uint16', index))
                self.sendAction('/rbt/hwassist/action/add_rule',
                                ('idx', 'uint16', index),
                                 *[(k, gui_AdvancedNetworking.hwAssistRuleSpec[k], v)
                                  for k, v in rule.iteritems()])

        elif 'removeRules' in fields:
            ids = FormUtils.getPrefixedFieldNames('movefrom_', fields)
            if cmcPolicy:
                Nodes.editNodeSequence(self.mgmt, base, gui_AdvancedNetworking.hwAssistRuleSpec,
                                      'remove', map(int, ids))
            else:
                ids.sort(key=int, reverse=True)
                for id in ids:
                    self.sendAction('/rbt/hwassist/action/remove_rule',
                                    ('idx', 'uint16', id))
        else: #moveto_
            for fromIdx, toIdx in self.reorderEntries('movefrom_', 'moveto_', base):
                if cmcPolicy:
                    Nodes.editNodeSequence(self.mgmt, base, gui_AdvancedNetworking.hwAssistRuleSpec, 'move',
                                          fromIdx, moveto=toIdx)
                else:
                    self.sendAction('/rbt/hwassist/action/move_rule',
                                    ('from_idx', 'uint16', str(fromIdx)),
                                    ('to_idx', 'uint16', str(toIdx)))

    def setupPortLabels(self):
        cmcMode = 'editPolicy' in self.fields
        if 'addPortLabel' in self.fields:
            name = self.fields.get('addPortLabel_name')
            portsText = self.fields.get('addPortLabel_ports')
            if cmcMode:
                self.setPortLabelsCMC(name, portsText)
            else:  # SH
                self.sendAction('/rbt/portlabel/action/action',
                                ('label', 'string', name),
                                ('action_name', 'string', 'add'),
                                ('ports', 'string', portsText))
        if 'editPortLabel' in self.fields:
            name = self.fields.get('editPortLabel_name')
            portsText = self.fields.get('editPortLabel_ports')
            if cmcMode:
                self.setPortLabelsCMC(name, portsText)
            else:  # SH
                self.sendAction('/rbt/portlabel/action/action',
                                ('label', 'string', name),
                                ('action_name', 'string', 'edit'),
                                ('ports', 'string', portsText))
        if 'removePortLabel' in self.fields:
            selecteds = FormUtils.getPrefixedFieldNames('selectedPortLabel_', self.fields)
            if cmcMode:
                base = self.cmcPolicyRetarget('/rbt/portlabel/config')
                FormUtils.deleteNodesFromConfigForm(self.mgmt,
                                                    base,
                                                    'selectedPortLabel_',
                                                    self.fields)
            else:  # SH
                for name in selecteds:
                    try:
                        self.sendAction('/rbt/portlabel/action/remove',
                                        ('label', 'string', name))
                    except:
                         raise NonZeroReturnCodeException, 'Port label \'%s\' is being used' % name


    def setupHostLabels(self):
        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(self.fields)

        HOST_LABEL_PREFIX = pathPrefix + '/rules/labels/host/config/label/'
        ACTION_MANUAL_RESOLVE = '/rules/labels/host/action/refresh_hostname_cache'

        def addNodeEntries(nodes, hostLabelName, opPrefix):

            # Create hostname nodes
            list = re.split("[,\s]+", self.fields.get(opPrefix + '_hostnameList'))
            for entry in list:
                if entry:
                    nodes.append((HOST_LABEL_PREFIX + '%s/hostname/%s'
                                % (hostLabelName, entry), 'hostname', entry))

            # Create subnet nodes
            list = re.split("[,\s]+", self.fields.get(opPrefix + '_subnetList'))
            for entry in list:
                if entry:
                    nodeEntry = entry.replace('/', '\\/')
                    nodes.append((HOST_LABEL_PREFIX + '%s/subnet/%s'
                                % (hostLabelName, nodeEntry), 'ipv6prefix', entry))

            self.setNodes(*nodes)

        if 'manualResolve' in self.fields:
            self.sendAction(ACTION_MANUAL_RESOLVE)

        elif 'addHostLabel' in self.fields:
            hostLabelName = self.fields.get('addHostLabel_name')
            nodes = [(HOST_LABEL_PREFIX + hostLabelName, 'string', hostLabelName)]
            addNodeEntries(nodes, hostLabelName, 'addHostLabel')

        elif 'editHostLabel' in self.fields:
            hostLabelName = self.fields.get('editHostLabel_name')
            nodes = [(HOST_LABEL_PREFIX + hostLabelName, 'none', '')]
            addNodeEntries(nodes, hostLabelName, 'editHostLabel')

        elif 'removeHostLabel' in self.fields:
            selectedList = FormUtils.getPrefixedFieldNames('selectedHostLabel_', self.fields)
            nodes = []
            for name in selectedList:
                nodes.append((HOST_LABEL_PREFIX + name))
            self.deleteNodes(*nodes)


class xml_AdvancedNetworking(XMLContent):
    dispatchList = ['asymmetricRouting',
                    'neighbors',
                    'netflow',
                    'peering',
                    'securePeer',
                    'servicePortMap',
                    'subnetSide',
                    'wccpGroups',
                    'hwAssistRules',
                    'portLabels',
                    'hostLabels',
                    'hostLabelsCMC']

    # for setupAdvNet_asymmetric.psp:
    #
    # <routes>
    #   <route name="" ip1="" ip2="" reason="" timeout=""/>
    #   ...
    # </routes>
    def asymmetricRouting(self):
        base = self.cmcPolicyRetarget('/rbt/sport/intercept/state/asym_routing')
        routes = Nodes.getMgmtSetEntries(self.mgmt, base)
        routeNames = routes.keys()
        routeNames.sort()
        result = self.doc.createElement('routes')
        for routeName in routeNames:
            route = routes.get(routeName)
            ip1 = route.get('ip1', '')
            ip2 = route.get('ip2', '')
            routeEl = self.doc.createElement('route')
            routeEl.setAttribute('ip-pair', '%s_%s' % (ip1, ip2))
            routeEl.setAttribute('ip1', ip1)
            routeEl.setAttribute('ip2', ip2)
            routeEl.setAttribute('reason', route.get('reason'))
            routeEl.setAttribute('timeout', route.get('timeout'))
            result.appendChild(routeEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()


    # for setupAdvNet_forwarding.psp:
    #
    # <neighbors>
    #   <neighbor name="" ip="" port="" />
    #   ...
    # </neighbors>
    def neighbors(self):
        base = self.cmcPolicyRetarget('/rbt/sport/intercept/config/neighbor/name')
        neighbors = Nodes.getMgmtSetEntries(self.mgmt, base)
        names = neighbors.keys()
        names.sort()
        result = self.doc.createElement('neighbors')
        for name in names:
            neighbor = neighbors[name]
            neighborEl = self.doc.createElement('neighbor')
            neighborEl.setAttribute('name', name)
            neighborEl.setAttribute('ip', neighbor.get('main_address'))
            neighborEl.setAttribute('port', neighbor.get('port'))
            addips = Nodes.getMgmtLocalChildrenNames(self.mgmt,
                                                     '%s/%s/additional_address' % (base, name))
            addips.sort(FormUtils.compareIpv4)
            for addip in addips:
                addIpEl = self.doc.createElement('additional-address')
                addIpEl.setAttribute('ip', addip)
                neighborEl.appendChild(addIpEl)
            result.appendChild(neighborEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()


    # for setupAdvNet_encryption.psp:
    #
    # Encryption pagelet
    #
    # <portmappings>
    #   <securePeer peer=""
    #               encryption=""
    #               authentication=""
    #               state=""
    #               duplex=""
    #               creation="">
    #   ...
    # </portmappings>
    def securePeer(self):
        base = self.cmcPolicyRetarget('/rbt/auth/config/peers')
        peers = self.mgmt.getChildren(base).values()
        peers.sort(FormUtils.compareIpv4)
        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(self.fields)
        result = self.doc.createElement('portmappings')
        for eachPeer in peers:
            element = self.doc.createElement('securePeer')
            if policyName:
                element.setAttribute('peer', eachPeer)
                element.setAttribute('encryption', 'N/A')
                element.setAttribute('authentication', 'N/A')
                element.setAttribute('state', 'N/A')
                element.setAttribute('duplex', 'N/A')
                element.setAttribute('creation', 'N/A')
            else:
                peerState = self.mgmt.get('/rbt/auth/state/peers/%s' % eachPeer)
                peerState = peerState.split()
                peer, encryption, authentication, state, duplex = peerState[0:5]
                creation = ' '.join(peerState[5:])
                if encryption == 'null':
                    encryption = 'NULL'
                if authentication == 'null' or authentication == '(null)':
                    authentication = 'NULL'
                element.setAttribute('peer', peer)
                element.setAttribute('encryption', encryption)
                element.setAttribute('authentication', authentication)
                element.setAttribute('state', state)
                element.setAttribute('duplex', duplex)
                element.setAttribute('creation', creation)
            result.appendChild(element)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupAdvNet_ports.psp:
    #
    # The servicePortMap command:
    #
    # <portmappings>
    #   <portmapping destinationport="" serviceport="" />
    # </portmappings>
    def servicePortMap(self):
        base = self.cmcPolicyRetarget('/rbt/sport/inner/config/map')
        mappings = Nodes.getMgmtSetEntries(self.mgmt, base)
        destPorts = mappings.keys()
        destPorts.sort(FormUtils.compareStringInts)
        result = self.doc.createElement('portmappings')
        for destPort in destPorts:
            element = self.doc.createElement('portmapping')
            element.setAttribute('destinationport', destPort)
            element.setAttribute('serviceport', mappings[destPort].get('port',''))
            result.appendChild(element)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupSubnetSide.psp:
    #
    # Subnet Side, for use by both Netflow and RSP Virtual Inpath mode,
    # to determine whether a packet came from the LAN side or WAN side
    # based on the source IP or subnet.
    #
    # Appears on the page:
    # Configure > Networking > Subnet Side
    #
    # Documented in TWiki, MidwayVirtualInpath
    #
    # <subnetSide>
    #   <side index="default"
    #         srcsubnet=""
    #         src_side="" />
    # </subnetSide>
    def subnetSide(self):
        base = self.cmcPolicyRetarget('/rbt/subnet/config/side/rule')
        mappings = Nodes.getMgmtSetEntries(self.mgmt, base)
        ruleIndices = mappings.keys()
        ruleIndices.sort(FormUtils.compareStringInts)
        mappings['default'] = {'network_prefix': '0.0.0.0/0', 'lan': 'false'}
        ruleIndices.append('default')
        result = self.doc.createElement('subnetSide')
        for index in ruleIndices:
            mapping = mappings.get(index)
            element = self.doc.createElement('side')
            element.setAttribute('index', index)
            netPrefix = mapping.get('network_prefix', '0.0.0.0/0')
            if '0.0.0.0/0' == netPrefix:
                netPrefix = 'all'
            element.setAttribute('srcsubnet', netPrefix)
            element.setAttribute('src_side', mapping.get('lan'))
            result.appendChild(element)
        result.appendChild(element)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()


    # for setupAdvNet_wccp.psp:
    #
    # The wccpGroups command:
    #
    # <wccpgroups>
    #    <wccpgroup interface_id=""
    #               interface_idPretty=""
    #               id=""
    #               interface=""
    #               encap_scheme=""
    #               protocol=""
    #               flags=""
    #               priority=""
    #               weight=""
    #      <routers>
    #        <router .../>
    #      </routers>
    #      <webcaches>
    #        <webcache .../>
    #      </webcaches>
    #   </webcaches>
    # </wccpgroups>
    def wccpGroups(self):
        configBase = self.cmcPolicyRetarget('/rbt/sport/wccp/config/interface')
        stateBase = self.cmcPolicyRetarget('/rbt/sport/wccp/state/interface')
        interfaces = Nodes.getMgmtSetEntries(self.mgmt, configBase)
        interfaceIds = interfaces.keys()
        interfaceIds.sort(FormUtils.alphanumericCompare)
        cmc = 'editPolicy' in self.fields
        result = self.doc.createElement('wccpgroups')
        for interfaceId in interfaceIds:
            groups = Nodes.getMgmtSetEntries(self.mgmt, '%s/%s/group' % (configBase, interfaceId))
            groupIds = groups.keys()
            groupIds.sort(FormUtils.alphanumericCompare)
            for groupId in groupIds:
                group = groups[groupId]
                groupEl = self.doc.createElement('wccpgroup')
                groupEl.setAttribute('id', groupId)
                groupEl.setAttribute('interface', interfaceId)

                # "&&&" is the delimiter. The AET needs one field that has both the interface and id info:
                groupEl.setAttribute('interface_id', '%s&&&%s' % (interfaceId, groupId))
                groupEl.setAttribute('interface_idPretty', '%s, %s' % (interfaceId, groupId))
                for key in ['assign_scheme', 'encap_scheme', 'protocol', 'flags', 'priority', 'weight', \
                            'src_ip_mask', 'dst_ip_mask', 'src_port_mask', 'dst_port_mask']:
                    groupEl.setAttribute(key, group.get(key, ''))
                groupEl.setAttribute('password', group.get('password') and FormUtils.bogusPassword or '')

                protocol = group.get('protocol', '').strip()
                if '6' == protocol:
                    groupEl.setAttribute('protocol_str', 'TCP')
                elif '17' == protocol:
                    groupEl.setAttribute('protocol_str', 'UDP')
                elif '1' == protocol:
                    groupEl.setAttribute('protocol_str', 'ICMP')
                # CLI and web GUI safeguard against any other protocols,
                # but mgmtd does not.
                # Ie., mdreq set create - \\
                # /rbt/sport/wccp/config/group/80/protocol uint16 80
                # works!
                else:
                    groupEl.setAttribute('protocol_str',
                        '%s (invalid)' % protocol)

                ports = Nodes.getMgmtLocalChildrenNames(self.mgmt, '%s/%s/group/%s/port' % (configBase, interfaceId, groupId))
                ports.sort(FormUtils.compareStringInts)
                groupEl.setAttribute('ports', ', '.join(ports))

                # Steelhead gets router status data (when valid), CMC does not
                routerIds = Nodes.getMgmtLocalChildrenNames(self.mgmt, '%s/%s/group/%s/router' % (configBase, interfaceId, groupId))
                routerIds.sort(FormUtils.compareIpv4)
                groupIsValid = 'true' == Nodes.present(self.mgmt, '%s/%s/group/%s/valid_status' % (stateBase, interfaceId, groupId), '')
                routerStatus = (not cmc) and groupIsValid and \
                               Nodes.getMgmtSetEntries(self.mgmt, '%s/%s/group/%s/router' % (stateBase, interfaceId, groupId))
                routersEl = self.doc.createElement('routers')
                for routerId in routerIds:
                    routerEl = self.doc.createElement('router')
                    routerEl.setAttribute('id', routerId)
                    router = routerStatus and routerStatus[routerId] or {}
                    for key in ['identity', 'state', \
                                'forward_scheme_negotiated', 'return_scheme_negotiated', 'assign_scheme_negotiated', \
                                'iseeyou_msg_count', 'iseeyou_msg_time', \
                                'removalquery_msg_count', 'removalquery_msg_time', \
                                'hereiam_msg_count', 'hereiam_msg_time', \
                                'redirectassign_msg_count', 'redirectassign_msg_time']:
                        routerEl.setAttribute(key, router.get(key, '--'))
                    routersEl.appendChild(routerEl)
                groupEl.appendChild(routersEl)

                # Steelhead gets webcache data, CMC does not
                if not cmc:
                    groupEl.appendChild(self.wccpWebcaches(interfaceId, groupId))
                result.appendChild(groupEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # compose a wccp webcaches xml element for the above
    def wccpWebcaches(self, interfaceId, groupId):
        webcachesEl = self.doc.createElement('webcaches')
        stateBase = self.cmcPolicyRetarget('/rbt/sport/wccp/state/interface/%s/group/%s' % (interfaceId, groupId))
        webcaches = Nodes.getMgmtSetEntries(self.mgmt, '%s/webcache' % (stateBase))
        webcacheIds = webcaches.keys()
        webcacheIds.sort(FormUtils.compareStringInts)
        ipToInterfaceMap = Nodes.ipToInterfaceMap(self.mgmt)

        for webcacheId in webcacheIds:
            webcache = webcaches[webcacheId]
            webcacheEl = self.doc.createElement('webcache')
            webcacheEl.setAttribute('id', webcacheId)
            self.xmlizeAttributes(webcacheEl, webcache, ('cacheid', 'is_hash'))

            # If this cache ID (IP address) corresponds to an interface on this
            # Steelhead, include the interface name too.
            webcacheIP = webcache.get('cacheid')
            if webcacheIP in ipToInterfaceMap:
                cacheidPretty = '%s (%s)' % (webcacheIP, ipToInterfaceMap[webcacheIP])
                webcacheEl.setAttribute('cacheidPretty', cacheidPretty)
            else:
                webcacheEl.setAttribute('cacheidPretty', webcacheIP)

            wcWeight = webcache.get('weight', '').strip()
            if '65535' == wcWeight:
                webcacheEl.setAttribute('wc_weight', 'Unassigned')
            else:
                webcacheEl.setAttribute('wc_weight', wcWeight)

            distRaw = webcache.get('distribution', '').strip()
            if '-1' == distRaw:
                webcacheEl.setAttribute('distribution', 'Unassigned')
            else:
                try:
                    dist = '%s (%.2f%%)' % (distRaw,
                                            float(webcache.get('distribution_percent')))
                    webcacheEl.setAttribute('distribution', dist)
                except:
                    webcacheEl.setAttribute('distribution', '')
            if 'true' == webcache.get('is_hash'):
                # hash mode
                hashReceived = Nodes.present(self.mgmt,
                                             '%s/webcache/1/hashvalue/received' % \
                                                 (stateBase))
                webcacheEl.setAttribute('hash_received', hashReceived)
            else:
                # masks mode
                masksEl = self.doc.createElement('masks')
                masksData = self.mgmt.getChildren('%s/webcache/%s/maskvalue/1' % \
                                                      (stateBase, webcacheId))
                self.xmlizeAttributes(masksEl, masksData, masksData.keys())
                masks = Nodes.getMgmtSetEntries(self.mgmt,
                                                '%s/webcache/%s/maskvalue/1/elem' % \
                                                    (stateBase, webcacheId))
                maskIds = masks.keys()
                maskIds.sort(FormUtils.alphanumericCompare)
                for maskId in maskIds:
                    mask = masks[maskId]
                    if mask.get('wc_ip') == webcacheIP:
                        try:
                            maskIdZ = str(int(maskId) - 1)
                        except:
                            maskIdZ = ''
                        maskEl = self.doc.createElement('mask')
                        maskEl.setAttribute('id', maskIdZ)
                        self.xmlizeAttributes(maskEl, mask, mask.keys())
                        masksEl.appendChild(maskEl)
                webcacheEl.appendChild(masksEl)
            webcachesEl.appendChild(webcacheEl)
        return webcachesEl

    # for setupAdvNet_netflow.psp:
    #
    # <collectors>
    #   <collector ip="" port="" export-if="" spoot="" id="" />
    # </collectors>
    def netflow(self):

        versionMap = {
            '9.1': 'CascadeFlow',
            '5.1': 'CascadeFlow-compatible',
            '9': 'Netflow v9',
            '5': 'Netflow v5',
        }

        base = self.cmcPolicyRetarget('/rbt/sport/netflow/config/collector/address')
        ips = Nodes.getMgmtLocalChildrenNames(self.mgmt, base)
        ips.sort(FormUtils.alphanumericCompare)
        result = self.doc.createElement('collectors')
        for ip in ips:
            ports = Nodes.getMgmtLocalChildrenNames(self.mgmt,
                                                    '%s/%s/port' % (base, ip))
            ports.sort(FormUtils.alphanumericCompare)
            for port in ports:
                collectorEl = self.doc.createElement('collector')
                collectorEl.setAttribute('ip', ip)
                collectorEl.setAttribute('port', port)
                collectorEl.setAttribute('addressPretty', '%s:%s' % (ip, port))
                collectorEl.setAttribute('id', '%s:%s' % (ip, port))
                portPath = '%s/%s/port/%s' % (base, ip, port)
                portData = self.mgmt.getChildren(portPath)
                collectorEl.setAttribute('export-if', portData.get('export_if', ''))
                version = portData.get('version', '')
                # spoof/'Show Lan Address' does not apply to v9 collectors
                if version in ('9', '9.1'):
                    collectorEl.setAttribute('spoof', 'N/A')
                else:
                    collectorEl.setAttribute('spoof', portData.get('spoof', ''))
                collectorEl.setAttribute('version', version)
                collectorEl.setAttribute(
                    'versionPretty', versionMap.get(version, version))
                collectorEl.setAttribute('filterEnable', portData.get('filter_enable', 'false'))

                # note: the pagelet depends on the exact format of the ifs attribute
                ifs = Nodes.getMgmtSetEntries(self.mgmt, portPath + '/interface')
                ifNames = ifs.keys()
                ifNames.sort(FormUtils.alphanumericCompare)
                ifStrings = []
                for ifName in ifNames:
                    capture = ifs[ifName].get('capture')
                    if capture:
                        ifStrings.append('%s: %s' % (ifName, capture))
                collectorEl.setAttribute('ifs', ';'.join(ifStrings))

                # filters:
                filters = Nodes.getMgmtSetEntries(self.mgmt, portPath + '/filter')
                filterIds = filters.keys()
                filterIds.sort(FormUtils.alphanumericCompare)
                filterStrings = []
                for idd in filterIds:
                    filt = filters[idd]
                    if '0' == filt.get('filter_port'):
                        # netmask case:
                        filterStrings.append(
                            '%s/%s' % (filt.get('filter_ip', ''),
                                       filt.get('filter_netmask', '')))
                    else:
                        # port case:
                        filterStrings.append(
                            '%s:%s' % (filt.get('filter_ip', ''),
                                       filt.get('filter_port', '')))
                collectorEl.setAttribute('filters', ';'.join(filterStrings))

                result.appendChild(collectorEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupAdvNet_peering.psp:
    #
    # <peers>
    #   <peer id=""
    #         type="" type-pretty=""
    #         source=""
    #         destination=""
    #         port="" port-pretty=""
    #         peer="" peer-pretty=""
    #         ssl="" ssl-pretty=""
    #         desc=""/>
    # </peers>
    def peering(self):
        base = self.cmcPolicyRetarget('/rbt/sport/peering/config/rule')
        rules = Nodes.getMgmtSetEntriesDeep(self.mgmt, base)
        ruleIds = rules.keys()
        ruleIds.sort(FormUtils.compareStringInts)
        # default rule at the end
        rules['default'] = {'action': 'normal',
                            'src/network': '::/1',
                            'dst/network': '::/1',
                            'dst/port_label': '0',
                            'peer/addr': '0.0.0.0',
                            'ssl_cap': 'dont_check',
                            'saas_action': 'auto'}
        ruleIds.append('default')
        result = self.doc.createElement('peering-rules')
        map_actionType = {'normal': 'Auto', 'respond': 'Accept', 'forward': 'Pass'}
        map_sslCapable = {'dont_check': 'No Check', 'capable': 'Capable', 'incapable': 'Incapable'}
        map_cloudAcceleration = {'auto': 'Auto', 'passthru': 'Pass'}

        for ruleID in ruleIds:
            rule = rules[ruleID]
            # perform some renaming
            ruleType = rule.get('action', '')
            ruleSrc = RVBDUtils.ipv4v6ToMappedSubnet(rule.get('src/network', '0.0.0.0/0'))
            ruleDst = RVBDUtils.ipv4v6ToMappedSubnet(rule.get('dst/network', '0.0.0.0/0'))
            rulePeer = rule.get('peer/addr', '0.0.0.0')
            if '0.0.0.0' == rulePeer:
                rulePeer = 'All-IPv4'
            rulePort = rule.get('dst/port_label', '0')
            rulePortPretty = rulePort
            if '0' == rulePort:
                rulePort = 'all'
                rulePortPretty = 'All'
            ruleCloudAcceleration = rule.get('saas_action', '')

            ruleEl = self.doc.createElement('rule')
            ruleEl.setAttribute('id', ruleID)
            ruleEl.setAttribute('type', ruleType)
            ruleEl.setAttribute('type-pretty', map_actionType.get(ruleType, ''))
            ruleEl.setAttribute('source', ruleSrc)
            ruleEl.setAttribute('destination', ruleDst)
            ruleEl.setAttribute('port', rulePort)
            ruleEl.setAttribute('port-pretty', rulePortPretty)
            ruleEl.setAttribute('peer', rulePeer)
            ruleEl.setAttribute('ssl', rule.get('ssl_cap', ''))
            ruleEl.setAttribute('ssl-pretty', map_sslCapable.get(rule.get('ssl_cap', ''), ''))
            ruleEl.setAttribute('cloud-acceleration', ruleCloudAcceleration)
            ruleEl.setAttribute('cloud-acceleration-pretty', map_cloudAcceleration.get(ruleCloudAcceleration, 'Auto'))
            ruleEl.setAttribute('description', rule.get('description', ''))
            result.appendChild(ruleEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()


    #<hwAssistRules>
    #  <hwAssistRule action="" description="" id=""
    #                subnet-a="" subnet-a-pretty=""
    #                subnet-b="" subnet-b-pretty=""
    #                vlan="" vlan-pretty="" />
    #</hwAssistRules>
    def hwAssistRules(self):
        prettyTypes = {'accept': 'Accept',
                       'pass-through': 'Pass-Through'}

        result = self.doc.createElement('hwAssistRules')
        default_vlan = Nodes.present(self.mgmt, '/rbt/hwassist/config/nic_def_vlan_id', '1')
        base = self.cmcPolicyRetarget('/rbt/hwassist/config/rule')
        rulesDict = Nodes.getMgmtSetEntriesDeep(self.mgmt, base)
        ruleIds = rulesDict.keys()
        ruleIds.sort(FormUtils.alphanumericCompare)
        rulesDict['default'] = {'id': 'default',
                                'description': 'Default hardware assist rule',
                                'action': 'accept',
                                'subnet_a/network': '0.0.0.0/0',
                                'subnet_b/network': '0.0.0.0/0',
                                'vlan': '-1'}
        ruleIds.append('default')

        for ruleId in ruleIds:
            rule = rulesDict[ruleId]
            ruleEl = self.doc.createElement('hwAssistRule')

            # action
            ruleAction = rule.get('action', '')
            ruleEl.setAttribute('action', ruleAction)
            ruleEl.setAttribute('type', \
                                prettyTypes.get(ruleAction, 'Accept'))

            # subnet_a/network
            subA = rule.get('subnet_a/network', '')
            subAPretty = subA
            if subA.endswith('/0'):
                subAPretty = 'All'
            ruleEl.setAttribute('subnet-a', subA)
            ruleEl.setAttribute('subnet-a-pretty', subAPretty)

            # subnet_b/network
            subB = rule.get('subnet_b/network', '')
            subBPretty = subB
            if subB.endswith('/0'):
                subBPretty = 'All'
            ruleEl.setAttribute('subnet-b', subB)
            ruleEl.setAttribute('subnet-b-pretty', subBPretty)

            # VLAN
            vlan, vlanPretty = RVBDUtils.translateVlanOutput(rule.get('vlan', ''), untaggedValue=default_vlan)
            ruleEl.setAttribute('vlan', vlan)
            ruleEl.setAttribute('vlan-pretty', vlanPretty)

            ruleEl.setAttribute('id', ruleId)
            ruleEl.setAttribute('description', rule.get('description', ''))
            result.appendChild(ruleEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupPortLabels.psp:
    #
    # <portlabels>
    #   <portlabel name="" range="" />
    #   ...
    # </portlabels>
    def portLabels(self):
        if RVBDUtils.isGW():
            path = '/rbt/gw/portlabel/config'
        else:
            path = '/rbt/portlabel/config'

        configPath = self.cmcPolicyRetarget(path)
        portLabels = Nodes.getMgmtLocalChildrenNames(self.mgmt, configPath)
        portLabels.sort()
        result = self.doc.createElement('portlabels')
        for portLabel in portLabels:
            portLabelEl = self.doc.createElement('portlabel')
            portLabelEl.setAttribute('name', portLabel)
            ports = Nodes.getMgmtSetEntries(self.mgmt, '%s/%s/port' % (configPath, portLabel))
            portNums = ports.keys()
            portNums.sort(FormUtils.compareStringInts)
            for portNum in portNums:
                start = ports[portNum]['start']
                end = ports[portNum]['end']
                portEl = self.doc.createElement('port')
                rangeVal = start
                if start != end:
                    rangeVal += '-' + end
                portEl.setAttribute('range', rangeVal)
                portLabelEl.appendChild(portEl)
            result.appendChild(portLabelEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupHostLabels.psp:
    #
    #   <hostLabels refreshTime="">
    #       <hostLabel name="">
    #           <host name="" status="" timestamp="">
    #               <ipList>
    #                   <ipAddr name="">
    #                   ...
    #               </ipList>
    #           </host>
    #           <subnetList>
    #               <subnet name=""/>
    #               ...
    #           </subnetList>
    #   </hostLabels>
    #
    def hostLabels(self):
        parentEl = self.doc.createElement('hostLabels')
        self.doc.documentElement.appendChild(parentEl)

        # Get the time interval for when automatic resolutions fires
        refreshTime = Nodes.present(self.mgmt, '/rules/labels/host/config/refresh_time', '0')
        parentEl.setAttribute('refreshTime', str(int(refreshTime) / 1000))

        hostLabelTree = Nodes.getTreeifiedSubtree(self.mgmt, '/rules/labels/host/state/label')
        keyNames = hostLabelTree.keys()
        keyNames.sort(FormUtils.alphanumericCompare)

        for key in keyNames:
            hostLabelEl = self.doc.createElement('hostLabel')
            parentEl.appendChild(hostLabelEl)
            hostLabelEl.setAttribute('name', key)
            if isinstance(hostLabelTree[key], dict):
                if 'host' in hostLabelTree[key].keys():
                    for host in sorted(hostLabelTree[key]['host'].keys(), cmp=FormUtils.alphanumericCompare):
                        hostEl = self.doc.createElement('host')
                        hostLabelEl.appendChild(hostEl)
                        hostEl.setAttribute('name', host)
                        if isinstance(hostLabelTree[key]['host'][host], dict) and \
                                'resolve' in hostLabelTree[key]['host'][host].keys():
                            resolve = hostLabelTree[key]['host'][host]['resolve']
                            if 'timestamp' in resolve.keys():
                                hostEl.setAttribute('timestamp', resolve['timestamp'])
                            if 'status' in resolve.keys():
                                hostEl.setAttribute('status', resolve['status'])
                            if 'address' in resolve.keys():
                                ipListEl = self.doc.createElement('ipList')
                                hostEl.appendChild(ipListEl)
                                sortedIPs = sorted(resolve['address'], cmp=FormUtils.alphanumericCompare)
                                for ip in sortedIPs:
                                    ipEntry = self.doc.createElement('ipAddr')
                                    ipListEl.appendChild(ipEntry)
                                    ipEntry.setAttribute('name', re.sub('\\\/\d+', '', ip))

                # For display purposes, 'IPv4' is ignored since 'IPv6' will
                # contain both IPv4 and IPv6 subnets

                if 'address' in hostLabelTree[key].keys():
                    subnetList = []
                    if 'ipv6' in hostLabelTree[key]['address']:
                        for ip in hostLabelTree[key]['address']['ipv6'].keys():
                            if not isinstance(hostLabelTree[key]['address']['ipv6'][ip], dict) or \
                                    'host' not in hostLabelTree[key]['address']['ipv6'][ip].keys():
                                subnetList.append(ip.replace('\\/', '/'))

                    subnetListEl = self.doc.createElement('subnetList')
                    hostLabelEl.appendChild(subnetListEl)

                    for subnet in sorted(subnetList, cmp=FormUtils.alphanumericCompare):
                        subnetEntry = self.doc.createElement('subnet')
                        subnetListEl.appendChild (subnetEntry)
                        subnetEntry.setAttribute('name', subnet)

        self.writeXmlDoc()

    # for setupHostLabels policy page on CMC (show only config information):
    #
    #   <hostLabels>
    #       <hostLabel name="" hostNames="" subnetNames="">
    #               ...
    #   </hostLabels>
    #
    def hostLabelsCMC(self):
        parentEl = self.doc.createElement('hostLabels')
        self.doc.documentElement.appendChild(parentEl)

        hostLabelTree = Nodes.getTreeifiedSubtree(self.mgmt, self.cmcPolicyRetarget('/rules/labels/host/config/label'))
        labelNames = hostLabelTree.keys()
        labelNames.sort(FormUtils.alphanumericCompare)

        for labelName in labelNames:
            hostLabelEl = self.doc.createElement('hostLabel')
            parentEl.appendChild(hostLabelEl)
            hostLabelEl.setAttribute('name', labelName)
            if isinstance(hostLabelTree[labelName], dict):
                hostnames = ''
                subnets = ''
                if 'hostname' in hostLabelTree[labelName].keys():
                    # hostnames configured
                    hostnames = ';'.join(sorted(hostLabelTree[labelName]['hostname'].values(),
                        cmp=FormUtils.alphanumericCompare))
                if 'subnet' in hostLabelTree[labelName].keys():
                    # subnets configured
                    subnets = ';'.join(sorted(hostLabelTree[labelName]['subnet'].values(),
                        cmp=FormUtils.alphanumericCompare))

                hostLabelEl.setAttribute('subnets', subnets)
                hostLabelEl.setAttribute('hostnames', hostnames)

        self.writeXmlDoc()

