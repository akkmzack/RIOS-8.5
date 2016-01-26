#!/usr/bin/python

""" script to work with Silverlight smooth streaming manifests, and to 
    optionally pull the video fragments as well
    """
    
import urllib
import sys
import os
import gc
import traceback
import optparse
from elementtree.ElementTree import parse
from elementtree.ElementTree import ElementTree

class ErrorCodes:
    """ error code constants """
    Ok                  =  0
    MissingUrl          = -1
    MissingBaseUrl      = -2
    MissingBaseUrlName  = -3
    MissingRootTag      = -4
    UnknownException    = -5
    KeyboardInterrupt   = -6
    SystemExit          = -7
    ParamError          = -8   # generic cmd-line param error
    
    def __setattr__(self, attr, value):
        raise ValueError, 'Attribute %s already has a value and so cannot be written to' % attr
        self.__dict__[attr] = value
        
class Error(Exception):
    """Exception raised for errors

    Attributes:
        code -- error code from ErrorCodes, becomes the return value of this process
        msg -- error msg
    """

    def __init__(self, code, msg):
        self.code = code
        self.msg = msg
        
    def __str__ (self):
        return "Exception: " + str(self.code) + ": " + self.msg

global logfile

def main(args):
    global logfile
    logfile = sys.stderr

    usage = "usage: %prog [options] manifest-url"
    parser = optparse.OptionParser(usage=usage, description="stream switching video utility")
    parser.add_option("-u", "--print-urls",
                action="store_true", dest="print_urls",
                help="print fragment urls to stdout")
    parser.add_option("-m", "--print-manifest",
                action="store_true", dest="print_manifest",
                help="print parsed manifest info to stdout")
    parser.add_option("-v", "--verbose",
                action="store_true", dest="verbose",
                help="verbose mode")
    parser.add_option("-l", "--log-file",
                action="store", dest="log_file", metavar="Log-file",
                help="filename of file to write errors to (defaults to stderr)")
    parser.add_option("-a", "--log-append",
                action="store_true", dest="log_append",
                help="append to logfile (-l) instead of overwriting (default == false). Requires -l")
    parser.add_option("-o", "--output-file",
                action="store", dest="output_file", metavar="Output-file",
                help="filename of file to output to (defaults to stdout)")
    parser.add_option("-f", "--manifest-file",
                action="store", dest="manifest_file", metavar="Manifest-file",
                help="filename of manifest file (use this to not fetch it from the manifest-url)")
    parser.add_option("-w", "--write_files", action="store", type="choice", 
                choices=["none", "pull", "write"],
                dest="write_files", metavar="Write-mode",
                help="what to do with video fragments. Values are: "
                    "none (don't retrieve video fragments (default)), "
                    "pull (pull fragments from server but don't save them), or "
                    "write (save fragments to disk)")
    parser.set_defaults(print_urls=False)
    parser.set_defaults(print_manifest=False)
    parser.set_defaults(verbose=False)
    parser.set_defaults(write_files="none")
    parser.set_defaults(manifest_file=None)
    parser.set_defaults(output_file=None)
    parser.set_defaults(log_file=None)
    parser.set_defaults(log_append=False)
    
    logfile = sys.stderr
    
    (options, args) = parser.parse_args()
    if len(args) == 0:
        parser.print_help(file=logfile)
        raise Error(ErrorCodes.MissingUrl, 
                    "no url specified.  Url to manifest file required")
    if options.log_append and options.log_file == None:
        parser.print_help(file=logfile)
        raise Error(ErrorCodes.ParamError, 
                    "-a only has effect if -l specified")    
    
    ######## done with arg handling, now do some work #######
    
    if options.log_file != None:
        try:
            if options.log_append:
                mode = 'a'
            else:
                mode = 'w'
            logfile = open(options.log_file, mode)
        except Exception, e:
            logfile = sys.stderr
            raise

    outputfile = sys.stdout
    if options.output_file != None:
        outputfile = open(options.output_file, 'w')
        
    url = None
    if options.manifest_file == None:
        url = args[0]
    else:
        url = "file:" + options.manifest_file
    streams = parse_manifest(url) # may throw exceptions
    if options.print_manifest:
        print_manifest(streams, options.verbose, outputfile)
    urls = generate_fragment_urls(streams)
    
    # expect incoming url to look like 
    #  http://www.site.net/x/y/file.ism/Manifest
    # and the video urls look like 
    #  http://www.site.net/x/y/file.ism/QualityLevels(160000)/Fragments(audio=100310204)
    
    base_url = ""
    idx = args[0].rfind('/')
    if idx != -1:
        base_url = args[0][0:idx] # http://www.site.net/x/y/file.ism
    
    if options.print_urls:
        for s in urls:
            print >> outputfile, base_url + '/' + s
        if outputfile != sys.stdout:
            outputfile.close()
        outputfile = None

    if options.write_files == "none":
        return

    ####### get the video fragments from the server ##############
        
    if base_url == None or base_url == "":
        raise Error(ErrorCodes.MissingBaseUrl, "couldn't find base url")
    idx = base_url.rfind('/')
    if idx == -1:
        raise Error(ErrorCodes.MissingBaseUrlName, 
               "couldn't find base url basename")

    base_name = '.'+ base_url[idx:] + '/'  # ./BigBuckBunny_720p.ism/
    if options.write_files == "write":
        makedirs(base_name, streams, options.verbose)

    num_fetched = fetch_urls(base_name, base_url, urls, options.write_files,
                             options.verbose)  # may throw exceptions
    print >> logfile, "fetched", num_fetched, "fragments"
    
