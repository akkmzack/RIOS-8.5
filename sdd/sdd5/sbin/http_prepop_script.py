#!/usr/bin/env python

"""
Original author: Santhosh Kokala <skokala@riverbed.com>
"""

import sgmllib
import urlparse
import sys
import traceback
import optparse
import os
import urllib2, sgmllib
import fileinput
import subprocess
import signal
import commands
import re
from time import gmtime, strftime

MAIN_URL = ""
CA_DIR = "/var/opt/rbt/decrypted/ssl/ca/"
MANIFEST_PROCESSOR ="/sbin/manifest-processor.py"
PREPOP_DIR = "/var/tmp/http_prepop"
global_logfile = sys.stderr
current_logfile = ""
prepop_list_name = ""
no_check_cert = False
add_params = None

class ErrorCodes:
    """ error code constants """
    Ok                  = 0
    MissingInputFile    = -1
    SystemExit          = -2
    UnknownException    = -3
    InvalidManifest     = 243
    NeedExternalData    = 245
    WgetNetworkFail     = 4
    WgetSSLCheckFail    = 5
    WgetServerError     = 8

    def __setattr__(self, attr, value):
        raise ValueError, 'Attribute %s already has a value and so cannot be written to' % attr
        self.__dict__[attr] = value

class Error(Exception):
    """ Exception raised for errors
    Attributes:
        code -- error code from ErrorCodes, becomes the return value of this process
        msg -- error msg
    """

    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    def __str__(self):
        #return "Exception: " + str(self.code) + ": " + self.msg
        return repr(self.args[0])

    def _get_message(self, msg): return self._msg
    def _set_message(self, msg): self._msg = msg
    message = property(_get_message, _set_message)



class MyParser(sgmllib.SGMLParser):
    "A simple parser class."

    def parse(self, s):
        "Parse the given string 's'."
        self.feed(s)
        self.close()

    def __init__(self, verbose=0):
        "Initialise an object, passing 'verbose' to the superclass."

        sgmllib.SGMLParser.__init__(self, verbose)
        self.hyperlinks = []

    def start_a(self, attributes):
        global MAIN_URL
        "Process a hyperlink and its 'attributes'."
        for name, value in attributes:
            if name == "href":
                absUrl = urlparse.urljoin(MAIN_URL, value)
                self.hyperlinks.append(absUrl)

    def do_img(self, attributes):
        global MAIN_URL
        "Process a img hyperlink and it's attributes"
        for name , value in attributes:
            if name == "src":
                image_url = urlparse.urljoin(MAIN_URL, value)
                self.hyperlinks.append(image_url)

    def do_script(self, attributes):
        global MAIN_URL
        "Process a img hyperlink and it's attributes"
        for name , value in attributes:
            if name == "src":
                script_url = urlparse.urljoin(MAIN_URL, value)
                self.hyperlinks.append(script_url)

    def do_param(self, attributes):
        global MAIN_URL
        if ('name', 'InitParams')  in attributes:
            for name, value in attributes:
                if name == "value":
                    # value = "selectedcaptionstream=textstream_eng,mediaurl=http://iismedia7/Example.isma/Manifest"
                    # Extract the mediaurl part
                    tokens_list = re.split(',', value)
                    for item in tokens_list:
                        item = item.strip()
                        if item.startswith("mediaurl=") == True:
                            value = item
                            break
                    # Remove "mediaurl=" before appending it to url list
                    value = value.replace("mediaurl=", "").strip()
                    silverlight_url = urlparse.urljoin(MAIN_URL, value)
                    self.hyperlinks.append(silverlight_url)

    def do_video(self, attributes):
        global MAIN_URL
        "Process video tag and it's attributes"
        for name , value in attributes:
            if name == "src":
                script_url = urlparse.urljoin(MAIN_URL, value)
                self.hyperlinks.append(script_url)

    def get_hyperlinks(self):
        "Return the list of hyperlinks."

        return self.hyperlinks

