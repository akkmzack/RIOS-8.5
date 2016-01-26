## Copyright 2006-2011, Riverbed Technology, Inc., All rights reserved.
## Author: Robin Schaufler
##

import os
import re
import stat
import time
import urllib
from types import StringType, MethodType, FunctionType

import RVBDUtils
import Logging
import OSUtils
import HTTPUtils
import Nodes
import FormUtils
import GfxUtils
import GraphUtils
from PagePresentation import PagePresentation
from XMLContent import XMLContent
import logDownload

basicPathName = "/var/opt/tms/"
allowedDirs = ["sysdumps", "snapshots", "tcpdumps"]

# Enable these booleans if per-product code is needed.
isCMC = RVBDUtils.isCMC()
# isIB  = RVBDUtils.isIB()
isSH  = RVBDUtils.isSH()

def findSysFiles(directory="sysdumps"):
    if directory not in allowedDirs:
        raise OSError, "%s is not a permitted system file category." % directory
    path = basicPathName + directory
    sysFiles = [f for f in os.listdir(path)
        if not f.startswith('.')
        and stat.S_ISREG(os.stat("%s/%s" % (path, f))[stat.ST_MODE])]
    sysFiles.sort()
    return sysFiles

class gui_Diagnostics(PagePresentation):
    # actions handled here
    actionList = ['generateSysdump',
                  'logRotate',
                  'removeDiagnosticFile',
                  'tcpDumps',
                  'diagnosticAlarms']

    def logRotate(self):
        fields = self.request().fields()
        if 'rotate' in fields:
            self.sendAction("/logging/rotation/global/rotate")
            self.setActionMessage('The logs have been rotated successfully.')

    def removeDiagnosticFile(self):
        fields = self.request().fields()
        if 'removeFiles' in fields and 'dir' in fields:
            directory = fields['dir']
            if directory not in allowedDirs:
                raise OSError, "'%s' is not a permitted system file category." % directory

            path = basicPathName + directory
            for systemFile in FormUtils.getPrefixedFieldNames('ck_', fields):
                self.sendAction('/file/delete_diagnostic',
                                ('local_dir', 'string', path),
                                ('local_filename', 'string', systemFile))

    def generateSysdump(self):
        fields = self.request().fields()
        if 'genSysdump' in fields:
            # Brief sysdumps are the sysdumps that are included in process dump
            # tarballs.  There's no good reason to allow a user to create one
            # manually, so we always create a full sysdump.  The user can still
            # create a brief sysdump from the CLI if they really want to.
            params = [('brief', 'bool', 'false')]

            if 'includeStats' in fields:
                params.append(('stats', 'bool', 'true'))

            if 'includeAllLogs' in fields:
                params.append(('all_logs', 'bool', 'true'))

            # The meaning of the 'rsp' option is flipped between Steelhead and
            # BOB.  For Steelhead, a value of "true" means "yes, include RSP in
            # the sysdump"; for BOB, a value of "true" means "no, don't include
            # ESXi in the sysdump".
            if ((not RVBDUtils.isBOB() and 'includeRsp' in fields) or
                (RVBDUtils.isBOB() and 'includeRsp' not in fields)):
                params.append(('rsp', 'bool', 'true'))

            response = self.sendAction('/debug/generate/dump', *params)

            msg = "System dump requested."
            if hasattr(response, 'keys') and 'dump_path' in response.keys():
                msg = '%s has been generated.' % response['dump_path'].split('/')[-1]

            self.setActionMessage(msg)

    # The Diagnostic Tcp Dumps page, both tables.
    def tcpDumps(self):
        # dump capture files table on top
        if 'removeFiles' in self.fields:
            self.removeDiagnosticFile()

        # running tcp dumps table below:
        elif 'addTcpDump' in self.fields:
            ifaces = FormUtils.getPrefixedFieldNames('iface_', self.fields)

            # We need to handle RiOS interfaces and host interfaces (BOB boxes).
            riosIfaces = []
            hostIfaces = []
            for iface in ifaces:
                if iface == 'All':
                    pass
                elif iface.startswith('host_'):
                    hostIfaces.append(iface[5:])
                else:
                    riosIfaces.append(iface)

            name = self.fields.get('addDump_captureName', '').strip()
            bufferSize = self.fields.get('addDump_bufferSize')
            snapLength = self.fields.get('addDump_snapLength')
            rotateCount = self.fields.get('addDump_rotation', '0')
            fileSize = self.fields.get('addDump_captureMax', '0')
            duration = self.fields.get('addDump_captureDuration', '0')
            flags = self.fields.get('addDump_flags', '')
            vlan = self.fields.get('addDump_vlanEnable')

            # for the ip and port fields, parse the comma-delimited list
            # return an empty list for the default cases
            def listOrEmpty(name):
                val = self.fields.get(name, '').strip().lower()
                if val in ('', 'all', '0.0.0.0', '0'):
                    return []
                return map(str.strip, val.split(','))

            sched = self.fields.get('addDump_schedule')

            args = [('rotate_count', 'uint32', rotateCount),
                    ('custom', 'string', flags)] + \
                   [('sip', 'ipv4addr', si) for si in listOrEmpty('addDump_srcIps')] + \
                   [('sport', 'uint16', sp) for sp in listOrEmpty('addDump_srcPorts')] + \
                   [('dip', 'ipv4addr', di) for di in listOrEmpty('addDump_dstIps')] + \
                   [('dport', 'uint16', dp) for dp in listOrEmpty('addDump_dstPorts')]

            if '0' != duration:
                args.append(('duration', 'duration_sec', duration))

            if '0' != fileSize:
                args.append(('file_size', 'uint32', fileSize))

            if bufferSize:
                args.append(('buffer_size', 'uint32', bufferSize))

            if snapLength:
                args.append(('snap_len', 'uint32', snapLength))

            if name:
                args.append(('cap_name', 'string', name))

            if 'true' == vlan:
                args.append(('dot1q', 'bool', 'true'))

            if 'true' == sched:
                schedDate = self.fields.get('addDump_scheduleDate', '')
                schedTime = self.fields.get('addDump_scheduleTime', '')
                args.append(('sched_date', 'date', schedDate))
                args.append(('sched_time', 'time_sec', schedTime))

            if riosIfaces:
                riosArgs = list(args)
                riosArgs += [('interface', 'string', iface) for iface in riosIfaces]
                self.sendAction('/rbt/tcpdump/action/start', *riosArgs)

            if hostIfaces:
                hostArgs = list(args)
                hostArgs += [('interface', 'string', iface) for iface in hostIfaces]
                self.sendAction('/host/tcpdump/action/start', *hostArgs)

            if not riosIfaces and not hostIfaces:
                self.setFormError('An interface must be selected.')

        elif 'removeTcpCaptures':
            captures = FormUtils.getPrefixedFieldNames('select_', self.fields)
            riosCaptures = Nodes.getMgmtLocalChildrenNames(self.mgmt, '/rbt/tcpdump/state/capture')
            if RVBDUtils.isBOB():
                hostCaptures = Nodes.getMgmtLocalChildrenNames(self.mgmt, '/host/tcpdump/state/capture')

            for capture in captures:
                name, runningOn = capture.split('/')

                # it could have finished while the user was admiring the page
                if runningOn == 'RiOS' and name in riosCaptures:
                    self.sendAction('/rbt/tcpdump/action/stop',
                                    ('cap_name', 'string', name))
                elif runningOn == 'Hypervisor' and name in hostCaptures:
                    self.sendAction('/host/tcpdump/action/stop',
                                    ('cap_name', 'string', name))

    # alarm actions from the Alarm Status page
    def diagnosticAlarms(self):
        # clearIPMI command
        if 'clearIPMI' in self.fields:
            self.sendAction('/hw/hal/ipmi/action/clear')
            self.setActionMessage('IPMI alarm cleared.  It may take up to 30 seconds for the appliance\'s health status to update.')

