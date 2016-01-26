## Copyright 2007 Riverbed Technology, Inc. All rights reserved.
##
## gfx.py
## Author: Don Tillman
##
## Provide an XML representation of data in the node tree, tweaked
## for table display.

import sys
import traceback
import xml.dom

import Capability
import FormUtils
import Nodes
import OSUtils
import Logging
from GfxContent import GfxContent
from WebKit.Application import EndResponse
try:
    from support_report_gfx import gfx_Report
except Exception, info:
    OSUtils.logException()
    class gfx_Report: pass


# This servlet replies to requests of the form:
#    /sh/gfx?p=NAME
#
# And the response is XML.
#
# ("p" originally meant "page", but now it's a general purpose selector thing)
#
# XXX/robin How do we catch exceptions in instantiation of base classes?
class gfx(gfx_Report,
          GfxContent):

    # Each mixin class contributes their dispatches.
    dispatchList = []

    # Catch errors in base class initialization.
    def __init__(self):
        try:
            super(gfx, self).__init__()
        except Exception, info:
            OSUtils.logException()
            return

    # Respond to requests
    def defaultActionContent(self):
        pField = self.fields.get('p')
        if pField in self.dispatchList:
            getattr(self, pField)()
        else:
            OSUtils.log(Logging.LOG_NOTICE, 'Request error in gfx: %s' % pField)
            raise KeyError, 'Request error in gfx: %s' % pField

# Compile up the mixin class dispatches.
GfxContent.compileClassList(gfx, 'dispatchList')