# retrieve the url content type
# examples: text/html, text/xml, video/x-flv, etc.
class HeadRequest(urllib2.Request):
    def get_method(self):
        return "HEAD"

def get_url_content_type(url):

    f = ''
    try:
        f = urllib2.urlopen(HeadRequest(url))
    except urllib2.HTTPError, e:
	# Some servers may return HTTP Response 404 for HEAD request. 
        try:
	   f = urllib2.urlopen(url)
	except urllib2.HTTPError, e:
	    write_to_log("Failed to open URL [%s:%s]" % (url, str(e.code))) 
	    return None
	except IOError, e:
	   if e.strerror == 'unknown url type':
	      #<a href="javascript:void(0)"> or <a href="#">
	      #For the above extracted urls, urllib2 urlopen will throw unknown url type exception
	      return None
           write_to_log("Failed to open url [%s:%s]" % (url, e.strerror))
           return None
	except Exception:
	   write_to_log("Failed to open url [%s: Unknown Exception]" % (url))
	   return None
    except IOError, e:
        if e.strerror == 'unknown url type':
           #<a href="javascript:void(0)"> or <a href="#">
           #For the above extracted urls, urllib2 urlopen will throw unknown url type exception
           return None
        write_to_log("Failed to open url [%s:%s]" % (url, e.strerror))
        return None
    except Exception:
	write_to_log("Failed to open url [%s: Unknown Exception]" % (url))
	return None

    return f.info().gettype()

def execute_cmd(cmd):
   
    code = 0
    try:
       code = subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError, e:
       return e.returncode

    return code

def build_wget_cmd_str(url, current_logfile, save_output=None, input_file=None):

   if input_file == None:
      cmd_str = '/usr/bin/wget "%s" --append-output %s --no-verbose --ca-directory %s --tries=2' \
                 % (url, current_logfile, CA_DIR) 
   else:
      cmd_str = "/usr/bin/wget --input-file %s --append-output %s --no-verbose --ca-directory %s --tries=2" \
                 % (input_file, current_logfile, CA_DIR) 

   if not save_output == None:
      cmd_str = cmd_str + " --output-document " + save_output

   if no_check_cert:
      cmd_str = cmd_str + " --no-check-certificate"

   if not add_params == None:
      cmd_str = cmd_str + " " + add_params
    
   return cmd_str 
     
       

def write_to_log(error_str):
    log_file = open(current_logfile, 'a')
    print >> log_file, "%s" %(error_str)
    log_file.close()

def read_external_data(manifest_file_links, base_url):
    external_manifest = []

    # Sample ExternalData output from manifest-processor. Each word is tab separated
    # gear1/prog_index.m3u8   PROGRAM-ID=1, BANDWIDTH=200000
    # gear2/prog_index.m3u8   PROGRAM-ID=1, BANDWIDTH=311111

    with open(manifest_file_links) as fHandle:
        for line in fHandle:
            absURL = urlparse.urljoin(base_url, line.split('\t')[0])
            external_manifest.append(absURL)

    return external_manifest

def clean_up_tmp_files(manifest_file=None, manifest_file_log=None, manifest_file_links=None):
    try:
        if manifest_file != None:
            os.remove(manifest_file)
        if manifest_file_log != None:
            os.remove(manifest_file_log)
        if manifest_file_links != None:
            os.remove(manifest_file_links)
    except Exception, e:
        pass
    
def is_external_data_bootstrap(manifest_file_links):

    with open(manifest_file_links) as fHandle:
        for line in fHandle:
            if line.find("$bootstrapInfo=") != -1:
                return True
    return False

