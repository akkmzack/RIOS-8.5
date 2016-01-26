
from rvbd.restdispatch.claims import Claims
import getopt
import sys

def _usage():
    print 'usage: python decoder_tool.py -c [-n <named_field>] <encoded_claims>'
    print 'usage: python decoder_tool.py -f [-n <named_field>] <claims_file_path>'
    print 'usage: python decoder_tool.py -f [-n <named_field>] -'
    print 'usage: python decoder_tool.py -h'
    print ' -c | --cmdline : decode from a command line argument'
    print ' -f | --file : decode from a file or standard input'
    print ' -n | --named-field : decode just the named field from the claims'
    print ' -h : help'

def _check_options(argv):
    options = None
    args = None
    try:
        opts, args = getopt.getopt(argv, "cdfhn:",
                                   ["cmdline",
                                    "decode",
                                    "file",
                                    "help",
                                    "named-field="])

        options = {}
        for o, a in opts:
            if o in ('-c', '--cmdline'):
                options['cmdline'] = True
            elif o in ('-f', '--file'):
                options['cmdline'] = False
            elif o in ('-n', '--named-field'):
                options['field'] = a
            else:
                options = None
                args = None
                break

    except getopt.error, msg:
        print >>sys.stderr, msg

    return options, args

def _main(argv):
    ec = 0

    options, args = _check_options(argv)
    if options == None:
        ec = 2
    else:
        if not 'cmdline' in options:
            ec = 2
        else:
            if options['cmdline'] == True:
                if len(args) != 1:
                    ec = 2
                else:
                    encoded_line = args[0]
            else:
                if len(args) != 1:
                    ec = 2
                else:
                    if args[0] == '-':
                        lines = sys.stdin.readlines()
                    else:
                        f = open(args[0])
                        lines = f.readlines()
                        f.close()
                    encoded_line = ''.join(lines)

            if ec == 0:
                claims = Claims(encoded_line)
                if not 'field' in options:
                    print claims.get_json()
                else:
                    field = options['field']
                    if not claims.exists(field):
                        print >>sys.stderr, 'Field \'%s\' not found' % field
                        ec = 1
                    else:
                        print claims.get_field(field)


    if ec == 2:
        _usage()
    return ec

if __name__ == '__main__':
    ec = _main(sys.argv[1:])
    sys.exit(ec)
