'''
Copyright 2009 Riverbed Technology, Inc. All rights reserved.

logout Steelhead Servlet class.
Author: Robin Schaufler
'''
import urllib
# from WebKit.Common import *
from WebKit.HTTPContent import HTTPContent
# from WebUtils import Funcs
from WebKit.Application import EndResponse
import HTTPUtils

class logout(HTTPContent):
    """Log out of the current session.

    Removes capabilities and localId from the session,
    so that next trip through the authentication servlet
    serves up the login form.
    """

    def _respond(self, transaction):
        app = transaction.application()
        request = transaction.request()

        if transaction.hasSession():
            transaction.session().expiring() # invalidates as well as expires
        else:
            # If the transaction doesn't already have a WebKit Session,
            # there is no Session clean-up to do, but there might still be
            # an obsolete session cookie to expire.
            if request.hasCookie(app.sessionName(transaction)):
                HTTPUtils.delCookie(transaction.response(), app.sessionName(transaction))

        # Send browser a response header forcing it to send a new request
        # for /mgmt/login?reason=1&dest=<urlencode(/mgmt/gui?p=home)>
        # with trivial token html content.
        querystring = {'dest': '/mgmt/gui?p=home',
                       'reason': 'logout'}
        querystring.update(transaction.request().fields())
        loginURL = '/mgmt/login?' + urllib.urlencode(querystring)
        res = transaction.response()
        res.write('<html><body><h1>redirect to <a href="' + loginURL
        + '">' + loginURL + '</a></h1></body></html>')
        res.sendRedirect(loginURL)

        raise EndResponse