def print_manifest(streams, verbose, file):
    """ print to stdout parsed data from the manifest
    
        streams - data produced by parse_manifest()
        verbose - if true also prints timecode data
    """
    
    for stream in streams:
        print >> file, "stream type=", stream['Type'], "url=", stream['Url'], \
                "num qualities=", len(stream['Qualities']), "num durations=", \
                len(stream['Durations'])
        if stream['ManifestOutput'] == "true":
            print >> file, "    ManifestOutput!"
        for quality in stream['Qualities']:
            print >> file, "    Bitrate=", quality['Bitrate']
            for c in quality['Cattrs']:
                print >> file, "        Cattr=", c
        if verbose:
            current_start = 0
            for duration in stream['Durations']:
                start = duration['start']
                if start != None:
                    current_start = int(start) 
                dur = int(duration['Duration'])
                print >> file, "    start=", current_start
                current_start += dur
    
# data looks like
#    <SmoothStreamingMedia
#        <StreamIndex
#            <QualityLevel
#                <CustomAttributes (optional)
#                    <Attribute
#            <c
def parse_manifest(url):
    """ given a url (http: or file:) get the manifest file and parse it """
    
    global logfile

    file = urllib.urlopen(url)
    #file.get_code() not added until python 2.6
    rss = parse(file).getroot()
    #code = urllib.getcode()
    #print "code=", code
    if rss.tag != 'SmoothStreamingMedia':
        raise Error(ErrorCodes.MissingRootTag, "root tag is " + rss.tag + 
                    " expecting SmoothStreamingMedia")
    major = rss.get('MajorVersion')
    minor = rss.get('MinorVersion')
    
    if int(major) != 2 or int(minor) != 1:
        print >> logfile, "warning: unexpected manifest version: major=", major, "minor=", minor
    streams = []
    elements = rss.findall('StreamIndex')
    for element in elements:
        qualities = []
        durations = []
        manifest_output = element.get('ManifestOutput')
        if manifest_output != None:
            # the spec says this value is case-insensitive
            manifest_output = manifest_output.lower()
        data = { 
            'Type': element.get('Type'),
            'Url': element.get('Url'),
            'ManifestOutput' : manifest_output,
            'Qualities': qualities,
            'Durations': durations
        }
        for quality in element.findall('QualityLevel'):
            cattrs = []
            for custom in quality.findall('CustomAttributes'):
                for attr in custom.findall('Attribute'):
                    cattr = (attr.get("Name"), attr.get("Value"))
                    cattrs.append(cattr)
            qdata = {
                'Bitrate': quality.get('Bitrate'),
                'Cattrs': cattrs
            }
            qualities.append(qdata)
        
        #note: duration attr might not be there for non-audio/video 
        #    streams (i.e. text streams, name=GSIS)

        for duration in element.findall('c'):
            dur_value = '0'
            dur_attr = duration.get('d')
            if dur_attr != None:
                dur_value = dur_attr
            durations.append({
                'Duration': dur_value,
                'start': duration.get('t')
            })
        streams.append(data)
    return streams
        
