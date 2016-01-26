#!/usr/bin/env python

# Filename:  $Source$
# Revision:  $Revision: 72030 $
# Date:      $Date: 2010-10-28 14:45:56 -0700 (Thu, 28 Oct 2010) $
# Author:    $Author: jshilkaitis $
#
# (C) Copyright 2003-2007 Riverbed Technology, Inc. 
# All Rights Reserved. Confidential.

'$Id: service_utils.py 72030 2010-10-28 21:45:56Z jshilkaitis $'

from soaplib.serializers.primitive import String, Integer, Array, Long
from soaplib.serializers.clazz import *
from soaplib.service import soapmethod
from soaplib.soap import make_soap_fault
from Logging import *
import pam
import os
import pwd
import Mgmt
import time

# XXX/jshilkaitis: flesh this out into a proper subclass of Exception
ServiceError = Exception

class AuthInfo(ClassSerializer):
    class types:
        username = String
        password = String

class Datapoint(ClassSerializer):
    class types:
        value = Long
        time = Integer
        duration = Integer

class TopConversation(ClassSerializer):
    """
    Class representing the number of bytes transferred between a particular
    combination of src_ip:src_port and dest_ip:dest_port.
    """
    class types:
        src_ip = String
        src_port = Integer
        dest_ip = String
        dest_port = Integer
        byte_count = Long

    def __repr__(self):
        return str((self.src_ip, self.src_port, self.dest_ip, self.dest_port, self.byte_count))

# TopSrcHost and TopDestHost are separate classes so that the server code
# can be more concise, and, dare I say, cleverer.
class TopSrcHost(ClassSerializer):
    """
    Class representing the number of bytes sent out from a particular IP
    address.
    """
    class types:
        src_ip = String
        byte_count = Long

    def __repr__(self):
        return str((self.src_ip, self.byte_count))

class TopDestHost(ClassSerializer):
    """
    Class representing the number of bytes received by a particular IP
    address.
    """
    class types:
        dest_ip = String
        byte_count = Long

    def __repr__(self):
        return str((self.dest_ip, self.byte_count))

class TopApplication(ClassSerializer):
    """
    Class representing the number of bytes sent out on a particular port.
    """
    class types:
        src_port = String
        byte_count = Long

    def __repr__(self):
        return str((self.src_port, self.byte_count))

StatsArray = Array(Array(Datapoint))

# XXX/TODO: figure out a clever way to merge rbt_ensure_auth and rbt_soapmethod
# into one decorator.

def rbt_ensure_auth(soap_service_func):
    """
    Decorator which will perform authorization prior to actually calling
    the decorated function.
    """

    # XXX/jshilkaitis: this decorator spoofs just enough of the underlying
    # function's func_code object to trick soaplib into doing what I want
    # it to do.  Thus, it is tightly coupled to how soaplib gets at function
    # metadata, so if soaplib ever changes how it does that, this will
    # break.  See the soaplib soapmethod decorator implementation for the
    # gritty details of how soaplib works.
    class FakeFunc:
        """
        C++ Functor-like class which tricks the soapmethod decorator into
        thinking it's looking directly at the function that rbt_ensure_auth
        is decorating.
        """

        class FakeFuncCode:
            def __init__(self, func):
                self.co_varnames = list(func.func_code.co_varnames)
                self.co_varnames.insert(1, 'auth_info')
                self.co_argcount = func.func_code.co_argcount + 1

        def __init__(self, func):
            self.func = func
            self.func_name = func.func_name
            self.func_code = self.FakeFuncCode(func)
            self.__doc__ = func.__doc__

        def __call__(self, *args, **kw):
            auth_info = args[1]

            # the (de-)serializer turns the empty string into None, which
            # ctypes will then turn into NULL.  This will crash the
            # pam_conversation function, so we protect against it here.
            if auth_info.password is None:
                auth_info.password = ""

            try:
                # XXX/jshilkaitis: is using wsmd okay here?
                pamh = pam.PamHandle("wsmd", auth_info.username,
                                     auth_info.password)

                # XXX/jshilkaitis: check to see if there are flags we want here
                pamh.authenticate(0)

                # XXX/jshilkaitis: flag check
                pamh.acct_mgmt(0)
            except:
                log(LOG_NOTICE, 'User %s failed to authenticate via the SOAP '
                    'server.' % auth_info.username)
                raise
            else:
                log(LOG_NOTICE, 'User %s succesfully authenticated via the '
                    'SOAP server.' % auth_info.username)

            # XXX/jshilkaitis: We need to ask PAM for the local username
            # and use that to get the proper uid/gid.

            # XXX/jshilkaitis: is username the LOCAL username?
            # We need to make sure that Tac+ and RADIUS auths play
            # nicely with the setuid/setgid.
            pwd_db_entry = pwd.getpwnam(auth_info.username)

            uid = pwd_db_entry[2]
            gid = pwd_db_entry[3]

            os.setegid(gid)
            os.seteuid(uid)

            # strip out auth_info
            args = list(args)
            args.pop(1)

            try:
                try:
                    Mgmt.open()
                except:
                    raise ServiceError, "Unable to connect to the " \
                                        "management backend."

                return self.func(*args, **kw)
            finally:
                Mgmt.close()

    return FakeFunc(soap_service_func)

