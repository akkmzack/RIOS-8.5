## Copyright 2012, Riverbed Technoloy, Inc., All rights reserved.
##
## support_papi.psp
##
## support for programmatic API operations

import Nodes
import FormUtils
from PagePresentation import PagePresentation
from XMLContent import XMLContent

class gui_PAPI(PagePresentation):

    actionList = ['setupRESTAccessCodes']

    def setupRESTAccessCodes(self):
        user = self.session().value('localId')
        fields = self.request().fields()
        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)

        if 'addAccessCode' in fields:
            desc = fields['accessCodeAdd_desc']

            if 'true' == fields.get('addAccessCode_generate'):
                self.sendAction(pathPrefix + '/papi/action/generate_access_code',
                                ('user', 'string', user),
                                ('desc', 'string', desc))
            else:
                data = fields['addAccessCode_data']

                self.sendAction(pathPrefix + '/papi/action/import_access_code',
                                ('data', 'string', data),
                                ('desc', 'string', desc))

        elif 'editAccessCode' in fields:
            desc = fields['accessCodeEdit_desc']
            jti = fields['accessCodeEdit_jti']

            self.setNodes(('%s/papi/config/code/%s/desc' % (pathPrefix, jti), 'string', desc))

        elif 'removeAccessCode' in fields:
            FormUtils.deleteNodesFromConfigForm(self.mgmt,
                                                self.cmcPolicyRetarget('/papi/config/code'),
                                                'accesscode_',
                                                fields)

class xml_PAPI(XMLContent):

    dispatchList = ['restAccessCodes']

    def restAccessCodes(self):
        mgmt = self.mgmt

        result = self.doc.createElement('restAccessCodes')

        path = self.cmcPolicyRetarget('/papi/config/code')
        jtis = Nodes.getMgmtSetEntries(self.mgmt, path)

        for jti, attribs in jtis.iteritems():
            entryEl = self.doc.createElement('accessCode')
            entryEl.setAttribute('jti', jti)
            entryEl.setAttribute('owner', attribs['user'])
            entryEl.setAttribute('desc', attribs['desc'])
            entryEl.setAttribute('code', attribs['data'])
            result.appendChild(entryEl)

        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()
