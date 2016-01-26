# Copyright 2006 Riverbed Technology, Inc. All rights reserved.
#
# login servlet class

import random
from XHTMLPage import XHTMLPage
import HTTPUtils
import OSUtils

# XHTMLPage subclass to display a login form.
class login(XHTMLPage):
    def __init__(self):
        XHTMLPage.__init__(self)

        self.javascriptFiles = ['/yui3.js',
                                '/rollup.js']

        self.stylesheets = ['/yui3.css',
                            '/rollup.css',
                            '/styles-ie6.css',
                            '/styles-ie7.css',
                            '/rollup-product.css']
        self.css = '''
        #licenseMessage {
            width: 500px;
        }
        '''
        self.titleText = '%s Login' % OSUtils.hostname()

    # overrides the version in page
    def writeBody(self):
        trans = self.transaction()
        request = trans.request()
        response = trans.response()
        # Enclose in a try/finally because we want to make sure that,
        # if there is no authenticated session, the session cookie gets expired
        # even if login.psp gets into trouble in any way.
        try:
            self.writeln('<body class="login">')
            if request.value('p', '') == 'passwordExpired':
                self.application().includeURL(trans, '/Templates/passwordExpired')
            else:
                self.application().includeURL(trans, '/Templates/login')
        finally:
            # Avoid session creation; only retrieve session if already exists.
            session = trans.hasSession() and trans._session or None
            if session and not session.isValid():
                # the user didn't login.
                session.expiring()
            # If the browser sent a cookie but the Application didn't find
            # a Session Object for that cookie value, expire the cookie.
            elif request and response \
            and request.hasCookie(trans.application().sessionName(trans)):
                HTTPUtils.delCookie(response, trans.application().sessionName(trans))
            self.writeln('</body>')