class xml_Diagnostics(XMLContent):
    # actions handled here
    dispatchList = ['logFiles',
                    'snapshotFiles',
                    'sysdumpFiles',
                    'tcpdumpFiles',
                    'tcpDumpsRunning',
                    'userLogFiles',
                    'sysDetails',
                    'netTestAction',
                    'netTestDetails',
                    'alarmdAlarms']

    dogKickerList = ['netTestAction']

    # Mapping from test names to test IDs.
    # NOTE: Update this map when a new test is added!
    # Maps to enum in products/rbt_sh/src/include/rbt_nettest.h
    netTestMap = {'NET_GATEWAY': 0,
                  'CABLE_SWAP': 1,
                  'DUPLEX': 2,
                  'PEER_REACH': 3,
                  'IP_PORT_REACH': 4}

    # Net tests will return a result code. Here we make them human-readable.
    # This maps to a mgmtd enum in products/rbt_sh/src/include/rbt_nettest.h
    netTestResultCodes = ["Not Run",      # 0
                          "Running",      # 1
                          "Passed",       # 2
                          "Failed",       # 3
                          "Error",        # 4
                          "Undetermined"] # 5

    if isSH:
        import rsp
        rspPublicName = rsp.publicName()
    else:
        rspPublicName = 'RSP'

    # Map alarm ids to enhanced trigger messages.
    # See getCustomTriggerMessages() for more information.
    _alarmNotesMap = {
        'ipmi': '''
          <p>
            <input type="submit" name="clearIPMI" value="Clear" />
            Clear the IPMI Alarm Now
          </p>''',
        'cpu_util_indiv': '''
          <p>
            For details, see the
            <a href="/mgmt/gui?p=reportHostCPUUtilization">CPU Utilization Report</a>.
          </p>''',
        'paging': '''
          <p>
            See the
             <a href="/mgmt/gui?p=reportHostMemoryPaging">Memory Paging Report</a>.
          </p>''',
        'secure_vault_rekey_needed': '''
          <p>See the
            <a href="/mgmt/gui?p=setupVault">Secure Vault Page</a>.
          </p>''',
        'secure_vault_unlocked': '''
          <p>See the
            <a href="/mgmt/gui?p=setupVault">Secure Vault Page</a>.
          </p>''',
        'fs_mnt:/config:full': '''
          <p>
            To relieve /config, visit the
            <a href="/mgmt/gui?p=setupConfig">Configuration Page</a>
            to remove some saved configuration files.
          </p>''',
        'fs_mnt:/proxy:full': '''
          <p>
            To relieve /proxy, visit the
            <a href="/mgmt/gui?p=setupRSPPackages">%s Packages</a> page
            to remove packages or the
            <a href="/mgmt/gui?p=setupPFSShares">PFS Shares</a> page
            to remove shares.
          </p>''' % rspPublicName,
        'fs_mnt:/var:full': '''
          <p>
            To relieve /var, visit the
            <a href="/mgmt/gui?p=setupAdministrationLogs">Logging Configuration Page</a>
            to reduce the size and number of archived logs, or visit the
            <a href="/mgmt/gui?p=diagnosticSnapshots">Process</a>,
            <a href="/mgmt/gui?p=diagnosticSysdumps">System</a>, or
            <a href="/mgmt/gui?p=diagnosticTcpdumps">TCP</a>
            Dump Diagnostics Reports to remove old dumps.
         </p>''',
        'cmc:certs_expiring': '''
          <p>
            See the
            <a href="/mgmt/gui?p=reportSSLCertsExpiring">Expiring Certificates
            Report</a>. <span class="hintStyle">(It may take up to three hours
            for this alarm to clear after the certificates have been
            removed.)</span>
          </p>''',
        'arcount': '''
          <p>
            See the
            <a href="/mgmt/gui?p=setupAdvNet_asymmetric">Asymmetric Routes Page</a>.
          </p>''',
        'linkstate': '''
          <p>
            See the <a href="/mgmt/gui?p=reportInterfaces"> Interface Counters Report</a>.
          </p>''',
        'critical_temp': '''
          <p>
            See the <a href="/mgmt/gui?p=setupAdminAlarms">Alarms Configuration Page</a> for current thresholds.
          </p>''',
        'warning_temp': '''
          <p>
            See the <a href="/mgmt/gui?p=setupAdminAlarms">Alarms Configuration Page</a> for current thresholds.
          </p>''',
        'cmc:license': '''
          <p>
            See the <a href="/mgmt/gui?p=setupAppliance_license">Licenses Page</a>.
          </p>''',
        'appliance_unlicensed': '''
          <p>
            See the <a href="/mgmt/gui?p=setupAppliance_license">Licenses Page</a>.
          </p>''',
        'license_expired': '''
          <p>
            See the <a href="/mgmt/gui?p=setupAppliance_license">Licenses Page</a>.
          </p>''',
        'license_expiring': '''
          <p>
            See the <a href="/mgmt/gui?p=setupAppliance_license">Licenses Page</a>.
          </p>''',
        'certs_expiring': '''
          <p>
            See the <a href="/mgmt/gui?p=setupAppliance_license">Licenses
            Page</a>.
          </p>''',
        'rsp_license_expiring': '''
          <p>
            See the <a href="/mgmt/gui?p=setupAppliance_license">Licenses
            Page</a>.
          </p>''',
        'rsp_license_expired': '''
          <p>
            See the <a href="/mgmt/gui?p=setupAppliance_license">Licenses
            Page</a>.
          </p>'''
        }

    # Dispatch method that executes nettest actions (currently 'run')
    # <result status="success|error" [errorMsg=""]>
    #   <response />
    # </result>
    def netTestAction(self):
        # id        - test id (integer)
        # action    - a specified action (currently only "run")
        # interface - (optional) a comma-separated list of interface names
        #                         or specify "All" to run all.
        # address   - (optional) ipv4 address
        # port      - (optional) port number
        def netTestHelper(responseEl,
                          id=None,
                          action=None,
                          interface=None,
                          address=None,
                          port=None,
                          appliance=None):

            assert action, 'No action specified.'
            assert int(id) in self.netTestMap.values(), 'Invalid test ID specified.'

            args = []
            args.append(('test_num', 'uint32', id))

            # path to action node
            actionPath = ''

            # Dispatch on various actions. Currently, only "run"
            if 'run' == action:
                # if this is a CMC, use a different action, and send along
                # the appliance we are operating on
                if isCMC:
                    actionPath = '/cmc/actions/remote/nettest'

                    assert appliance
                    app_prod, app_sn = appliance.split('_')
                    args.append(('appliance', 'string', app_sn))

                else:
                    actionPath = '/rbt/nettest/action/exec_test'

                # Accomodate for tests with params.
                if id == str(self.netTestMap.get('DUPLEX')):
                    assert interface, 'Must specify at least one interface to run Duplex Test on.'
                    assert address, 'IP address must be specified.'
                    args.append(('param1', 'string', interface))
                    args.append(('param2', 'string', address))

                elif id == str(self.netTestMap.get('PEER_REACH')):
                    # Peer reachability test requires IP address
                    assert address, 'IP address must be specified.'
                    args.append(('param1', 'string', address))

                elif id == str(self.netTestMap.get('IP_PORT_REACH')):
                    # IP-Port reachability test requires ip address and
                    # source interface
                    assert address, 'IP address must be specified.'
                    assert interface, 'Must specify source interface.'
                    args.append(('param1', 'string', interface))
                    args.append(('param2', 'string', address))
                    if port:
                        args.append(('param3', 'string', port))

            # An invalid action keyword
            else:
                raise Exception, 'Invalid action specified.'

            self.sendAction(actionPath, *args)

        # netTestAction makes this one call.
        self.remoteCallWrapper(netTestHelper)


    # Return full test results
    # <testDetails id="" name="" has_run="" run_state="" last_run=""
    #              num_passed="" num_error="" num_failed="" num_undetermined="">
    #   <testDetail attrib_0="" attrib_1="" ... attrib_n="" />
    # </testDetails>
    def netTestDetails(self):
        fields = self.request().fields()
        base = '/rbt/nettest/state/'
        table = self.getXmlTable(None, tagNames=('testDetails', 'testDetail'))

        testId = fields.get('id', '-1')
        assert int(testId) in self.netTestMap.values(), 'Invalid test specified.'

        testBasePath = base + testId # '/rbt/nettest/state/<testId>'

        # get all nodes under testBasePath
        if isCMC:
            app_prod, app_sn = self.fields.get('appliance').split('_')

            resp = self.mgmt.action(
                '/cmc/actions/appliance/query',
                ('appliance', 'string', app_sn),
                ('operation', 'string', 'iterate'),
                ('flags', 'string', 'subtree'),
                ('timeout', 'uint32', '120'),
                ('node', 'string', testBasePath))

            # take a dictionary of flat nodes and strip the base path off
            # the keys
            subtreeDict = {}
            for key, val in resp.iteritems():
                # strip /rbt/nettest/state/<testID>/
                subtreeDict[key[len(testBasePath) + 1:]] = val

            testSubtree = Nodes.treeifySubtree(subtreeDict)

        else:
            testSubtree = Nodes.getTreeifiedSubtree(self.mgmt, testBasePath)

        if 'attrib' in testSubtree:
            numRows = len(testSubtree['attrib'])
        else:
            numRows = 0

        aggregateResultDict = {}
        for row in xrange(numRows):
            res = testSubtree['result'][str(row)]
            if res in aggregateResultDict:
                aggregateResultDict[res] += 1
            else:
                aggregateResultDict[res] = 1

        # Parse run time output.
        hasRun = testSubtree['has_run']
        lastRun = testSubtree['last_run']
        lastRunPretty = ''
        if ('true' == hasRun):
            # expected time format to parse: "1970/01/01 13:59:59"
            format = '%Y/%m/%d %H:%M:%S'
            t = time.strptime(lastRun, format)
            # Two formats will work well here:
            # '%I:%M%p on %B %d, %Y' => "1:59PM on January 01, 1970"
            # '%Y/%m/%d %I:%M%p' => "1970/01/01 1:59PM"
            prettyFormat = '%I:%M%p on %B %d, %Y' # Use the former
            lastRunPretty = time.strftime(prettyFormat, t)

        table.open(self.request(),
                   id=testId,
                   name=testSubtree['name'],
                   has_run=hasRun,
                   run_state=self.netTestResultCodes[int(testSubtree['run_state'])],
                   last_run=lastRunPretty,
                   num_passed=aggregateResultDict.get('2', 0),
                   num_failed=aggregateResultDict.get('3', 0),
                   num_error=aggregateResultDict.get('4', 0),
                   num_undetermined=aggregateResultDict.get('5', 0))

        for row in xrange(numRows):
            cols = testSubtree['attrib'][str(row)]['value']

            # Create a list of arguments to pass to addEntry
            # {'attrib_0' : ../value/0,
            #  'attrib_1' : ../value/1,
            #  ...}
            args = {}
            for col in cols:
                attribName = 'attrib_' + str(col)
                args[attribName] = cols[col]

            # Results are returned from the backend as an enum value.
            returnCode = int(testSubtree['result'][str(row)])

            # Return the human-readable result code: 0 -> "Not Run", 3 -> "Error", etc
            args['result'] = self.netTestResultCodes[returnCode]

            # Equivalent to calling:
            # table.addEntry(attrib_0 = <value>, attrib_1 = <value>, ...)
            table.addEntry(**args)

        table.close()

    # for diagnosticSystemDetails.psp:
    #
    # Displays system module details in a tree table.
    # <systemDetails>
    #   <module name="" info="" status="" />
    #     <module name="" info="" status="" />
    #     ...
    #   ...
    # </systemDetails>
    def sysDetails(self):
        basePath = self.cmcPolicyRetarget('/rbt/sport/sysdetail/state')
        fields = self.fields
        appliance = fields.get('appliance')

        if appliance:
            # Get the data from the appliance directly.
            data = self.mgmt.action(
                    '/cmc/actions/appliance/query',
                    ('appliance', 'string', appliance),
                    ('operation', 'string', 'iterate'),
                    ('flags', 'string', 'subtree'),
                    ('timeout', 'uint32', '30'),
                    ('node', 'string', basePath))

            # Pop off the basePath from the keys so we can treeify correctly.
            for k in data.keys():
                v = data.pop(k)
                if k.startswith(basePath):
                    k = k[len(basePath):]
                    if k.startswith("/"):
                        k = k[1:]
                    if k:
                        data[k] = v

            data = Nodes.treeifySubtree(data);
        else:
            data = Nodes.getTreeifiedSubtree(self.mgmt, basePath);

        # if sport is not running there won't be a 'sport' subtree so
        # use an empty dict instead
        sportModules = data.get('sport') or {}
        systemModules = data.get('system') or {}

        result = self.doc.createElement('systemDetails')

        # Maps to a 'status_map' enum in the backend:
        #     products/rbt_sh/src/bin/cli/modules/python/cli_rbt_sysdetail_cmds.py
        prettyStatuses = ['OK', 'Warning', 'Error', 'Disabled']

        # Takes in a system details data dict and adds each entry as an
        # attribute to the XML element in a pretty way.
        # moduleEl - an XML element
        # moduleName - the name the system module. Due to the design
        #                     of the backend, this attribute is not included
        #                     in moduleData dict.
        # moduleData - a data dict with entries that become XML attributes.
        def parseDataAndAttributizeXml(moduleEl, moduleName, moduleData):
            moduleEl.setAttribute('name', moduleName)

            # Formatting module data by replacing newlines with semicolons.
            # Semicolons get converted to newlines in JS.
            info = moduleData.get('info', '').replace('\n', ';')

            # Strip the last newline from info output (this fixes the bug where
            # an extra <br /> would show up at the end of each module info div)
            if info[-1:] == ';':
                info = info[:-1]

            if not info: # If no details, insert "<None>" message.
                info = "No details."
            moduleEl.setAttribute('info', info)

            statusMsg = prettyStatuses[int(moduleData.get('status', '2'))]
            moduleEl.setAttribute('status', statusMsg)
            moduleEl.setAttribute('statusTdClass', statusMsg.lower())

            return moduleEl

        # Sort module names to maintain display order.
        sysModuleNames = systemModules.keys()
        sysModuleNames.sort(FormUtils.alphanumericCompare)
        sportModuleNames = sportModules.keys()
        sportModuleNames.sort(FormUtils.alphanumericCompare)
        sortedModuleNames = sysModuleNames + sportModuleNames

        for moduleName in sortedModuleNames:
            if moduleName in sysModuleNames:
                moduleData = systemModules.get(moduleName)
            else:
                moduleData = sportModules.get(moduleName)

            moduleEl = self.doc.createElement('module')
            moduleEl = parseDataAndAttributizeXml(moduleEl,
                                                  moduleName,
                                                  moduleData)

            # Display additional submodules
            if 'items' in moduleData:
                submodules = moduleData.get('items')
                submoduleNames = submodules.keys()
                submoduleNames.sort(FormUtils.alphanumericCompare)

                # Loop through each submodule and add each entry as a child to
                # the module XML node
                for subName in submoduleNames:
                    subData = submodules.get(subName)
                    submoduleEl = self.doc.createElement('module')
                    prettyName = subData.get('name', '')

                    submoduleEl = parseDataAndAttributizeXml(submoduleEl,
                                                             prettyName,
                                                             subData)
                    moduleEl.appendChild(submoduleEl)

            result.appendChild(moduleEl)

        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for diagnosticSysdumps.psp:
    #
    def sysdumpFiles(self):
        self.xmlizeFiles('sysdumps', 'sysdump')

    def tcpdumpFiles(self):
        self.xmlizeFiles('tcpdumps', 'tcpdump')

    def snapshotFiles(self):
        self.xmlizeFiles('snapshots', 'snapshot')

    def readMd5Sum(self, directory, fileName):
        absFileName = os.path.join(basicPathName, directory, "md5/", fileName)
        md5filename = absFileName + ".md5"
        try:
            fd = open(md5filename, "rb")
        except IOError:
            return ""
        content = fd.readline()
        fd.close()
        return content

    def xmlizeFiles(self, directory, fileType):
        # stat table contains triples of (time, file, stat)
        statTable = []
        fields = self.request().fields()
        for f in findSysFiles(directory):
            s = os.stat(os.path.join(basicPathName, directory, f))
            md5sum = self.readMd5Sum(directory, f)
            statTable.append((s[stat.ST_MTIME], f, s, md5sum))
        # sort first by reverse time, then by name
        statTable.sort(lambda a,b: cmp(b[0], a[0]) or FormUtils.alphanumericCompare(a[1], b[1]))

        result = self.doc.createElement(directory)
        for sysMtime, eachFile, fileStat, md5Sum in statTable:
            sysBytes = fileStat[stat.ST_SIZE]
            sysTimeStr = time.strftime('%Y/%m/%d %H:%M',
                                       time.localtime(sysMtime))
            fileEl = self.doc.createElement('file')
            fileEl.setAttribute('name', eachFile)
            fileEl.setAttribute(
                'href', '/mgmt/download?f=%s&type=%s' % (eachFile, fileType))
            # bytes are for column sorting
            fileEl.setAttribute('bytes', '%d' % sysBytes)
            fileEl.setAttribute('sizeStr', GraphUtils.scale(
                sysBytes, GraphUtils.SCALER_HUNDREDS_OF_BYTES))
            # timestamp is for column sorting
            fileEl.setAttribute('timestamp', '%d' % sysMtime)
            fileEl.setAttribute('timestring', sysTimeStr)
            fileEl.setAttribute('md5sum', '%s' % md5Sum)
            result.appendChild(fileEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # for logDownload.psp:
    #
    def logFiles(self):
        fields = self.request().fields()
        baseName = fields.get('logPrefix', '') + 'messages'
        msgFileSeq = logDownload.findMessageFiles(baseName)
        result = self.doc.createElement('logfiles')

        if baseName in msgFileSeq:
            plainSize = os.stat('/var/log/' + baseName)[stat.ST_SIZE]
            plainSize = '(%s)' % \
                        GraphUtils.scale(plainSize,
                                       GraphUtils.SCALER_TENTHS_OF_BYTES,
                                       precision=1)

            fileEl = self.doc.createElement('file')
            fileEl.setAttribute('logName', 'Current Log')
            fileEl.setAttribute('uncompressedTitle',
                'Download the current log as plain text')
            fileEl.setAttribute(
                'uncompressedHref',
                '/mgmt/download?f=%s&type=plainlog' % baseName)
            fileEl.setAttribute('compressedTitle', '')
            fileEl.setAttribute('compressedHref', '')
            fileEl.setAttribute('plainSize', plainSize)
            result.appendChild(fileEl)
            msgFileSeq.remove(baseName)

        downloads = []
        for num in [mf.split('.')[1] for mf in msgFileSeq]:
            if num not in downloads:
                downloads.append(num)
        downloads.sort(FormUtils.alphanumericCompare)
        downloads = [(num, '%s.%s' % (baseName, num),
                           '%s.%s.gz' % (baseName, num))
                     for num in downloads]
        downloads = [(num,
                      plain in msgFileSeq and plain or compressed,
                      compressed in msgFileSeq and compressed or '')
                     for num, plain, compressed in downloads]

        for num, plain, compressed in downloads:
            fileEl = self.doc.createElement('file')
            fileEl.setAttribute('logName', 'Archived log # ' + num)
            fileEl.setAttribute('uncompressedTitle',
                'Download archived log # %s as plain text' % num)
            plainSize = ''
            if plain.endswith('.gz'):
                fileEl.setAttribute('uncompressedHref',
                    '/mgmt/download?f=%s&type=gunzippedlog' % plain)
            else:
                fileEl.setAttribute('uncompressedHref',
                    '/mgmt/download?f=%s&type=plainlog' % plain)
                plainSize = os.stat('/var/log/' + plain)[stat.ST_SIZE]
                plainSize = '(%s)' % \
                       GraphUtils.scale(plainSize,
                                      GraphUtils.SCALER_TENTHS_OF_BYTES,
                                      precision=1)
            compressedSize = ''
            if compressed:
                fileEl.setAttribute('compressedTitle',
                    'Download archived log # %s in gzip format' % num)
                fileEl.setAttribute('compressedHref',
                    '/mgmt/download?f=%s&type=gzippedlog' % compressed)
                compressedSize = os.stat('/var/log/' + compressed)[stat.ST_SIZE]
                compressedSize = '(%s)' % \
                       GraphUtils.scale(compressedSize,
                                      GraphUtils.SCALER_TENTHS_OF_BYTES,
                                      precision=1)
            else:
                fileEl.setAttribute('compressedTitle', '')
                fileEl.setAttribute('compressedHref', '')
            fileEl.setAttribute('plainSize', plainSize)
            fileEl.setAttribute('compressedSize', compressedSize)
            result.appendChild(fileEl)

        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # diagnosticTcpdumps.psp:
    #
    # <tcp-dumps-running>
    #   <tcp-dump name="" runningOn="" start="" />
    #   ...
    # </tcp-dumps-running>
    def tcpDumpsRunning(self):
        result = self.doc.createElement('tcp-dumps-running')
        self.doc.documentElement.appendChild(result)

        allCaptures = []

        # Look for all the running RiOS captures.
        riosCaptures = Nodes.getMgmtSetEntries(self.mgmt, '/rbt/tcpdump/state/capture')
        for name in riosCaptures:
            allCaptures.append((name, 'RiOS', riosCaptures[name]['start']))

        # Look for all the running hypervisor captures (for BOB).
        if RVBDUtils.isBOB():
            hostCaptures = Nodes.getMgmtSetEntries(self.mgmt, '/host/tcpdump/state/capture')
            for name in hostCaptures:
                allCaptures.append((name, 'Hypervisor', hostCaptures[name]['start']))

        # Sort by the capture name (which is basically a timestamp).
        allCaptures.sort(key=lambda x: x[0])

        for capture in allCaptures:
            dumpEl = self.doc.createElement('tcp-dump')
            result.appendChild(dumpEl)
            dumpEl.setAttribute('name', capture[0])
            dumpEl.setAttribute('runningOn', capture[1])
            dumpEl.setAttribute('start', capture[2])
            dumpEl.setAttribute('internalName', '%s/%s' % (capture[0], capture[1]))

        self.writeXmlDoc()

    ## Member function you can override to add additional alarms.
    # The dict returned will be merged in with the regular alarms.
    #
    # The alarms returned will be added as a child of 'health',
    # the root of the alarm tree.
    #
    # Here's an example of a dict containing one alarm:
    # @code
    #    { 'my_special_alarm' : {
    #        'aggregates': '',
    #        'clear_threshold': 'true',
    #        'description': 'Steelhead Optimization Service Error',
    #        'disable_allowed': 'false',
    #        'display_name': 'Optimization Service',
    #        'enabled': 'true',
    #        'error_threshold': 'true',
    #        'health_note': '',
    #        'hidden': 'false',
    #        'rising': 'true',
    #        'severity': '50',
    #        'severity_str': 'Critical',
    #        'triggered': 'true'
    #        }
    #    }
    # @endcode
    # @return
    #   a dict, with each key = alarm id (a string) and value = alarm (a dict)
    #
    def getSyntheticAlarms(self):
        return {}

    ## Member function you can override to provide specialized trigger messages.
    # The dict returned will be merged in with the regular alarm trigger messages.
    #
    # Value can be a string, which may contain HTML, or a member function
    # that returns a string which may contain HTML.
    #
    # The function signature should be of the form
    # @code
    # myFunc(self, defaultMsg)
    # @endcode
    # where defaultMsg will be the string already present in
    # the associated alarm's 'description' field.
    #
    # That way, the client can return an enhanced message
    # that's based on the original one.
    #
    # @return
    #   a dict, with key = alarm id (a string), and value = your message
    #
    def getCustomTriggerMessages(self):
        return {}

    # The Diagnostic Alarms page
    # <alarms>
    #    <alarm id="" prettyName="" status=""
    #           statusStyle="" collapse="">
    #      <triggerMessage> ... </triggerMessage>
    #    </alarm>
    #    ...
    # </alarms>
    def alarmdAlarms(self):
        # First check if the alarmd is terminated
        alarmdStatus = Nodes.present(self.mgmt, '/pm/monitor/process/alarmd/state')
        if alarmdStatus != 'running':
            self.xmlError('', 'the alarm service is not running.')
            return

        # slashes are escaped in this list
        alarmNames = Nodes.getMgmtLocalChildrenNames(self.mgmt,
                                                     '/alarm/state/alarm')

        # avoid the appliance and group healths
        alarmNames = [name
                      for name in alarmNames
                      if not (name.startswith('app:') or name.startswith('group:'))]

        alarmsRaw = self.mgmt.getPattern(*['/alarm/state/alarm/%s/*' % name
                                           for name in alarmNames])

        # build the alarm table (with unescaped slashes)
        alarms = {}
        for k, v in alarmsRaw.iteritems():
            name, entry = re_alarmSplit.match(k).groups()
            name = name.replace('\\/', '/')
            if name not in alarms:
                alarms[name] = {}
            alarms[name][entry] = v

        # Insert an item into a CSV string.
        # The CSV string is returned alphabetically sorted.
        def csvInsert(csv, item):
            if csv:
                csvList = csv.split(',')
                csvList.append(item)
                csvList.sort(FormUtils.alphanumericCompare)
                csv = ','.join(csvList)
            else:
                csv = item
            return csv

        # Add in any synthetic alarms.
        root = alarms['health']
        synths = self.getSyntheticAlarms()
        for k, v in synths.iteritems():
            root['aggregates'] = csvInsert(root['aggregates'], k)
        alarms.update(synths)

        # Add in any custom trigger notes.
        notesMap = self._alarmNotesMap.copy()
        notesMap.update(self.getCustomTriggerMessages())

        # get children for this alarm id
        def getChildren(alarmId):
            aggs = alarms[alarmId]['aggregates']
            if aggs:
                return aggs.split(',')
            else:
                return []

        # does this alarm have any non-hidden children?
        def hasVisibleChildren(alarmId):
            for ch in getChildren(alarmId):
                if 'true' != alarms[ch].get('hidden'):
                    return True
            return False

        # sort this alarm id's chilren, plop them in
        def xmlizeChildren(parentEl, alarmId):
            children = getChildren(alarmId)
            children.sort(FormUtils.alphanumericCompare,
                          key=lambda a: alarms[a]['display_name'])
            for ch in children:
                xmlizeAlarm(parentEl, ch)

        # xmlize an alarm, and place it in the parent el
        def xmlizeAlarm(parentEl, alarmId):
            alarm = alarms[alarmId]

            # skip it if "hidden"
            if 'true' == alarm.get('hidden'):
                return

            status = 'OK'
            statusStyle = 'statusSuccess'
            collapse = alarm['aggregates']
            note = False

            # 'suppressed' == true overrides 'enabled' != true
            if 'true' == alarm.get('suppressed'):
                # suppressed:
                status = 'Suppressed'
                statusStyle = 'statusDisabled'
            elif 'true' != alarm.get('enabled'):
                # not enabled:
                status = 'Disabled'
                statusStyle = 'statusDisabled'

            if 'true' == alarm.get('triggered'):
                # triggered:
                status = alarm['severity_str']
                if status.lower() == 'status':
                    status = alarm.get('health_note', 'Needs Attention')
                statusStyle = 'statusFailure'
                collapse = False
                note = alarm.get('trigger_reason', '')
                if alarmId in notesMap:
                    special = notesMap[alarmId]
                    if type(special) is MethodType:
                        note = special(alarm)
                    elif type(special) is FunctionType:
                        note = special(self.mgmt, alarm)
                    elif type(special) is StringType:
                        note = note + special

            el = self.doc.createElement('alarm')
            el.setAttribute('id', alarmId)
            el.setAttribute('prettyName', alarm['display_name'])
            el.setAttribute('status', status)
            el.setAttribute('description', alarm['description'])
            el.setAttribute('statusStyle', statusStyle)
            el.setAttribute('collapse', collapse and 'true' or 'false')
            if note:
                noteEl = self.doc.createElement('triggerMessage')
                noteEl.setAttribute('hasChildAlarms', hasVisibleChildren(alarmId) and 'true' or 'false')
                noteEl.appendChild(self.doc.createTextNode(note))
                el.appendChild(noteEl)
            parentEl.appendChild(el)
            xmlizeChildren(el, alarmId)

        # the 'health' alarm is a top-level container of all the others
        # (this may need to be tweaked in the future)
        alarmsEl = self.doc.createElement('alarms')
        xmlizeChildren(alarmsEl, 'health')
        self.doc.documentElement.appendChild(alarmsEl)
        self.writeXmlDoc()

# constant for alarm parsing
re_alarmSplit = re.compile('/alarm/state/alarm/(.+)/(.+)')
