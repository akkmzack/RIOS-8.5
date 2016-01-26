# Filename:  $Source$
# Revision:  $Revision: 102950 $
# Date:      $Date: 2013-02-15 14:55:44 -0800 (Fri, 15 Feb 2013) $
# Author:    $Author: asweigart $
#
# (C) Copyright 2003-2007 Riverbed Technology, Inc.
# All Rights Reserved. Confidential.

# '$Id: fwk_service.py 102950 2013-02-15 22:55:44Z asweigart $'

"""fwk_service contains the FrameworkService class which implements all
of the non-product-specific services made available via the SOAP server."""

from soaplib.wsgi_soap import SimpleWSGISoapApp
from soaplib.serializers.primitive import *
from soaplib.serializers.binary import Attachment
from soaplib.service import soapmethod
from service_utils import rbt_ensure_auth, rbt_soapmethod, ServiceError, StatsArray, time_to_local_time, check_rbm_permissions, RBM_WRITE, RBM_READ, RBM_ACTION
import Mgmt
import common
import os
import time
from Logging import *
import bulk_stats

# XXX/jshilkaitis: should we use str.upper() and str.lower() to make input
# more tolerant of users using the incorrect case or should we simply error
# out and bitch when they use the wrong case?  On the one hand, users are
# expected to use the correct case when entering usernames/password.  On the
# other hand, it could be annoying to have inputs rejected based on incorrect
# case when case is not important (e.g. md5 vs MD5 in set_snmp_password)
#
# We can do this lowering/uppering automatically by adding
# UpperString/LowerString serializers to soaplib

# Assume success if there is no SOAP fault.

# NOTE: The WSDL revision must be incremented on ANY change to the
# FrameworkService interface.  This includes addition/removal of entire
# API calls and changes to parameters of existing API calls.  The WSDL revision
# must also be bumped by a significant number (e.g. 1000) for new major/minor
# releases for reasons similar to why we leave gaps in mgmtd module numbers.

FRAMEWORK_WSDL_VERSION = 1001

