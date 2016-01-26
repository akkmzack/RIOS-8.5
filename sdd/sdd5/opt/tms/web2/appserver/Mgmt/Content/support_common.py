## @file support_common.py
#  @brief This file contains support classes that are common to all the pages.
#
#
#  Copyright 2011 Riverbed Technology, Inc. All rights reserved.

import FormUtils
import Reports2
import UserConfig

import os
import pprint
import random
import re
import tempfile
import time

from XMLContent import XMLContent
from JSONContent import JSONContent
from gclclient import NonZeroReturnCodeException

## Miscellaneous AJAX functions that defy categorization.
class xml_Common(XMLContent):

    dispatchList = [
        'searchText',
    ]

    dogKickerList = [
        'searchText',
    ]

    ## @brief This function is called when the user enters a query in the search
    #         box on the UI page. It returns an xml file containing the search
    #         results.
    def searchText(self):

        # these may not exist if search isn't supported for this
        # product so we only try to import if this function gets
        # called
        import xapian
        from Searcher import Searcher

        # A constant for the number of results that should be returned for
        # every query.
        MAX_NO_OF_RESULTS = 10

        # A constant for the position of the file path within the document
        # object.
        XAPIAN_FILE_NAME_SLOT = 1

        # Add the wildcard implicitly to the query string. This allows the user
        # to enter only part of the query in order to get search results.
        queryString = self.fields['query'] + '*'

        # Get the reference to the gui class.
        guiReference = self.session().value('guiReference')

        # Searcher object for performing the actual search.
        searcher = Searcher('/opt/tms/web2/appserver/search_index',
                                xapian.QueryParser.STEM_SOME)

        # Configuration flags for the query parser.
        # Note: Synonyms are OR'd with the query entered. Eg: if foo is a
        # synonym for bar, then the query bar wil expand to ==> bar or baz.
        searchFlags = xapian.QueryParser.FLAG_PHRASE \
                        | xapian.QueryParser.FLAG_WILDCARD \
                        | xapian.QueryParser.FLAG_AUTO_MULTIWORD_SYNONYMS \
                        | xapian.QueryParser.FLAG_SPELLING_CORRECTION \
                        | xapian.QueryParser.FLAG_AUTO_SYNONYMS \
                        | xapian.QueryParser.FLAG_BOOLEAN_ANY_CASE

        # Top level results node.
        results = self.doc.createElement('results');

        # Counter for the number of results.
        resultCount = 0

        # Matches obtained on doing a search.
        matches = searcher.search(searchFlags, queryString)

        ## @brief Creates a structure within the xml file of the form:
        #
        #  <result title="TITLE" link="LINK" />
        #
        #  @param titleText This is the entry that will be displayed for this result
        #                   within the autocomplete list. It will be the same as the
        #                   title for every pagelet.
        #  @param linkText This is the link to the result. This is the text that
        #                  occurs after p= for the gui servlet.
        def appendResult(titleText, linkText):
            result = self.doc.createElement('result')
            result.setAttribute('title', titleText)
            result.setAttribute('link', linkText)
            results.appendChild(result)

        # Process the results
        for match in matches:

            # Get the name of the file without its extension.
            fileName = match.document.get_value(XAPIAN_FILE_NAME_SLOT)

            # Get the title for the result.
            pageletTitle = guiReference.findBestFitPagelet(fileName, {}).getPageletTitle()

            # If no appropriate pagelet title is found then the indexed page
            # isn't present in the navbar so we can ignore this result.
            if pageletTitle == '':
                continue

            # Increment the number of results that have been found. If that
            # exceeds the maximum desired then stop adding additional elements
            # to the xml document.
            resultCount += 1
            if resultCount > MAX_NO_OF_RESULTS:
                break

            # Create an xml structure representing a result within the xml
            # document.
            appendResult(pageletTitle, fileName)

        # Add a count of the number of results available.
        results.setAttribute('resultCount', str(resultCount))

        # Add the results to the document.
        self.doc.documentElement.appendChild(results)

        # Write the xml document in the response.
        self.writeXmlDoc()


