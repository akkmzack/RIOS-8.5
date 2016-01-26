#!/usr/bin/python
#
# $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/fwk_heartbeat.py $
# $Id: fwk_heartbeat.py 106391 2013-06-26 00:09:52Z cscuderi $
# 
# Framework Heartbeat Helper Script
#
from optparse import OptionParser
import sys, Mgmt

local = 0
radius = 1
tacacs = 2

def countValues(bindings, findValue=None, skipEmpty=False):
    """
    Takes a list of bindings, as returned by a get_children or get_pattern
    call, and returns the specified value. If no value (search) is specified,
    returns the number of bindings.

    @param bindings:  Either an array of (node,type,value) bindings returned
                      by the Mgmt object, or a flat array. (e.g. with
                      countUnique) If used with findValue, this *must* be
                      [(n,t,v),]
    @param findValue: Find only bindings with a certain value (string,
                      matches whatever the backend returns).
    @param skipEmpty: Skips over empty values, returns the count of non-empty
                      values only. Is a no-op if @c findValue is specified.
    """
    if not bindings:
        return 0

    if not findValue and not skipEmpty:
        return len(bindings)

    elif findValue:
        num_vals = len([v for (n,t,v) in bindings if v == findValue])
        return num_vals

    elif skipEmpty:
        num_vals = len([v for (n,t,v) in bindings if v])
        return num_vals

def getRBMUsersCount():
    """
    @returns the number of RBM users on the system.
    """
    return countValues(Mgmt.get_pattern("/rbm/config/user/*"))

def getNTPAuthEnabled():
    """
    @returns true if any enabled NTP server has a valid key configured.
    """
    auth_enabled = False

    ntp_hosts = Mgmt.get_pattern('/ntp/server/address/*')
    for host in ntp_hosts:
        key = Mgmt.get_value('/ntp/server/address/%s/key' % host[2])
        enable = Mgmt.get_value('/ntp/server/address/%s/enable' % host[2])

        if (key != '0') and (enable == 'true'):
            if Mgmt.get_value('/ntp/keys/%s' % key):
                auth_enabled = True
                break

    return auth_enabled

def getValidServersCount(method):
    """
    @param method: tacacs or radius, the server type to check.

    @returns number of enabled servers configured for the
             specified method
    """
    configured = False

    if method == tacacs:
        servers = Mgmt.get_pattern('/tacacs/server/*/enable')
    elif method == radius:
        servers = Mgmt.get_pattern('/radius/server/*/enable')
    else:
        servers = None

    count = 0
    for server in servers:
        if server[2] == 'true':
            count = count + 1

    return count

def getTACACSAccountingCfged():
    """
    @returns true if TACACS+ is configured as an accounting method
             and that there is a valid TACACS+ server configured.
    """
    acct = [Mgmt.get_value("/aaa/cmd_audit_method/1/name"),
            Mgmt.get_value("/aaa/cmd_audit_method/2/name")]

    return ('tacacs+' in acct)

def getTACACSAuthorizationCfged():
    """
    @returns true if TACACS+ is configured as an authorization method
             and that there is a valid TACACS+ server configured.
    """
    author = [Mgmt.get_value("/aaa/cmd_author_method/1/name"),
              Mgmt.get_value("/aaa/cmd_author_method/2/name")]

    return ('tacacs+' in author)

def getAuthenticationCfged(auth_method):
    """
    @params auth_method: The authentication method to look for.
                         local, radius or tacacs.

    @returns bool indicating whether the specified authentication
             method is configured.  In the case of TACACS+ and RADIUS,
             true is only returned if the authentication method is
             configured AND a valid RADIUS/TACACS+ server is configured.
    """
    auth = [Mgmt.get_value("/aaa/auth_method/1/name"),
            Mgmt.get_value("/aaa/auth_method/2/name"),
            Mgmt.get_value("/aaa/auth_method/3/name")]

    if auth_method == radius:
        configured = ('radius' in auth)
    elif auth_method == tacacs:
        configured = ('tacacs+' in auth)
    elif auth_method == local:
        configured = ('local' in auth)
    else:
        configured = False

    return configured

def initMgmt():
    Mgmt.open(gcl_provider='mgmtd')

def killMgmt():
    Mgmt.close()

def main():
    parser = OptionParser(usage="Framework Heartbeat Queries")

    parser.add_option("--rbm_users", action="store_true",
                       help="Count the number of rbm users")

    parser.add_option("--ntp_auth", action="store_true",
                       help="NTP auth configured")

    parser.add_option("--local_auth", action="store_true",
                      help="Local authentication is configured")

    parser.add_option("--tacacs_auth", action="store_true",
                      help="TACACS+ authentication is configured, "
                      "and there are valid TACACS+ servers")

    parser.add_option("--radius_auth", action="store_true",
                      help="RADIUS authentication is configured, "
                      "and there are valid RADIUS servers")

    parser.add_option("--tacacs_acct", action="store_true",
                      help="TACACS+ command accounting is configured, "
                      "and there are valid TACACS+ servers")

    parser.add_option("--tacacs_author", action="store_true",
                      help="TACACS+ command authorization is configured,"
                      "and there are valid TACACS+ servers")

    parser.add_option("--tacacs_servers", action="store_true",
                      help="Number of TACACS+ servers configured")

    parser.add_option("--radius_servers", action="store_true",
                      help="Number of RADIUS servers configured")

    (opts, args) = parser.parse_args()

    initMgmt()

    if opts.rbm_users:
        print getRBMUsersCount()

    elif opts.ntp_auth:
        print getNTPAuthEnabled()

    elif opts.local_auth:
        print getAuthenticationCfged(local)

    elif opts.tacacs_auth:
        print getAuthenticationCfged(tacacs)

    elif opts.radius_auth:
        print getAuthenticationCfged(radius)

    elif opts.tacacs_acct:
        print getTACACSAccountingCfged()

    elif opts.tacacs_author:
        print getTACACSAuthorizationCfged()

    elif opts.tacacs_servers:
        print getValidServersCount(tacacs)

    elif opts.radius_servers:
        print getValidServersCount(radius)

    else:
        print 0;

    killMgmt()

if __name__ == "__main__":
    sys.exit(main())
