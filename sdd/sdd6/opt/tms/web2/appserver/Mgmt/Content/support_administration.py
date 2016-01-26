## Copyright 2006, Riverbed Technology, Inc., All rights reserved.
##
## Setup Administration action and xmldata.
## Author: Robin Schaufler

import os
import time
from iph import iph
import FormUtils
import Nodes
import cgi
import RVBDUtils, Logging
from PagePresentation import PagePresentation
from XMLContent import XMLContent
import logDownload

class gui_Administration(PagePresentation):
    # actions handled here
    actionList = ['smtpAction',
                  'snmpAction',
                  'logsAction',
                  'monitoredPorts',
                  'jobsAction',
                  'webAction',
                  'clearIPMI']

    def smtpAction(self):
        if 'apply' in self.fields:
            ## eventRecipients and failureRecipients are word lists
            eventRecipients = self.fields.get('eventRecipients', '')
            Nodes.setWordList(self.mgmt,
                              self.cmcPolicyRetarget('/email/notify/events/recipients'),
                              eventRecipients)
            failureRecipients = self.fields.get('failureRecipients', '')
            Nodes.setWordList(self.mgmt,
                              self.cmcPolicyRetarget('/email/notify/failures/recipients'),
                              failureRecipients)
            params = []
            # remove the 'from_address' if the checkbox is unchecked
            if 'enableFromAddress' not in self.fields:
                params.append((self.cmcPolicyRetarget('/email/client/from_address'), 'string', ''))
            FormUtils.setNodesFromConfigForm(self.mgmt, self.fields, *params)

    # SNMP Pages
    #
    # add/remove Receivers
    # add/remove SNMP Users
    # add/remove Security Names
    # add/remove Groups
    # add/edit/remove Views
    # add/remove Access Policies
    def snmpAction(self):
        base = self.cmcPolicyRetarget('/snmp/trapsink/sink')
        userBase = self.cmcPolicyRetarget('/snmp/usm/users')
        nameBase = self.cmcPolicyRetarget('/snmp/vacm/sec_names')
        groupBase = self.cmcPolicyRetarget('/snmp/vacm/groups')
        groupSpec = {'sec_name': 'string',
                     'sec_model': 'string'}
        aclBase = self.cmcPolicyRetarget('/snmp/vacm/acls')
        aclSpec = {'group_name': 'string',
                   'sec_level': 'string',
                   'read_view': 'string'}

        id, val = FormUtils.getPrefixedField('controlReceiver_', self.fields)
        if id:
            self.mgmt.set(('%s/%s/enable' % (base, id), 'bool', ('enabled' == val) and 'true' or 'false'))

        if 'addReceiver' in self.fields:
            host = self.fields.get('addReceiver_host')
            port = self.fields.get('addReceiver_port')
            version = self.fields.get('addReceiver_version')
            enable = self.fields.get('addReceiver_enable', 'false')

            pre = '%s/%s' % (base, host)
            nodes = [(pre + '/type', 'string', version),
                     (pre + '/enable', 'bool', enable)]

            if port:
                nodes += [(pre + '/port', 'uint16', port)]
            if 'trap-v3' != version:
                # version 1, version 2
                community = self.fields.get('addReceiver_community', '')
                nodes += [(pre + '/community', 'string', community)]
            else:
                # version 3
                user = self.fields.get('addReceiver_user')
                mode = self.fields.get('addReceiver_mode')
                protocol = self.fields.get('addReceiver_protocol')
                auth = self.fields.get('addReceiver_auth')

                # key from the user, or derrived from the password
                if 'password'== mode:
                    password = self.fields.get('addReceiver_password')
                    key = self.sendAction('/snmp/usm/actions/generate_auth_key',
                                          ('password', 'string', password),
                                          ('hash_function', 'string', protocol))
                    key = key.get('auth_key', '')
                else:
                    key = self.fields.get('addReceiver_key')
                nodes += [(pre + '/username', 'string', user),
                          (pre + '/hash_function', 'string', protocol),
                          (pre + '/auth_key', 'string', key),
                          (pre + '/sec_level', 'string', auth)]
                # AuthPriv option of Security Level
                if 'authpriv'== auth:
                    privacyMode = self.fields.get('addReceiver_privacyMode')
                    if 'authPrivacy'== privacyMode:
                       # Use the same key generated from authentication password or entered for authentication
                        privacyKey = key
                    elif 'password'== privacyMode:
                       # Generate key from privacy password entered by user
                        privacyPassword = self.fields.get('addReceiver_privacyPassword')
                        privacyKey = self.sendAction('/snmp/usm/actions/generate_auth_key',
                                                    ('password', 'string', privacyPassword),
                                                    ('hash_function', 'string', protocol))
                        privacyKey = privacyKey.get('auth_key', '')
                    elif 'key'== privacyMode:
                       # Use privacy key provided by the user
                        privacyKey = self.fields.get('addReceiver_privacyKey')
                    privacyProtocol = self.fields.get('addReceiver_privacyProtocol')
                    nodes += [(pre + '/privacy_protocol', 'string', privacyProtocol),
                              (pre + '/privacy_key', 'string', privacyKey)]
            self.setNodes(*nodes)

        elif 'removeReceivers' in self.fields:
            FormUtils.deleteNodesFromConfigForm(self.mgmt, base, 'ck_', self.fields)

        elif 'addSnmpUser' in self.fields:
            name = self.fields.get('addSnmpUser_name')
            protocol = self.fields.get('addSnmpUser_protocol')
            if 'password'== self.fields.get('addSnmpUser_mode'):
                password = self.fields.get('addSnmpUser_password')
                key = self.sendAction('/snmp/usm/actions/generate_auth_key',
                                      ('password', 'string', password),
                                      ('hash_function', 'string', protocol))
                key = key.get('auth_key', '')
            else:
                key = self.fields.get('addSnmpUser_key', '')
            nodes = [('%s/%s' % (userBase, name), 'string', name),
                    ('%s/%s/auth_key' % (userBase, name), 'string', key),
                    ('%s/%s/hash_function' % (userBase, name), 'string', protocol)]
            privacyOption = self.fields.get('addSnmpUser_privacyOption', 'false')
            if 'true' == privacyOption:
                # The user wishes to use the privacy feature, therefore checkbox is checked.
                privacyProtocol = self.fields.get('addSnmpUser_privacyProtocol')
                privacyMode = self.fields.get('addSnmpUser_privacyMode')
                if 'authPrivacy' == privacyMode:
                    # Use the same key generated from authentication or entered for authentication
                    privacyKey = key
                elif 'password' == privacyMode:
                    # Generate key from password entered for privacy
                    privacyPassword = self.fields.get('addSnmpUser_privacyPassword')
                    privacyKey = self.sendAction('/snmp/usm/actions/generate_auth_key',
                                      ('password', 'string', privacyPassword),
                                      ('hash_function', 'string', protocol))
                    privacyKey = privacyKey.get('auth_key', '')
                elif 'key' == privacyMode:
                    # Use the privacy key provided by the user
                    privacyKey = self.fields.get('addSnmpUser_privacyKey')
            elif 'false' == privacyOption:
                # Privacy feature not to be used. Clear the privacy_key and privacy_protocol nodes
                privacyKey = ''
                privacyProtocol = ''
            nodes += [('%s/%s/privacy_protocol' % (userBase, name), 'string', privacyProtocol),
                      ('%s/%s/privacy_key' % (userBase, name), 'string', privacyKey)]
            self.setNodes(*nodes)
            
        elif 'removeSnmpUsers' in self.fields:
            FormUtils.deleteNodesFromConfigForm(
                self.mgmt, userBase, 'snmpUser_', self.fields)
        elif 'addSecurityName' in self.fields:
            name = self.fields.get('addSecurityName_name')
            community = self.fields.get('addSecurityName_community')
            ipBits = self.fields.get('addSecurityName_ip', ':')
            if '/' not in ipBits:
                return
            ip, maskBits = ipBits.split('/')
            self.setNodes(
                ('%s/%s' % (nameBase, name), 'string', name),
                ('%s/%s/community' % (nameBase, name), 'string', community),
                ('%s/%s/src/ip' % (nameBase, name), 'ipv4addr', ip),
                ('%s/%s/src/mask_len' % (nameBase, name), 'uint8', maskBits))
        elif 'removeSecurityNames' in self.fields:
            FormUtils.deleteNodesFromConfigForm(
                self.mgmt, nameBase, 'secName_', self.fields)
        elif 'addGroup' in self.fields:
            name = self.fields.get('addGroup_name')
            i = 0
            while True:
                model = self.fields.get('addSnmpGroup_secModel_%d' % i)
                if 'editPolicy' in self.fields:
                    if model == 'usm':
                        user = self.fields.get('addSnmpGroupUsm_secName_%d' % i)
                    else:
                        user = self.fields.get('addSnmpGroup_secName_%d' % i)
                else:
                    user = self.fields.get('addSnmpGroup_secName_%d' % i)
                if not (user and model):
                    break
                path = '%s/%s/grp_entry' % (groupBase, name)
                self.editNodeSequence(path, groupSpec, 'add', -1,
                                      {'sec_name': user,
                                       'sec_model': model})
                i += 1
        elif 'removeGroups' in self.fields:
            FormUtils.deleteNodesFromConfigForm(self.mgmt,
                                                groupBase,
                                                'group_',
                                                self.fields)
        elif 'addView' in self.fields:
            name = self.fields.get('addView_name')
            incField = self.fields.get('addView_includes')
            # If the addView_includes/_excludes field is blank, then we want a blank list.
            includes = incField and [inc.strip() for inc in incField.split('\n') if inc.strip() != ''] or []
            excField = self.fields.get('addView_excludes')
            excludes = excField and [exc.strip() for exc in excField.split('\n') if exc.strip() != ''] or []
            viewBase = self.cmcPolicyRetarget('/snmp/vacm/views/%s' % name)
            # Note: Because we don't call Nodes.deleteChildNodes here, adding a view with the
            # same name as an existing view will append those OIDs, rather than overwriting
            # the whole list of OIDs.
            nodes = [(viewBase, 'string', name)] + \
                    [('%s/included/%s' % (viewBase, inc), 'string', inc) for inc in includes] + \
                    [('%s/excluded/%s' % (viewBase, exc), 'string', exc) for exc in excludes]
            self.setNodes(*nodes)

        elif 'editView' in self.fields:
            name = self.fields.get('editView_name')
            incField = self.fields.get('editView_includes')
            # If the editView_includes/_excludes field is blank, then we want a blank list.
            includes = incField and [inc.strip() for inc in incField.split('\n') if inc.strip() != ''] or []
            excField = self.fields.get('editView_excludes')
            excludes = excField and [exc.strip() for exc in excField.split('\n') if exc.strip() != ''] or []

            viewBase = self.cmcPolicyRetarget('/snmp/vacm/views/%s' % name)
            Nodes.deleteChildNodes(self.mgmt, viewBase + '/included')
            Nodes.deleteChildNodes(self.mgmt, viewBase + '/excluded')
            nodes = [('%s/included/%s' % (viewBase, inc), 'string', inc) for inc in includes] + \
                    [('%s/excluded/%s' % (viewBase, exc), 'string', exc) for exc in excludes]
            self.setNodes(*nodes)

        elif 'removeViews' in self.fields:
            viewBase = self.cmcPolicyRetarget('/snmp/vacm/views')
            FormUtils.deleteNodesFromConfigForm(self.mgmt,
                                                viewBase,
                                                'view_',
                                                self.fields)
        elif 'addAcl' in self.fields:
            group = self.fields.get('addAcl_group')
            auth = self.fields.get('addAcl_auth')
            readView = self.fields.get('addAcl_readView')

            # group/sec pairs must be unique, so if there's currently
            # a group/sec like this one, we replace it
            acls = Nodes.getMgmtSetEntries(self.mgmt, aclBase)
            for k, v in acls.iteritems():
                if (group == v.get('group_name')) and \
                   (auth == v.get('sec_level')):
                    self.editNodeSequence(aclBase, aclSpec, 'edit', int(k),
                                          {'group_name': group,
                                           'sec_level': auth,
                                           'read_view': readView})
                    break;
            else:
                self.editNodeSequence(aclBase, aclSpec, 'add', -1,
                                      {'group_name': group,
                                       'sec_level': auth,
                                       'read_view': readView})
        elif 'removeAcls' in self.fields:
            acls = FormUtils.getPrefixedFieldNames('acl_', self.fields)
            self.editNodeSequence(aclBase, aclSpec, 'remove', map(int, acls))


    def logsAction(self):
        logServerBase = self.cmcPolicyRetarget('/logging/syslog/action/host')
        filterBase = self.cmcPolicyRetarget('/logging/syslog/config/filter/process')
        if 'addRemote' in self.fields:
            addServer = self.fields.get('addLogServer_Host')
            addSeverity = self.fields.get('addLogServer_Severity', 'notice')
            self.mgmt.set(
                ('%s/%s' % (logServerBase, addServer), 'hostname', addServer),
                ('%s/%s/selector/0/priority' % (logServerBase, addServer),
                 'string', addSeverity))
        elif 'removeLogservers' in self.fields:
            FormUtils.deleteNodesFromConfigForm(self.mgmt, logServerBase,
                                                'logserver_', self.fields)
        elif 'addFilter' in self.fields:
            process = self.fields.get('addFilter_Process')
            level = self.fields.get('addFilter_Level')
            self.mgmt.set(
                ('%s/%s' % (filterBase, process), 'string', process),
                ('%s/%s/level' % (filterBase, process), 'string', level))
        elif 'removeFilters' in self.fields:
            FormUtils.deleteNodesFromConfigForm(self.mgmt, filterBase,
                                                'filter_', self.fields)
        elif 'apply' in self.fields:
            if self.fields.get('thresholdSize'):
                thresholdSize = self.fields.get('thresholdSize')
                thresholdSize = str(max(1, int(thresholdSize)) * 1024 * 1024)
                tsNode = self.cmcPolicyRetarget('/logging/rotation/global/criteria/threshold_size')
                self.setNodes((tsNode, 'uint64', thresholdSize))
            if 'editPolicy' not in self.fields:
                # SH:
                oldKeep = int(self.mgmt.get('/logging/rotation/global/keep_number'))
                self.setFormNodes()
                newKeep = int(self.mgmt.get('/logging/rotation/global/keep_number'))
                obsolete = []
                if newKeep < oldKeep:
                    logfiles = logDownload.fillLogCategories('messages')
                    obsolete = ['/var/log/messages.%s' % x
                                for x in logfiles['ArchivedPlain']
                                if newKeep < int(x)]
                    obsolete += ['/var/log/messages.%s.gz' % x
                                 for x in logfiles['ArchivedCompressed']
                                 if newKeep < int(x)]
                for x in obsolete:
                    os.unlink(x)
            else:
                # CMC
                self.setFormNodes()

    def monitoredPorts(self):
        if 'editPolicy' in self.fields:
            base = self.cmcPolicyRetarget('/rbt/sport/reports/config/bandwidth/port')
        else:
            base = RVBDUtils.monitoredPortsPath()

        if 'addPort' in self.fields.keys():
            number = self.fields.get('addPort_number')
            if Nodes.present(self.mgmt, '%s/%s' % (base, number)):
                self.setFormError("Port %s is already being monitored." % number)
                return
            else:
                desc = self.fields.get('addPort_desc')
                self.setNodes(('%s/%s/desc' % (base, number), 'string', desc))
        elif 'removePorts' in self.fields.keys():
            FormUtils.deleteNodesFromConfigForm(self.mgmt, base, 'ck_', self.fields)
        elif 'editPort' in self.fields.keys():
            number = self.fields.get('editPort_number', None)
            desc = self.fields.get('editPort_desc', None)
            self.setNodes(('%s/%s/desc' % (base, number), 'string', desc))

    def jobsAction(self):
        id, val = FormUtils.getPrefixedField('controlJob_', self.fields)
        if id:
            self.mgmt.set(('/sched/job/%s/enable' % id, 'bool',
                           ('enabled' == val) and 'true' or 'false'))
        elif 'removeJobs' in self.fields:
            fieldPrefix = 'selectedJob_'
            FormUtils.deleteNodesFromConfigForm(self.mgmt,
                '/sched/job', 'selectedJob_', self.fields)
        elif 'editJob_cancelJob' in self.fields:
            job = '/sched/job/%s' % self.fields['editJob_jobId']
            self.mgmt.delete(job)
        elif 'editJob_executeJob' in self.fields:
            job = self.fields['editJob_jobId']
            self.sendAction('/sched/job/actions/execute',
                            ('job_id', 'string', job))
        elif 'editJob_modifyJob' in self.fields:
            prefix = '/sched/job/%s/%%s' % self.fields['editJob_jobId']
            if self.fields['editJob_datetime']:
                datetime = self.fields['editJob_datetime']
            else:
                datetime = time.strftime('%Y/%m/%d %H:%M:%S', time.gmtime(0))
            datetime = datetime.split(' ')
            apply = [
                (prefix % 'name', 'string', self.fields.get('editJob_name', "")),
                (prefix % 'comment', 'string',
                    self.fields.get('editJob_comment', "")),
                (prefix % 'date', 'date', datetime[0]),
                (prefix % 'time', 'time_sec', datetime[1]),
                (prefix % 'recurring', 'uint32',
                    self.fields.get('editJob_frequency', "")),
                (prefix % 'enable', 'bool',
                    self.fields.get('editJob_enable', "false"))
            ]
            self.mgmt.set(*apply)

    def webAction(self):
        inactivityTimeout = self.fields.get('inactivityTimeout')
        try:
            self.setNodes((self.cmcPolicyRetarget('/wsm/inactivity_timeout'),
                                              'duration_sec',
                                              str(int(inactivityTimeout) * 60)))
        except:
            raise ValueError, 'Inactivity timeout must be between 0 (no timeout) and 43200 minutes (30 days)'

        self.setFormNodes()

    def clearIPMI(self):
        self.sendAction('/hw/hal/ipmi/action/clear')
        self.setActionMessage('IPMI alarm cleared.  It may take up to 30 seconds for the appliance\'s health status to update.')