class json_Common(JSONContent):

    alwaysKeepAliveList = [
        'sendFeedback',
        'setUserConfigNodes',
    ]

    # these are used for testing:
    alwaysKeepAliveList += [
        'rpcTest',
        'dynamicListTest',
        'colorsDemo'
    ]

    neverKeepAliveList = []
    autoRefreshList = []

    ## Send feedback from the web UI.
    #
    # This expects the following form fields:
    #
    # - @c address:  The e-mail address of the sender.
    # - @c url:  The URL that the feedback was sent from.
    # - @c subject
    # - @c comment
    def sendFeedback(self):

        def internal(address, url, subject, comment):
            self.mgmt.action(
                '/email/actions/send',
                ('reply_to', 'string', address),
                ('subject', 'string', '[web feedback] ' + subject),
                ('body', 'string', 'URL: %s\n\n%s' % (url, comment)),
                ('recipients', 'string', 'hkao@riverbed.com'))

        self.rpcWrapper(internal)

    ## Set the value of userconfig nodes.
    #
    # This expects a variable-number of fields where each key is a
    # path and the corresponding value is the node value to set.
    def setUserConfigNodes(self):
        def internal(**kwargs):
            UserConfig.set(self.session(), *kwargs.items())
        self.rpcWrapper(internal)

    ## For RPC functional testing.
    #
    # This returns a JSON object via JSONContent.rpcWrapper() for the
    # purpose of testing the RPC mechanism.  There is one required
    # field, @c action, that determines what it returns:
    #
    # - @c echo - @c success is @c true and @c response is an object
    #   containing all of the fields that were sent to the server.
    # - @c timeout - Sleep for 2 seconds.  @c success is @c true and
    #   @c response is an object containing all of the fields that
    #   were sent to the server.
    # - @c error - @c success is @c false and @c errorMsg is
    #   "foobarbaz".
    # - @c echo - @c success is @c true and @c response the first 100
    #   characters from the file that was passed in the @c file field.
    #
    # @sa JSONContent.rpcWrapper() for the format of the JSON response.
    def rpcTest(self):

        def internal(**kw):

            if kw['action'] == 'echo':
                return kw

            elif kw['action'] == 'timeout':
                time.sleep(2)
                return kw

            elif kw['action'] == 'error':
                raise NonZeroReturnCodeException, 'foobarbaz'

            elif kw['action'] == 'file':
                return kw['file'].value[:100]

        self.rpcWrapper(internal)

    ## For testing the dynamic list.
    #
    # This looks through the form fields and calls
    # FormUtils.getDynamicListFields() to retrieve the data in the
    # dynamic list called @c testList.  It then returns a
    # prettyprinted version of the results via
    # JSONContent.rpcWrapper().
    def dynamicListTest(self):

        def internal(**kw):
            return '\n'.join([pprint.pformat(item)
                for item in FormUtils.getDynamicListFields('testList', kw)])

        self.rpcWrapper(internal)

    # Colors demo for Reports 2.0.
    def colorsDemo(self):
        def internal(lb):
            result = Reports2.fetchData(
                mgmt=self.mgmt,
                action='/stats/actions/generate_report/paging',
                subClass=None,
                numSets=1,
                lb=int(lb)
            )

            allSeries = []

            valueOffset = 90
            for color in ('Aqua', 'Blue', 'Brown', 'Medium Gray', 'Green', 'Orange', 'Pink', 'Purple', 'Red', 'Yellow'):
                allSeries.append({'name': color,
                                  'data': [(valueOffset + random.random() * 10, x[1], x[2]) for x in result[0]]})
                valueOffset -= 10

            return Reports2.adjustTimeSeriesStats(allSeries)

        self.rpcWrapper(internal)
