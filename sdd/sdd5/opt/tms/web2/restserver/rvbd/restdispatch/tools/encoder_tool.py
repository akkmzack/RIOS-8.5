
from rvbd.restdispatch.claims import Claims
import getopt
import sys

def _usage():
    print 'usage: python encoder_tool.py [-a audience] [-i issuer] [-j jti] [-l lifetime] [-p principle]'
    print 'usage: python encoder_tool.py -h'
    print ' -a audience | --audience=audience : URL of the token endpoint of issuing server'
    print ' -i issuer | --issuer=issuer : base URL of issuing server'
    print ' -j jti | --jti=jti : jti for object being encoded'
    print ' -l lifetime | --lifetime=lifetime : lifetime of claims in seconds'
    print ' -p principle | --principle=principle : principle to be put into the claims'
    print ' -h : help'

def _check_options(argv):
    options = None
    args = None
    try:
        opts, args = getopt.getopt(argv, "a:hi:j:l:n:p:",
                                   ["audience=",
                                    "help",
                                    "issuer=",
                                    "jti=",
                                    "lifetime=",
                                    "principle="])

        options = {}
        for o, a in opts:
            if o in ('-a', '--audience'):
                options['audience'] = a
            elif o in ('-i', '--issuer'):
                options['issuer'] = a
            elif o in ('-j', '--jti'):
                options['jti'] = a
            elif o in ('-l', '--lifetime'):
                options['lifetime'] = a
            elif o in ('-p', '--principle'):
                options['principle'] = a
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
        audience = options.get('audience', None)
        jti = options.get('jti', None)
        issuer = options.get('issuer', None)
        lifetime = options.get('lifetime', None)
        principle = options.get('principle', None)

        if lifetime != None:
            try:
                lifetime = int(lifetime)
            except ValueError:
                print >>sys.stderr, "Bad value given for lifetime"
                ec = 2

        if ec == 0:
            claims = Claims(audience=audience, jti=jti, issuer=issuer, lifetime=lifetime, principle=principle)
            print claims.get_encoded()

    if ec == 2:
        _usage()
    return ec

if __name__ == '__main__':
    ec = _main(sys.argv[1:])
    sys.exit(ec)
