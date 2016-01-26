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
import cgi

import FormUtils
import HTTPUtils
import Nodes
import OSUtils
import Logging
import UserConfig
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
            perField = self.fields.get('per', '')
            lbField = self.fields.get('lb', '')
            ubField = self.fields.get('ub', '')
            tField = self.fields.get('viaemail', 'false')
            eField = self.fields.get('email', '')

            # Update the user config nodes.
            userconfigSetParams = [
                ('web/reports/export/report', rField),
                ('web/reports/export/email', tField)
            ]

            if tField == 'true':
                userconfigSetParams.append(('web/reports/export/email_address', eField))

            UserConfig.set(self.session(), *userconfigSetParams)

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

            # Determine the proper lb and ub values based on the user's
            # selections for the three time interval widgets.
            now = time.time()
            datetimeFormat = '%Y/%m/%d %H:%M:%S'
            if perField == 'min5':
                lb = time.strftime(datetimeFormat, time.localtime(now - (5 * 60)))
                ub = time.strftime(datetimeFormat, time.localtime(now))
            elif perField == 'hour':
                lb = time.strftime(datetimeFormat, time.localtime(now - (60 * 60)))
                ub = time.strftime(datetimeFormat, time.localtime(now))
            elif perField == 'day':
                lb = time.strftime(datetimeFormat, time.localtime(now - (24 * 60 * 60)))
                ub = time.strftime(datetimeFormat, time.localtime(now))
            elif perField == 'week':
                lb = time.strftime(datetimeFormat, time.localtime(now - (7 * 24 * 60 * 60)))
                ub = time.strftime(datetimeFormat, time.localtime(now))
            elif perField == 'month':
                lb = time.strftime(datetimeFormat, time.localtime(now - (30 * 24 * 60 * 60)))
                ub = time.strftime(datetimeFormat, time.localtime(now))
            elif perField == 'cust':
                lb = lbField
                ub = ubField
            else:
                lb = ''
                ub = ''

            if lb != '':
                params += [('time_lb', 'datetime_sec', lb)]
            if ub != '':
                params += [('time_ub', 'datetime_sec', ub)]

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

                # Put together a nice filename for the user in this format:
                # hostname-date-time-report.csv
                browserFilename = '%s-%s-%s.csv' % \
                                  (OSUtils.hostname(), time.strftime('%Y%m%d-%H%M%S'), rField)

                response.setHeader('Content-Type', 'application/octet-stream')
                response.setHeader('Content-Disposition', 'attachment; filename=%s' % browserFilename)
                response.setHeader('Content-Length', os.stat(filename).st_size)
                self.sendExportFile(filename)
                os.unlink(filename)
            else:
                # This servlet doesn't inherit from PagePresentation, so we
                # can't use the handy setActionMessage() function to set an
                # action message.  Alas, we'll have to set the session value
                # and URL parameter manually.
                msg = cgi.escape('Report data emailed to %s.' % eField)
                msgid = str(self.request().requestID())
                self.session().setValue('msg_' + msgid, ([], [msg]))
                response.sendRedirect('/mgmt/gui?p=reportExports&_msg=%s' % msgid)

        except Exception, info:
            OSUtils.logException()
            try:
                response.setStatus(500, str(info))
            except Exception, leveltwo:
                OSUtils.logException()
            try:
                response.setHeader('Content-Type','text/html')
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
