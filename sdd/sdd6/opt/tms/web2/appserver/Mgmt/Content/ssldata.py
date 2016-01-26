# Copyright 2006 Riverbed Technology, Inc. All rights reserved.
#
# ssldata servlet
# Author: Munir Bandukwala

from WebKit.HTTPContent import HTTPContent
from gclclient import NonZeroReturnCodeException
import Nodes
import FormUtils

class ssldata(HTTPContent):

    # ssldata always counts as busy against idle timeout.
    def awake(self, transaction):
        transaction.session().moreBusy()
        HTTPContent.awake(self, transaction)

    def sleep(self, transaction):
        HTTPContent.sleep(self, transaction)
        transaction.session().lessBusy()

    # Get the data and send data as application/octet
    def _respond(self, transaction):
        mgmt = transaction.session().value('mgmt')
        fields = transaction.request().fields()
        response = transaction.response()

        data = ''
        filename = ''
        try:
            if 'monitor' == mgmt.remoteUser.lower():
                data = {'file_contents': 'Not permitted for monitor.'}
                filename='NotPermittedForMonitor.txt'

            elif 'exportBulkSSLData' == fields.get('action'):
                args = [('enc_password', 'string', fields.get('exportPassword', ''))]
                if 'true' == fields.get('exportIncludeServers'):
                    args.append(('include_servers', 'bool', 'true'))
                if 'true' == fields.get('exportIncludeAltCfg'):
                    args.append(('include_alt_cfg', 'bool', 'true'))
                data = Nodes.action(mgmt, '/rbt/sport/ssl/action/all/export', *args)
                filename = 'ssl_bulk_export.bin'

            elif 'exportPeeringSSLData' == fields.get('action'):
                args = [('enc_password', 'string', fields.get('exportPassword', ''))]
                if 'true' == fields.get('exportIncludeKey'):
                    args.append(('include_key', 'bool', 'true'))
                data = Nodes.action(mgmt, '/rbt/sport/ssl/action/tunnel/export', *args)
                filename = 'ssl_peer_export.bin'

            elif 'generateCSRSSLData' == fields.get('action'):
                common_name = fields.get('common_name')
                org = fields.get('org')
                org_unit = fields.get('org_unit')
                locality = fields.get('locality')
                state = fields.get('state')
                country = fields.get('country')
                email = fields.get('email')
                data = Nodes.action(mgmt,
                                    '/rbt/sport/ssl/action/tunnel/generate_csr',
                                    ('common_name', 'string', common_name),
                                    ('org', 'string', org),
                                    ('org_unit', 'string', org_unit),
                                    ('locality', 'string', locality),
                                    ('state', 'string', state),
                                    ('country', 'string', country),
                                    ('email', 'string', email))
                filename = 'ssl_peer.csr'

            elif 'generateCSRSSLDataWeb' == fields.get('action'):
                common_name = fields.get('common_name')
                org = fields.get('org')
                org_unit = fields.get('org_unit')
                locality = fields.get('locality')
                state = fields.get('state')
                country = fields.get('country')
                email = fields.get('email')
                data = Nodes.action(mgmt,
                                    '/web/action/httpd/ssl/cert/generate_csr',
                                    ('common_name', 'string', common_name),
                                    ('org', 'string', org),
                                    ('org_unit', 'string', org_unit),
                                    ('locality', 'string', locality),
                                    ('state', 'string', state),
                                    ('country', 'string', country),
                                    ('email', 'string', email))
                filename = 'ssl_web.csr'

            elif 'exportSigningSSLData' == fields.get('action'):
                args = [('enc_password', 'string',
                         fields.get('exportPassword', ''))]
                if 'true' == fields.get('exportIncludeKey'):
                    args.append(('include_key', 'bool', 'true'))
                data = Nodes.action(mgmt, '/rbt/sport/ssl/action/signing/export', *args)
                filename = 'ssl_signing_export.bin'

            elif 'generateCSRSSLSigningData' == fields.get('action'):
                common_name = fields.get('common_name')
                org = fields.get('org')
                org_unit = fields.get('org_unit')
                locality = fields.get('locality')
                state = fields.get('state')
                country = fields.get('country')
                email = fields.get('email')
                data = Nodes.action(mgmt,
                                    '/rbt/sport/ssl/action/signing/generate_csr',
                                    ('common_name', 'string', common_name),
                                    ('org', 'string', org),
                                    ('org_unit', 'string', org_unit),
                                    ('locality', 'string', locality),
                                    ('state', 'string', state),
                                    ('country', 'string', country),
                                    ('email', 'string', email))
                filename = 'ssl_signing.csr'



            elif 'serverCertCSR' == fields.get('_action_'):
                name = fields.get('serverCert_name')
                common_name = fields.get('csr_common_name')
                org = fields.get('csr_org')
                org_unit = fields.get('csr_org_unit')
                locality = fields.get('csr_locality')
                state = fields.get('csr_state')
                country = fields.get('csr_country')
                email = fields.get('csr_email')
                data = Nodes.action(mgmt,
                                    '/rbt/sport/ssl/action/server_certs/generate_csr',
                                    ('name', 'string', name),
                                    ('common_name', 'string', common_name),
                                    ('country', 'string', country),
                                    ('email', 'string', email),
                                    ('locality', 'string', locality),
                                    ('org', 'string', org),
                                    ('org_unit', 'string', org_unit),
                                    ('state', 'string', state))
                filename = '%s.csr' % name

            elif 'exportServerCert' == fields.get('_action_'):
                name = fields.get('serverCert_name')
                includeKey = fields.get('export_includeKey', 'false')
                args = [('name', 'string', name),
                        ('include_key', 'bool', includeKey)]
                if 'true' == includeKey:
                    password = fields.get('export_password')
                    args.append(('enc_password', 'string', password))
                data = Nodes.action(mgmt,
                                    '/rbt/sport/ssl/action/server_certs/export',
                                    *args)
                filename = '%s.bin' % name

            response.setHeader('Content-type', 'application/octet-stream')
            response.setHeader('Content-Disposition', 'attachment; filename=' + filename)
            response.write(data['file_contents'])

        except NonZeroReturnCodeException, x:
            response.write('An error occurred: ' + str(x))
