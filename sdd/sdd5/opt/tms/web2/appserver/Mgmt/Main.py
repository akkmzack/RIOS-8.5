'''
Copyright 2006-2009 Riverbed Technology, Inc. All rights reserved.

Main Steelhead Servlet.
Author: Robin Schaufler
'''

from AuthenticationServlet import AuthenticationServlet

# Inherit everything from AuthenticationServlet
class Main(AuthenticationServlet):
    def productContent(self):
        return {
            'ssldata': AuthenticationServlet.login,
            'reportExporter': AuthenticationServlet.login,
            'reportConnections': AuthenticationServlet.forbidden,
        }