class FrameworkService(SimpleWSGISoapApp):
    """
    Class implementing all non-product-specific SOAP server RPC calls.

    All API calls take an AuthInfo structure as their first parameter.  The
    AuthInfo structure contains a username and a password and is used as
    the authentication token for the call.
    """

    def onReturn(self, environ, returnString):
        # The Attachment serializer doesn't serialize the file it is given
        # until the response is generated, so we can't clean up the temp
        # csv file in the get_stats_internal function.  We have to wait
        # until after serialization, which this hook conveniently allows us to do.
        try:
            os.remove(self.msg_file)
        except:
            pass

    @rbt_soapmethod()
    @rbt_ensure_auth
    def reboot(self):
        """
        reboot(auth) -> None

        Reboot the appliance.

        Exceptions:
        rebootFault - Unable to verify user permissions
        rebootFault - Authorization failure: unable to complete action for user
        """
        reboot_node = '/pm/actions/reboot'

        check_rbm_permissions(reboot_node, RBM_ACTION)

        # XXX/jshilkaitis: _highly_ questionable implementation, but we need
        # something now.  Flaws: relies on arbitrary 3 second sleep, and does
        # not report an error to the client if the reboot action fails.  The
        # action failing should be rare enough to not worry about, though.
        if os.fork() == 0:
            time.sleep(3) # give parent SOAP server time to respond

            # we fork so that the parent SOAP server can respond to the
            # client.  The following action does not return if it is
            # successful.
            Mgmt.action(reboot_node)

    @rbt_soapmethod()
    @rbt_ensure_auth
    def write_config(self):
        """
        write_config(auth) -> None

        Save the current in-memory configuration to disk.

        Exceptions: None
        """
        code, msg, bindings = Mgmt.action('/mgmtd/db/save')

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod()
    @rbt_ensure_auth
    def revert_config(self):
        """
        revert_config(auth) -> None

        Revert the current in-memory configuration to the last saved
        configuration.

        Exceptions: None
        """
        code, msg, bindings = Mgmt.action('/mgmtd/db/revert')

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(String)
    @rbt_ensure_auth
    def set_snmp_community_string(self, community_string):
        """
        set_snmp_community_string(auth, community_string) -> None

        Set the SNMP community string.

        Parameters:
        community_string (string) - SNMP community string to be set

        Exceptions: None
        """
        code, msg = Mgmt.set(
            ('/snmp/access/rocommunity', 'string', community_string))

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(String, String, String)
    @rbt_ensure_auth
    def set_snmp_password(self, username, password, auth_protocol):
        """
        set_snmp_password(auth, username, password, auth_protocol) -> None

        Configure a SNMP user.

        Parameters:
        username - username of user to configure
        password - user's new password
        auth_protocol - protocol used to encrypt the password

        Exceptions:
        set_snmp_passwordFault - password must contain at least 8 characters
        set_snmp_passwordFault - XXX/BUG 47861/48172 for bad auth_protocol value
        """
        # XXX/jshilkaitis: lame, should be an action on the mgmtd side

        # 8 is USM_LENGTH_P_MIN from net-snmp
        if len(password) < 8:
            raise ServiceError, "password must contain at least 8 characters"

        auth_protocol = auth_protocol.upper()

        code, msg, bindings = Mgmt.action(
            '/snmp/usm/actions/generate_auth_key',
            ('password', 'string', password),
            ('hash_function', 'string', auth_protocol)
            )

        if code != 0:
            raise ServiceError, msg

        auth_key = bindings['auth_key']

        snmp_user_pfx = '/snmp/usm/users/%s' % username
        code, msg = Mgmt.set(
            (snmp_user_pfx, 'string', username),
            (snmp_user_pfx + '/auth_key', 'string', auth_key),
            (snmp_user_pfx + '/hash_function', 'string', auth_protocol)
            )

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(String, String, String)
    @rbt_ensure_auth
    def set_snmp_password_preencrypted(self, username, digest, auth_protocol):
        """
        set_snmp_password_preencrypted(auth, username, digest, auth_protocol) -> None

        Configure a SNMP user using a pre-encrypted password.

        Parameters:
        username - username of user to configure
        digest - user's pre-encrypted password
        auth_protocol - protocol used to encrypt the password

        Exceptions:
        set_snmp_passwordFault - XXX/BUG 47861/48172 for bad auth_protocol value
        """
        snmp_user_pfx = '/snmp/usm/users/%s' % username
        code, msg = Mgmt.set(
            (snmp_user_pfx, 'string', username),
            (snmp_user_pfx + '/auth_key', 'string', digest),
            (snmp_user_pfx + '/hash_function', 'string', auth_protocol)
            )

        if code != 0:
            raise ServiceError, msg

    def __set_user_password(self, username, password):
        # XXX/jshilkaitis: lame, should be an action on the mgmtd side

        # XXX/jshilkaitis: why doesn't the framework do validation?

        valid_password = common.lc_password_validate(password)

        if not valid_password:
            # XXX/jshilkaitis: hardcode the reason for now, since we know
            # length is the only criterion, but that may not be true in the
            # future.
            raise ServiceError, 'Password must contain at least 6 characters'

        use_sha512 = Mgmt.get_value('/rbt/support/config/sha_password/enable')

        if use_sha512:
            crypted_password = common.sha_encrypt_password(False, password)
        else:
            crypted_password = common.ltc_encrypt_password(password)

        password_node_name = '/auth/passwd/user/%s/password' % username

        code, msg = Mgmt.set((password_node_name, 'string', crypted_password))

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(String, String)
    @rbt_ensure_auth
    def set_user_password(self, username, password):
        """
        set_user_password(auth, username, password) -> None

        Modify the password of an existing user.

        Parameters:
        username (string) - username whose password will be modified
        password (string) - username's new password

        Exceptions:
        set_user_passwordFault - Cannot modify non-existent user
        set_user_passwordFault - Password must contain at least 6 characters
        set_user_passwordFault - Cannot modify another user's password
        """
        existing_user = Mgmt.get_value('/auth/passwd/user/%s/password' %
                                       username)

        if existing_user is None:
            raise ServiceError, \
                  'Cannot modify non-existent user "%s"' % username

        self.__set_user_password(username, password)

    @rbt_soapmethod(String, String)
    @rbt_ensure_auth
    def add_user(self, username, password):
        """
        add_user(auth, username, password) -> None

        Add a new RBM user to the system.

        Parameters:
        username (string) - username to be added
        password (string) - username's password

        Exceptions:
        add_userFault - Password must contain at least 6 characters
        """
        self.__set_user_password(username, password)

    @rbt_soapmethod(String)
    @rbt_ensure_auth
    def delete_user(self, username):
        """
        delete_user(auth, username) -> None

        Remove an existing user.

        Parameters:
        username (string) - username to be deleted

        Exceptions: None
        """
        code, msg = Mgmt.delete('/auth/passwd/user/%s' % username)

        if code != 0:
            raise ServiceError, msg

    # XXX/jshilkaitis: need an easy-to-express way to auto-generate these
    # simple set RPC calls.
    def __set_banner(self, node_list, motd):
        """Helper function for setting motd/login banner"""
        nodes_to_set = [(x, 'string', motd) for x in node_list]
        code, msg = Mgmt.set(*nodes_to_set)

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(String)
    @rbt_ensure_auth
    def set_motd(self, banner):
        """
        set_motd(auth, banner) -> None

        Set the message of the day.

        Parameters:
        banner (string) - message of the day

        Exceptions: None
        """
        self.__set_banner(['/system/motd'], banner)

    @rbt_soapmethod(String)
    @rbt_ensure_auth
    def set_login_local_banner(self, banner):
        """
        set_login_local_banner(auth, banner) -> None

        Set the local login banner.

        Parameters:
        banner (string) - local login banner

        Exceptions: None
        """
        self.__set_banner(['/system/issue'], banner)

    @rbt_soapmethod(String)
    @rbt_ensure_auth
    def set_login_remote_banner(self, banner):
        """
        set_login_remote_banner(auth, banner) -> None

        Set the remote login banner.

        Parameters:
        banner (string) - remote login banner

        Exceptions: None
        """
        self.__set_banner(['/system/issue_net'], banner)

    @rbt_soapmethod(String)
    @rbt_ensure_auth
    def set_logging_level(self, level):
        """
        set_logging_level(auth, level) -> None

        Set the minimum logging level.

        Parameters:
        level (string) - logging level to set

        Exceptions: None
        """
        level = level.lower()

        code, msg = Mgmt.set(('/logging/syslog/action/file/\/var\/log\/messages/selector/0/priority', 'string', level))

        if code != 0:
            raise ServiceError, msg

    def __assert_alarm_exists(self, alarm):
        alarm_exists = Mgmt.get_value('/stats/config/alarm/%s/enable' % alarm)

        if alarm_exists is None:
            raise ServiceError, 'Alarm %s does not exist' % alarm


    @rbt_soapmethod(String, Boolean)
    @rbt_ensure_auth
    def enable_alarm(self, alarm, enable):
        """
        enable_alarm(auth, alarm, enable) -> None

        Turn an alarm on or off.

        Parameters:
        alarm (string) - name of the alarm to change
        enable (bool) - true to enable alarm, false to disable alarm

        Exceptions:
        enable_alarmFault - Alarm does not exist
        """
        alarm = alarm.lower()

        self.__assert_alarm_exists(alarm)

        code, msg = Mgmt.set(
            ('/stats/config/alarm/%s/enable' % alarm, 'bool', enable))

        if code != 0:
            raise ServiceError, msg

    def __set_alarm_threshold(self, alarm, rising_or_falling,
                              error_or_clear, val):
        alarm = alarm.lower()
        rising_or_falling = rising_or_falling.lower()
        error_or_clear = error_or_clear.lower()

        self.__assert_alarm_exists(alarm)

        node_name = '/stats/config/alarm/%s/%s/%s_threshold' % \
                    (alarm, rising_or_falling, error_or_clear)

        # should never fail because we ensure that the alarm exists
        node_type = Mgmt.query(node_name)[0][1]

        code, msg = Mgmt.set((node_name, node_type, val))

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(String, String)
    @rbt_ensure_auth
    def set_alarm_rising_error_threshold(self, alarm, val):
        """
        set_alarm_rising_error_threshold(auth, alarm, val) -> None

        Set an alarm's rising error threshold.

        Parameters:
        alarm (string) - name of the alarm to change
        val (any) - new value for the alarm's rising error threshold

        Exceptions:
        set_alarm_rising_error_thresholdFault - Alarm does not exist
        """
        self.__set_alarm_threshold(alarm, 'rising', 'error', val)

    @rbt_soapmethod(String, String)
    @rbt_ensure_auth
    def set_alarm_rising_clear_threshold(self, alarm, val):
        """
        set_alarm_rising_clear_threshold(auth, alarm, val) -> None

        Set an alarm's rising clear threshold.

        Parameters:
        alarm (string) - name of the alarm to change
        val (any) - new value for the alarm's rising clear threshold

        Exceptions:
        set_alarm_rising_clear_thresholdFault - Alarm does not exist
        """
        self.__set_alarm_threshold(alarm, 'rising', 'clear', val)

    @rbt_soapmethod(String, String)
    @rbt_ensure_auth
    def set_alarm_falling_error_threshold(self, alarm, val):
        """
        set_alarm_falling_error_threshold(auth, alarm, val) -> None

        Set an alarm's falling error threshold.

        Parameters:
        alarm (string) - name of the alarm to change
        val (any) - new value for the alarm's falling error threshold

        Exceptions:
        set_alarm_falling_error_thresholdFault - Alarm does not exist
        """
        self.__set_alarm_threshold(alarm, 'falling', 'error', val)

    @rbt_soapmethod(String, String)
    @rbt_ensure_auth
    def set_alarm_falling_clear_threshold(self, alarm, val):
        """
        set_alarm_falling_clear_threshold(auth, alarm, val) -> None

        Set an alarm's falling clear threshold.

        Parameters:
        alarm (string) - name of the alarm to change
        val (any) - new value for the alarm's falling clear threshold

        Exceptions:
        set_alarm_falling_clear_thresholdFault - Alarm does not exist
        """
        self.__set_alarm_threshold(alarm, 'falling', 'clear', val)

    @rbt_soapmethod(String, _returns=String)
    @rbt_ensure_auth
    def get_alarm_status(self, alarm):
        """
        get_alarm_status(auth, alarm) -> string

        Get an alarm's status.

        Parameters:
        alarm (string) - name of the alarm whose status will be returned

        Exceptions:
        get_alarm_statusFault - Alarm does not exist
        get_alarm_statusFault - Server Error.  Contact Support.
        """
        alarm = alarm.lower()

        alarm_enabled = Mgmt.get_value('/stats/config/alarm/%s/enable'
                                       % alarm)

        if alarm_enabled is None:
            raise ServiceError, 'Alarm %s does not exist' % alarm
        elif alarm_enabled == 'false':
            return 'disabled'
        elif alarm_enabled == 'true':
            # XXX/jshilkaitis: use mdc_iterate_binding_pattern one day, but
            # need to expose it first, and since it's non-trivial, I'm
            # punting on that for now.
            alarm_pfx = '/stats/state/alarm/' + alarm
            alarm_nodes = Mgmt.iterate(alarm_pfx, subtree=True)

            for node in alarm_nodes:
                if ((Mgmt.bn_name_pattern_match(
                    node[0], alarm_pfx + '/node/*/rising/error') or
                     Mgmt.bn_name_pattern_match(
                    node[0], alarm_pfx + '/node/*/falling/error')) and
                    node[2] == 'true'):
                    return 'ERROR'
        else:
            raise ServiceError, 'Server error. Contact Support.'

        return 'ok'

    # I figure it's worth justifying the use of target_url here, since,
    # at the time of this writing, no other APIs use it.  This API call
    # uses target_url because giving raw config data back to the user
    # in the form of a SOAP Attachment doesn't make much sense. I can't
    # think of a single useful thing that a user could do with the
    # data besides save it directly to a file, which is exactly what
    # target_url lets this function do.
    @rbt_soapmethod(String, String)
    @rbt_ensure_auth
    def get_config(self, config_name, target_url):
        """
        get_config(config_name, target_url) -> None

        Download a configuration to the location specified by target_url.

        Parameters:
        config_name (string) - name of config to download
        target_url (string) - location to which the config will be downloaded

        Exceptions:
        get_configFault - database file does not exist
        get_configFault - unsupported transfer protocol (scp/ftp support only)
        get_configFault - upload failed for unknown reasons.  Check logs.
        """
        code, msg, bindings = Mgmt.action('/mgmtd/db/upload',
                                          ('db_name', 'string', config_name),
                                          ('remote_url', 'string', target_url))

        if code != 0:
            raise ServiceError, msg

    # XXX/jshilkaitis: refactor this TCPdump stuff
    @rbt_soapmethod(String, String, Integer, Integer)
    @rbt_ensure_auth
    def start_tcpdump(self, interfaces, filename, duration, max_size):
        """
        start_tcpdump(auth, interfaces, filename, duration, max_size) -> None

        Start a TCP dump.

        Parameters:
        interfaces (string): comma-separated list of interfaces or 'all'
        filename (string): id string added to the boilerplate capture name
        duration (int): maximum number of seconds that the capture will run or
                        0 to run until stop_tcpdump is called
        max_size (int): maximum size, in megabytes, of capture file.  Settimg
                        this to 0 causes the system default size to be used.

        Exceptions:
        start_tcpdumpFault - Invalid capture name
        start_tcpdumpFault - Invalid interfaces
        start_tcpdumpFault - Capture name too long
        start_tcpdumpFault - Duplicate interface name
        start_tcpdumpFault - No valid interfaces provided
        start_tcpdumpFault - Invalid file name (same as invalid capture name)

        """
        if filename.find('..') != -1:
            raise ServiceError("filename %s must not contain '..'" % filename)

        action_params = []

        if interfaces == 'all':
            action_params.append(('all_interfaces', 'bool', 'true'))
        else:
            for iface in interfaces.split(','):
                action_params.append(('interface', 'string', iface))

        action_params.append(('cap_name', 'string', filename))
        action_params.append(('duration', 'duration_sec', duration))
        action_params.append(('file_size', 'uint32', max_size))

        code, msg, bindings = Mgmt.action('/rbt/tcpdump/action/start',
                                          action_params)

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(String)
    @rbt_ensure_auth
    def stop_tcpdump(self, filename):
        """
        stop_tcpdump(auth, filename) -> None


        Stop a TCP dump

        Parameter:
        filename (string): name of capture to stop.  This should be the same
                           as the filename parameter passed to start_tcpdump
                           or schedule_tcpdump.

        Exceptions:
        stop_tcpdumpFault - Unknown capture name
        """
        code, msg, bindings = Mgmt.action('/rbt/tcpdump/action/stop',
                                          ('cap_name', 'string', filename))

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(String, String, Integer, DateTime, Integer)
    @rbt_ensure_auth
    def schedule_tcpdump(self, interfaces, filename, duration, date_and_time,
                         max_size):
        """
        schedule_tcpdump(auth, interfaces, filename, duration, date_and_time,
                         max_size) -> None

        Schedule a TCP dump to run at a later time.

        Parameters:
        interfaces (string): comma-separated list of interfaces or 'all'
        filename (string): id string added to the boilerplate TCP dump name
        duration (int): maximum number of seconds that the capture will run or
                        0 to run until stop_tcpdump is called
        date_and_time (datetime): date and time to start the TCP dump
        max_size (int): maximum size, in megabytes, of capture file.  Settimg
                        this to 0 causes the system default size to be used.

        Exceptions:
        schedule_tcpdumpFault - Invalid capture name
        schedule_tcpdumpFault - Invalid interfaces
        schedule_tcpdumpFault - Capture name too long
        schedule_tcpdumpFault - Duplicate interface name
        schedule_tcpdumpFault - No valid interfaces provided
        schedule_tcpdumpFault - Invalid file name (same as invalid capture name)
        schedule_tcpdumpFault - Invalid date or time
        """
        if filename.find('..') != -1:
            raise ServiceError("filename %s must not contain '..'" % filename)

        action_params = []

        if interfaces == 'all':
            action_params.append(('all_interfaces', 'bool', 'true'))
        else:
            for iface in interfaces.split(','):
                action_params.append(('interface', 'string', iface))

        action_params.append(('cap_name', 'string', filename))
        action_params.append(('duration', 'duration_sec', duration))
        action_params.append(('file_size', 'uint32', max_size))

        date_and_time = time_to_local_time(date_and_time)
        dump_date, dump_time = date_and_time.split()

        action_params.append(('sched_time', 'time_sec', dump_time))
        action_params.append(('sched_date', 'date', dump_date))

        code, msg, bindings = Mgmt.action('/rbt/tcpdump/action/start',
                                          action_params)

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(String, _returns=Attachment)
    @rbt_ensure_auth
    def get_tcpdump(self, filename):
        """
        get_tcpdump(auth, filename) -> SOAP attachment

        Fetch a completed TCP dump.

        Parameters:
        filename (string) - name of the TCP dump to fetch

        Exceptions:
        get_tcpdumpFault - Invalid filename
        """
        if filename.find('..') != -1:
            raise ServiceError("filename %s must not contain '..'" % filename)

        check_rbm_permissions("/rbm_fake/debug/generate/tcpdump", RBM_READ)

        full_file_path = '/var/opt/tms/tcpdumps/%s' % filename

        try:
            file(full_file_path)
        except IOError:
            raise ServiceError, "Capture file %s does not exist" % filename

        return Attachment(fileName=full_file_path)

    def __get_logs(self, path, log_index):
        if log_index == 0:
            # save off msg_file path for later deletion by onReturn hook
            self.msg_file = '/var/tmp/tmp_messages.%u.gz' % os.getpid()
            os.system('/usr/bin/gzip -c ' + path + ' > ' + self.msg_file)
            path = self.msg_file
        else:
            path = path + str(log_index) + '.gz'

            try:
                os.stat(path)
            except OSError:
                raise ServiceError, 'Requested log file does not exist'

        return Attachment(fileName=path)


    @rbt_soapmethod(Integer, _returns=Attachment)
    @rbt_ensure_auth
    def get_system_log(self, log_index):
        """
        get_system_log(auth, log_index) -> SOAP attachment

        Fetch a compressed system log.

        Parameters:
        log_index (int) - index of log to return (0 for current log file)

        Exceptions:
        get_system_logFault - Log file does not exist
        """
        check_rbm_permissions('/rbm_fake/logging/syslog/action/file/\\/var\\/log\\/messages/download', RBM_READ)

        return self.__get_logs('/var/log/messages', log_index)

    @rbt_soapmethod(Integer, _returns=Attachment)
    @rbt_ensure_auth
    def get_user_log(self, log_index):
        """
        get_user_log(auth, log_index) -> SOAP attachment

        Fetch a compressed user log.

        Parameters:
        log_index (int) - index of log to return (0 for current log file)

        Exceptions:
        get_user_logFault - Log file does not exist
        """
        check_rbm_permissions('/rbm_fake/logging/syslog/action/file/\\/var\\/log\\/user_messages/download', RBM_READ)

        return self.__get_logs('/var/log/user_messages', log_index)


    def get_stats_internal(self, report_name, num_sets, start_time, end_time,
                    subclass=None):

        start_time = time_to_local_time(start_time)
        end_time = time_to_local_time(end_time)

        bns = [('time_lb', 'datetime_sec', start_time),
               ('time_ub', 'datetime_sec', end_time)]

        if subclass is not None:
            bns.append(('subclass', 'uint32', subclass))

        code, msg, bindings = Mgmt.action(
            '/stats/actions/generate_report/%s' % report_name,
            *bns
            )

        if code != 0:
            raise ServiceError, msg

        # save off the file name so we can remove it in self.onReturn()
        results = bindings['results']

        res = bulk_stats.bsp_to_data_val_sets(results, num_sets)

        return res

    @rbt_soapmethod(DateTime, DateTime, Integer, _returns=StatsArray)
    @rbt_ensure_auth
    def get_cpu_stats(self, start_time, end_time, cpu_num):
        """
        get_cpu_stats(auth, start_time, end_time, cpu_num) ->
        [
            [cpu utilization datapoints]
        ]

        Fetch the system's CPU utilization statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        cpu_num (integer) - ID of the cpu whose stats are desired

        Exceptions:
        get_cpu_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('cpu_utilization', 1,
                                       start_time, end_time, cpu_num)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_paging_stats(self, start_time, end_time):
        """
        get_paging_stats(auth, start_time, end_time) ->
        [
            [paging datapoints]
        ]

        Fetch the system's memory paging statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_paging_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('paging', 1, start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_memory_stats(self, start_time, end_time):
        """
        get_memory_stats(auth, start_time, end_time) ->
        [
            [physical memory datapoints]
        ]

        Fetch the system's physical memory statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_memory_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('physical_memory', 1,
                                       start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_swap_stats(self, start_time, end_time):
        """
        get_memory_stats(auth, start_time, end_time) ->
        [
            [swap datapoints]
        ]

        Fetch the system's swap statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_swap_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('swap_memory', 1, start_time, end_time)

    @soapmethod(_returns=Integer)
    # This function should not require auth.  See bug 52587
    def get_wsdl_version(self):
        """
        get_wsdl_version() -> int

        Return the SOAP server's WSDL version.  This is used to check
        client/server compatibility.

        Parameters: None

        Exceptions: None

        NOTE: This function should be overwritten by a product-side function
        with the same name that adds the framework wsdl version number to
        the product-specific wsdl version number in order to get a per-product
        wsdl version number that will increase given either a framework change
        or a product-side change.
        """
        return FRAMEWORK_WSDL_VERSION

service = FrameworkService
