## Copyright 2006, Riverbed Technology, Inc., All rights reserved.
##
## Advanced networking support for gui and xmldata.
## Author: Don Tillman

import re
import FormUtils
import GraphUtils
import Nodes
import qos
import RVBDUtils
from PagePresentation import PagePresentation
from XMLContent import XMLContent

class gui_AdvancedNetworking(PagePresentation):
    # actions handled here
    actionList = ['setupAsymmetricRouting',
                  'setupConnectionForwarding',
                  'setupNetworkAuth',
                  'setupNetworkNetflow',
                  'setupServicePeering',
                  'setupServicePorts',
                  'setupSubnetSide',
                  'setupQoSClassSettings',
                  'setupQoSClasses',
                  'setupQoSSitesRules',
                  'setupQoSMarkingOptimized',
                  'setupQoSMarkingPassthru',
                  'setupQoSMigration',
                  'setupInboundQoSSettings',
                  'setupInboundQoSClasses',
                  'setupInboundQoSRules',
                  'setupServiceWccp',
                  'setupEasyQoS_sites',
                  'setupEasyQoS_apps',
                  'setupEasyQoS_profiles',
                  'setupEasyQoS_easyGatekeeper',
                  'setupEasyQoS_advGatekeeper',
                  'setupHWAssistRules']

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
                self.editNodeSequence(base, self.subnetSpec, 'add',
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
                    self.editNodeSequence(base, self.subnetSpec,
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
                    self.editNodeSequence(base, self.subnetSpec, 'move',
                            fromIdx, moveto=toIdx)
                else: #SH
                    self.sendAction('/rbt/subnet/action/side/rule/move',
                                    ('from_idx', 'uint32', fromIdx),
                                    ('to_idx', 'uint32', toIdx))

    # Peering pagelet
    def setupServicePeering(self):
        fields = self.fields
        base = self.cmcPolicyRetarget('/rbt/sport/peering/config/rule')
        peeringRuleSpec = {'action': 'string',
                           'description': 'string',
                           'dst/network': 'ipv4prefix',
                           'dst/port_label': 'string',
                           'peer/addr': 'ipv4addr',
                           'src/network': 'ipv4prefix',
                           'ssl_cap': 'string'}
        if 'addPeeringRule' in fields:
            # handle add rule
            idx = fields.get('addRule_idx')
            if self.isCMC():
                # Make a rule dict, and edit it in
                rule = dict([(k, self.fields.get('addRule_' + k, ''))
                             for k,t in peeringRuleSpec.iteritems()])
                # handle the special case port value of 'All' here
                if 'all' == rule['dst/port_label'].lower():
                    rule['dst/port_label'] = '0'

                self.editNodeSequence(base, peeringRuleSpec, 'add', int(idx), rule)
            else:  # SH
                action = fields.get('addRule_action')
                description = fields.get('addRule_description', '')
                dst = fields.get('addRule_dst/network')
                port = fields.get('addRule_dst/port_label')
                if port == 'all':
                    port = '0'
                peer = fields.get('addRule_peer/addr')
                src = fields.get('addRule_src/network')
                ssl_cap = fields.get('addRule_ssl_cap')
                self.sendAction('/rbt/sport/peering/action/add_rule',
                                ('action', 'string', action),
                                ('description', 'string', description),
                                ('dst/network', 'ipv4prefix', dst),
                                ('dst/port_label', 'string', port),
                                ('peer/addr', 'ipv4addr', peer),
                                ('src/network', 'ipv4prefix', src),
                                ('ssl_cap', 'string', ssl_cap),
                                ('idx', 'uint16', idx))
        elif 'editPeeringRule' in fields:
            # handle edit rule
            index = fields.get('editRule_index')
            if self.isCMC():
                # Make a rule dict, and edit it in
                rule = dict([(k, self.fields.get('editRule_' + k, ''))
                             for k,t in peeringRuleSpec.iteritems()])
                # handle the special case port value of 'All' here
                if 'all' == rule['dst/port_label'].lower():
                    rule['dst/port_label'] = '0'
                self.editNodeSequence(base, peeringRuleSpec, 'edit', int(index), rule)
            else:  # SH
                action = fields.get('editRule_action')
                description = fields.get('editRule_description', '')
                dst = fields.get('editRule_dst/network')
                port = fields.get('editRule_dst/port_label')
                if port == 'all':
                    port = '0'
                peer = fields.get('editRule_peer/addr')
                src = fields.get('editRule_src/network')
                ssl_cap = fields.get('editRule_ssl_cap')
                self.sendAction('/rbt/sport/peering/action/edit_rule',
                                ('action', 'string', action),
                                ('description', 'string', description),
                                ('dst/network', 'ipv4prefix', dst),
                                ('dst/port_label', 'string', port),
                                ('peer/addr', 'ipv4addr', peer),
                                ('src/network', 'ipv4prefix', src),
                                ('ssl_cap', 'string', ssl_cap),
                                ('idx', 'uint16', index))
        elif 'removeRules' in self.fields:
            ruleIds = FormUtils.getPrefixedFieldNames('moveFromPeeringRule_',
                                                      self.fields)
            ruleIds.sort(FormUtils.compareStringInts)
            ruleIds.reverse()
            for eachRuleId in ruleIds:
                if self.isCMC():
                    self.editNodeSequence(base, peeringRuleSpec, 'remove', int(eachRuleId))
                else:
                    self.sendAction('/rbt/sport/peering/action/remove_rule',
                                    ('idx', 'uint16', eachRuleId))
        else:
            for fromIdx, toIdx in self.reorderEntries('moveFromPeeringRule_',
                                                      'moveToPeeringRule_',
                                                      '/rbt/sport/peering/config/rule'):
                if self.isCMC():
                    self.editNodeSequence(base, peeringRuleSpec, 'move',
                                          fromIdx, moveto=toIdx)
                else:
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

    ## The settings in the "WAN Link" section at the top of the Advanced QoS Page.
    def setupQoSClassSettings(self):
        fields = self.fields
        mgmt = self.mgmt

        base = self.cmcPolicyRetarget('/rbt/hfsc/state/global/all_interface')

        isEditingCMCPolicy = RVBDUtils.isEditingCmcPolicy(mgmt, fields)

        if not isEditingCMCPolicy:
            # setting qos on the SH
            ifaces = Nodes.getMgmtLocalChildrenNames(mgmt, base)
            globalSetParams = []
            for iface in ifaces:
                globalSetParams.append(('interface/%s/enable' % iface, 'bool', ('enableIface_%s' % iface) in fields and 'true' or 'false'))
                globalSetParams.append(('interface/%s/rate' % iface, 'uint32', fields['linkrate_%s' % iface] == '' and '0' or fields['linkrate_%s' % iface]))

            self.sendAction('/rbt/hfsc/action/advanced/shaping/global_set',
                            ('shaping_enable', 'bool', 'globalQosShapingEnable' in fields and 'true' or 'false'),
                            ('marking_enable', 'bool', 'globalQosMarkingEnable' in fields and 'true' or 'false'),
                            ('hier_mode_enable', 'bool', fields['hierarchyMode']),
                            *globalSetParams)
            return

        if isEditingCMCPolicy:
            policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)
            # CMC - get all possible interfaces
            ifaces = ['primary']
            for i in Nodes.allInterfaceIndices:
                ifaces.append('wan%s' % i)
        else:
            ifaces = Nodes.getMgmtLocalChildrenNames(mgmt, base)

        if fields['hierarchyMode'] == 'false' and qos.hasHierarchicalClasses(mgmt, fields):
            # User is trying to set Flat mode even though there are hierarchical
            # classes. We attempt to set the node just to generate the error message.
            Nodes.set(mgmt, (self.cmcPolicyRetarget('/rbt/hfsc/config/global/hier_mode/enable'), 'bool', 'false'))
            return

        if 'globalQosShapingEnable' in fields and not FormUtils.getPrefixedFieldNames('enableIface_', fields):
            self.setFormError('One or more QoS interfaces must be enabled before the QoS feature can be enabled.')
            return

        for iface in ifaces:
            if (fields['linkrate_%s' % iface] == '' or \
                fields['linkrate_%s' % iface] == '0') and \
                'enableIface_%s' % iface in fields:
                self.setFormError('WAN Bandwidth must be set before enabling QoS on an interface.')
                return

        if Nodes.present(mgmt, self.cmcPolicyRetarget('/rbt/hfsc/config/global/enable')) == 'true':
            # Note: The global qos setting cannot be enabled if no interfaces are enabled.
            self.setNodes((self.cmcPolicyRetarget('/rbt/hfsc/config/global/enable'), 'bool', 'false'))

        # Note: The ordering of operations is important here, because the link rate cannot
        # be set to zero while the interface is enabled, and qos cannot be in an enabled
        # state if there are no interfaces enabled.
        for iface in ifaces:
            linkRate = fields['linkrate_%s' % iface] == '' and '0' or fields['linkrate_%s' % iface]

            if 'enableIface_%s' % iface in fields:
                # Set the link rate before enabling an interface.
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/adv_qos/interface/rate/set',
                                    ('iface', 'string', iface),
                                    ('rate', 'uint32', linkRate),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                    self.sendAction('/cmc/policy/action/adv_qos/interface/enable',
                                    ('iface', 'string', iface),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/adv_qos/interface/rate/set',
                                    ('iface', 'string', iface),
                                    ('rate', 'uint32', linkRate))
                    self.sendAction('/rbt/hfsc/action/adv_qos/interface/enable',
                                    ('iface', 'string', iface))
            else:
                # Disable the interface first, because we could possibly
                # be setting the link rate to 0.
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/adv_qos/interface/disable',
                                    ('iface', 'string', iface),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                    self.sendAction('/cmc/policy/action/adv_qos/interface/rate/set',
                                    ('iface', 'string', iface),
                                    ('rate', 'uint32', linkRate),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/adv_qos/interface/disable',
                                    ('iface', 'string', iface))
                    self.sendAction('/rbt/hfsc/action/adv_qos/interface/rate/set',
                                    ('iface', 'string', iface),
                                    ('rate', 'uint32', linkRate))

        if 'globalQosShapingEnable' in fields:
            self.setNodes((self.cmcPolicyRetarget('/rbt/hfsc/config/global/enable'), 'bool', 'true'))

        self.setNodes((self.cmcPolicyRetarget('/rbt/hfsc/config/global/mark_enable'), 'bool',
                       'globalQosMarkingEnable' in fields and 'true' or 'false'))

        Nodes.set(mgmt, (self.cmcPolicyRetarget('/rbt/hfsc/config/global/hier_mode/enable'), 'bool', fields['hierarchyMode']))

    # Bottom of the QoS Classes Page
    def setupQoSClasses(self):
        fields = self.fields
        base = self.cmcPolicyRetarget('/rbt/hfsc/config/class')
        isEditingCMCPolicy = RVBDUtils.isEditingCmcPolicy(self.mgmt, fields)
        if isEditingCMCPolicy:
            policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)
        isAdd = 'addQoSClass' in fields
        isEdit = 'editQoSClass' in fields
        if isAdd or isEdit:
            # handle add or edit QoS class
            pr = isAdd and 'addQoSClass' or isEdit and 'editQoSClass'
            lspct = fields.get('%s_lspct' % pr) # Link Share Weight Percent
            queue = fields['%s_queue' % pr]

            args = [('class_name', 'string', fields['%s_className' % pr]),
                    ('class_type', 'string', qos.getDefaultClassType(fields['%s_priority' % pr])),
                    ('min_bw_pct', 'float32', 'rrtcp' == queue and fields['%s_mxtcpbw' % pr] or fields['%s_gbw' % pr]),
                    ('ul_rate_pct', 'float32', 'rrtcp' == queue and fields['%s_mxtcpbw' % pr] or fields['%s_ubw' % pr]),
                    ('out_dscp', 'uint8', fields['%s_out_dscp' % pr]),
                    ('class_queue', 'string', queue)]

            if isAdd:
                if ('%s_parent' % pr) in fields:
                    parent = fields['%s_parent' % pr]
                    args.append(('parent', 'string', parent))
            if lspct:
                args.append(('ls_rate_pct', 'float32', lspct))
            if queue != 'packet-order':
                args.append(('conn_limit', 'uint32', fields['%s_connlimit' % pr] or '0'))

            op = isAdd and 'add' or 'modify'
            if isEditingCMCPolicy:
                args.append(('policy', 'string', policyName))
                args.append(('type', 'string', policyType))
                actionNode = '/cmc/policy/action/adv_qos/class/%s' % op
            else:
                actionNode = '/rbt/hfsc/action/%s_class' % op
            self.sendAction(actionNode, *args)

        elif 'removeQoSClasses' in fields:
            # handle remove QoS class
            selecteds = FormUtils.getPrefixedFieldNames('selectedClass_', fields)
            for each in selecteds:
                # check before sending action, could be a page refresh
                if Nodes.present(self.mgmt, '%s/%s'% (base, each)):
                    if isEditingCMCPolicy:
                        self.sendAction('/cmc/policy/action/adv_qos/class/remove',
                                        ('class_name', 'string', each),
                                        ('policy', 'string', policyName),
                                        ('type', 'string', policyType))
                    else:
                        self.sendAction('/rbt/hfsc/action/remove_class',
                                        ('class_name', 'string', each))


    def setupQoSSitesRules(self):
        fields = self.fields

        isEditingCMCPolicy = RVBDUtils.isEditingCmcPolicy(self.mgmt, fields)
        if isEditingCMCPolicy:
            policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)

        if 'add_QoS_Site' in fields:
            siteName = fields['addQoSSite_siteName']
            subnets = [x.strip()
                       for x in fields['addQoSSite_siteSubnet'].split('\n')
                       if x.strip() != '']
            defaultClass = fields['addQoSSite_siteDefaultClass']
            defaultDscp = fields['addQoSSite_siteDefaultDscp']

            if isEditingCMCPolicy:
                self.sendAction('/cmc/policy/action/adv_qos/site/add',
                                ('site_name', 'string', siteName),
                                ('network', 'ipv4prefix', subnets[0]),
                                ('out_dscp_def_rule', 'uint8', defaultDscp),
                                ('default_class', 'string', defaultClass),
                                ('policy', 'string', policyName),
                                ('type', 'string', policyType))
            else:
                self.sendAction('/rbt/hfsc/action/adv_qos/site/add',
                                ('site_name', 'string', siteName),
                                ('network', 'ipv4prefix', subnets[0]),
                                ('out_dscp_def_rule', 'uint8', defaultDscp),
                                ('default_class', 'string', defaultClass))

            for i in range(1, len(subnets)):
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/adv_qos/site/edit/add_net',
                                    ('site_name', 'string', siteName),
                                    ('network', 'ipv4prefix', subnets[i]),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/adv_qos/site/edit/add_net',
                                    ('site_name', 'string', siteName),
                                    ('network', 'ipv4prefix', subnets[i]))
        elif 'edit_QoS_Site' in fields:
            siteIdx = fields['editQoSSite_id']
            siteName = fields['editQoSSite_name']
            subnets = [x.strip()
                for x in fields['editQoSSite_siteSubnet'].split('\n')
                if x.strip() != '']

            # Remove all subnets, then add the ones from the form.
            base = self.cmcPolicyRetarget('/rbt/hfsc/config/site/%s/networks')
            networkIndexes = Nodes.getMgmtLocalChildrenNames(
                self.mgmt, base % (siteIdx))
            networkIndexes.sort(key=int, reverse=True)
            for idx in networkIndexes:
                if isEditingCMCPolicy:
                    self.sendAction(
                        '/cmc/policy/action/adv_qos/site/edit/remove_net',
                        ('site_name', 'string', siteName),
                        ('idx', 'uint16', idx),
                        ('policy', 'string', policyName),
                        ('type', 'string', policyType))
                else:
                    self.sendAction(
                        '/rbt/hfsc/action/adv_qos/site/edit/remove_net',
                        ('site_name', 'string', siteName),
                        ('idx', 'uint16', idx))

            for i in range(len(subnets)):
                if isEditingCMCPolicy:
                    self.sendAction(
                        '/cmc/policy/action/adv_qos/site/edit/add_net',
                        ('site_name', 'string', siteName),
                        ('network', 'ipv4prefix', subnets[i]),
                        ('policy', 'string', policyName),
                        ('type', 'string', policyType))
                else:
                    self.sendAction(
                        '/rbt/hfsc/action/adv_qos/site/edit/add_net',
                        ('site_name', 'string', siteName),
                        ('network', 'ipv4prefix', subnets[i]))

        elif 'add_QoS_Rule' in fields or 'edit_QoS_Rule' in fields:
            addingRule = 'add_QoS_Rule' in fields # syntactic sugar
            editingRule = 'edit_QoS_Rule' in fields # syntactic sugar

            prefix = addingRule and 'addQoSRule' or editingRule and 'editQoSRule'

            # handle add QoS rule
            if addingRule:
                siteId = fields['addQoSRule_siteId']
                # strip() must be called on the "at" field, see bug 70309 for details
                idx = fields['addQoSRule_at'].strip()
            if editingRule:
                siteId = fields['editQoSRule_siteId']
                idx = fields['editQoSRule_ruleId']

            className = fields['%s_class' % prefix]

            # On the default rule we can only change the class and DSCP values.  This
            # This is a fake rule so we actually want to change the default class and
            # DSCP values of the site.
            if idx == 'default':
                siteName = Nodes.present(self.mgmt,
                                         self.cmcPolicyRetarget('/rbt/hfsc/config/site/%s/site_name') % siteId)
                if isEditingCMCPolicy:
                    self.sendAction(
                        '/cmc/policy/action/adv_qos/site/edit/change_default_class',
                        ('site_name', 'string', siteName),
                        ('default_class', 'string', fields['editQoSRule_class']),
                        ('policy', 'string', policyName),
                        ('type', 'string', policyType))
                    self.sendAction(
                        '/cmc/policy/action/adv_qos/site/edit/out_dscp_def_rule',
                        ('site_name', 'string', siteName),
                        ('out_dscp_def_rule', 'uint8', fields['editQoSRule_out_dscp']),
                        ('policy', 'string', policyName),
                        ('type', 'string', policyType))
                else:
                    self.sendAction(
                        '/rbt/hfsc/action/adv_qos/site/edit/change_default_class',
                        ('site_name', 'string', siteName),
                        ('default_class', 'string', fields['editQoSRule_class']))
                    self.sendAction(
                        '/rbt/hfsc/action/adv_qos/site/edit/out_dscp_def_rule',
                        ('site_name', 'string', siteName),
                        ('out_dscp_def_rule', 'uint8', fields['editQoSRule_out_dscp']))
                return

            # non-default rules:
            ruleName = fields['%s_ruleName' % prefix]
            desc = fields['%s_desc' % prefix]

            srcSubnet = fields['%s_srcsubnet' % prefix]
            if not srcSubnet or srcSubnet.lower() == 'all':
                srcSubnet = '0.0.0.0/0'
            srcPort = fields['%s_srcport' % prefix]
            if srcPort.lower() == 'all':
                srcPort = '0'

            dstSubnet = fields['%s_dstsubnet' % prefix]
            if not dstSubnet or dstSubnet.lower() == 'all':
                dstSubnet = '0.0.0.0/0'
            dstPort = fields['%s_dstport' % prefix]
            if dstPort.lower() == 'all':
                dstPort = '0'

            protocol = fields['%s_protocol' % prefix]
            traffic = fields['%s_traffic' % prefix]

            dscp = fields['%s_dscp' % prefix].strip().lower()
            if not dscp or ('all' == dscp):
                dscp = '-1'

            out_dscp = fields['%s_out_dscp' % prefix]

            vlan = RVBDUtils.translateVlanInput(fields['%s_vlan' % prefix])

            # List of L7 protocol-specific attributes to be passed to protocol-specific table
            additionalArguments = []
            selectedl7Protocol = fields['%s_l7protocol' % prefix]

            # It's OK to specify an empty string for the layer 7 protocol name when editing a rule,
            # but when adding a rule, that's an error:  to add a new rule without a specific layer 7 protocol,
            # don't add the argument at all.  This could be considered a back-end bug.
            #
            if editingRule:
                l7ProtocolName = selectedl7Protocol and qos.layer7ProtocolNames(self.mgmt, fields, flip=True)[selectedl7Protocol] or ''
                additionalArguments.append( ('l7protocol', 'string', l7ProtocolName) )
            elif addingRule and selectedl7Protocol:
                l7ProtocolName = qos.layer7ProtocolNames(self.mgmt, fields, flip=True)[selectedl7Protocol]
                additionalArguments.append( ('l7protocol', 'string', l7ProtocolName) )

            if selectedl7Protocol == 'ica':
                additionalArguments.extend([
                    ('ica/priority/0', 'string',
                    fields['%s_l7Protocol_icaPriority0' % prefix]),
                    ('ica/priority/1', 'string',
                    fields['%s_l7Protocol_icaPriority1' % prefix]),
                    ('ica/priority/2', 'string',
                    fields['%s_l7Protocol_icaPriority2' % prefix]),
                    ('ica/priority/3', 'string',
                    fields['%s_l7Protocol_icaPriority3' % prefix]),
                    ('ica/priority/0/out_dscp', 'uint8',
                    fields['%s_l7Protocol_icaOutDscp0' % prefix]),
                    ('ica/priority/1/out_dscp', 'uint8',
                    fields['%s_l7Protocol_icaOutDscp1' % prefix]),
                    ('ica/priority/2/out_dscp', 'uint8',
                    fields['%s_l7Protocol_icaOutDscp2' % prefix]),
                    ('ica/priority/3/out_dscp', 'uint8',
                    fields['%s_l7Protocol_icaOutDscp3' % prefix]),
                    ])
            elif selectedl7Protocol == 'http':
                additionalArguments.extend([('http/domain_name', 'string',
                    fields['%s_l7Protocol_httpDomainName' % prefix]),
                    ('http/relative_path', 'string',
                    fields['%s_l7Protocol_httpRelativePath' % prefix])])

            # XXX-CMC-XXX    Search for 'XXX-CMC-XXX' to find where
            # XXX-CMC-XXX    the editing code for the CMC needs to be changed.

            if isEditingCMCPolicy:
                # XXX-CMC-XXX Remove this block.
                if editingRule:
                    self.sendAction('/cmc/policy/action/adv_qos/rule/remove',
                                    ('idx', 'uint16', idx),
                                    ('site_num', 'uint16', siteId),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                additionalArguments.extend([('policy', 'string', policyName),
                                            ('type', 'string', policyType)])
                # XXX-CMC-XXX Remove the next line
                action = '/cmc/policy/action/adv_qos/rule/add'
                # XXX-CMC-XXX Uncomment the next lines.
                # XXX-CMC-XXX Ensure that the action name is correct.
                # if editingRule:
                #     action = '/cmc/policy/action/adv_qos/rule/edit'
                # else:
                #     action = '/cmc/policy/action/adv_qos/rule/add'
            else:
                if editingRule:
                    action = '/rbt/hfsc/action/adv_qos/rule/edit'
                else:
                    action = '/rbt/hfsc/action/adv_qos/rule/add'

            self.sendAction(action,
                ('site_num', 'uint16', siteId),
                ('idx', 'uint16', idx),
                ('rule_name', 'string', ruleName),
                ('desc', 'string', desc),
                ('class_name', 'string', className),
                ('src/network', 'ipv4prefix', srcSubnet),
                ('src/port', 'string', srcPort),
                ('dst/network', 'ipv4prefix', dstSubnet),
                ('dst/port', 'string', dstPort),
                ('protocol', 'int16', protocol),
                ('traffic_type', 'string', traffic),
                ('dscp', 'int16', dscp),
                ('out_dscp', 'uint8', out_dscp),
                ('vlan', 'int16', vlan),
                *additionalArguments)

        elif 'removeQosSitesRules' in fields:
            # This is used for removing both QoS Sites and QoS Rules, since they are on the same AET.

            # First, remove any rules:
            siteIds = {}
            for idd in FormUtils.getPrefixedFieldNames('moveFromQoSRule_', fields):
                siteId, ruleId = idd.split('_')
                siteIds.setdefault(siteId, [])
                siteIds[siteId].append(ruleId)

            for eachSiteId in siteIds:
                ruleIds = siteIds[eachSiteId]
                ruleIds.sort(FormUtils.compareStringInts, reverse=True)
                for eachRuleId in ruleIds:
                    if isEditingCMCPolicy:
                        self.sendAction('/cmc/policy/action/adv_qos/rule/remove',
                                        ('idx', 'uint16', eachRuleId),
                                        ('site_num', 'uint16', eachSiteId),
                                        ('policy', 'string', policyName),
                                        ('type', 'string', policyType))
                    else:
                        self.sendAction('/rbt/hfsc/action/adv_qos/rule/remove',
                                        ('idx', 'uint16', eachRuleId),
                                        ('site_num', 'uint16', eachSiteId))

            # Next, remove the sites.
            siteIds = FormUtils.getPrefixedFieldNames('moveFromQoSSite_', fields)
            for eachSiteId in siteIds:
                siteName = Nodes.present(self.mgmt, self.cmcPolicyRetarget('/rbt/hfsc/config/site/%s/site_name') % eachSiteId)
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/adv_qos/site/remove',
                                    ('site_name', 'string', siteName),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/adv_qos/site/remove',
                                    ('site_name', 'string', siteName))

        else: # move{From,To}QoSRule_ and move{From,To}QoSSite_
            movingSites = FormUtils.getPrefixedFieldNames('moveFromQoSSite_', fields)
            movingRules = FormUtils.getPrefixedFieldNames('moveFromQoSRule_', fields)

            if movingSites:
                for fromIdx, toIdx in self.reorderEntries('moveFromQoSSite_',
                                                          'moveToQoSSite_',
                                                          self.cmcPolicyRetarget('/rbt/hfsc/config/site')):
                    if isEditingCMCPolicy:
                        self.sendAction('/cmc/policy/action/adv_qos/site/move',
                                        ('from_idx', 'uint16', str(fromIdx)),
                                        ('to_idx', 'uint16', str(toIdx)),
                                        ('policy', 'string', policyName),
                                        ('type', 'string', policyType))
                    else:
                        self.sendAction('/rbt/hfsc/action/adv_qos/site/move',
                                        ('from_idx', 'uint16', str(fromIdx)),
                                        ('to_idx', 'uint16', str(toIdx)))
            if movingRules:
                siteId = movingRules[0].split('_')[0]

                moveToIndex = FormUtils.getPrefixedField('moveToQoSRule_%s_' % siteId, self.fields)[0]
                if moveToIndex is None:
                    # All of the Rules AET's "default" rules have the same
                    # "moveToQoSRule_default" field name, so set the prefix
                    # to 'moveToQoSRule_'
                    moveToPrefix = 'moveToQoSRule_'
                else:
                    # reorderEntries() cannot handle the "<sitenum>_<rulenum>" format
                    # the Rules AET uses. In order to make our format compatible, we
                    # have to change the field value to just "<rulenum>".
                    #
                    # E.g. The value of fields['moveToQoSRule_1_5'] changes from '1_5' to '5'
                    fieldName = 'moveToQoSRule_%s_%s' % (siteId, moveToIndex) # short-hand var
                    fields[fieldName] = fields[fieldName].rsplit('_', 1)[-1]
                    moveToPrefix = 'moveToQoSRule_%s_' % siteId
                for fromIdx, toIdx in self.reorderEntries('moveFromQoSRule_%s_' % siteId,
                                                          moveToPrefix,
                                                          self.cmcPolicyRetarget('/rbt/hfsc/config/site/%s/filter') % siteId):
                    if isEditingCMCPolicy:
                        self.sendAction('/cmc/policy/action/adv_qos/rule/move',
                            ('from_idx', 'uint16', str(fromIdx)),
                            ('to_idx',   'uint16', str(toIdx)  ),
                            ('site_num', 'uint16', str(siteId) ),
                            ('policy', 'string', policyName),
                            ('type', 'string', policyType))
                    else:
                        self.sendAction('/rbt/hfsc/action/adv_qos/rule/move',
                                        ('from_idx', 'uint16', str(fromIdx)),
                                        ('to_idx',   'uint16', str(toIdx)  ),
                                        ('site_num', 'uint16', str(siteId) ))


    def setupQoSMarkingOptimized(self):
        # Note: The QoS Marking page only exists as a CMC policy page
        fields = self.fields
        base = self.cmcPolicyRetarget('/rbt/sport/qos/config/optimized/rule')
        spec = {'description': 'string',
                'dscp': 'uint8',
                'dst/network': 'ipv4prefix',
                'dst/port_label': 'string',
                'src/network': 'ipv4prefix'}
        if 'addQoSOptimizedMap' in fields:
            srcSubnet = fields.get('addQoSOptimizedMap_srcSubnet')
            srcPort = fields.get('addQoSOptimizedMap_srcPort')
            dstSubnet = fields.get('addQoSOptimizedMap_dstSubnet')
            dstPort = fields.get('addQoSOptimizedMap_dstPort')
            if srcPort == 'all':
                srcPort = '0'
            if dstPort == 'all':
                dstPort = '0'
            dscp = fields.get('addQoSOptimizedMap_dscp')
            desc = fields.get('addQoSOptimizedMap_description')
            map = {'src/network': srcSubnet,
                   'src/port_label': srcPort,
                   'dst/network': dstSubnet,
                   'dst/port_label': dstPort,
                   'dscp': dscp,
                   'description': desc}
            self.editNodeSequence(base, spec, 'add', 1, map)
        elif 'editQoSOptimizedMap' in fields:
            index = fields.get('editQoSOptimizedMap_index')
            srcSubnet = fields.get('editQoSOptimizedMap_srcSubnet')
            srcPort = fields.get('editQoSOptimizedMap_srcPort')
            dstSubnet = fields.get('editQoSOptimizedMap_dstSubnet')
            dstPort = fields.get('editQoSOptimizedMap_dstPort')
            if srcPort == 'all':
                srcPort = '0'
            if dstPort == 'all':
                dstPort = '0'
            dscp = fields.get('editQoSOptimizedMap_dscp')
            desc = fields.get('editQoSOptimizedMap_description')
            map = {'src/network': srcSubnet,
                   'src/port_label': srcPort,
                   'dst/network': dstSubnet,
                   'dst/port_label': dstPort,
                   'dscp': dscp,
                   'description': desc}
            self.editNodeSequence(base, spec, 'edit', int(index), map)
        elif 'removeQosMaps' in fields:
            ruleIds = FormUtils.getPrefixedFieldNames('moveFromQoSMapOptimized_',
                                                      self.fields)
            ruleIds.sort(FormUtils.compareStringInts)
            ruleIds.reverse()
            for eachRuleId in ruleIds:
                self.editNodeSequence(base, spec, 'remove', int(eachRuleId))
        else: # move{From,To}QoSMapOptimized_
            for fromIdx, toIdx in self.reorderEntries('moveFromQoSMapOptimized_',
                                                      'moveToQoSMapOptimized_',
                                                      '/rbt/sport/qos/config/optimized/rule'):
                self.editNodeSequence(base, spec, 'move',
                                      fromIdx, moveto=toIdx)

    def setupQoSMarkingPassthru(self):
        # Note: The QoS Marking page only exists as a CMC policy page
        fields = self.fields
        base = self.cmcPolicyRetarget('/rbt/sport/qos/config/passthrough/rule')
        spec = {'description': 'string',
                'src/network': 'ipv4prefix',
                'src/port_label': 'string',
                'dst/network': 'ipv4prefix',
                'dst/port_label': 'string',
                'dscp': 'uint8'}
        if 'addQoSPassthruMap' in fields:
            srcSubnet = fields.get('addQoSPassthruMap_srcSubnet')
            srcPort = fields.get('addQoSPassthruMap_srcPort')
            if srcPort == 'all':
                srcPort = '0'
            dstSubnet = fields.get('addQoSPassthruMap_dstSubnet')
            dstPort = fields.get('addQoSPassthruMap_dstPort')
            if dstPort == 'all':
                dstPort = '0'
            dscp = fields.get('addQoSPassthruMap_dscp')
            desc = fields.get('addQoSPassthruMap_description')
            map = {'src/network': srcSubnet,
                   'src/port_label': srcPort,
                   'dst/network':  dstSubnet,
                   'dst/port_label': dstPort,
                   'dscp': dscp,
                   'description': desc}
            self.editNodeSequence(base, spec, 'add', int(1), map)
        elif 'editQoSPassthruMap' in fields:
            index = fields.get('editQoSPassthruMap_index')
            srcSubnet = fields.get('editQoSPassthruMap_srcSubnet')
            srcPort = fields.get('editQoSPassthruMap_srcPort')
            if srcPort == 'all':
                srcPort = '0'
            dstSubnet = fields.get('editQoSPassthruMap_dstSubnet')
            dstPort = fields.get('editQoSPassthruMap_dstPort')
            if dstPort == 'all':
                dstPort = '0'
            dscp = fields.get('editQoSPassthruMap_dscp')
            desc = fields.get('editQoSPassthruMap_description')
            map = {'src/network': srcSubnet,
                   'src/port_label': srcPort,
                   'dst/network':  dstSubnet,
                   'dst/port_label': dstPort,
                   'dscp': dscp,
                   'description': desc}
            self.editNodeSequence(base, spec, 'edit', int(index), map)
        elif 'removeQosMaps' in fields:
            ruleIds = FormUtils.getPrefixedFieldNames('moveFromQoSMapPassthrough_',
                                                      self.fields)
            ruleIds.sort(FormUtils.compareStringInts)
            ruleIds.reverse()
            for eachRuleId in ruleIds:
                self.editNodeSequence(base, spec, 'remove', int(eachRuleId))
        else: # move{From,To}QoSMapPassthrough_
            for fromIdx, toIdx in self.reorderEntries('moveFromQoSMapPassthrough_',
                                                      'moveToQoSMapPassthrough_',
                                                      '/rbt/sport/qos/config/passthrough/rule'):
                self.editNodeSequence(base, spec, 'move',
                                      fromIdx, moveto=toIdx)

    def setupInboundQoSSettings(self):
        # Handle general settings at the top of the Inbound QoS page.

        for field in self.fields:
            if field.endswith('/link_rate') and self.fields[field] == '':
                self.fields[field] = '0' # blank link_rate value causes errors

        FormUtils.setNodesFromConfigForm(self.mgmt, self.fields)

    def setupInboundQoSClasses(self):
        # Inbound QoS's classes table (adding/editing/removing classes)
        fields = self.fields
        if 'addQoSClass' in fields:
            self.sendAction('/rbt/qos/inbound/action/class/add',
                            ('name', 'string', fields['addQoSClass_className']),
                            ('priority', 'string', fields['addQoSClass_classPriority']),
                            ('min_rate_pct', 'float32', fields['addQoSClass_classMinBW']),
                            ('ul_rate_pct', 'float32', fields['addQoSClass_classMaxBW']),
                            ('ls_weight', 'float32', fields['addQoSClass_classLinkShareWeight']))
        elif 'editQoSClass' in fields:
            self.sendAction('/rbt/qos/inbound/action/class/modify',
                            ('name', 'string', fields['editClassName']),
                            ('priority', 'string', fields['editQoSClass_classPriority']),
                            ('min_rate_pct', 'float32', fields['editQoSClass_classMinBW']),
                            ('ul_rate_pct', 'float32', fields['editQoSClass_classMaxBW']),
                            ('ls_weight', 'float32', fields['editQoSClass_classLinkShareWeight']))
        elif 'removeQoSClasses' in fields:
            for className in FormUtils.getPrefixedFieldNames('selectedClass_', fields):
                Nodes.delete(self.mgmt, '/rbt/qos/inbound/config/class/%s' % (className))
        else:
            assert False, 'Unhandled action for setupInboundQoSClasses.'

    def setupInboundQoSRules(self):
        # Inbound QoS's rules table (adding/editing/moving/removing rules)
        fields = self.fields
        if 'addQoSRule' in fields:
            vlanValue = RVBDUtils.translateVlanInput(fields['addQoSRule_ruleVlan'])
            dscpValue = (fields['addQoSRule_ruleDscp'].lower() == 'all') and '-1' or fields['addQoSRule_ruleDscp']
            srcPort = (fields['addQoSRule_ruleSrcPort'].lower() == 'all') and '0' or fields['addQoSRule_ruleSrcPort']
            dstPort = (fields['addQoSRule_ruleDstPort'].lower() == 'all') and '0' or fields['addQoSRule_ruleDstPort']

            self.sendAction('/rbt/qos/inbound/action/filter/add',
                            ('name', 'string', fields['addQoSRule_ruleName']),
                            ('class', 'string', fields['addQoSRule_ruleClass']),
                            ('idx', 'uint16', fields['addQoSRule_ruleAt']),
                            ('description', 'string', fields['addQoSRule_ruleDesc']),
                            ('traffic_type', 'string', fields['addQoSRule_ruleTraffic']),
                            ('vlan', 'int16', vlanValue),
                            ('dscp', 'int16', dscpValue),
                            ('ip_protocol', 'int16', fields['addQoSRule_ruleProtocol']),
                            ('src_network', 'ipv4prefix', fields['addQoSRule_ruleSrcSubnet']),
                            ('dst_network', 'ipv4prefix', fields['addQoSRule_ruleDstSubnet']),
                            ('src_port', 'string', srcPort),
                            ('dst_port', 'string', dstPort),
                            ('dpi_protocol', 'string', fields['addQoSRule_ruleL7Proto']),
                            ('http/domain_name', 'string', fields.get('addQoSRule_ruleL7Proto_HTTP_domainName', '')),
                            ('http/relative_path', 'string', fields.get('addQoSRule_ruleL7Proto_HTTP_relativePath', '')))


        elif 'editQoSRule' in fields:
            vlanValue = RVBDUtils.translateVlanInput(fields['editQoSRule_ruleVlan'])
            dscpValue = (fields['editQoSRule_ruleDscp'].lower() == 'all') and '-1' or fields['editQoSRule_ruleDscp']
            srcPort = (fields['editQoSRule_ruleSrcPort'].lower() == 'all') and '0' or fields['editQoSRule_ruleSrcPort']
            dstPort = (fields['editQoSRule_ruleDstPort'].lower() == 'all') and '0' or fields['editQoSRule_ruleDstPort']
            l7protoParams = []
            if fields['editQoSRule_ruleL7Proto'] == 'http':
                l7protoParams = [('http/domain_name',   'string',     fields['editQoSRule_ruleL7Proto_HTTP_domainName']),
                                 ('http/relative_path', 'string',     fields['editQoSRule_ruleL7Proto_HTTP_relativePath'])]
            self.sendAction('/rbt/qos/inbound/action/filter/modify',
                            ('name',               'string',     fields['editQoSRule_ruleName']),
                            ('class',              'string',     fields['editQoSRule_ruleClass']),
                            ('idx',                'uint16',     fields['editRuleAt']),
                            ('description',        'string',     fields['editQoSRule_ruleDesc']),
                            ('traffic_type',       'string',     fields['editQoSRule_ruleTraffic']),
                            ('vlan',               'int16',      vlanValue),
                            ('dscp',               'int16',      dscpValue),
                            ('ip_protocol',        'int16',      fields['editQoSRule_ruleProtocol']),
                            ('src_network',        'ipv4prefix', fields['editQoSRule_ruleSrcSubnet']),
                            ('dst_network',        'ipv4prefix', fields['editQoSRule_ruleDstSubnet']),
                            ('src_port',           'string',     srcPort),
                            ('dst_port',           'string',     dstPort),
                            ('dpi_protocol',       'string',     fields['editQoSRule_ruleL7Proto']),
                            *l7protoParams)
        elif 'removeQosRules' in fields:
            indexes = [int(x) for x in FormUtils.getPrefixedFieldNames('moveFromQoSRule_', fields)]
            indexes.sort(reverse=True) # Delete rules in descending order to avoid shifting their indexes.
            for ruleIdx in indexes:
                ruleIdx = str(ruleIdx)
                self.sendAction('/rbt/qos/inbound/action/filter/remove',
                                ('idx', 'uint16', ruleIdx))
        else:
            # move inbound qos rules
            base = self.cmcPolicyRetarget('/rbt/qos/inbound/config/filter')
            for fromIdx, toIdx in self.reorderEntries('moveFromQoSRule_',
                                                      'moveToQoSRule_',
                                                      base):
                self.sendAction('/rbt/qos/inbound/action/filter/move',
                                ('from_idx', 'uint16', fromIdx),
                                ('to_idx',   'uint16', toIdx))

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

    # Simplified QoS UI: sites tab
    def setupEasyQoS_sites(self):
        fields = self.fields
        siteConfigPath = self.cmcPolicyRetarget('/rbt/hfsc/config/site')

        isEditingCMCPolicy = RVBDUtils.isEditingCmcPolicy(self.mgmt, fields)
        if isEditingCMCPolicy:
            policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)

        if 'localSite' in fields:
            if isEditingCMCPolicy:
                # CMC - get all possible interfaces
                ifaces = ['primary']
                for i in Nodes.allInterfaceIndices:
                    ifaces.append('wan%s' % i)
            else:
                base = '/rbt/hfsc/state/global/all_interface'
                ifaces = Nodes.getMgmtLocalChildrenNames(self.mgmt, base)
                globalSetParams = []
                for iface in ifaces:
                    globalSetParams.append(('interface/%s/enable' % iface, 'bool', ('enableIface_%s' % iface) in fields and 'true' or 'false'))
                self.sendAction('/rbt/hfsc/action/basic/shaping/global_set',
                                ('shaping_enable', 'bool', 'globalQosShapingEnable' in fields and 'true' or 'false'),
                                ('marking_enable', 'bool', 'globalQosMarkingEnable' in fields and 'true' or 'false'),
                                ('wan_os_enable', 'bool', 'overcommit_enable' in fields and 'true' or 'false'),
                                ('wan_rate', 'uint32', fields['linkrate'] or '0'),
                                *globalSetParams)
                return

            if 'globalQosShapingEnable' in fields and not FormUtils.getPrefixedFieldNames('enableIface_', fields):
                self.setFormError('One or more QoS interfaces must be enabled and the WAN Bandwidth set before the QoS feature can be enabled.')
                return

            # Set Basic QoS's "Bandwidth Overcommit" node.
            linkRate = fields['linkrate'] or '0'
            if 'overcommit_enable' in fields:
                # if enabling bw overcommit, do it before setting the link rate to avoid invalid states.
                self.setNodes((self.cmcPolicyRetarget('/rbt/hfsc/config/global/bw_overcommit'),
                               'bool', 'true'))
            elif qos.isBandwidthOvercommitted(self.mgmt, fields, linkRate):
                # In this case, bw overcommit is disabled or being disabled,
                # and the remote site's total bandwidth is greater than what
                # the user is setting the WAN bandwidth to (i.e. overcommitted)

                # This will cause an error situation in one of two ways: Either
                # we are disabling bw overcommit while overcommitted, or bw
                # overcommit is already disabled and we are setting the WAN
                # throughput to be overcommitted.

                # One of the following calls will generate the appropriate error message:
                self.setNodes((self.cmcPolicyRetarget('/rbt/hfsc/config/global/bw_overcommit'),
                               'bool', 'false'))
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/easy_qos/interface/rate/set',
                                    ('rate', 'uint32', linkRate),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/easy_qos/interface/rate/set',
                                    ('rate', 'uint32', linkRate))
                return

            if Nodes.present(self.mgmt, self.cmcPolicyRetarget('/rbt/hfsc/config/global/enable')) == 'true':
                # Note: The global qos setting cannot be enabled if no interfaces are enabled.
                self.setNodes((self.cmcPolicyRetarget('/rbt/hfsc/config/global/enable'), 'bool', 'false'))

            # Note: The ordering of operations is important here, because the link rate cannot
            # be set to zero while the interface is enabled, and qos cannot be in an enabled
            # state if there are no interfaces enabled.
            if linkRate != '0':
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/easy_qos/interface/rate/set',
                                    ('rate', 'uint32', linkRate),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/easy_qos/interface/rate/set',
                                    ('rate', 'uint32', linkRate))

            for iface in ifaces:
                ifaceEnable = 'enableIface_%s' % iface in fields and 'enable' or 'disable'
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/easy_qos/interface/%s' % ifaceEnable,
                                   ('iface', 'string', iface),
                                   ('policy', 'string', policyName),
                                   ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/easy_qos/interface/%s' % ifaceEnable,
                                   ('iface', 'string', iface))

            # Only bother setting the link rate if it is different from what is
            # already set. This is because intially the link rate is set to 0, but 0
            # is not a valid value to set the field to. (See bug 67888.)
            originalLinkRate = Nodes.present(self.mgmt, self.cmcPolicyRetarget('/rbt/hfsc/config/global/interface/primary/link_rate'))
            if linkRate != originalLinkRate and linkRate == '0':
                # If the link rate is being set to 0, then set the link rate after
                # enabling/disabling the interfaces
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/easy_qos/interface/rate/set',
                                    ('rate', 'uint32', linkRate),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/easy_qos/interface/rate/set',
                                    ('rate', 'uint32', linkRate))

            if 'overcommit_enable' not in fields:
                # if disabling bw overcommit, do it after setting the link rate to avoid invalid states.
                self.setNodes((self.cmcPolicyRetarget('/rbt/hfsc/config/global/bw_overcommit'),
                               'bool', 'false'))

            if 'globalQosShapingEnable' in fields:
                self.setNodes((self.cmcPolicyRetarget('/rbt/hfsc/config/global/enable'), 'bool', 'true'))

            self.setNodes((self.cmcPolicyRetarget('/rbt/hfsc/config/global/mark_enable'), 'bool',
                           'globalQosMarkingEnable' in fields and 'true' or 'false'))

        elif 'addSite' in fields:
            # strip() must be called on the "addSite_order" field,
            # see bug 70309 for details
            fields['addSite_order'] = fields['addSite_order'].strip()

            siteName = fields['addSite_name']
            subnets = [x.strip()
                       for x in fields.get('addSite_subnet').split('\n')
                       if x.strip() != '']

            if isEditingCMCPolicy:
                self.sendAction('/cmc/policy/action/easy_qos/site/add',
                            ('idx', 'uint16', fields['addSite_order']),
                            ('site_name', 'string', siteName),
                            ('wan_bw', 'uint32', fields['addSite_wanbandwidth'] or '0'),
                            ('profile_name', 'string', fields['addSite_bandwidthprofile']),
                            ('network', 'ipv4prefix', subnets[0]),
                            ('policy', 'string', policyName),
                            ('type', 'string', policyType))
            else:
                self.sendAction('/rbt/hfsc/action/easy_qos/site/add',
                            ('idx', 'uint16', fields['addSite_order']),
                            ('site_name', 'string', siteName),
                            ('wan_bw', 'uint32', fields['addSite_wanbandwidth'] or '0'),
                            ('profile_name', 'string', fields['addSite_bandwidthprofile']),
                            ('network', 'ipv4prefix', subnets[0]))
            # Add subnets
            for subnet in subnets[1:]: # first subnet is added with the action/easy_qos/site/add action
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/easy_qos/site/edit/add_net',
                                    ('site_name', 'string', siteName),
                                    ('network', 'ipv4prefix', subnet.strip()),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/easy_qos/site/edit/add_net',
                                    ('site_name', 'string', siteName),
                                    ('network', 'ipv4prefix', subnet.strip()))

        elif 'editSite' in fields:
            siteName = fields['editSite_name']
            sitesPath = self.cmcPolicyRetarget('/rbt/hfsc/config/site')
            allSites = Nodes.getTreeifiedSubtree(self.mgmt, sitesPath)
            siteIdx = [idx for idx, data in allSites.items() if
                       data['site_name'] == siteName][0]

            # Site actions are unconventional, resulting in an awkward
            # way to edit. First, edit all site attributes except the subnets.
            if isEditingCMCPolicy:
                self.sendAction('/cmc/policy/action/easy_qos/site/edit',
                    ('site_name', 'string', siteName),
                    ('wan_bw', 'uint32', fields['editSite_wanbandwidth'] or '0'),
                    ('profile_name', 'string', fields['editSite_bandwidthprofile']),
                    ('policy', 'string', policyName),
                    ('type', 'string', policyType))
            else:
                self.sendAction('/rbt/hfsc/action/easy_qos/site/edit',
                    ('site_name', 'string', siteName),
                    ('wan_bw', 'uint32', fields['editSite_wanbandwidth'] or '0'),
                    ('profile_name', 'string', fields['editSite_bandwidthprofile']))

            # Second, delete all existing subnets.  (The
            # subnet field will not be present for the default site
            # since its subnets are not editable.  In that case we
            # shouldn't be touching the subnets at all.)
            if 'editSite_subnet' in fields:
                delSubnets = allSites.get(siteIdx, {}).get('networks', {}).keys()
                delSubnets.sort(FormUtils.alphanumericCompare, reverse=True)
                for idx in delSubnets:
                    if isEditingCMCPolicy:
                        self.sendAction('/cmc/policy/action/easy_qos/site/edit/remove_net',
                                        ('site_name', 'string', siteName),
                                        ('idx', 'uint16', idx),
                                        ('policy', 'string', policyName),
                                        ('type', 'string', policyType))
                    else:
                        self.sendAction('/rbt/hfsc/action/easy_qos/site/edit/remove_net',
                                        ('site_name', 'string', siteName),
                                        ('idx', 'uint16', idx))

                # Finally re-add the new subnets.
                subnets = [x.strip()
                           for x in fields.get('editSite_subnet').split('\n')
                           if x.strip() != '']
                for subnet in subnets:
                    if isEditingCMCPolicy:
                        self.sendAction('/cmc/policy/action/easy_qos/site/edit/add_net',
                                        ('site_name', 'string', siteName),
                                        ('network', 'ipv4prefix', subnet.strip()),
                                        ('policy', 'string', policyName),
                                        ('type', 'string', policyType))
                    else:
                        self.sendAction('/rbt/hfsc/action/easy_qos/site/edit/add_net',
                                        ('site_name', 'string', siteName),
                                        ('network', 'ipv4prefix', subnet.strip()))

        elif 'removeSite' in fields:
            sites = FormUtils.getPrefixedFieldNames('selectedSite_', self.fields)
            sites.sort(FormUtils.alphanumericCompare, reverse=True)
            for siteIdx in sites:
                sitename = Nodes.present(self.mgmt, '%s/%s/site_name' % \
                                             (siteConfigPath, siteIdx))
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/easy_qos/site/remove',
                                    ('site_name', 'string', sitename),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/easy_qos/site/remove',
                                    ('site_name', 'string', sitename))

        else: # Reorder sites
            for fromIdx, toIdx in self.reorderEntries('selectedSite_',
                                                      'moveToSelectedSite_',
                                                      siteConfigPath):
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/easy_qos/site/move',
                                    ('from_idx', 'uint16', fromIdx),
                                    ('to_idx', 'uint16', toIdx),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/easy_qos/site/move',
                                    ('from_idx', 'uint16', fromIdx),
                                    ('to_idx', 'uint16', toIdx))

    # Simplified QoS UI: applications tab
    def setupEasyQoS_apps(self):
        fields = self.fields

        isEditingCMCPolicy = RVBDUtils.isEditingCmcPolicy(self.mgmt, fields)
        if isEditingCMCPolicy:
            policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)

        if 'addApplication' in fields:
            self._addOrEditGlobalApp()

        elif 'editApplication' in fields:
            appName = qos.getAppNameFromOrderNum(self.mgmt, fields, fields['editApp_order'])
            # XXX-CMC-XXX Remove this block when direct editing on the CMC becomes available.
            if isEditingCMCPolicy:
                self.sendAction(
                    '/cmc/policy/action/easy_qos/global_app_rule/remove',
                    ('global_app_name', 'string', appName),
                    ('policy', 'string', policyName),
                    ('type', 'string', policyType))
            self._addOrEditGlobalApp()

        elif 'removeApplication' in fields:
            appIndices = FormUtils.getPrefixedFieldNames('selectedApp_', self.fields)
            appIndices.sort(FormUtils.alphanumericCompare, reverse=True)
            for appIdx in appIndices:
                appName = Nodes.present(self.mgmt,
                                        self.cmcPolicyRetarget('/rbt/hfsc/config/global_app/%s/global_app_name') % appIdx)
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/easy_qos/global_app_rule/remove',
                                    ('global_app_name', 'string', appName),
                                    ('policy', 'string', policyName),
                                    ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/easy_qos/global_app_rule/remove',
                                ('global_app_name', 'string', appName))

        else: #reorder applications
            base = self.cmcPolicyRetarget('/rbt/hfsc/config/global_app')
            for fromIdx, toIdx in self.reorderEntries('selectedApp_',
                                                      'moveToSelectedApp_',
                                                      base):
                if isEditingCMCPolicy:
                    self.action('/cmc/policy/action/easy_qos/global_app_rule/move',
                              ('from_idx', 'uint16', fromIdx),
                              ('to_idx', 'uint16', toIdx),
                              ('policy', 'string', policyName),
                              ('type', 'string', policyType))
                else:
                    self.action('/rbt/hfsc/action/easy_qos/global_app_rule/move',
                                  ('from_idx', 'uint16', fromIdx),
                                  ('to_idx', 'uint16', toIdx))

    # Given the set of fields that are received from the global app tab add or edit div
    # create or modify a global app rule.
    def _addOrEditGlobalApp(self):
        fields = self.fields
        # prefix will pull out the right fields depending on whether the fields come
        # from the add div or the edit div.
        isEdit = 'editApplication' in fields
        prefix = isEdit and 'editApp_' or 'addApp_'

        # strip() must be called on the "order" field, see bug 70309 for details
        fields['%sorder' % prefix] = fields['%sorder' % prefix].strip()

        args = []
        l7Protocol = fields['%sl7protocol' % prefix]

        if l7Protocol:
            args.append(('l7protocol', 'string',
                               qos.layer7ProtocolNames(self.mgmt, fields, flip=True)[l7Protocol]))
        elif isEdit:
            args.append(('l7protocol', 'string', ''))
        if l7Protocol == 'http':
            args.append(('http/domain_name', 'string',
                               fields['%shttp_domain_name' % prefix]))
            args.append(('http/relative_path', 'string',
                               fields['%shttp_relative_path' % prefix]))

        srcPort = fields['%ssrcport' % prefix]
        if srcPort.lower() == 'all':
            srcPort = '0'
        srcSubnet = fields['%ssrcsubnet' % prefix]
        if not srcSubnet or srcSubnet.lower() == 'all':
            srcSubnet = '0.0.0.0/0'
        srcPort = fields['%ssrcport' % prefix]
        if srcPort.lower() == 'all':
            srcPort = '0'
        dstSubnet = fields['%sdstsubnet' % prefix]
        if not dstSubnet or dstSubnet.lower() == 'all':
            dstSubnet = '0.0.0.0/0'
        dstPort = fields['%sdstport' % prefix]
        if dstPort.lower() == 'all':
            dstPort = '0'
        dscp = fields['%sdscp' % prefix].strip().lower()
        if not dscp or ('all' == dscp):
            dscp = '-1'
        vlan = RVBDUtils.translateVlanInput(fields['%svlan' % prefix])

        if RVBDUtils.isEditingCmcPolicy(self.mgmt, fields):
            policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)
            args.extend(
                [('policy', 'string', policyName),
                 ('type', 'string', policyType)])
            # XXX-CMC-XXX Remove the next line when CMC editing becomes available.
            action = '/cmc/policy/action/easy_qos/global_app_rule/add'
            # XXX-CMC-XXX Uncomment the next lines when CMC editing becomes available.
            # XXX-CMC-XXX Ensure the action names are correct.
            # if isEdit:
            #     action = '/cmc/policy/action/easy_qos/global_app_rule/edit'
            # else:
            #     action = '/cmc/policy/action/easy_qos/global_app_rule/add'
        else:
            if isEdit:
                action = '/rbt/hfsc/action/easy_qos/global_app_rule/edit'
            else:
                action = '/rbt/hfsc/action/easy_qos/global_app_rule/add'

        args.extend(
            [('idx', 'uint16', fields['%sorder' % prefix]),
             ('global_app_name', 'string', fields['%sname' % prefix]),
             ('desc', 'string', fields['%sdesc' % prefix]),
             ('src/network', 'ipv4prefix', srcSubnet),
             ('src/port', 'string', srcPort),
             ('dst/network', 'ipv4prefix', dstSubnet),
             ('dst/port', 'string', dstPort),
             ('dscp', 'int16', dscp),
             ('protocol', 'int16', fields['%sprotocol' % prefix]),
             ('vlan', 'int16', vlan),
             ('traffic_type', 'string', fields['%straffic' % prefix]),
             ('default_class', 'string', fields['%scls' % prefix]),
             ('out_dscp', 'uint8', fields['%sout_dscp' % prefix])])

        self.sendAction(action, *args)

    # Simplified QoS UI: bandwidth profiles tab
    def setupEasyQoS_profiles(self):
        fields = self.fields

        isEditingCMCPolicy = RVBDUtils.isEditingCmcPolicy(self.mgmt, fields)
        if isEditingCMCPolicy:
            policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)

        if 'addProfile' in fields:
            self._addOrEditProfile(mode='add')

        elif 'editProfile' in fields:
            self._addOrEditProfile(mode='edit')

        elif 'removeProfile' in fields:
            profiles = FormUtils.getPrefixedFieldNames('selectedProfile_', self.fields)
            for profile in profiles:
                if isEditingCMCPolicy:
                    self.sendAction('/cmc/policy/action/easy_qos/profile/remove',
                                 ('profile_name', 'string', profile),
                                 ('policy', 'string', policyName),
                                 ('type', 'string', policyType))
                else:
                    self.sendAction('/rbt/hfsc/action/easy_qos/profile/remove',
                                     ('profile_name', 'string', profile))

    # Given the set of fields that are received from the global app tab add or edit div,
    # add or edit a global app rule.
    def _addOrEditProfile(self, mode):
        assert mode in ('add', 'edit')

        fields = self.fields
        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)
        isEditingCMCPolicy = policyType is not None

        action = '%s/action/easy_qos/profile/%sall' %  \
            (isEditingCMCPolicy and '/cmc/policy' or '/rbt/hfsc', mode)

        prefix = mode + 'Profile'
        args = [('profile_name', 'string', fields['%s_name' % prefix])]

        if isEditingCMCPolicy:
            args.extend(
                [('policy', 'string', policyName),
                 ('type', 'string', policyType)])

        idx = 1
        for cls in qos.DEFAULT_CLASSES:
            clsAttrib = qos.attributizeName(cls)
            args.extend(
                [('min_bw_pct_%d' % idx, 'float32',
                  fields['%s_%s_guaranteed' % (prefix, clsAttrib)]),
                 ('ul_rate_pct_%d' % idx, 'float32',
                  fields['%s_%s_upper' % (prefix, clsAttrib)]),
                 ('out_dscp_%d' % idx, 'uint8',
                  fields['%s_%s_out_dscp' % (prefix, clsAttrib)])])

            idx += 1

        self.sendAction(action, *args)

    # Gatekeeper widget on Easy QoS page, for when the user is in Advanced mode.
    def setupEasyQoS_easyGatekeeper(self):
        fields = self.fields
        if 'clearQoSSettings' in fields:
            if 'editPolicy' in fields:
                policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)
                self.sendAction('/cmc/policy/action/qos_purge',
                                ('migrate_to_basic', 'bool', 'true'),
                                ('policy', 'string', policyName),
                                ('type', 'string', policyType))
            else:
                self.sendAction('/rbt/hfsc/action/qos_purge',
                                ('migrate_to_basic', 'bool', 'true'))

    # Gatekeeper widget on Advanced QoS page, for when the user is in Easy mode.
    def setupEasyQoS_advGatekeeper(self):
        fields = self.fields
        if 'migrateToAdvanced' in fields:
            if 'editPolicy' in fields:
                policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)
                self.sendAction('/cmc/policy/action/migrate_to_advanced_mode',
                                ('policy', 'string', policyName),
                                ('type', 'string', policyType))
            else:
                self.setNodes((self.cmcPolicyRetarget('/rbt/hfsc/config/global/easy_qos_mode'), 'bool', 'false'),
                              (self.cmcPolicyRetarget('/rbt/hfsc/config/global/hier_mode/enable'), 'bool', 'true'))
        self.setActionMessage('Successfully migrated Basic Outbound QoS configuration to Advanced Outbound QoS.')


    hwAssistRuleSpec = {'action': 'string',
                        'description': 'string',
                        'subnet_a/network': 'ipv4prefix',
                        'subnet_b/network': 'ipv4prefix',
                        'vlan': 'int16'}

    # Hardware Assist Rules page
    def setupHWAssistRules(self):
        fields = self.fields
        cmcPolicy = fields.get('editPolicy')
        base = self.cmcPolicyRetarget('/rbt/hwassist/config/rule')
        if 'addHWAssistRule' in fields:
            index = fields.get('addHWAssist_idx')
            # retrieve the fields as a batch from the rulespec above
            # rule is a dict of key, value pairs
            rule = dict([(k, fields.get('addHWAssist_' + k, ''))
                         for k in gui_AdvancedNetworking.hwAssistRuleSpec.iterkeys()])
            # adjust the vlan value
            rule['vlan'] = RVBDUtils.translateVlanInput(rule['vlan'], untaggedValue='1')

            if cmcPolicy:
                # CMC
                self.editNodeSequence(base, gui_AdvancedNetworking.hwAssistRuleSpec, 'add',
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
            rule['vlan'] = RVBDUtils.translateVlanInput(rule['vlan'], untaggedValue='1')
            if cmcPolicy:
                # CMC
                self.editNodeSequence(base, gui_AdvancedNetworking.hwAssistRuleSpec, 'edit',
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
                self.editNodeSequence(base, gui_AdvancedNetworking.hwAssistRuleSpec,
                                      'remove', map(int, ids))
            else:
                ids.sort(key=int, reverse=True)
                for id in ids:
                    self.sendAction('/rbt/hwassist/action/remove_rule',
                                    ('idx', 'uint16', id))
        else: #moveto_
            for fromIdx, toIdx in self.reorderEntries('movefrom_', 'moveto_', base):
                if cmcPolicy:
                    self.editNodeSequence(base, gui_AdvancedNetworking.hwAssistRuleSpec, 'move',
                                          fromIdx, moveto=toIdx)
                else:
                    self.sendAction('/rbt/hwassist/action/move_rule',
                                    ('from_idx', 'uint16', str(fromIdx)),
                                    ('to_idx', 'uint16', str(toIdx)))


class xml_AdvancedNetworking(XMLContent):
    dispatchList = ['asymmetricRouting',
                    'neighbors',
                    'netflow',
                    'peering',
                    'qosClasses',
                    'qosSitesRules',
                    'qosMarkingOptimized',
                    'qosMarkingPassthru',
                    'inboundQoSClasses',
                    'inboundQoSRules',
                    'securePeer',
                    'servicePortMap',
                    'subnetSide',
                    'wccpGroups',
                    'easyQoS_sites',
                    'easyQoS_apps',
                    'easyQoS_profiles',
                    'hwAssistRules']

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

    # Inbound qos pagelet
    # <inboundQosClasses>
    #   <class name="" priority="" minbw="" maxbw="" linkshare="">
    def inboundQoSClasses(self):
        base = self.cmcPolicyRetarget('/rbt/qos/inbound/config/class')
        classes = Nodes.getMgmtSetEntriesDeep(self.mgmt, base)
        sortedClasses = sorted(classes.keys(), cmp=FormUtils.alphanumericCompare)

        result = self.doc.createElement('inboundQosClasses')
        defaultElem = None
        for className in sortedClasses:
            classElem = self.doc.createElement('class')
            classElem.setAttribute('name', className)
            classElem.setAttribute('priority', classes[className]['priority'])
            prettyPriority = qos.getDefaultClassMgmtName(classes[className]['priority'])
            classElem.setAttribute('prettyPriority', prettyPriority)
            classElem.setAttribute('minbw', RVBDUtils.truncZeros(classes[className]['min_rate_pct'], 2))
            classElem.setAttribute('maxbw', RVBDUtils.truncZeros(classes[className]['ul_rate_pct'], 2))
            classElem.setAttribute('linkshare', RVBDUtils.truncZeros(classes[className]['ls_weight'], 2))
            if className == 'Default':
                defaultElem = classElem # save Default class to be appended to the end
            else:
                result.appendChild(classElem)
        if defaultElem is not None:
            # There is no Default class only if the user lacks qos permissions
            # and so sortedClasses is empty.
            result.appendChild(defaultElem)

        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # Inbound qos pagelet
    # <inboundQosRules>
    #   <rule name="" order="" class="" srcsubnet="" srcport="" dstsubnet="" dstport=""
    #         traffic="" protocol="" dscp="" vlan="" description="" l7protocol=""
    #         domainname="" relativepath="">
    def inboundQoSRules(self):
        base = self.cmcPolicyRetarget('/rbt/qos/inbound/config/filter')
        rules = Nodes.getMgmtSetEntriesDeep(self.mgmt, base)
        ruleIds = rules.keys()
        ruleIds.sort(FormUtils.alphanumericCompare)
        defaultRuleId = str(len(ruleIds) + 1)
        ruleIds.append(defaultRuleId)

        # default rule is added by the web ui code since there is no node for it.
        rules[defaultRuleId] = {'name': 'default',
                                'order': defaultRuleId,
                                'class': 'Default',
                                'description': '',
                                'src_network': '0.0.0.0/0',
                                'src_port': '0',
                                'dst_network': '0.0.0.0/0',
                                'dst_port': '0',
                                'traffic_type': 'all',
                                'ip_protocol': '-1',
                                'dscp': '-1',
                                'vlan': '-1',
                                'dpi_protocol': ''}


        result = self.doc.createElement('inboundQosRules')
        l7NameMap = qos.layer7ProtocolNames(self.mgmt, self.fields, flip=True)

        for ruleID in ruleIds:
            rule = rules[ruleID]
            srcPort = rule['src_port'] == '0' and 'all' or rule['src_port']
            dstPort = rule['dst_port'] == '0' and 'all' or rule['dst_port']
            dscp = rule['dscp'] == '-1' and 'all' or rule['dscp']

            ruleEl = self.doc.createElement('rule')
            ruleEl.setAttribute('name',        rule['name'])
            ruleEl.setAttribute('order',       (ruleID != defaultRuleId) and ruleID or 'default')
            ruleEl.setAttribute('class',       rule['class'])
            ruleEl.setAttribute('description', rule['description'])
            ruleEl.setAttribute('srcsubnet',   rule['src_network'])
            ruleEl.setAttribute('srcport',     srcPort)
            ruleEl.setAttribute('dstsubnet',   rule['dst_network'])
            ruleEl.setAttribute('dstport',     dstPort)
            ruleEl.setAttribute('traffic',     rule['traffic_type'])
            ruleEl.setAttribute('protocol',    rule['ip_protocol'])
            ruleEl.setAttribute('dscp',        dscp)
            ruleEl.setAttribute('prettyvlan',  RVBDUtils.translateVlanOutput(rule['vlan'])[0])
            ruleEl.setAttribute('l7protocol',  rule['dpi_protocol'])
            ruleEl.setAttribute('prettyl7protocol',  l7NameMap.get(rule['dpi_protocol'], ''))

            if rule['dpi_protocol'] != '':
                # get the extra DPI params for the DPI protocol.
                dpi_base = self.cmcPolicyRetarget('/rbt/qos/inbound/config/dpi_params/http')
                dpi_params = Nodes.getMgmtSetEntries(self.mgmt, dpi_base)

                if rule['dpi_protocol'] == 'http':
                    # Handling the HTTP L7 protocol parameters:
                    ruleEl.setAttribute('domainname', dpi_params[rule['dpi_params_idx']]['domain_name'])
                    ruleEl.setAttribute('relativepath', dpi_params[rule['dpi_params_idx']]['relative_path'])
                # Currently only http has additional DPI parameters.
            result.appendChild(ruleEl)

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
        cmc = 'editPolicy' in self.fields
        result = self.doc.createElement('portmappings')
        for eachPeer in peers:
            element = self.doc.createElement('securePeer')
            if cmc:
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

    # for setupAdvNet_qosClasses.psp:
    #
    # QOS Classes, new tree form
    #
    # <qos-classes>
    #   <qos-class connlimit=""
    #              gbw=""
    #              id=""
    #              lsbw=""
    #              name=""
    #              parent=""
    #              priority=""
    #              queue=""
    #              queue-pretty=""
    #              ubw=""
    #     <qos-class .../>
    #     ...
    #   </qos-class>
    #   ...
    # </qosclasses>
    def qosClasses(self):
        def getQosClasses(policyName):
            assert isCMCAdvPreview
            assert policyName
            # When one is viewing the Advanced preview of a Basic QoS policy on
            # a CMC, the information about the sites and rules is retrieved
            # by calling an action.
            qosClassesDict = self.sendAction('/cmc/policy/action/easy_qos/get_classes',
                                            ('policy', 'string', policyName),
                                            ('type', 'string', 'networking'))
            # The keys of the above dict have the entire path name.
            # Ex: '/cmc/policy/config/sh/networking/policy_name/node/rbt/hfsc/config/class/Default-Site$$Low-Priority/params/class_type'
            # In order to process the information in the dict, the prefix
            # '/cmc/policy/config/sh/networking/policy_name/node/rbt/hfsc/config/class/'
            # needs to be removed from the keys. Additionally, the dict also
            # has some node paths that don't have the above mentioned prefix.
            # These nodes should be removed from the dict. (qosClasses assumes
            # that all the keys of the dict returned by this function are
            # class names. If we don't remove the nodes which have a different
            # prefix, there is a real danger that qosClasses will incorrectly
            # assume that they too represent class names.)
            prefix = '/cmc/policy/config/sh/networking/%s/node/rbt/hfsc/config/class/' % policyName
            prefixLength = len(prefix)
            for nodePath in qosClassesDict.keys():
                value = qosClassesDict.pop(nodePath)
                if nodePath.startswith(prefix):
                    nodePath = nodePath[prefixLength:]
                    qosClassesDict[nodePath] = value
            qosClasses = Nodes.treeifySubtree(qosClassesDict)
            return qosClasses

        def xmlizeQosClass(qosClasses, name, parent):
            qosClass = qosClasses[name]
            classEl = self.doc.createElement('qos-class')
            classEl.setAttribute('name', name)
            # id only shows for deletable leaves
            if qosClass['children']:
                classEl.setAttribute('id', '')
            else:
                classEl.setAttribute('id', name)
            params = qosClass['params']
            classEl.setAttribute('parent', params['parent'])
            classEl.setAttribute('priority', qos.getDefaultClassMgmtName(params['class_type']))
            queue = params['queue_type']
            classEl.setAttribute('queue', queue)
            classEl.setAttribute('queue-pretty',
                                 {'pfifo': 'fifo', 'rrtcp': 'mxtcp'}.get(queue, queue))
            connlimit = params['connection_limit']
            if connlimit == '0' or queue == 'packet-order':
                connlimit = ''
            classEl.setAttribute('connlimit', connlimit)
            qosClassSc = params['sc']

            gbw = qosClassSc['rt'].get('min_bw_pct') or 0.0
            ubw = qosClassSc['ul'].get('rate_pct') or 0.0
            lsbw = qosClassSc['ls'].get('min_bw_pct') or 0.0
            classEl.setAttribute('gbw', RVBDUtils.truncZeros(gbw, 2))
            classEl.setAttribute('lsbw', RVBDUtils.truncZeros(lsbw, 2))
            classEl.setAttribute('ubw', RVBDUtils.truncZeros(ubw, 2))
            classEl.setAttribute('gbwPretty', '%.2f' % float(gbw))
            classEl.setAttribute('lsbwPretty', '%.2f' % float(lsbw))
            classEl.setAttribute('ubwPretty', '%.2f' % float(ubw))

            outDscp = params['out_dscp']
            outDscpPretty = RVBDUtils.prettyDSCP(outDscp)
            classEl.setAttribute('out_dscp', outDscp)
            classEl.setAttribute('out_dscp_pretty', outDscpPretty)

            for childName in qosClass['children']:
                xmlizeQosClass(qosClasses, childName, classEl)
            parent.appendChild(classEl)

        mgmt = self.mgmt
        isCMCAdvPreview, policyName = qos.isBasicQoSOnCMC(mgmt, self.fields)
        if isCMCAdvPreview:
            if policyName:
                qosClasses = getQosClasses(policyName)
            else:
                qosClasses = {}
        else:
            qosClasses = Nodes.getTreeifiedSubtree(mgmt, self.cmcPolicyRetarget('/rbt/hfsc/config/class'))

        roots = [] # contains the parentless classes
        # add all child classes to the 'children' list.
        for name in qosClasses.keys():
            qosClasses[name]['children'] = []
        for name in qosClasses:
            parentname = qosClasses[name]['params'].get('parent')
            if parentname in qosClasses:
                qosClasses[parentname]['children'].append(name)
            else:
                roots.append(name)
        for name in qosClasses:
            qosClasses[name]['children'].sort()
        result = self.doc.createElement('qos-classes')

        roots.sort()
        for root in roots:
            xmlizeQosClass(qosClasses, root, result)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()


    # for setupAdvNet_qosClasses.psp:
    #
    # QoS Rules
    # Hierarchically ordered by site.
    # <sites>
    #   <site id="" moveGroup="" moveGroupButtonText="" name="" subnets="">
    #     <rule class_name="" dscp="" dstPort="" dstPretty="" dstSubnet=""
    #           fullId="" id="" l7ProtocolPretty="" l7protocol="" moveGroup=""
    #           moveGroupButtonText="" name="" protocol="" protocolPretty=""
    #           srcPort="" srcPretty="" srcSubnet="" traffic_type="" vlan=""/>
    #     ...
    #   </site>
    #   ...
    # </sites>
    def qosSitesRules(self):

        def prettySubnet(subnet, port):
            if subnet.endswith('/0'):
                subnet = 'all'
            if '0' ==  port:
                port = 'all'
            return '%s:%s' % (subnet, port)

        def prettyPriority(val):
            return {'-1': 'all'}.get(val, val)

        def prettyProtocol(val):
            return {'6': 'TCP',
                   '17': 'UDP',
                   '47': 'GRE',
                   '-1': 'all',
                    '1': 'ICMP',
                   '51': 'IPsec'}.get(val, val)

        def getSitesAndProtocolInfo(policyName):
            assert isCMCAdvPreview
            assert policyName
            # When one is viewing the Advanced preview of a Basic QoS policy on
            # a CMC, the information about the sites and rules is retrieved
            # by calling an action.
            sitesAndRules = self.sendAction(
                '/cmc/policy/action/easy_qos/get_site_rules',
                ('policy', 'string', policyName),
                ('type', 'string', 'networking'))
            # The dict returned by the above has two types of key:value pairs:
            # 1. These keys have the prefix
            # '/cmc/policy/config/sh/networking/policy_name/node/rbt/hfsc/config/site/'
            # and contain information about the sites and rules.
            # 2. These keys have the prefix
            # '/cmc/policy/config/sh/networking/policy_name/node/rbt/hfsc/config/l7protocol'
            # and contain additional information about the l7protocol used by the
            # rules.
            # These key:value pairs are separated into two different dicts
            # below. Additionally, the above mentioned prefixes are stripped
            # from the keys.
            sitesPrefix = '/cmc/policy/config/sh/networking/%s/node/rbt/hfsc/config/site/' % policyName
            protocolPrefix = '/cmc/policy/config/sh/networking/%s/node/rbt/hfsc/config/l7protocol/' % policyName
            sitesPrefixLength = len(sitesPrefix)
            protocolPrefixLength = len(protocolPrefix)
            sites = {}
            protocols = {}
            for key in sitesAndRules.keys():
                value = sitesAndRules[key]
                if key.startswith(sitesPrefix):
                    key = key[sitesPrefixLength:]
                    sites[key] = value
                elif key.startswith(protocolPrefix):
                    key = key[protocolPrefixLength:]
                    protocols[key] = value
            # Information on sites like their subnets and their name, are not
            # returned by the action get_site_rules. That information has to be
            # retrieved from mgmtd.
            moreSitesInfo = mgmt.getSubtree(self.cmcPolicyRetarget('/rbt/hfsc/config/site'))
            # Add the information in moreSitesInfo to sites
            for key in moreSitesInfo.keys():
                sites[key] = moreSitesInfo[key]
            sites = Nodes.treeifySubtree(sites)
            return sites, protocols

        mgmt = self.mgmt
        isCMCAdvPreview, policyName = qos.isBasicQoSOnCMC(mgmt, self.fields)
        if isCMCAdvPreview:
            if policyName:
                sites, protocols = getSitesAndProtocolInfo(policyName)
            else:
                sites, protocols = {}, {}
        else:
            # We are either on a SH, or we are looking at the QoS configuration
            # for an Advanced QoS policy on a CMC.
            sites = Nodes.getTreeifiedSubtree(mgmt, self.cmcPolicyRetarget('/rbt/hfsc/config/site'))

        siteIds = sites.keys()
        siteIds.sort(FormUtils.alphanumericCompare)

        sitesEl = self.doc.createElement('sites')
        for siteId in siteIds:
            siteEl = self.doc.createElement('site')
            siteData = sites[siteId]

            siteEl.setAttribute('name', siteData.get('site_name'))
            siteEl.setAttribute('id', siteId)

            networkIndices = siteData.get('networks').keys()
            networkIndices.sort(key=int)
            networks = [siteData['networks'][i]['network']
                for i in networkIndices]
            siteEl.setAttribute('subnets', ';'.join(networks)) # the ; will be displayed as a newline
            siteEl.setAttribute('moveGroup', '_sites')
            siteEl.setAttribute('moveGroupButtonText', 'Move Sites...')

            # Rules
            rules = siteData.get('filter', {})
            ruleIds = rules.keys()
            ruleIds.sort(FormUtils.alphanumericCompare)

            # Each site gets a default rule.  The default rule's class
            # and out-DSCP values are those of the site.
            rules['default'] = {'class_name': siteData['default_class'],
                                'desc': '',
                                'dscp': '-1',
                                'out_dscp': siteData['out_dscp_def_rule'],
                                'out_dscp_pretty': RVBDUtils.prettyDSCP(siteData['out_dscp_def_rule']),
                                'dst': {'network': '0.0.0.0/0',
                                        'port': '0'},
                                'protocol': '-1',
                                'rule_name': 'default',
                                'src': {'network': '0.0.0.0/0',
                                        'port': '0'},
                                'traffic_type': 'all',
                                'vlan': '-1'}
            ruleIds.append('default')

            for ruleId in ruleIds:
                rule = rules[ruleId]
                ruleEl = self.doc.createElement('rule')
                ruleEl.setAttribute('id', ruleId)
                ruleEl.setAttribute('fullId', (ruleId == 'default') and
                                              '%s_default' % (siteId) or '%s_%s' % (siteId, ruleId))
                self.xmlizeAttributes(ruleEl, rule, ('class_name', 'traffic_type'))

                ruleEl.setAttribute('ruleName', rule['rule_name'])
                ruleEl.setAttribute('desc', rule['desc'])

                src = rule.get('src', {})
                dst = rule.get('dst', {})

                ruleEl.setAttribute('srcSubnet', src.get('network', ''))
                if src.get('port', '0') == '0':
                    ruleEl.setAttribute('srcPort', 'all')
                else:
                    ruleEl.setAttribute('srcPort', src.get('port', ''))
                ruleEl.setAttribute('srcPretty', prettySubnet(src.get('network', ''),
                                                              src.get('port', '')))
                ruleEl.setAttribute('dstSubnet', dst.get('network', ''))
                if dst.get('port', '0') == '0':
                    ruleEl.setAttribute('dstPort', 'all')
                else:
                    ruleEl.setAttribute('dstPort', dst.get('port', ''))
                ruleEl.setAttribute('dstPretty', prettySubnet(dst.get('network', ''),
                                                              dst.get('port', '')))

                ruleEl.setAttribute('protocol', rule['protocol'])
                ruleEl.setAttribute('protocolPretty', prettyProtocol(rule['protocol']))
                ruleEl.setAttribute('dscp', rule['dscp'])
                ruleEl.setAttribute('vlan', RVBDUtils.translateVlanOutput(rule['vlan'])[0])
                ruleEl.setAttribute('out_dscp', rule['out_dscp'])
                ruleEl.setAttribute('out_dscp_pretty', RVBDUtils.prettyDSCP(rule['out_dscp']))

                ruleEl.setAttribute('moveGroup', siteData.get('site_name', ''))
                ruleEl.setAttribute('moveGroupButtonText', 'Move %s\'s Rules...' % siteData.get('site_name', 'Site'))

                # ---------------------------------------
                # Set L7 protocol-specific attributes.
                # ---------------------------------------
                l7Protocol = rule.get('l7protocol', '')
                ruleEl.setAttribute('l7protocol', l7Protocol)

                # Query protocol-specific options. Will create pretty protocol names as side effect.
                l7PathBase = '/rbt/hfsc/config/l7protocol' # Path to L7 protocol table
                l7ProtocolPretty = qos.layer7ProtocolNames(self.mgmt, self.fields, flip=True).get(l7Protocol, '')

                if 'http' == l7Protocol:
                    l7ProtocolIndex = rule.get('l7protocol_index')
                    if isCMCAdvPreview:
                        domainName = protocols.get('http/%s/domain_name' % l7ProtocolIndex, '')
                        relativePath = protocols.get('http/%s/relative_path' % l7ProtocolIndex, '')
                    else:
                        l7Base = self.cmcPolicyRetarget(l7PathBase + '/http/' + l7ProtocolIndex)
                        l7Options = self.mgmt.getChildren(l7Base)
                        domainName = l7Options.get('domain_name', '')
                        relativePath = l7Options.get('relative_path', '')
                    ruleEl.setAttribute('l7protocol_http_domain_name', domainName)
                    ruleEl.setAttribute('l7protocol_http_relative_path', relativePath)
                    if domainName:
                        l7ProtocolPretty += ';Domain: %s' % domainName
                    if relativePath:
                        l7ProtocolPretty += ';Path: %s' % relativePath

                elif 'ica' == l7Protocol:
                    l7ProtocolIndex = rule.get('l7protocol_index')
                    if isCMCAdvPreview:
                        for i in range(4):
                            ruleEl.setAttribute('l7protocol_ica_priority%s' % (i),
                                                protocols.get('ica/%s/priority/%s/class' % (l7ProtocolIndex , i), ''))
                            ruleEl.setAttribute('l7protocol_ica_out_dscp%s' % (i),
                                                protocols.get('ica/%s/priority/%s/out_dscp' % (l7ProtocolIndex , i), ''))
                    else:
                        l7Base = self.cmcPolicyRetarget(l7PathBase + \
                                                        '/ica/' + l7ProtocolIndex + '/priority')
                        for i in range(4):
                            ruleEl.setAttribute('l7protocol_ica_priority%s' % (i),
                                                Nodes.present(self.mgmt, '%s/%s/class' % (l7Base, i)))
                            ruleEl.setAttribute('l7protocol_ica_out_dscp%s' % (i),
                                                Nodes.present(self.mgmt, '%s/%s/out_dscp' % (l7Base, i)))

                ruleEl.setAttribute('l7ProtocolPretty', l7ProtocolPretty)

                siteEl.appendChild(ruleEl)

            sitesEl.appendChild(siteEl)

        self.doc.documentElement.appendChild(sitesEl)
        self.writeXmlDoc()

    # QoS Marking Optimized
    #
    # <qos-marking-optimized>
    #   <rule id="" description="" dscp=""
    #         src-network="" src-port="" src-pretty=""
    #         dst-network="" dst-port="" dst-pretty="" />
    #   ...
    # </qos-marking-optimized>
    #
    def qosMarkingOptimized(self):
        base = self.cmcPolicyRetarget('/rbt/sport/qos/config/optimized/rule')
        rules = Nodes.getMgmtSetEntriesDeep(self.mgmt, base)
        ruleIds = rules.keys()
        ruleIds.sort(FormUtils.alphanumericCompare)
        # default rule
        rules['default'] = {'id': 'default',
                            'description': 'default',
                            'src/network': 'all',
                            'src/port_label': 'all',
                            'dst/network': 'all',
                            'dst/port_label': 'all',
                            'dscp': 'Reflect'}
        ruleIds.append('default')
        self.xmlifyRules(rules, ruleIds, 'qos-marking-optimized')

    # QoS Marking Passthrough
    #
    # <qos-marking-passthru>
    #   <rule id="" description="" dscp=""
    #         src-network="" src-port="" src-pretty=""
    #         dst-network="" dst-port="" dst-pretty="" />
    #   ...
    # </qos-marking-passthru>
    #
    def qosMarkingPassthru(self):
        base = self.cmcPolicyRetarget('/rbt/sport/qos/config/passthrough/rule')
        rules = Nodes.getMgmtSetEntriesDeep(self.mgmt, base)
        ruleIds = rules.keys()
        ruleIds.sort(FormUtils.compareStringInts)
        # default
        rules['default'] = {'id': 'default',
                            'description': 'default',
                            'src/network': 'all',
                            'src/port_label': 'all',
                            'dst/network': 'all',
                            'dst/port_label': 'all',
                            'dscp': 'Reflect'}
        ruleIds.append('default')
        self.xmlifyRules(rules, ruleIds, 'qos-marking-passthru')

    # Ship out QoS rules.
    # Used by qosMarkingOptimized() and qosMarkingPassthru() above.
    def xmlifyRules(self, rules, ruleIds, tagName):
        result = self.doc.createElement(tagName)
        for ruleId in ruleIds:
            rule = rules[ruleId]

            srcNetwork = rule.get('src/network', '')
            srcPort = rule.get('src/port_label', '')
            if '0' == srcPort:
                srcPort = 'all'
            dstNetwork = rule.get('dst/network', '')
            dstPort = rule.get('dst/port_label', '')
            if '0' == dstPort:
                dstPort = 'all'
            dscp = rule.get('dscp', '')
            if '255' == dscp:
                dscp = 'Reflect'

            element = self.doc.createElement('rule')
            element.setAttribute('id', ruleId)
            element.setAttribute('description', rule.get('description', ''))
            element.setAttribute('src-network', srcNetwork)
            element.setAttribute('src-port', srcPort)
            element.setAttribute('dst-network', dstNetwork)
            element.setAttribute('dst-port', dstPort)
            element.setAttribute('dscp', dscp)

            element.setAttribute('src-pretty', '%s : %s' % (srcNetwork, srcPort))
            element.setAttribute('dst-pretty', '%s : %s' % (dstNetwork, dstPort))

            result.appendChild(element)
        self.doc.documentElement.appendChild(result)
        result.writexml(self)

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
    #         source="" source-pretty=""
    #         destination="" destination-pretty=""
    #         port="" port-pretty=""
    #         peer="" peer-pretty=""
    #         ssl=""
    #         desc=""/>
    # </peers>
    def peering(self):
        base = self.cmcPolicyRetarget('/rbt/sport/peering/config/rule')
        rules = Nodes.getMgmtSetEntriesDeep(self.mgmt, base)
        ruleIds = rules.keys()
        ruleIds.sort(FormUtils.compareStringInts)
        # default rule at the end
        rules['default'] = {'action': 'normal',
                            'src/network': '0.0.0.0/0',
                            'dst/network': '0.0.0.0/0',
                            'dst/port_label': '0',
                            'peer/addr': '0.0.0.0/0'}
        ruleIds.append('default')
        result = self.doc.createElement('peering-rules')
        map_actionType = {'normal': 'Auto', 'respond': 'Accept', 'forward': 'Pass'}
        for ruleID in ruleIds:
            rule = rules[ruleID]
            # perform some renaming
            ruleType = rule.get('action', '')
            ruleSrc = rule.get('src/network', '0.0.0.0/0')
            ruleSrcPretty = ruleSrc
            if '0.0.0.0/0' == ruleSrc:
                ruleSrcPretty = 'All'
            ruleDst = rule.get('dst/network', '0.0.0.0/0')
            ruleDstPretty = ruleDst
            if '0.0.0.0/0' == ruleDst:
                ruleDstPretty = 'All'
            rulePeer = rule.get('peer/addr', '0.0.0.0/0')
            rulePeerPretty = rulePeer
            if '0.0.0.0/0' == rulePeer:
                rulePeerPretty = 'All'
            rulePort = rule.get('dst/port_label', '0')
            rulePortPretty = rulePort
            if '0' == rulePort:
                rulePort = 'all'
                rulePortPretty = 'All'
            ruleEl = self.doc.createElement('rule')
            ruleEl.setAttribute('id', ruleID)
            ruleEl.setAttribute('type', ruleType)
            ruleEl.setAttribute('type-pretty', map_actionType.get(ruleType, ''))
            ruleEl.setAttribute('source', ruleSrc)
            ruleEl.setAttribute('source-pretty', ruleSrcPretty)
            ruleEl.setAttribute('destination', ruleDst)
            ruleEl.setAttribute('destination-pretty', ruleDstPretty)
            ruleEl.setAttribute('port', rulePort)
            ruleEl.setAttribute('port-pretty', rulePortPretty)
            ruleEl.setAttribute('peer', rulePeer)
            ruleEl.setAttribute('peer-pretty', rulePeerPretty)
            ruleEl.setAttribute('ssl', rule.get('ssl_cap', ''))
            ruleEl.setAttribute('description', rule.get('description', ''))
            result.appendChild(ruleEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()


    # for setupAdvNet_qosEasy_sites.psp:
    #
    # <sites>
    #   <site>
    # </sites>
    def easyQoS_sites(self):
        table = self.getXmlTable(None, tagNames=('sites', 'site'))
        table.open(self.request())

        base = self.cmcPolicyRetarget('/rbt/hfsc/config/site')
        sites = Nodes.getTreeifiedSubtree(self.mgmt, base)
        siteOrder = sites.keys()
        siteOrder.sort(FormUtils.alphanumericCompare)

        for orderIndex in siteOrder:
            data = sites[orderIndex]

            subnetList = []
            subnets = data.get('networks', {})
            subnetOrder = subnets.keys()
            subnetOrder.sort(FormUtils.alphanumericCompare)
            for i in subnetOrder:
                subnetList.append(subnets.get(i, {}).get('network'))
            subnetPretty = ';'.join(subnetList) # the ; will be displayed as a newline

            wanBW = data.get('wan_bw', '0')
            wanBWPretty = GraphUtils.scale(float(wanBW) * 1000, GraphUtils.SCALER_BITS_PER_SECOND, 2)

            table.addEntry(name=data.get('site_name'),
                           subnet=subnetPretty,
                           bandwidth_profile=data.get('profile_name'),
                           remote_link_bw_pretty=wanBWPretty,
                           remote_link_bw=wanBW,
                           order_idx=orderIndex)
        table.close()


    # for setupAdvNet_qosEasy_apps.psp:
    #
    # <applications>
    #   <application cls=""
    #                cls_sort=""
    #                details=""
    #                dscp="all"
    #                dstport="all"
    #                dstsubnet=""
    #                l7protocol=""
    #                l7protocol_pretty=""
    #                name=""
    #                order=""
    #                protocol=""
    #                srcport=""
    #                srcsubnet=""
    #                traffic=""
    #                vlan=""/>
    #  </applications>
    def easyQoS_apps(self):
        table = self.getXmlTable(None, tagNames=('applications', 'application'))
        table.open(self.request())

        base = self.cmcPolicyRetarget('/rbt/hfsc/config/global_app')
        apps = Nodes.getTreeifiedSubtree(self.mgmt, base)

        appOrder = apps.keys()
        appOrder.sort(FormUtils.alphanumericCompare)

        # Create a map from L7 protocol mgmt name -> display name.  This
        # is used later to look up the display name from the
        # machine-friendly name.
        l7ProtocolNameMap = qos.layer7ProtocolNames(self.mgmt, self.fields, flip=True)

        for orderIdx in appOrder:
            globalAppData = apps[orderIdx]

            src = globalAppData.get('src', {})
            dst = globalAppData.get('dst', {})

            prettyDscp = globalAppData['dscp']
            prettyDscp = prettyDscp == '-1' and 'all' or prettyDscp

            vlan = RVBDUtils.translateVlanOutput(globalAppData['vlan'])[0]

            prettySrcPort = src['port']
            prettySrcPort = prettySrcPort == '0' and 'all' or prettySrcPort

            prettyDstPort = dst['port']
            prettyDstPort = prettyDstPort == '0' and 'all' or prettyDstPort

            defaultClass = globalAppData['default_class']
            classPriority = qos.getDefaultClassPriority(defaultClass)

            outDscp = globalAppData['out_dscp']
            outDscpPretty = RVBDUtils.prettyDSCP(outDscp)

            details = ''
            l7Protocol = globalAppData['l7protocol']
            l7ProtocolParams = {}
            l7ProtocolPretty = l7ProtocolNameMap.get(l7Protocol, '')
            if l7ProtocolPretty:
                # If there exist additional protocol options in the l7protocol table,
                # fetch them for display in the "Details" column and xml data.
                if l7Protocol in ('http',):
                    l7ProtocolIndex = globalAppData.get('l7protocol_index', '')
                    details, l7ProtocolParams = self._l7AppDetails(l7Protocol, l7ProtocolIndex)
            l7ProtocolPretty += details

            table.addEntry(name=globalAppData.get('global_app_name'),
                           desc=globalAppData['desc'],
                           cls=defaultClass,
                           cls_sort=classPriority,
                           srcsubnet=src['network'],
                           srcport=prettySrcPort,
                           dstsubnet=dst['network'],
                           dstport=prettyDstPort,
                           protocol=globalAppData['protocol'],
                           traffic=globalAppData['traffic_type'],
                           dscp=prettyDscp,
                           out_dscp=outDscp,
                           out_dscp_pretty=outDscpPretty,
                           vlan=vlan,
                           l7protocol=l7Protocol,
                           l7protocol_pretty=l7ProtocolPretty,
                           details=details,
                           order=orderIdx,
                           **l7ProtocolParams)
        table.close()

    def _l7AppDetails(self, l7Protocol, l7ProtocolIndex):
        if l7Protocol != 'http':
            return

        l7path = self.cmcPolicyRetarget('/rbt/hfsc/config/l7protocol/%s/%s') % (l7Protocol,
                                                                                   l7ProtocolIndex)
        l7OptionNodes = Nodes.getTreeifiedSubtree(self.mgmt, l7path)

        details = ''
        l7ProtocolParams = {}

        if 'http' == l7Protocol:
            # Retrieve the domain_name and relative_path parameters
            domainName = l7OptionNodes.get('domain_name', '')
            relativePath = l7OptionNodes.get('relative_path', '')
            l7ProtocolParams['l7protocol_http_domain_name'] = domainName
            l7ProtocolParams['l7protocol_http_relative_path'] = relativePath
            if domainName:
                details += ';Domain: %s' % domainName
            if relativePath:
                details += ';Path: %s' % relativePath

        return details, l7ProtocolParams

    def easyQoS_profiles(self):

        profilePath = self.cmcPolicyRetarget('/rbt/hfsc/config/profile')
        profiles = Nodes.getTreeifiedSubtree(self.mgmt, profilePath)
        profileOrder = profiles.keys()
        profileOrder.sort(FormUtils.alphanumericCompare)

        sitePath = self.cmcPolicyRetarget('/rbt/hfsc/config/site')
        allSites = Nodes.getTreeifiedSubtree(self.mgmt, sitePath)

        table = self.getXmlTable(None, tagNames=('profiles', 'profile'))
        table.open(self.request())
        for profileName in profileOrder:
            bwMapping = {} # maps class name to its corresponding bw %
            profileData = profiles.get(profileName, {})
            profileClasses = profileData.get('class', {})

            # For each class in the profile, look up its associated bw percentage.
            # classData represents the subtree from the node at
            # /rbt/hfsc/config/class/*
            for className, classData in profileClasses.iteritems():
                # When presenting, display float values to up to 2 sig digits
                # after decimal point, truncating trailing zeroes as much as possible.
                # 0.1000 -> '0.1'
                # 1.1111 -> '1.11'
                # 1.0000 -> '1'
                minBw = classData.get('min_bw_pct', '0')
                maxBw = classData.get('ul_rate_pct', '0')
                minTable = ('%.2f' % float(minBw)).rstrip("0").rstrip(".")
                maxTable = ('%.2f' % float(maxBw)).rstrip("0").rstrip(".")
                minPretty = minBw.rstrip("0").rstrip(".")
                maxPretty = maxBw.rstrip("0").rstrip(".")
                outDscp = classData.get('out_dscp', '255')
                outDscpPretty = RVBDUtils.prettyDSCP(outDscp)
                minBwmaxBwoutDscpPretty = "%3s-%s%%;%3s" % (minTable, maxTable, outDscpPretty)

                attName = qos.attributizeName(className)
                bwMapping['rt_min_bw_pct_' + attName] = minPretty
                bwMapping['ul_rate_pct_' + attName] = maxPretty
                bwMapping['table_data_' + attName] = minBwmaxBwoutDscpPretty
                bwMapping['out_dscp_' + attName] = outDscp

            # Add blank values for any unspecified classes in the profile (this can
            # happen when the user begins to make a profile in the CLI but has not
            # completed it yet.)
            for className in qos.DEFAULT_CLASSES:
                if className not in profileClasses:
                    attName = qos.attributizeName(className)
                    bwMapping['rt_min_bw_pct_' + attName] = ''
                    bwMapping['ul_rate_pct_' + attName] = ''
                    bwMapping['table_data_' + attName] = ''
                    bwMapping['out_dscp_' + attName] = ''

            # Find a list of sites associated with this profile.
            profileSites = [siteData.get('site_name')
                            for siteData in allSites.itervalues()
                            if siteData.get('profile_name') == profileName]

            # Arrange them nicely.
            profileSites.sort(FormUtils.alphanumericCompare)

            #  Create an abbreviated string of sites from the complete site list.
            #
            #  if there is exactly one site:
            #      if it is too long to fit:
            #          abbreviate it using the first 10 and last 3 letters, separated by an ellipsis
            #      else:
            #          use it verbatim
            #  else:
            #      if the first site is too long to fit:
            #          abbreviate it using the first 6 and last 3 letters, separated by an ellipsis
            #      else:
            #          keep it verbatim
            #      append a comma and ellipsis
            #
            #  Examples:
            #
            #      ['California']                      ->  'California'
            #      ['California', 'Nevada']            ->  'California,...'
            #      ['Supercalifragilistic']            ->  'Supercalif...tic'
            #      ['Supercalifragilistic', 'Nevada']  ->  'Superc...tic,...'
            #
            ## profileSitesCell = ''
            ## profileSitesLen = len(profileSites)
            ## if profileSitesLen > 0:
            ##     maxLen = profileSitesLen == 1 and 16 or 12
            ##     ps = profileSites[0]
            ##     if len(ps) > maxLen:
            ##         ps = ps[0:maxLen-6] + '...' + ps[-3:]
            ##     profileSitesCell = profileSitesLen == 1 and ps or ps + ',...'

            table.addEntry(name=profileName,
                           sites=', '.join(profileSites),
                           # abbrSites=profileSitesCell,
                           abbrSites=', '.join(profileSites),
                           **bwMapping)
        table.close()


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
            vlan, vlanPretty = RVBDUtils.translateVlanOutput(rule.get('vlan', ''), untaggedValue='1')
            ruleEl.setAttribute('vlan', vlan)
            ruleEl.setAttribute('vlan-pretty', vlanPretty)

            ruleEl.setAttribute('id', ruleId)
            ruleEl.setAttribute('description', rule.get('description', ''))
            result.appendChild(ruleEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()