def subst_pattern(pattern, bitrate, start, custom):
    """ take the url pattern from the manifest and substitute bitrate, start
        time and custom attributes into it
    """    
    
    # we could almost use str.format(), but the url pattern has param names
    # that contain spaces ("start time"), and we'd open up a potential problem
    # if the string contained characters that format() might interpret as
    # metacharacters
    
    # the spec allows Bitrate and bitrate, start time and start_time
    s = pattern.replace("{bitrate}", bitrate, 1)
    s = s.replace("{Bitrate}", bitrate, 1)
    s = s.replace("{start time}", str(start), 1)
    s = s.replace("{start_time}", str(start), 1)
    for c in custom:
        attr_str = "%s=%s" % c
        s = s.replace("{CustomAttributes}", attr_str, 1)
    return s
    
def generate_fragment_urls(streams):
    """ given data generated by parse_manifest(), generate a list of urls of
        video fragments 
    """
    
    urls = []
    for stream in streams:
        if stream['ManifestOutput'] == "true":
            continue # all data in the manifest file; not fetched
        for quality in stream['Qualities']:
            current_duration = 0
            for duration in stream['Durations']:
                start = duration['start']
                if start != None:
                    current_duration = int(start) 
                                
                dur = int(duration['Duration'])
                url = subst_pattern(stream['Url'], quality['Bitrate'], 
                                    current_duration, quality['Cattrs'])
                #url = 'QualityLevels(%s)/Fragments(%s=%d)' % \
                #        (quality['Bitrate'], stream['Type'], current_duration)
                urls.append(url)
                current_duration += dur
    return urls

def makedirs(base_name, streams, verbose):
    """ make all directories needed to store the video fragments
    
        base_name - "foo.ism[l]/" from the url
        streams - data from parse_manifest
        verbose - if true prints progress info
    """
    for stream in streams:
        if stream['ManifestOutput'] == "true":
            continue # all data in the manifest file; not fetched
        for quality in stream['Qualities']:
            dirname = base_name + 'QualityLevels(%s)' % quality['Bitrate']
            if not os.path.exists(dirname):
                os.makedirs(dirname)
                if verbose:
                    print "created", dirname
            else:
                if verbose:
                    print "dir already exists:", dirname
    
def pull_file(data):
    """ read all data from a file-like object but don't save it anywhere
    
        reads 64k at a time
    """
    
    bytes = 0
    try:
        while True:
            s = data.read(64 * 1024) 
            if s == "":
                break;
            bytes += len(s)
    except KeyboardInterrupt:
        raise Error(KeyboardInterrupt, "Interrupted by user")
    except Exception, e:
        data.close()
        raise
        # my dev box has python 2.3, which has lame exception support
    data.close()
    return bytes
    
def fetch_urls(base_name, base_url, urls, write_option, verbose):
    """ pulls video fragments from a source, and handles them according to
        write_option
        
        base_name - foo.ism[l]/
        base_url - http://site.com/foo.ism - the stuff including the base name
        urls - list of url suffixes generated by generate_fragment_urls
        write_option - "pull" or "write"
        verbose - true or false
        
        garbage collects every 50 urls
    """
    global logfile

    num_urls = 0
    for url in urls:
        fullurl = base_url + '/' + url
        filename = base_name + url
        if write_option == "write":
            urllib.urlretrieve(fullurl, filename) # returns (filename, headers)
            if verbose:
                print "wrote", fullurl, "-->", filename
        elif write_option == "pull":
            data = urllib.urlopen(fullurl)
            bytes = pull_file(data) # can throw exceptions
            if verbose:
                print "pulled", bytes, "bytes from", fullurl
        else:
            print >> logfile, "unknown value for write_option:", write_option
            break
        num_urls += 1
        if num_urls % 50 == 49:
            if verbose:
                print "about to gc"
            gc.collect() # gc every 50 to limit memory usage in case we run this on steelheads
    return num_urls
                
if __name__ == "__main__":
    global logfile

    try:
        code = 0
        main(sys.argv)
    except Error, e:
        print >> logfile, "Exception:", e
        traceback.print_exc(file=logfile)
        code = e.code
    except SystemExit, e:
        code = ErrorCodes.SystemExit
    except Exception, e:
        print >> logfile, "Other Exception:", e
        code = ErrorCodes.UnknownException
        traceback.print_exc(file=logfile)
    if logfile != None and logfile != sys.stderr:
        logfile.close()

    sys.exit(code)
    