def get_bootstrap_file_manifest(baseURL, manifest_file, manifest_file_links):

    cmd = ""
    # This contains (bootstrap_file_name, bootstrap_id)
    bootstrapFile_info = []

    with open(manifest_file_links) as fHandle:
        for line in fHandle:
            line = line.rstrip('\r\n')
            line = line.split('\t')

            #
            # $bootstrapInfo=bootstrap5078    http://flash.floridakeysmedia.com/../livestream3.bootstrap
            #
            external_data = urlparse.urljoin(baseURL, line[1])
            external_data_id = line[0].split("$bootstrapInfo=")[1]

            file_name = external_data.split('/')
            file_name = file_name[len(file_name) - 1]

            bootstrapFile_info.append(file_name + "," + external_data_id)

            write_to_log("Fetching external bootsrap data [%s]" % external_data)

            cmd = build_wget_cmd_str(external_data, current_logfile)
            code = execute_cmd(cmd)
            if not code == 0: 
                write_to_log("Error fetching external bootstrap file [%s]" % url)
                clean_up_tmp_files(manifest_file, manifest_file_links)
                return
    
    #
    # After fetching external binary data, feed it to manifest-processor using the switch "-x"
    #
    cmd = "/usr/bin/python %s -u -f %s -o %s" % (MANIFEST_PROCESSOR, manifest_file, manifest_file_links)
    for item in bootstrapFile_info:
        cmd = cmd + " -x " + item

    cmd = cmd + " " + baseURL

    # cmd = /usr/bin/python /sbin/manifest-processor.py -u -f manifest_file -o manifest_file_links 
    #       -x bootstrap_file1,bootstrap_id1
    #       -x bootstrap_file2,bootstrap_id2
    #       ..
    #       ..
    #       -x bootstrap_filen,bootstrap_idn
    #       http://urls.com/manifest
    code = execute_cmd(cmd)
    if not code == 0:
        write_to_log("Error parsing manifest file and external bootsrap data")
    else:
        # After parsing external data and manifest file, fetch the video fragments
        # from the URLs that manifest-processor generated (<listname>_manifest_links_<fileindex>)
        cmd = build_wget_cmd_str(None, current_logfile, '/dev/null', manifest_file_links) 
        code = execute_cmd(cmd) 
        if not code == 0:
           write_to_log("Error fetching manifest file urls [%s]" % url)
    
    # Delete the external bootstrap files that we fetched
    # sample.boostrap, sample1.boostrap...etc in /var/tmp/http_prepop/
    clean_up_tmp_files(manifest_file, manifest_file_links)
    for name in bootstrapFile_info:
        name = name.split(',')[0]
        try:
            os.remove(name)
        except Exception, e:
            write_to_log("Error deleting bootstrap file [%s]" % name)
            pass
    return

def generate_fetch_manifest(url, file_index=0):

    try:
        #fetch the manifest url from the server i
        #This will return xml for Silverlight manifest and text for
        #Apple manifest
        manifest_file = PREPOP_DIR + prepop_list_name + '_manifest_' + str(file_index)
        cmd = build_wget_cmd_str(url, current_logfile, manifest_file) 
        code = execute_cmd(cmd) 

        #Error fetching the manifest file. Skipping generating manifest links and fetching them
        if not code == 0: 
           write_to_log("Error fetching manifest file [%s]" % url)
           clean_up_tmp_files(manifest_file)
           return
           
        # Feed the manifest to manifest-processor script (list of urls in txt)
        manifest_file_links = PREPOP_DIR + prepop_list_name + '_manifest_links_' + str(file_index)
        manifest_file_log = PREPOP_DIR + prepop_list_name + '_manifest_log_' + str(file_index)
        cmd = "/usr/bin/python %s -u -f %s -o %s -l %s -a %s" % (MANIFEST_PROCESSOR, manifest_file, manifest_file_links, manifest_file_log, url)

        external_manifest = None
        code = execute_cmd(cmd) 
        # Return error code. If the code is 245 (NeedExternalData) we need some further processing
        if not code == 0:
           if code == ErrorCodes.NeedExternalData:
               if file_index > 0:
                   write_to_log("Recursion depth is greater than the allowed depth for [%s]" % url)
                   clean_up_tmp_files(manifest_file, manifest_file_log, manifest_file_links)
                   return

               write_to_log("Need external data for manifest file [%s]" % url)
               #
               # In adobe flash, sometimes the external data is a binary file (bootstrapInfo)
               # containing the information to parse the manifest file
               #
               if not is_external_data_bootstrap(manifest_file_links):
                   external_manifest = read_external_data(manifest_file_links, url)
               else:
                   clean_up_tmp_files(None, None, manifest_file_log)
                   get_bootstrap_file_manifest(url, manifest_file, manifest_file_links)
                   return

               index = 0
               for ext_manifest_url in external_manifest:
                   index = index + 1
                   code = generate_fetch_manifest(ext_manifest_url, index)

               # At the end clean up and return from here
               clean_up_tmp_files(manifest_file, manifest_file_log, manifest_file_links)
               return
           else:
               write_to_log("Error parsing manifest file [%s]" % url)
               # XXX/TODO Try to add a function to accept variable parameters
               # which will delete the files
               clean_up_tmp_files(manifest_file, manifest_file_log, manifest_file_links)
               return

        # run Wget to fetch the video fragments (list of urls in txt) 
        # the fragments will be stored in the segstore db
        #cmd = "/usr/bin/wget --input-file %s --append-output %s --output-document /dev/null --no-verbose --ca-directory %s --tries=2" \
        #    % (manifest_file_links, current_logfile, CA_DIR)
        cmd = build_wget_cmd_str(None, current_logfile, '/dev/null', manifest_file_links)
        code = execute_cmd(cmd) 
        if not code == 0:
           write_to_log("Error fetching manifest file urls [%s]" % url)

        # At the end, remove the temperary files 
        clean_up_tmp_files(manifest_file, manifest_file_log, manifest_file_links)
    except Exception, e:
       raise 

