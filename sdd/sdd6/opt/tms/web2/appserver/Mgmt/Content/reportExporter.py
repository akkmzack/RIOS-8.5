## Copyright 2007-2009 Riverbed Technology, Inc. All rights reserved.
##
## report_export.py
## Author: John Cho
##
## Download reports.

import sys
import os
import time
import traceback
import xml.dom

import FormUtils
import HTTPUtils
import Nodes
import OSUtils
import Logging
from WebKit.Application import EndResponse
from WebKit.HTTPContent import HTTPContent

class reportExporter(HTTPContent):

    # reportExporter always counts as busy against idle timeout.
    def awake(self, transaction):
        transaction.session().moreBusy()
        HTTPContent.awake(self, transaction)

    def sleep(self, transaction):
        HTTPContent.sleep(self, transaction)
        transaction.session().lessBusy()

    def sendExportFile(self, filename):
        try:
            exfile = file(filename, 'rb')
        except IOError, info:
            OSUtils.logException()
            return
        bufsize = 4096
        returned = bufsize
        try:
            while bufsize == returned:
                bytes = exfile.read(bufsize)
                returned = len(bytes)
                if returned:
                    self.write(bytes)
        except Exception, info:
            OSUtils.logException()

    def defaultAction(self):
        try:
            transaction = self.transaction()
            response = transaction.response()
        except Exception, info:
            OSUtils.logException()
            return
        try:
            self.mgmt = self.session().value('mgmt')
            self.fields = self.request().fields()

            rField = self.fields.get('r', '')
            fField = self.fields.get('format', 'csv')
            lbField = self.fields.get('time_lb', '')
            ubField = self.fields.get('time_ub', '')
            tField = self.fields.get('viaemail', 'false')
            eField = self.fields.get('email', '')

            if tField == 'false':
                filename = '/var/opt/tms/stats/reports/webreport.%s' % fField
                recv_type = 'file'
                recv_id = 'webreport'
            else:
                recv_type = 'email'
                recv_id = eField

            params = [('id', 'string', rField),
                      ('format', 'string', fField),
                      ('recipient_type', 'string', recv_type),
                      ('recipient_id', 'string', recv_id)]
            if lbField != '':
                params += [('time_lb', 'datetime_sec', lbField)]
            if ubField != '':
                params += [('time_ub', 'datetime_sec', ubField)]

            self.mgmt.action('/stats/actions/export', *params)

            # hack ported from the old web ui that waits up to 30 seconds for the file to
            # finish being exported.
            if tField == 'false':
                i = 0
                while i < 30:
                    if os.path.exists(filename) == True:
                        break
                    time.sleep(1)
                    i += 1

                response.setHeader('Content-type','application/octet-stream')
                response.setHeader('Content-Disposition',
                    'attachment; filename=stats.csv')
                self.sendExportFile(filename)
                os.unlink(filename)
            else:
                response.sendRedirect('/mgmt/gui?p=reportExports')

        except Exception, info:
            OSUtils.logException()
            try:
                response.setStatus(500, str(info))
            except Exception, leveltwo:
                OSUtils.logException()
            try:
                response.setHeader('Content-type','text/html')
            except Exception, leveltwo:
                OSUtils.logException()
            try:
                # This HTML should only be seen in development mode.
                # Nonetheless, we must supply some HTML.
                response.write(HTTPUtils.errorResponseHtml(
                    transaction, errorCode=500, reason=info))
            except Exception, leveltwo:
                OSUtils.logException()
        raise EndResponse
