## Copyright 2006 Riverbed Technology, Inc. All rights reserved.
##
## Servlet class for plain display of html content, like
## with a popup window.
##
## Author: Don Tillman

import sys
import traceback
import Nodes
from XHTMLPage import XHTMLPage

class popup(XHTMLPage):

    def __init__(self):
        XHTMLPage.__init__(self)
        self.stylesheets = ['/styles-popup.css']
        self.titleText = 'Riverbed'
        self.mgmt = None
        self.fields = None

    def awake(self, transaction):
        # popup always counts as busy against idle timeout.
        transaction.session().moreBusy()
        XHTMLPage.awake(self, transaction)

    def sleep(self, transaction):
        XHTMLPage.sleep(self, transaction)
        transaction.session().lessBusy()

    def defaultAction(self):
        try:
            self.mgmt = self.session().value('mgmt')
            self.fields = self.request().fields()
            XHTMLPage.defaultAction(self)
        except Exception, e:
            traceback.print_exc(sys.stdout)

    def writeContent(self):
        pageletName = self.fields.get('p')
        # certs handled below
        if 'cert' == pageletName:
            self.cert()
        elif pageletName:
            self.application().includeURL(self.transaction(), '/Templates/' + pageletName)
        else:
            pass


    # Handle certs here in a common way.
    # Place the cert data on the transaction and call the presentCert psp.
    #
    # Expecting fields 'type' and 'name' to find the cert.
    # CMC aware.
    def cert(self):
        certType = self.fields.get('type')
        certName = self.fields.get('name')

        # adjust the path for these cert types
        if 'ca' == certType:
            path = '/rbt/sport/ssl/state/ca/%s' % (certName)
        elif 'peering' == certType:
            path = '/rbt/sport/ssl/state/tunnel/ca/%s' % (certName)
        elif 'mobile' == certType:
            path = '/rbt/sport/ssl/state/tunnel/shm_ca/%s' % (certName)
        elif certType in ('black', 'gray', 'white'):
            path = '/rbt/sport/ssl/state/tunnel/%s_list/%s/cert' % (certType, certName)
        elif 'chain' == certType:
            sid = self.request().fields().get('sid')
            path = '/rbt/sport/ssl/state/server_certs/names/%s/chain_cert/%s' % (sid, certName)
        elif 'appliance' == certType:
            path = '/rbt/sport/ssl/state/tunnel/cert'
        else:
            raise 'unknown cert type ' + certType

        policyName = self.fields.get('policy')
        if policyName:
            # get the cert data for the CMC
            cert = Nodes.action(self.mgmt,
                                '/rbt/sport/ssl/action/iterate_node',
                                ('profile', 'string', policyName),
                                ('node', 'string', path))
            prefixLen = len(path) + 1
            # remove the prefixes
            cert = dict([(k[prefixLen:], v) for k,v in cert.iteritems()])
        else:
            # get the cert data for the SH or other
            cert = self.mgmt.getChildren(path)
        # tweakage for colors
        if certType in ('black', 'gray', 'white'):
            self.transaction().color_info = True
            cert['IP'] = certName

        # display cert
        self.transaction().cert = cert
        # Bug 33438 specified that we needed a way to move certs between "Peering" and "Mobile"
        # bins. Allow peering/mobile base64 PEM certs to be viewable in the popup. User can move
        # certs now by cutting and pasting.
        # TODO May want to extend this functionality to all popup certs in the future.
        if certType in ('peering', 'mobile', 'appliance'):
            self.application().includeURL(self.transaction(), '/Templates/presentCertWithPEM')
        else:
            self.application().includeURL(self.transaction(), '/Templates/presentCert')