def parse_recursively(filename):

    global MAIN_URL
    global current_logfile
    #text/plain            adobe
    #application/f4m+xml   adobe
    #text/xml              silverlight
    #others                apple
    manifest_mime_type = ["audio/x-mpegurl",              
                          "text/xml",
                          "application/x-mpegurl",
                          "application/vnd.apple.mpegurl", 
                          "application/f4m+xml",
                          "text/plain"]
    write_to_log("\nStart time: %s\n" % (strftime("%Y-%m-%d %H:%M:%S", gmtime())))

    for url in fileinput.input(filename):

        url = url.rstrip("\r\n")
        MAIN_URL = url

        content_type = get_url_content_type(url)
        if content_type == None:
            #Do nothing
            pass
        elif content_type == "text/html":
            # Get something to work with.
            f = urllib2.urlopen(url)
            s = f.read()

            # Try and process the page.
            # The class should have been defined first, remember.
            myparser = MyParser()
	    try:
                myparser.parse(s)
	    except sgmllib.SGMLParseError, e:
                write_to_log("Unable to parse the input html.Possibly malformed html [%s]" % url)
	        continue

            # Get the hyperlinks.
            links = myparser.get_hyperlinks()

            # For each link, get the object using /usr/bin/wget
            for link in links:
               # For each link check the content type.
               # if the content is a manifest, call generate_fetch_silverlight_manifest()
               # else do a /usr/bin/wget on the link
               content_type = get_url_content_type(link)
               if content_type == None:
                  # Do nothing.
                  pass
               elif content_type.lower() in manifest_mime_type:
                   generate_fetch_manifest(link)
               else:
                  #cmd = '/usr/bin/wget "%s" --output-document /dev/null --append-output %s --no-verbose --tries=2' \
                  #      % (link, current_logfile)
                  cmd = build_wget_cmd_str(link, current_logfile, "/dev/null")
                  code = execute_cmd(cmd)
        elif content_type.lower() in manifest_mime_type:
            generate_fetch_manifest(url)
        else:
            #cmd = '/usr/bin/wget "%s" --output-document /dev/null --append-output %s --no-verbose --tries=2' \
            #      % (url, current_logfile)
            cmd = build_wget_cmd_str(url, current_logfile, "/dev/null")
            code = execute_cmd(cmd)

    write_to_log("\n\nEnd time: %s\n" % (strftime("%Y-%m-%d %H:%M:%S", gmtime())))
    return

