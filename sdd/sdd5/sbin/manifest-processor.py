#!/usr/bin/python

""" script to work with Silverlight smooth streaming manifests, and to 
    optionally pull the video fragments as well
    
    support for flash http dynamic streaming ongoing
    """
    
import urllib
import sys
import os
import gc
import traceback
import optparse
import base64
import struct
import urlparse
from xml.etree.ElementTree import parse
from xml.etree.ElementTree import ElementTree
from xml.parsers import expat

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
    ParseError          = -9
    BootstrapError      = -10 # flash
    NeedExternalData    = -11
    RecursionDepth      = -12
    InvalidManifest     = -13
    
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

class MissingRootTagException(Error):
    """Exception raised for not finding the expected xml root tag in a manifest

    Attributes:
        msg -- error msg
    """
    def __init__(self, msg):
        Error.__init__(self, ErrorCodes.MissingRootTag, msg)

class NeedExternalDataException(Error):
    """ exception used when a manifest references data stored at a url
    """

    def __init__(self, url_list, msg = "External data needed"):
        Error.__init__(self, ErrorCodes.NeedExternalData, msg)
        self.url_list = url_list

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
    parser.add_option("-x", "--external-data", 
                action="append", dest="external_data",
                help="supply filename and name (comma separated) of external data, can be repeated")
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
    parser.set_defaults(external_data=[])
    
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
    
    external_data = {}
    external_data_list = map(lambda x: tuple(x.split(",",1)), options.external_data)
    for entry in external_data_list:
        if len(entry) != 2:
            raise Error(ErrorCodes.ParamError, "-x requires 2 comma-separated parts")
        external_data[entry[1].strip()] = entry[0].strip() #key=name, value=filename

    # now want to change list entries into a dict
    # where for each element, [0] is key and [1] is value
    
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

    base_url = ""
    idx = args[0].rfind('/')
    if idx != -1:
        # http://www.site.net/x/y/foo.xml -> http://www.site.net/x/y/
        base_url = args[0][0:idx + 1] 

    this_file_url = args[0]
    
    manifest = None
    try:
        manifest = SilverlightManifest(options.verbose, options.log_file, 
                                       external_data, base_url)
        manifest.parse_manifest(url) # may throw exceptions
    except (MissingRootTagException, expat.ExpatError), e:
        # if it's not silverlight, try flash
        try:
            manifest = FlashManifest(options.verbose, options.log_file, 
                                     external_data, base_url)
            manifest.parse_manifest(url) # may throw exceptions
        except (MissingRootTagException, expat.ExpatError), e:
            manifest = AppleHttpManifest(options.verbose, options.log_file, 
                                        external_data, base_url)
            manifest.parse_manifest(url) # may throw exceptions
        
    if options.print_manifest:
        manifest.print_manifest(outputfile)
        
    if manifest.external_data_needed():
        for t in manifest.get_external_data():
            if t[1] == this_file_url:
                raise Error(RecursionDepth, "manifest references itself")
            print >> outputfile, t[0] + '\t' + t[1]  # for debugging
        if outputfile != sys.stdout:
            outputfile.close()
        raise NeedExternalDataException(manifest.get_external_data())
    
    urls = manifest.generate_fragment_urls()
    
    # expect incoming url to look like 
    #  http://www.site.net/x/y/file.ism/Manifest
    # and the video urls look like 
    #  http://www.site.net/x/y/file.ism/QualityLevels(160000)/Fragments(audio=100310204)
        
    if options.print_urls:
        for s in urls:
            print >> outputfile, s
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
        manifest.makedirs(base_name)

    num_fetched = fetch_urls(base_name, base_url, urls, options.write_files,
                             options.verbose)  # may throw exceptions
    print >> logfile, "fetched", num_fetched, "fragments"

######################