def rbt_soapmethod(*params, **kparams):
    """
    Decorator used in combination with rbt_ensure_auth that sneaks an
    AuthInfo serializer into the soapmethod decorator so that rbt_ensure_auth
    can get at the auth_info.
    """
    return soapmethod(AuthInfo, *params, **kparams)

def is_dst():
    return time.localtime()[-1] == 1

def time_to_local_time(t):
    """
    Takes a datetime or stringified datetime of the form
    'YYYY-MM-DD HH:MM:SS.ffff[+-]ZZ:ZZ' and converts it to a stringified local
    datetime of the form 'YYYY/MM/DD HH:MM:SS'.

    NOTE: if no UTC offset is specified, we will assume the time is already
    local

    NOTE: fractional seconds in the input are truncated and not
    reflected in the output.

    NOTE: See http://www.w3.org/TR/xmlschema-2/#dateTime for more info on
    why this function does what it does
    """

    t = str(t)

    c = t.count('-')

    def strip_fractional_seconds(t):
        if t.rfind('.') != -1:
            return t[:t.rfind('.')]
        return t

    if c == 3:
        offset_idx = t.rfind('-') # look for a negative UTC offset
    elif c == 2:
        offset_idx = t.rfind('+') # look for a positive UTC offset
        if offset_idx == -1:
            if t[-1] == 'Z': # Z is the only other valid UTC offset
                pass # offset_idx = -1 will strip the Z below
            else:
                t = strip_fractional_seconds(t)
                return t.replace('-', '/')
    else:
        raise ServiceError, "Unexpected number of '-' characters in %s" % t

    # figure out the time difference between the client and server
    if is_dst() == 1:
        server_offset = time.altzone
    else:
        server_offset = time.timezone

    client_offset = t[offset_idx:]
    if client_offset.upper() == 'Z':
        client_offset = 0
    else:
        client_offset = int(client_offset.split(':')[0])

    client_offset = client_offset * 3600 # hours to seconds

    client_time = t[:offset_idx]
    client_time = strip_fractional_seconds(client_time)
    client_time = time.strptime(client_time, "%Y-%m-%d %H:%M:%S")
    client_time = time.mktime(client_time)

    utc_time = client_time - client_offset

    server_time = utc_time - server_offset

    return time.strftime("%Y/%m/%d %H:%M:%S",
                         time.localtime(server_time))

RBM_WRITE = True
RBM_READ = False
RBM_ACTION = True

def check_rbm_permissions(node_name, write_needed):
    """
    Raises an exception if the user does not have at least the permissions
    specified by write_needed for the node specified by node_name.

    A questionable interface, but it works well for the SOAP server.
    """
    import pwd

    username = pwd.getpwuid(os.geteuid())[0]

    # XXX/jshilkaitis: a small hack to get around the fact that the RBM
    # nodes verify action doesn't do what I want for admin or monitor.
    # I should figure out a cleaner way to do this in the future.
    if username == 'admin' or username == 'monitor':
        return

    code, msg, bindings = Mgmt.action('/rbm/action/nodes/verify',
                                      ('username', 'string', username),
                                      ('nodenames', 'string', node_name))

    if code != 0:
        raise ServiceError, msg

    try:
        perms = bindings['permissions']
    except:
        raise ServiceError, 'Server Error: Unable to authorize current user'

    if ((write_needed and perms != 'write') or
        (not write_needed and perms != 'write' and perms != 'read')):
        # XXX/jshilkaitis: make this match the message returned by the backend
        # someday.  Same goes for the CLI.
        raise ServiceError, "Insufficient permissions for command execution."

def main():

    # XXX/jshilkaitis: these tests only work in PST :-D
    time_to_local_time_test_cases = [
        ["2009-08-22 12:00:00+10:00", "2009/08/21 18:00:00"],

        # apparently Python can handle pre-epoch times...
        ["1978-08-22 12:00:00+10:00", "1978/08/21 18:00:00"],

        # but nothing past the end of time.
        # ["2040-08-22 12:00:00+10:00", "2040/08/21 04:00:00"],

        ["2009-08-22 00:00:00-10:00", "2009/08/22 02:00:00"],
        ["2009-08-22 12:00:00.12345-10:00", "2009/08/22 14:00:00"],
        ["2009-08-22 12:00:00.12345Z", "2009/08/22 04:00:00"],
        ["2009-09-22 00:00:00-07:00", "2009/09/21 23:00:00"],
        ]

    result_fmt = "%Y/%m/%d %H:%M:%S"
    if is_dst() == 1:
        for test in time_to_local_time_test_cases:
            time_in_secs = time.strptime(test[1], result_fmt)
            time_in_secs = time.mktime(time_in_secs)
            time_in_secs += 3600
            test[1] = time.strftime(result_fmt, time.localtime(time_in_secs))

    import datetime
    # non-offset tests don't play nice with the DST adjustment above
    time_to_local_time_test_cases.extend([
        ["2009-08-22 12:00:00", "2009/08/22 12:00:00"],
        ["2009-08-22 12:00:00.56535", "2009/08/22 12:00:00"],
        [datetime.datetime(2009, 8, 22, 12, 0, 0, 123), "2009/08/22 12:00:00"],
        ])

    for test in time_to_local_time_test_cases:
        assert test[1] == time_to_local_time(test[0]), \
               str(test) + " failed"

if __name__ == '__main__':
    main()