def kill_signal_handler(signum, frame):
    write_to_log("Cancelling prepop operation")

    cmd = "/usr/bin/pgrep -P %d" % os.getpid()
    [status, cpids] = commands.getstatusoutput(cmd)

    cpids = cpids.split('\n')

    write_to_log("\n\nEnd time: %s\n" % (strftime("%Y-%m-%d %H:%M:%S", gmtime())))
    for pid in cpids:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except OSError, e:
            if not e.strerror == 'No such process':
                write_to_log("Failed to kill child process [%s]" % e.strerror)
            pass
    try:
        os.kill(os.getpid(), signal.SIGKILL)
    except OSError, e:
        write_to_log("Failed to cancel the prepop operation.")
        pass

def main(args):
    global current_logfile
    global prepop_list_name
    global no_check_cert
    global add_params
    global PREPOP_DIR

    # Registering SIGTERM handler
    signal.signal(signal.SIGTERM, kill_signal_handler)
    
    usage = "usage: %prog [options] input-file-with-urls"
    parser = optparse.OptionParser(usage=usage, description="Utility to fetch contents recursively")
    parser.add_option("-i", "--input-file",
                      action="store", dest="input_file", metavar="input-file",
                      help="Input file containing urls")
    parser.add_option("-a", "--append-output",
                      action="store", dest="output_file", metavar="output-file",
                      help="Append log to specified output file")
    parser.add_option("-o", "--output-document",
                      action="store", dest="output_document", metavar="output-document",
                      help="Save the fecthed documents to this file")
    parser.add_option("-c", "--ca-directory",
                      action="store", dest="ca_directory", metavar="ca_directory",
                      help="CA certificates directory")
    parser.add_option("-V", "--no-verbose",
                      action="store_true", dest="no_verbose", metavar="no_verbose",
                      help="No verbose logs")
    parser.add_option("-t", "--tries",
                      action="store", dest="tries", metavar="tries",
                      help="Number of retries")
    parser.add_option("-l", "--list-name",
                      action="store", dest="list_name", metavar="list_name",
                      help="Prepop list name")
    parser.add_option("-n", "--no-check-certificate",
                      action="store_true", dest="no_check_cert", metavar="no_check_cert",
                      help="Prepop no check certificate")
    parser.add_option("-p", "--additional-params",
                      action="store", dest="add_params", metavar="add_params",
                      help="additional params from user debugging")
    parser.set_defaults(input_file=None)
    parser.set_defaults(output_file=None)
    parser.set_defaults(output_document=None)
    parser.set_defaults(ca_directory=None)
    parser.set_defaults(no_verbose=False)
    parser.set_defaults(tries=None)
    parser.set_defaults(list_name=None)
    parser.set_defaults(no_check_cert=True)
    parser.set_defaults(add_params=None)

    (options, args) = parser.parse_args()

    if options.input_file == None:
        parser.print_help(file=global_logfile)
        return
        #raise Error(ErrorCodes.MissingInputFile,
        #            "No input file specified. Input file with links required")

    if options.output_file != None:
        current_logfile = options.output_file

    if options.list_name != None:
	PREPOP_DIR = PREPOP_DIR + "/" + options.list_name + "/"
        prepop_list_name = options.list_name
    else:
        raise Error(ErrorCodes.UnknownException,
                    "No list name is specified.")
    
    if options.no_check_cert:
        no_check_cert = True    

    if options.add_params != None:
        add_params = options.add_params

    """ Read the file which has all the links that needs to be recursively populated """
    parse_recursively(options.input_file)
    return

if __name__ == "__main__":

    try:
        code = 0
        main(sys.argv)
    except SystemExit, e:
        code = ErrorCodes.SystemExit
        traceback.print_exc(file=global_logfile)
    except Error, e:
        print >> global_logfile, "Exception:", e.msg
        traceback.print_exc(file=global_logfile)
    except Exception, e:
        print >> global_logfile, "Other Exception:", e.msg
        code = ErrorCodes.UnknownException
        traceback.print_exc(file=global_logfile)

    sys.exit(0)