class AbstractManifest:
    """ intput_external_data is a dictionary, with key = bootstrap id, value =
        url (for flash).  If none supplied and external references found, then
        external_data is set a list of tuples of these values
    """
    def __init__(self, verbose, logfile, input_external_data, base_url):
        self.verbose = verbose
        self.logfile = logfile
        self.streams = None
        self.external_data = None
        self.input_external_data = input_external_data        
        self.base_url = base_url

    def parse_manifest(self, url):
        pass
    
    def print_manifest(self, file):
        pass
    
    def generate_fragment_urls(self):
        pass
    
    def makedirs(self, base_name):
        pass
    
    def get_external_data(self):
        return self.external_data
    
    def generate_absolute_url(self, base_url, url):
        parsed_url = urlparse.urlparse(url)
        if parsed_url[0] == '' or parsed_url[1] == '':
            if base_url is None or base_url == '':
                # need the url of the manifest, without the trailer
                base_url = self.base_url
            # if base_url ends in a non-slash, the last component is removed
            new_url = urlparse.urljoin(base_url, url)
        else:
            new_url = url
        return new_url

    def external_data_needed(self):
        return self.external_data != None and len(self.external_data) > 0
    
###################### apple
   
class AppleHttpManifest(AbstractManifest):
    def __init__(self, verbose, logfile, input_external_data, base_url):
        AbstractManifest.__init__(self, verbose, logfile, input_external_data,
                                  base_url)
        self.streams = None
        self.max_depth = 4 # max recursion depth for manifests
         
    def parse_manifest(self, url):
        """ given a url (http: or file:) get the manifest file and parse it """
        self.streams = []
        if self.external_data == None:
            self.external_data = []
        file = urllib.urlopen(url)
        #file.get_code() not added until python 2.6
        lines = file.readlines()
        depth = 0
        self.parse_manifest_file(depth, lines, self.streams, self.external_data, 
                                 "base")
        
    def parse_manifest_file(self, depth, lines, streams, external_data, name):
        """ this is called recursively if external manifests are specified, and
            the manifests are provided """
            
        have_inf = False
        is_variant = False
        stream = None
        newname = ""
        str_inf_tag = "#EXT-X-STREAM-INF:"
        found_start_tag = False

        for line in lines:
            l = line.strip()
            if len(l) == 0:
                continue
            if l.startswith("#EXTM3U"):
                found_start_tag = True
            elif found_start_tag == False:
                continue
            elif l.startswith("#EXT-X-ENDLIST"):
                break # this tag is optional
            elif have_inf:
                #the line following an inf tag is a url
                if is_variant:
            #        print "found variant: " + l #this is a fname/url
                    if newname in self.input_external_data:
            #            print "found input external data " + l
                        f = open(self.input_external_data[newname])
                        variant_lines = f.readlines()
                        if depth == self.max_depth:
                            raise Error(RecursionDepth, "Max recursion depth exceeded")
                        self.parse_manifest_file(depth + 1, variant_lines, streams, 
                                       external_data, newname)
                        f.close()
                    else:
                        url = self.generate_absolute_url(None, l)
                        external_data.append((l, newname))
             #           print "adding needed external: " + l + " mewname: " + newname
                else:
		    # This is a quick fix to BugId: 124427
		    # Need to revisit this code to add support for newly added tags
		    if l.startswith("#"):
		    	continue
                    # not a variant; this is a fragment url
                    url = self.generate_absolute_url(None, l)
                    if stream == None:
                        stream = {
                                  'Type': name,
                                  'Urls': []
                                  }
		    # Check if the Url is not already present in the list
		    if not url in stream['Urls']:
                    	stream['Urls'].append(url)
                    # note: each url is part of a stream, not the stream itself
                have_inf = False
                is_variant = False
            elif l.startswith("#EXTINF:"):
                have_inf = True
            elif l.startswith(str_inf_tag): #definition of an external manifest
                have_inf = True
                is_variant = True
                newname = l[len(str_inf_tag):]

            #check for version
        if stream != None:
            streams.append(stream)
        return

    def print_manifest(self, file):
        """ print to stdout parsed data from the manifest
        
        """
        
        print >> file, "Apple manifest,", len(self.streams), "streams"
        
        for stream in self.streams:
            print >> file, "stream type=", stream['Type'], len(stream['Urls']), "urls"
            if self.verbose:
                for url in stream['Urls']:
                    print >> file, "    url: " + url 

    def generate_fragment_urls(self):
        """ given data generated by parse_manifest(), generate a list of urls of
            video fragments 
        """
        
        urls = []
        for stream in self.streams:
            for url in stream['Urls']:
                urls.append(url)
        return urls

    def makedirs(self, base_name):
        """ make all directories needed to store the video fragments
        """
        #FIXME -this should just like at the list of urls, not need to be a method?
        for stream in self.streams:
            for url in stream['Url']:
                #FIXME - might need to remove the last component of the name to get just a dir
                if not os.path.exists(url):
                    os.makedirs(url)
                    if self.verbose:
                        print "created", url
                else:
                    if self.verbose:
                        print "dir already exists:", url
        
