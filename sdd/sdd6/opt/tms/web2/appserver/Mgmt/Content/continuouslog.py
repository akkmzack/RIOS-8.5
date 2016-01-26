'''
Copyright 2006 Riverbed Technology, Inc. All rights reserved.

continuouslog Steelhead Servlet class.

Display continuous logging in a popup window.
We seek to the end of the log file and then stream so that
we don't disrupt sport by rattling the disk with a lot of seeks.

We can't stream into an XMLHttpRequest because Microsoft explicitly
prohibits it.

If we want to AJAX continuous logging, we should do the following:
1) When starting a continuous log, start a thread in webasd to continuously
   read from the end of the log, and keep a pointer for how much
   has been displayed.
2) Associate the thread with a session, so that when a new continuous log
   request comes in, or when the session expires, the old thread gets
   cleaned up.
3) Use XMLHttpRequest to query the buffer-so-far from the continuous log
   thread.

Author: Robin Schaufler
'''
import time
import select
import os
import stat
import cgi
import OSUtils
import Logging
import Nodes
from WebKit.HTTPContent import HTTPContent
from WebKit.Application import ConnectionAbortedError
import WebKit.AppServer as AppServerModule

class continuouslog(HTTPContent):
    # XXX/robin we want ContentType = 'text/plain'
    #           but then the browser buffers input before display!!!
    #           MIND YOU, this problem caused untold weeping and gnashing
    #           of teeth to figure out!!!
    # XXX/robin If SHs are optimizing HTTP traffic, they may buffer the
    #           continuous log. If this happens, switch to https.
    # ContentType = 'text/html'
    ContentType = 'text/html'

    # Mapping of the 'logtype' parameter to the filename prefix.
    LOGTYPE_PREFIX = {'host': 'host_',
                      'sys': '',
                      'user': 'user_'}

    # continuouslog always counts as busy against idle timeout.
    def awake(self, transaction):
        transaction.session().moreBusy()
        HTTPContent.awake(self, transaction)

    def sleep(self, transaction):
        HTTPContent.sleep(self, transaction)
        transaction.session().lessBusy()

    def _respond(self, transaction):

        mgmt = self.session().value('mgmt')
        assert 'monitor' != mgmt.remoteUser.lower(), \
               'Monitor may not view or download logs.'
        # check permissions
        assert Nodes.permission(mgmt,
            '/logging/syslog/action/file/\/var\/log\/messages') != 'deny', \
            ('%s may not view or download logs.' % mgmt.remoteUser)

        request = transaction.request()
        response = transaction.response()
        fields = request.fields()
        logtype = fields.get('logtype', 'user')
        mime = fields.get('mime', '') or self.ContentType
        logfilename = '/var/log/%smessages' % self.LOGTYPE_PREFIX[logtype]
        try:
            bytesize = os.stat(logfilename)[stat.ST_SIZE]
            seekto = max(0, bytesize - 500)
            response.setHeader('Content-type', mime)
            response.commit()
            if mime.endswith('html'):
                response.write('<html>\n')
                response.write('<head>\n')
                response.write('<title>Continuous Log</title>\n')
                response.write('</head>\n')
                response.write('<body>\n')
                response.write('<pre>\n')
            response.flush(True)

            logfile = file(logfilename)
            logfile.seek(seekto) # Seek to almost EOF
            # Print out the last few lines of the log,
            # stripping out any partial line artifact of our seek()
            txt = cgi.escape(logfile.read() or '')
            txt = txt[txt.find('\n') + 1:]
            writingDots = 0
            # Write to log after seek so we should read it in the first
            # iteration of reading logfile.
            while hasattr(request, '_transaction') and \
                  2 < AppServerModule.globalAppServer._running:
                if txt:
                    if writingDots:
                        response.write('\n')
                        writingDots = 0
                    response.write(txt)
                else:
                    writingDots += 1
                    if 0 == writingDots % 80:
                        response.write('\n')
                    response.write('. ')
                    time.sleep(3)
                response.flush() # I don't trust auto flush
                txt = cgi.escape(logfile.read() or '')
        except ConnectionAbortedError:
            pass
        except:
            OSUtils.logException()
