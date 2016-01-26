## Copyright 2006, Riverbed Technology, Inc., All rights reserved.
##
## Exportable Report Servlet class
## Author: Mark Stevans

from BodyPresentation import BodyPresentation

## Respond to browser requests for a pagelet display, possibly running
## an action first.

class exportableReport(
        BodyPresentation,
    ):

    def __init__(self):
        super(exportableReport, self).__init__()

    def defaultAction(self):

        # continue with BodyPresentation.defaultAction()
        super(exportableReport, self).defaultAction()
