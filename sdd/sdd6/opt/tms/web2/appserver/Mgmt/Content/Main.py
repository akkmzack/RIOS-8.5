'''
Copyright 2006 Riverbed Technology, Inc. All rights reserved.

Main Steelhead Servlet Base class.
Author: Robin Schaufler

Very much under construction; pardon our mess.
'''
from WebKit.Common import *
from WebKit.HTTPServlet import HTTPServlet
from WebUtils import Funcs
from iph import iph

class Main(HTTPServlet):
    """Catch-all for unfound Content servlets

    Displays the infamous error 404 - page not found.
    Someday, maybe it will do the display internally and do something
    more sophisticated, but this will do for now.
    """

    def _respond(self, transaction):
        """Respond to action.
        """
        req = transaction.request()
        res = transaction.response()
        res.write('<html><body><h1>Error 404 - Servlet ' + req.originalURLPath() + ' Not Found</h1></body></html>')

    def respondToGet(self, transaction):
        """Respond to GET.

        Invoked in response to a GET request method. All methods
        are passed to `_respond`.
        """
        self._respond(transaction)

    def respondToPost(self, transaction):
        """Respond to POST.

        Invoked in response to a POST request method. All methods
        are passed to `_respond`.

        """
        self._respond(transaction)
