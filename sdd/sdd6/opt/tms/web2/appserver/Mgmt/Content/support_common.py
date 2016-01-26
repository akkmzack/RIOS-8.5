## @file support_common.py
#  @brief This file contains support classes that are common to all the pages.
#
#
#  Copyright 2011 Riverbed Technology, Inc. All rights reserved.

import os
import re
import tempfile
import UserConfig

from XMLContent import XMLContent

## Miscellaneous AJAX functions that defy categorization.
class xml_Common(XMLContent):

    dispatchList = [
        'searchText',
        'sendFeedback',
        'setUserConfigNode',
    ]

    dogKickerList = [
        'searchText',
        'sendFeedback',
        'setUserConfigNode',
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

            # Note:  It would be better to call a backend action to
            # send the e-mail but the existing one isn't flexible
            # enough.  See bug 88171.

            # make sure we don't pass dangerous characters to the
            # shell; replace everything but alphanumerics and spaces
            safeSubject = re.sub(r'[^\w ]', '_', subject)

            # write the body of the e-mail to a file
            file = tempfile.NamedTemporaryFile()
            file.write('From: %s\nURL: %s\n\n%s' % (address, url, comment))
            file.flush()

            # send the message
            status = os.system('/sbin/makemail.sh -s "[web feedback] %s" '
                '-t hkao@riverbed.com -i %s' % (safeSubject, file.name))

            # we have no idea why this failed but at least tell the
            # user that it didn't work
            assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0, \
                'Failed to send e-mail.'

        self.rpcWrapper(internal)
    
    ## Set the value of a userconfig node.
    #
    # This expects the following fields:
    #
    # - @c path:  The shorthand userconfig node path.
    # - @c value:  The userconfig node value.
    def setUserConfigNode(self):
        def internal(path, value):
            UserConfig.set(self.session(), path, value)
        self.rpcWrapper(internal)