###################### silverlight

class SilverlightManifest(AbstractManifest):
    def __init__(self, verbose, logfile, input_external_data, base_url):
        AbstractManifest.__init__(self, verbose, logfile, input_external_data,
                                  base_url)
        self.streams = None
        
    # data looks like
    #    <SmoothStreamingMedia
    #        <StreamIndex
    #            <QualityLevel
    #                <CustomAttributes (optional)
    #                    <Attribute
    #            <c
    def parse_manifest(self, url):
        """ given a url (http: or file:) get the manifest file and parse it """
            
        file = urllib.urlopen(url)
        #file.get_code() not added until python 2.6
        rss = parse(file).getroot()
        if rss.tag == None or rss.tag != 'SmoothStreamingMedia':
            raise MissingRootTagException("root tag is " + rss.tag + 
                        " expecting SmoothStreamingMedia")
        major = rss.get('MajorVersion')
        minor = rss.get('MinorVersion')
        
        if int(major) != 2 or int(minor) != 1:
            print >> self.logfile, "warning: unexpected manifest version: major=", major, "minor=", minor
        self.streams = []
        elements = rss.findall('StreamIndex')
        for element in elements:
            qualities = []
            durations = []
            manifest_output = element.get('ManifestOutput')
            if manifest_output != None:
                # the spec says this value is case-insensitive
                manifest_output = manifest_output.lower()
            url = element.get('Url')
            if url is not None:
                url = self.generate_absolute_url(None, url)
            data = { 
                'Type': element.get('Type'),
                'Url': url,
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
            self.streams.append(data)
            
        return
        
    
    def print_manifest(self, file):
        """ print to stdout parsed data from the manifest
        
        """
        
        print >> file, "silverlight manifest,", len(self.streams), "streams"
        
        for stream in self.streams:
            print >> file, "stream type=", stream['Type'], "url=", stream['Url'], \
                    "num qualities=", len(stream['Qualities']), "num durations=", \
                    len(stream['Durations'])
            if stream['ManifestOutput'] == "true":
                print >> file, "    ManifestOutput!"
            for quality in stream['Qualities']:
                print >> file, "    Bitrate=", quality['Bitrate']
                for c in quality['Cattrs']:
                    print >> file, "        Cattr=", c
            if self.verbose:
                current_start = 0
                for duration in stream['Durations']:
                    start = duration['start']
                    if start != None:
                        current_start = int(start) 
                    dur = int(duration['Duration'])
                    print >> file, "    start=", current_start
                    current_start += dur
    
    def subst_pattern(self, pattern, bitrate, start, custom):
        """ take the url pattern from the manifest and substitute bitrate, start
            time and custom attributes into it
        """    
        
        # we could almost use str.format(), but the url pattern has param names
        # that contain spaces ("start time"), and we'd open up a potential problem
        # if the string contained characters that format() might interpret as
        # metacharacters
        
        # the spec allows Bitrate and bitrate, start time and start_time
        s = pattern
        if bitrate != None:
            s = s.replace("{bitrate}", bitrate, 1)
            s = s.replace("{Bitrate}", bitrate, 1)
        if start != None:
            s = s.replace("{start time}", str(start), 1)
            s = s.replace("{start_time}", str(start), 1)
        if custom != None:
            for c in custom:
                attr_str = "%s=%s" % c
                s = s.replace("{CustomAttributes}", attr_str, 1)
        return s
        
    def generate_fragment_urls(self):
        """ given data generated by parse_manifest(), generate a list of urls of
            video fragments 
        """
        
        urls = []
        for stream in self.streams:
            if stream['ManifestOutput'] == "true":
                continue # all data in the manifest file; not fetched
            for quality in stream['Qualities']:
                current_duration = 0
                for duration in stream['Durations']:
                    start = duration['start']
                    if start != None:
                        current_duration = int(start) 
                                    
                    dur = int(duration['Duration'])
                    url = self.subst_pattern(stream['Url'], quality['Bitrate'], 
                                        current_duration, quality['Cattrs'])
                    #url = 'QualityLevels(%s)/Fragments(%s=%d)' % \
                    #        (quality['Bitrate'], stream['Type'], current_duration)
                    urls.append(url)
                    current_duration += dur
        return urls
        
    def makedirs(self, base_name):
        """ make all directories needed to store the video fragments
        
            base_name - "foo.ism[l]/" from the url
        """
        #FIXME -this should just like at the list of urls, not need to be a method?
        for stream in self.streams:
            if stream['ManifestOutput'] == "true":
                continue # all data in the manifest file; not fetched
            for quality in stream['Qualities']:
                dirname = base_name + 'QualityLevels(%s)' % quality['Bitrate']
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
                    if self.verbose:
                        print "created", dirname
                else:
                    if self.verbose:
                        print "dir already exists:", dirname
        
############# flash

def parse_string(s, current_offset = 0):
    ''' parse a 0-terminated string out of a string
    
        return a tuple of (#bytes parsed, string)
    '''
    index = s.find('\0', current_offset)
    if index == -1:
        raise Error("string not terminated")
    str = s[current_offset:index]
    if index - current_offset != len(str):
        raise Error("problem with lengths")
    length = index - current_offset
    length += 1 # add in the 0-byte
    return (length, str)

def parse_counted_string_array(s, current_offset = 0):
    ''' parse an array of o-terminated strings out of a string
        expects a 1-byte count at the start
        returns a tuple of (#bytes parsed, string[])
    '''
    num_strings = struct.unpack(">B", s[current_offset])
    current_offset += 1
    tuple = parse_string_array(s, num_strings[0], current_offset)
    return (tuple[0] + 1, tuple[1])

def parse_string_array(s, num_strings, current_offset = 0):
    ''' parse an array of o-terminated strings out of a string
        returns a tuple of (#bytes parsed, string[])
    '''
    
    strings = []
    len = 0
    for x in range(num_strings):
        tuple = parse_string(s, current_offset + len)
        len += tuple[0]
        strings.append(tuple[1])
    return (len, strings)

class FlashManifest(AbstractManifest):
    def __init__(self, verbose, logfile, input_external_data, base_url):
        AbstractManifest.__init__(self, verbose, logfile, input_external_data,
                                  base_url)
        self.streams = None
        self.bootstraps = None
        
    def parse_boxhdr(self, s, expecting = None):  # FIXME - really static
        short_fmt = ">L4s"
        long_fmt =  ">L4sQ"
        
        tuple = struct.unpack(short_fmt, s[:8])
        data = {
                'Type' : tuple[1],
                'Size' : tuple[0],
                'Used' : 8
        }
        if tuple[0] == 1:
            tuple = struct.unpack(long_fmt, s[:16])
            data['Size'] = tuple[2]
            data['Used'] = 16
            
        if expecting != None:
            if expecting != data['Type']:
                raise Error(ErrorCodes.ParseError, "expecting box " + expecting
                            + " but got " + data['Type'])
            
        return data
        
    def parse_abst(self, s): # FIXME - really static
        """ takes a string of binary data and returns a tuple of the abst
        
            assumes that the box header has already been parsed
        """
        fmt = ">B3BLBLQQ" # through the SmpteTimeCode field
        first_part_length = 29 # struct.calcsize not added until 2.5
        first_tuple = struct.unpack(fmt, s[:first_part_length])
         
        # now expecting movie identifier, 0-term string
        tuple = parse_string(s, first_part_length)
        movie_identifier = tuple[1]
        current_offset = first_part_length + tuple[0]
        
        tuple = parse_counted_string_array(s, current_offset)
        current_offset += tuple[0]
        server_entries = tuple[1]
        
        tuple = parse_counted_string_array(s, current_offset)
        current_offset += tuple[0]
        quality_entries = tuple[1]

        tuple = parse_string(s, current_offset)
        drm_data = tuple[1]
        current_offset += tuple[0]

        tuple = parse_string(s, current_offset)
        meta_data = tuple[1]
        current_offset += tuple[0]

        segment_run_table_count = struct.unpack(">B", s[current_offset])
        current_offset += 1
                
        return (current_offset, (first_tuple, movie_identifier, server_entries, 
                quality_entries, drm_data, meta_data, segment_run_table_count[0]))
        
    def parse_asrt(self, s): # FIXME - really static
        fmt = ">L"
        first_part_length = 4 # struct.calcsize not added until 2.5
        tuple = struct.unpack(fmt, s[:first_part_length])
        first_dict = {
            'Version' : tuple[0] >> 24,  # top byte
            'Flags': tuple[0] & 0xffffff,
        }
        
        tuple = parse_counted_string_array(s, first_part_length)
        current_offset = first_part_length + tuple[0]
        quality_segment_url_modifiers = tuple[1]
        
        segment_run_entry_count = struct.unpack(">L", s[current_offset:current_offset + 4])
        current_offset += 4
        
        segment_run_entries = []
        keys = ['FirstSeg', 'FragsPerSeg']
        for x in range(segment_run_entry_count[0]):
            fmt = ">LL"
            tuple = struct.unpack(fmt, s[current_offset:current_offset + 8])
            current_offset += 8
            seg = dict(zip(keys, tuple))
            segment_run_entries.append(seg)
            
        return (current_offset, (first_dict, quality_segment_url_modifiers,
                segment_run_entries))

    def parse_afrt(self, s): # FIXME - really static
        fmt = ">LL" # through the time scale
        first_part_length = 8 # struct.calcsize not added until 2.5
        tuple = struct.unpack(fmt, s[:first_part_length])
        
        first_dict = {
            'Version' : tuple[0] >> 24,  # top byte
            'Flags': tuple[0] & 0xffffff,
            'TimeScale' : tuple[1]
        }
        tuple = parse_counted_string_array(s, first_part_length)
        current_offset = first_part_length + tuple[0]
        quality_segment_url_modifiers = tuple[1]
        
        fragment_run_entry_count = struct.unpack(">L", s[current_offset:current_offset + 4])
        current_offset += 4
        
        fragment_run_entries = []
        keys = ['FirstFrag', 'FirstFragTimestamp', 'FragDuration', 'Discontinuity']
        for x in range(fragment_run_entry_count[0]):
            fmt = ">LQL" # through the quality entry count
            fmt_length = 16
            tuple = struct.unpack(fmt, s[current_offset:current_offset + fmt_length])
            if tuple[2] == 0:
                fmt = fmt + "B"
                fmt_length += 1
                tuple = struct.unpack(fmt, s[current_offset:current_offset + fmt_length])

            frag = dict(zip(keys, tuple))
            current_offset += fmt_length
            fragment_run_entries.append(frag)
        
        return (current_offset, (first_dict, quality_segment_url_modifiers,
                fragment_run_entries))
        
    def parse_bootstrap(self, s):
        abst_box = self.parse_boxhdr(s, "abst")
        current_offset = abst_box['Used']
        if len(s) != abst_box['Size']:
            raise Error(ErrorCodes.ParseError, "expecting bootstrap info to be " 
                        + str(abst_box['Size']) + " but got " + str(len(s)))
        abst = self.parse_abst(s[current_offset:])
        current_offset += abst[0]
        
        segments = []        
        abstdata = abst[1]
        for x in range(abstdata[6]):
            asrt_box = self.parse_boxhdr(s[current_offset:], "asrt")
            current_offset += asrt_box['Used']
            asrt = self.parse_asrt(s[current_offset:])
            current_offset += asrt[0]
            segments.append(asrt[1])
            
        fragments = []
        num_frags = struct.unpack(">B", s[current_offset:current_offset + 1])
        current_offset += 1
        for x in range(num_frags[0]):
            afrt_box = self.parse_boxhdr(s[current_offset:], "afrt")
            current_offset += afrt_box['Used']
            afrt = self.parse_afrt(s[current_offset:])
            current_offset += afrt[0]
            fragments.append(afrt[1])
            
        return { 'Size': current_offset, 'Abst': abst[1], 'Segments': segments, 
                'Fragments': fragments }
        
    def parse_manifest(self, url):
        """ given a url (http: or file:) get the manifest file and parse it """
            
        self.streams = []
        self.bootstraps = {}

        file = urllib.urlopen(url)
        #file.get_code() not added until python 2.6
        rss = parse(file).getroot()
        
        prefix = None
        if rss.tag == 'manifest':
            prefix = ""
        elif rss.tag == "{http://ns.adobe.com/f4m/1.0}manifest":
            prefix = "{http://ns.adobe.com/f4m/1.0}"
        elif rss.tag == "{http://ns.adobe.com/f4m/2.0}manifest":
            prefix = "{http://ns.adobe.com/f4m/2.0}"
        if prefix == None: # didn't find a valid flash tag
            raise MissingRootTagException("root tag is " + rss.tag + 
                        " expecting manifest") # FIXME-could be expecting SmoothStreamingMedia, tell which we're looking for from the url?
            
        # FIXME - need to look at the mimeType subelement, baseURL subelement
        base_url = ""
        base_url_element = rss.find(prefix + "baseURL")
        if base_url_element is not None and base_url_element.text is not None:
            base_url = base_url_element.text.strip()
            if base_url[-1] != '/':
                base_url += '/'
        elements = rss.findall(prefix + 'bootstrapInfo')
        for element in elements:
            bootstrap = None
            url = element.get('url') #might not exist
            if url is not None:
                url = self.generate_absolute_url(base_url, url)
            if element.text != None:
                body = element.text.strip()
                if len(body) > 0:
                    bodydata = base64.decodestring(body)
                    if bodydata != None and len(bodydata) > 0:
                        bootstrap = self.parse_bootstrap(bodydata)
            data = { 
                'Id': element.get('id'),
                'Url': url, # if external, bootstrap is file containing the abst etc boxes, not base64 encoded
                'Bootstrap': bootstrap
            }
            self.bootstraps[data['Id']] = data
            if data['Url'] != None:
                if data['Id'] in self.input_external_data:
                    #now read and parse the external boot data
                    # then add the parsed data to self.bootstraps
                    #    with url = None, Id = tuple[0], bootstrap = parsed data
                    f = open(self.input_external_data[data['Id']], "rb")
                    s = f.read()
                    f.close()
                    bootstrap = self.parse_bootstrap(s)
                    self.bootstraps[data['Id']]['Bootstrap'] = bootstrap
                else:
                    if self.external_data == None:
                        self.external_data = []
                    # FIXME - need to apply base url to the url before storing
                    self.external_data.append(("$bootstrapInfo=" + data['Id'], data['Url']))
        
        elements = rss.findall(prefix + 'media')
        for element in elements:
            url = element.get('url')
            if url is not None:
                url = self.generate_absolute_url(base_url, url)
                data = { 
                    'Url': url,
                    'Bitrate': element.get('bitrate'),
                    'Bootstrap': element.get('bootstrapInfoId') #implies we need to index bootstraps
                }
                self.streams.append(data)
            else:
                href = element.get('href')
                if href is not None:
                    bitrate = "bitrate=%s" % element.get('bitrate')
                    if self.external_data == None:
                        self.external_data = []
                    self.external_data.append((href, bitrate))
        return
    
    def print_manifest(self, file):
        """ print to stdout parsed data from the manifest
        
        """
        print >> file, "flash manifest,", len(self.streams), "streams"
        if self.streams == None:
            return
        
        for stream in self.streams:
            print >> file, "url=", stream['Url'], "bitrate=", stream['Bitrate'],\
                    "bootstrap=", stream['Bootstrap']
        boots = self.bootstraps.iteritems()
        for boot_tuple in boots:
            boot = boot_tuple[1] # the item
            if boot['Bootstrap'] != None:
                bootstrap = boot['Bootstrap']
                print >> file, "Bootstrap: Id=" + boot['Id'], "url=", boot['Url'],\
                    ""
                print >> file, "{"
                print >> file, "    \'Abst\':", bootstrap['Abst']
                
                print >> file, "    \'Segments\':"
                segs = bootstrap['Segments']
                for seg in segs:
                    print >> file, "        ", seg[0], seg[1]
                    entries = seg[2]
                    for entry in entries:
                        print >> file, "            ", entry
                
                print >> file, "    \'Fragments\':"
                frags = bootstrap['Fragments']
                for frag in frags:
                    print >> file, "        ", frag[0], frag[1]
                    entries = frag[2]
                    for entry in entries:
                        print >> file, "            ", entry
                print >> file, "}"
            else:
                print >> file, "Bootstrap: Id=", boot['Id'], "boot=", boot['Url']
                            
    def generate_fragment_urls(self):
        """ given data generated by parse_manifest(), generate a list of urls of
            video fragments 
        """
        
        urls = []
        for stream in self.streams:
            #roughly stream['Url'] + "Seg" + seg + "-Frag" + frag
            # looking for something like "Hillman_720p23.976_3000kbpsSeg1-Frag10"
            # first need to figure out which bootstrap info to use - a global one
            # or one specified by name for this stream, then see if the bootstrap
            # data is specified in data or specified by url.  if specified by
            # url it needs to be fetched somehow  
            base = stream['Url'] + "Seg"
            bootstrap_id = stream['Bootstrap']
            bootstrap = self.bootstraps[bootstrap_id]
            if bootstrap == None:
                raise Error(ErrorCodes.BootstrapError, 
                        "stream requested unknown bootstrap " + bootstrap_id)
            if bootstrap['Bootstrap'] == None:
                raise Error (ErrorCodes.BootstrapError,
                        "stream requested bootstrap with no embedded info: " +
                        bootstrap_id)
            boot = bootstrap['Bootstrap']
            segments = boot['Segments']
            segdict = {}
            for segment in segments:
                # construct a map of all asrt boxes, indexed by the qual levels they apply to
                qualsegs = segment[1]
                for qual in qualsegs:
                    segdict[qual] = segment
            fragments = boot['Fragments']
            fragdict = {}
            for fragment in fragments:
                # construct a map of all afrt boxes, indexed by the qual levels they apply to
                qualfrags = fragment[1]
                for qual in qualfrags:
                    fragdict[qual] = fragment
                    

            # now pick the asrt and abst to use based on the quality modifiers 
            # but there might not be any, so just pick the first of each
            # how do the abst quality levels and xml stream ids/bitrates relate?
                    
            #FIXME - need to look at the quality segment url modifiers to see which segment and fragment entries apply to a specific stream's quality level
            # for each stream, get the asrt and afrt that applies to it
            # if a asrt or afrt has no seg url modifiers, it applies to all
            for asrt in boot['Segments']: # list of asrt chunks
                for segment_entry in asrt[2]:
                    segnum = segment_entry['FirstSeg']
                    num_frags = segment_entry['FragsPerSeg']
                    frags_encountered = 0
                    for afrt in boot['Fragments']:
                        frag_entries = afrt[2]
                        current_frag_index = 0
                        while current_frag_index < len(frag_entries):
                            current_frag = frag_entries[current_frag_index]
                            if current_frag['FragDuration'] == 0:
                                if current_frag['Discontinuity'] == 0:
                                    # we're done with this fragment
                                    break
                            fragnum = current_frag['FirstFrag']
                            if current_frag_index == len(frag_entries) - 1:
                                # last one
                                next_fragnum = fragnum + 1
                            else:
                                next_frag = frag_entries[current_frag_index + 1]
                                next_fragnum = next_frag['FirstFrag']
                            if next_fragnum == 0: #last entry
                                next_fragnum = fragnum + 1
                            for x in range(fragnum, next_fragnum):
                                url = base + str(segnum) + "-Frag" + str(x)
                                urls.append(url)
                            current_frag_index += 1
                        
        return urls
                 
    def makedirs(self, base_name):
        """ make all directories needed to store the video fragments
        
            base_name - "foo.ism[l]/" from the url
        """
        for stream in self.streams:
            dirname = base_name
            if not os.path.exists(dirname):
                os.makedirs(dirname)
                if self.verbose:
                    print "created", dirname
            else:
                if self.verbose:
                    print "dir already exists:", dirname
                            
############## fragment pulling
    
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
                
#################################
                
if __name__ == "__main__":
    global logfile

    try:
        code = 0
        main(sys.argv)
    except NeedExternalDataException, e:
        print >> logfile, "NeedExternalDataException:", e
        code = e.code
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
    
