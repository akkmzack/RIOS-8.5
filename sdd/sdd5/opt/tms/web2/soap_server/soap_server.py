#!/usr/bin/env python

# Filename:  $Source$
# Revision:  $Revision: 102950 $
# Date:      $Date: 2013-02-15 14:55:44 -0800 (Fri, 15 Feb 2013) $
# Author:    $Author: asweigart $
#
# (C) Copyright 2003-2007 Riverbed Technology, Inc.
# All Rights Reserved. Confidential.

'$Id: soap_server.py 102950 2013-02-15 22:55:44Z asweigart $'

# Inspired by (okay copied verbatim with minor modifications) from
# http://www.python.org/dev/peps/pep-0333/

import os, sys
from Logging import *

def run_with_cgi(application):
    environ = os.environ.copy()

    # the current version of soaplib only honors wsgi.url_scheme and wsgi.input
    environ['wsgi.input']        = sys.stdin

    if environ.get('HTTPS','off') in ('on','1'):
        environ['wsgi.url_scheme'] = 'https'
    else:
        environ['wsgi.url_scheme'] = 'http'

    # soaplib gets upset if environ['PATH_INFO'] doesn't exist/is None
    if not environ.get('PATH_INFO'):
        environ['PATH_INFO'] = ''

    headers_set = []
    headers_sent = []

    def write(data):
        if not headers_set:
             raise AssertionError("write() before start_response()")

        elif not headers_sent:
             # Before the first output, send the stored headers
             status, response_headers = headers_sent[:] = headers_set
             sys.stdout.write('Status: %s\r\n' % status)
             for header in response_headers:
                 sys.stdout.write('%s: %s\r\n' % header)
             sys.stdout.write('\r\n')

        sys.stdout.write(data)
        sys.stdout.flush()

    def start_response(status,response_headers,exc_info=None):
        if exc_info:
            try:
                if headers_sent:
                    # Re-raise original exception if headers sent
                    raise exc_info[0], exc_info[1], exc_info[2]
            finally:
                exc_info = None     # avoid dangling circular ref
        elif headers_set:
            raise AssertionError("Headers already set!")

        headers_set[:] = [status,response_headers]
        return write

    result = application(environ, start_response)

    try:
        for data in result:
            if data:    # don't send headers until body appears
                write(data)
        if not headers_sent:
            write('')   # send headers now if body was empty
    finally:
        if hasattr(result,'close'):
            result.close()

# Use the framework service if a product-side service doesn't exist, so that
# we can easily support the SOAP server on all products. The product-side
# service is assumed to derive from the framework service,
# so all framework services should always be available.
try:
    from rbt_service import service
except ImportError:
    try:
        from fwk_service import service
    except ImportError:
        # This should really never happen, not sure it's even worth writing
        # the headers
        sys.stdout.write('Status: 500 Internal Server Error\r\n')
        sys.stdout.write('No SOAP service found.  Please contact support.')
        sys.stdout.flush()
        sys.exit(0)

if __name__ == '__main__':
    log_init('soap_server', '', LCO_none, component_id(LCI_SOAP_SERVER),
             LOG_DEBUG, LOG_LOCAL0, LCT_SYSLOG)
    run_with_cgi(service())