class xml_Administration(XMLContent):
    # actions handled here
    dispatchList = [
        'webCertReplace',
        'jobsXmldata',
        'logserverXmldata',
        'monitoredPorts',
        'perProcessLogging',
        'portsXmldata',
        'snmpTrapReceivers',
        'snmpTrapTest',
        'snmpUsers',
        'snmpSecurityNames',
        'snmpGroups',
        'snmpViews',
        'snmpAcls',
    ]

    dogKickerList = [
        'webCertReplace',
        'snmpTrapTest',
    ]

    ## Replace the web SSL cert via AJAX.
    #
    # We expect a field called <tt>certMode</tt> whose value
    # determines whether we're replacing by (1) importing a monolithic
    # cert+key, (2) importing the cert and key separately, or (3)
    # generating a new cert.
    #
    # The existence of additional fields depend on the value of
    # <tt>certMode</tt> as follows:
    #
    # - <tt>certMode == 'import1'</tt>
    #   - <tt>certKeyFileMode</tt>: 'true' if a file is being uploaded
    #     and 'false' otherwise.
    #   - <tt>certKeyUploadFile</tt>:  Exists if
    #     <tt>certKeyFileMode</tt> is 'true'.
    #   - <tt>certKeyText</tt>:  Exists if <tt>certKeyFileMode</tt> is
    #     'false'.
    #   - <tt>certKeyPassword1</tt>
    # - <tt>certMode == 'import2'</tt>
    #   - <tt>certFileMode</tt>: 'true' if a file is being uploaded
    #     and 'false' otherwise.
    #   - <tt>certUploadFile</tt>:  Exists if <tt>certFileMode</tt> is
    #     'true'.
    #   - <tt>certText</tt>:  Exists if <tt>certFileMode</tt> is
    #     'false'.
    #   - <tt>keyFileMode</tt>: 'true' if a file is being uploaded
    #     and 'false' otherwise.
    #   - <tt>keyUploadFile</tt>:  Exists if <tt>keyFileMode</tt> is
    #     'true'.
    #   - <tt>keyText</tt>:  Exists if <tt>keyFileMode</tt> is
    #     'false'.
    # - <tt>certMode == 'generate'</tt>
    #   - <tt>generate_cipherBits</tt>
    #   - <tt>generate_org</tt>
    #   - <tt>generate_org_unit</tt>
    #   - <tt>generate_locality</tt>
    #   - <tt>generate_state</tt>
    #   - <tt>generate_country</tt>
    #   - <tt>generate_email</tt>
    #   - <tt>generate_valid_days</tt>
    #
    # We also may receive the <tt>appSn</tt> field telling us the appliance
    # serial to use if we are dealing with a CMC managed appliance (and there is
    # no harm in passing an empty app_serial parameter to the cert actions).
    #
    # Web certs are unusual in that httpd is sent a HUP in the middle
    # of the action.  This means that we can't guarantee that we'll
    # be able to return a response.  (It depends on how soon httpd is
    # able to handle the signal.)  However, we can return failures and
    # assume on the client side that an interrupted response to this
    # request means that the operation succeeded.
    #
    # This returns the following response:
    #
    # @verbatim
    # {
    #   'success': Boolean,
    #   'errorMsg': String   # only present if success is false
    # }
    # @endverbatim
    #
    # Design doc:
    # https://twiki.nbttech.com/twiki/bin/view/NBT/WebUiCertMgmtDesign
    def webCertReplace(self):

        def internal(**kw):

            result = {}
            actionBase = '/web/action'
            appSn = ''

            if 'appSn' in kw:
                # The CMC has it's own web certificate, but in this scenario
                # we are interacting with a managed appliance's web cert
                # through a CMC appliance specific policy page.
                actionBase = '/cmc/policy/action/web'
                appSn = kw['appSn']

            try:

                # Monolithic cert+key, either in a file or a text
                # field.
                if kw['certMode'] == 'import1':

                    if kw['certKeyFileMode'] == 'true':
                        certKey = kw['certKeyUploadFile'].value
                    else:
                        certKey = kw['certKeyText']

                    code, msg, bindings = self.mgmt.actionResults(
                        actionBase + '/httpd/ssl/cert/import',
                        ('app_serial', 'string', appSn),
                        ('cert_and_key', 'binary', certKey),
                        ('dec_password', 'string', kw['certKeyPassword1']))

                # Separate cert and key.  In this case the key is
                # optional and either can be a file or a text field.
                elif kw['certMode'] == 'import2':

                    if kw['certFileMode'] == 'true':
                        cert = kw['certUploadFile'].value
                    else:
                        cert = kw['certText']

                    if kw['keyFileMode'] == 'true':
                        keyFileField = kw['keyUploadFile']
                        key = isinstance(keyFileField, cgi.FieldStorage) \
                            and keyFileField.value or ''
                    else:
                        key = kw['keyText']

                    params = [
                        ('dec_password', 'string', kw['certKeyPassword2']),
                        ('cert', 'binary', cert),
                    ]

                    if key:
                        params.append(('key', 'binary', key))

                    code, msg, bindings = self.mgmt.actionResults(
                        actionBase + '/httpd/ssl/cert/import',
                        ('app_serial', 'string', appSn), *params)

                # Generate a new cert.
                else:  # kw['certMode'] == 'generate'
                    code, msg, bindings = self.mgmt.actionResults(
                        actionBase + '/httpd/ssl/cert/generate',
                        ('app_serial', 'string', appSn),
                        ('cipher_bits', 'uint32', kw['generate_cipherBits']),
                        ('org', 'string', kw['generate_org']),
                        ('org_unit', 'string', kw['generate_org_unit']),
                        ('locality', 'string', kw['generate_locality']),
                        ('state', 'string', kw['generate_state']),
                        ('country', 'string', kw['generate_country']),
                        ('email', 'string', kw['generate_email']),
                        ('valid_days', 'uint32', kw['generate_valid_days']))

                # Set the status to success if the return code is 0.
                # Also save the message (if it exists) in the session
                # so that it can be displayed when the page refreshes.
                # (This is handled by the PSP.)
                if code == 0:
                    result['success'] = True
                    if msg:
                        self.session().setValue('webCertReplaceMessage', msg)
                else:
                    result['success'] = False
                    result['errorMsg'] = msg

            # Catch all unexpected exceptions and return the messages.
            # We need to do this because OOB errors are considered
            # successes on the client side due to the httpd HUP.
            except Exception, e:
                result['success'] = False
                result['errorMsg'] = 'Internal error: ' + str(e)

            return result

        self.rpcWrapper(internal)

    # for setupAdministrationJobs.psp:
    #
    # <jobs>
    #   <job jobId=""
    #        name=""
    #        comment=""
    #        status="completed / error / inactive / pending / unknown"
    #        statusDetail="Completed / Inactive / Pending / ERRORSTRING"
    #        statusIcon="icon_job_STATUS.gif"
    #        recurs="Y / N"
    #        recurIcon="icon_refresh.gif / icon_job_once.gif"
    #        enable="true / false"
    #        frequencySeconds=""
    #        frequencyLang="Not recurring / Recurs every N seconds"
    #        datetime=""
    #        creation=""
    #        lastrun="">
    #     <command instruction="no radius host 192.168.200.201" />
    #     <command instruction="radius host 192.168.300.301" />
    #   </job>
    # </jobs>
    def jobsXmldata(self):
        jobs = Nodes.getMgmtSetEntriesDeep(self.mgmt, '/sched/job')
        jobIds = jobs.keys()
        jobIds.sort(FormUtils.compareStringInts)
        gmStartEpoch = time.strftime('%Y/%m/%d %H:%M:%S', time.gmtime(0))
        localStartEpoch = time.strftime('%Y/%m/%d %H:%M:%S', time.localtime(0))
        result = self.doc.createElement('jobs')
        for jobId in jobIds:
            outputInfo = 'None.'
            outputFile = Nodes.present(self.mgmt, '/sched/job/%s/output_file' % jobId, '')
            if outputFile:
                try:
                    outputLines = file(outputFile).readlines()
                    if outputLines and len(outputLines) > 0:
                        outputInfo = '#012;'
                        for outputLine in outputLines:
                            outputInfo += '%s#012;' % cgi.escape(outputLine)
                except:
                    outputInfo = 'None.'

            job = jobs[jobId]
            jobEl = self.doc.createElement('job')
            jobEl.setAttribute('jobId', jobId)
            jobEl.setAttribute('name', job['name'])
            jobEl.setAttribute('comment', job['comment'])
            jobEl.setAttribute('output', outputInfo)
            status = job.get('status', "unknown")
            errorString = job.get('error_string', "")
            # if errorString and 'completed' == status:
            if errorString:
                status = 'error'
            jobEl.setAttribute('status', status)
            jobEl.setAttribute('statusIcon', 'icon_job_%s.gif' % status)
            if not errorString:
                errorString = status.capitalize()
            jobEl.setAttribute('statusDetail', errorString)
            frequency = job.get('recurring', '0')
            jobEl.setAttribute('frequencySeconds', frequency)
            jobEl.setAttribute('frequencyLang', iph(int(frequency)).then(
                'Recurs every %s seconds' % frequency, 'Not recurring'))
            jobEl.setAttribute('recurs', iph(int(frequency)).then('Y', 'N'))
            jobEl.setAttribute('recurIcon', iph(int(frequency)).then(
                'icon_refresh.gif', 'icon_job_once.gif'))
            jobEl.setAttribute('enabled',
                ('true' == job['enable']) and 'enabled' or 'disabled')
            datetime = ' '.join((job['date'], job['time']))
            if gmStartEpoch == datetime:
                datetime = ""
            jobEl.setAttribute('datetime', datetime)
            datetime = job.get('create_time', '')
            if localStartEpoch == datetime:
                datetime = ""
            jobEl.setAttribute('creation', datetime)
            datetime = job.get('last_exec_time', '')
            if localStartEpoch == datetime:
                datetime = ""
            jobEl.setAttribute('lastrun', datetime)
            commandSeqs = [x.split('/')[-1]
                for x in job.keys()
                if x.startswith('commands/') and not x.endswith('/command')]
            commandSeqs.sort(FormUtils.compareStringInts)
            for eachSeq in commandSeqs:
                command = job['commands/%s/command' % eachSeq]
                commandEl = self.doc.createElement('command')
                commandEl.setAttribute('instruction', command)
                jobEl.appendChild(commandEl)
            result.appendChild(jobEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupAdminSNMP_basic.psp:
    #
    # <snmp-trap-receivers>
    #   <receiver />
    #   ...
    # </snmp-trap-receivers>
    def snmpTrapReceivers(self):
        table = self.getXmlTable(None, tagNames=('snmp-trap-receivers', 'receiver'))
        table.open(self.request())

        base = self.cmcPolicyRetarget('/snmp/trapsink/sink')
        receivers = Nodes.getMgmtSetEntries(self.mgmt, base)
        hosts = receivers.keys()
        hosts.sort(FormUtils.alphanumericCompare)
        for host in hosts:
            receiver = receivers[host]
            version = receiver.get('type')[len('trap-'):]
            port = receiver.get('port')
            if 'v3' == version:
                user = receiver.get('username', '')
                protocol = receiver.get('hash_function', '')
                auth = receiver.get('sec_level', '')
                authValue = (('auth' == auth) and 'Auth' or 
                             ('noauth' == auth) and 'No Auth' or 
                             ('authpriv' == auth) and 'AuthPriv')
                # update the community/user to include privacy protocol and security level as authpriv
                if authValue == 'AuthPriv':
                    privacyProtocol = receiver.get('privacy_protocol', '')
                    desc = 'user: %s, %s, %s, %s' % (user, protocol, authValue, privacyProtocol)
                else:
                    desc = 'user: %s, %s, %s' % (user, protocol, authValue)
            else:
                desc = 'community: %s' % (receiver.get('community') or 'public')
            table.addEntry(host=host,
                           version=version,
                           port=port,
                           desc=desc,
                           enabled=('true' == receiver['enable']) and 'enabled' or 'disabled')
        table.close()

    # for setupAdminSNMP_basic.psp:
    #
    def snmpTrapTest(self):
        self.sendAction('/snmp/actions/trap/test')
        result = self.doc.createElement('reply')
        result.appendChild(self.doc.createTextNode('Trap test sent.'))
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupAdminSNMP_v3.psp:
    #
    # System Settings SNMP page
    #
    # <users>
    #   <user name="" protocol="" key="" />
    # </users>
    def snmpUsers(self):
        base = self.cmcPolicyRetarget('/snmp/usm/users')
        users = Nodes.getMgmtSetEntries(self.mgmt, base)
        names = users.keys()
        names.sort(FormUtils.alphanumericCompare)
        table = self.getXmlTable(None, tagNames=('users', 'user'))
        table.open(self.request())
        for name in names:
            user = users[name]
            table.addEntry(name=name,
                           protocol=user.get('hash_function'),
                           key=user.get('auth_key'),
                           privacy=user.get('privacy_protocol'),
                           privacyKey=user.get('privacy_key'))                           
        table.close()

    # for setupAdminSNMP_acl.psp:
    #
    def snmpSecurityNames(self):
        base = self.cmcPolicyRetarget('/snmp/vacm/sec_names')
        secNamesTree = self.mgmt.getSubtree(base)
        names = [k for k,v in secNamesTree.iteritems() if k == v and '/' not in k]
        names.sort(FormUtils.alphanumericCompare)
        table = self.getXmlTable(None, tagNames=('sec-users', 'sec-user'))
        table.open(self.request())

        for name in names:
            table.addEntry(name=name,
                           community=secNamesTree.get(name + '/community'),
                           src=secNamesTree.get(name + '/src/ip', '') + '/' + \
                               secNamesTree.get(name + '/src/mask_len'))
        table.close()

    # for setupAdminSNMP_acl.psp:
    #
    def snmpGroups(self):
        base = self.cmcPolicyRetarget('/snmp/vacm/groups')
        groupTree = self.mgmt.getSubtree(base)
        names = [k for k,v in groupTree.iteritems() if k == v and '/' not in k]
        names.sort(FormUtils.alphanumericCompare)

        result = self.doc.createElement('groups')
        for name in names:
            groupEl = self.doc.createElement('group')
            groupEl.setAttribute('name', name)
            prefix = name + '/grp_entry/'
            afterPrefix = len(prefix) + 1
            indexes = [v
                       for k, v in groupTree.iteritems()
                       if k.startswith(prefix) and k.endswith(v) and \
                           (-1 == k.find('/', afterPrefix))]
            indexes.sort(lambda a, b: cmp(int(a), int(b)))
            for index in indexes:
                eachName = groupTree['%s%s/sec_name' % (prefix, index)]
                eachModel = groupTree['%s%s/sec_model' % (prefix, index)]
                entryEl = self.doc.createElement('entry')
                entryEl.setAttribute('index', index)
                entryEl.setAttribute('name', eachName)
                entryEl.setAttribute('model', eachModel)
                entryEl.setAttribute('pretty', '%s: %s' % (eachModel, eachName))
                groupEl.appendChild(entryEl)
            result.appendChild(groupEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupAdminSNMP_acl.psp:
    #
    def snmpViews(self):
        base = self.cmcPolicyRetarget('/snmp/vacm/views')
        viewsTree = self.mgmt.getSubtree(base)
        names = [k for k,v in viewsTree.iteritems() if k == v and '/' not in k]
        names.sort(FormUtils.alphanumericCompare)

        table = self.getXmlTable(None, tagNames=('views', 'view'))
        table.open(self.request())

        for name in names:
            includes = [v
                        for k,v in viewsTree.iteritems()
                        if k.startswith('%s/included/' % name)]
            includes.sort(FormUtils.alphanumericCompare)

            MAX_OID_CHARS = 20

            # The includes "preview" is displayed in the AET row. The full list
            # of included OIDs is displayed in the edit div.
            includesPreview = ','.join(includes)
            if len(includesPreview) > MAX_OID_CHARS: # Truncate if the string is too long.
                includesPreview = includesPreview[:MAX_OID_CHARS - 3] + '...'
            if len(includes) > 1: # Detail how many OIDs are in the list.
                includesPreview = '(%s OIDs) ' % len(includes) + includesPreview

            excludes = [v
                        for k,v in viewsTree.iteritems()
                        if k.startswith('%s/excluded/' % name)]
            excludes.sort(FormUtils.alphanumericCompare)

            # The excludes "preview" is similar to includes preview.
            excludesPreview = ','.join(excludes)
            if len(excludesPreview) > MAX_OID_CHARS: # Truncate if the string is too long.
                excludesPreview = excludesPreview[:MAX_OID_CHARS - 3] + '...'
            if len(excludes) > 1: # Detail how many OIDs are in the list.
                excludesPreview = '(%s OIDs) ' % len(excludes) + excludesPreview

            table.addEntry(name=name,
                           includes='\\;'.join(includes),
                           excludes='\\;'.join(excludes),
                           includesPreview=includesPreview,
                           excludesPreview=excludesPreview)
        table.close()

    # for setupAdminSNMP_acl.psp:
    #
    def snmpAcls(self):
        base = self.cmcPolicyRetarget('/snmp/vacm/acls')
        acls = Nodes.getMgmtSetEntries(self.mgmt, base)
        ids = acls.keys()
        ids.sort(lambda a, b: cmp(int(a), int(b)))

        table = self.getXmlTable(None, tagNames=('policies', 'policy'))
        table.open(self.request())
        for id in ids:
            acl = acls[id]
            table.addEntry(id=id,
                           group_name=acl.get('group_name'),
                           sec_level=acl.get('sec_level'),
                           read_view=acl.get('read_view'))
        table.close()

    # for setupAdministrationLogs.psp, error403.psp:
    #
    # <logservers>
    #   <logserver serverIp="" priority="" />
    #   ...
    # </logservers>
    def logserverXmldata(self):
        remotePrefix = self.cmcPolicyRetarget('/logging/syslog/action/host')
        priority = 'selector/0/priority'
        lvl=['emerg','alert','crit','err','warning','notice','info','debug','none']
        levelNameToInt = dict(zip(lvl, range(len(lvl))))
        remoteMap = Nodes.getMgmtTabularDescendents(
            self.mgmt, remotePrefix,
            lambda x, y: cmp(levelNameToInt[x[priority]],
                             levelNameToInt[y[priority]]),
            priority)
        result = self.doc.createElement('logservers')
        for eachRemote in remoteMap:
            logserver = self.doc.createElement('logserver')
            logserver.setAttribute('serverIp', eachRemote['parentKey'])
            logserver.setAttribute('priority', eachRemote[priority])
            result.appendChild(logserver)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupAdministrationLogs.psp:
    #
    # <perProcessLogging>
    #   <processFilter process="" prettyName="" level="" />
    #   ...
    # </perProcessLogging>
    def perProcessLogging(self):
        # level -> pretty name map
        levelOptions = {
            'emerg': 'Emergency',
            'alert': 'Alert',
            'crit': 'Critical',
            'err': 'Error',
            'warning': 'Warning',
            'notice': 'Notice',
            'info': 'Info',
        }

        # filters <- {process: {..., 'level': level, ...}
        base = self.cmcPolicyRetarget('/logging/syslog/config/filter/process')
        filters = Nodes.getMgmtSetEntries(self.mgmt, base)

        filterDescription = \
            self.cmcPolicyRetarget('/logging/syslog/state/filter/process/%s/description')
        # fetch pretty names
        filterNameMap = self.mgmt.getMultiple(*[
            filterDescription % k for k in filters.iterkeys()])
        # filters <- [(prettyName, process, level), ...]
        filters = [(filterNameMap.get(filterDescription % k) or k,
                    k, v.get('level'))
                   for k, v in filters.items()]
        # Sort on prettyName, then process, then level.
        filters.sort()
        result = self.doc.createElement('perProcessLogging')
        for prettyName, process, level in filters:
            processFilter = self.doc.createElement('processFilter')
            processFilter.setAttribute('prettyName', prettyName)
            processFilter.setAttribute('process', process)
            processFilter.setAttribute(
                'level', levelOptions.get(level, level))
            result.appendChild(processFilter)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for setupAdministrationPorts.psp:
    #
    def monitoredPorts(self):
        if 'editPolicy' in self.fields:
            base = self.cmcPolicyRetarget('/rbt/sport/reports/config/bandwidth/port')
        else:
            base = RVBDUtils.monitoredPortsPath()

        portMap = Nodes.getMgmtTabularSubtree(self.mgmt, base, Nodes.parentKeyStringIntCmp)
        result = self.doc.createElement('monitoredPorts')
        for eachPort in portMap:
            portEl = self.doc.createElement('port')
            portEl.setAttribute('number', eachPort['parentKey'])
            portEl.setAttribute('desc', eachPort['desc'])
            result.appendChild(portEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

