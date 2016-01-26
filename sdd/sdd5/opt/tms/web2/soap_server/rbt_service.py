# Filename:  $Source$
# Revision:  $Revision: 67531 $
# Date:      $Date: 2010-07-08 16:02:16 -0700 (Thu, 08 Jul 2010) $
# Author:    $Author: jshilkaitis $
#
# (C) Copyright 2003-2007 Riverbed Technology, Inc. 
# All Rights Reserved. Confidential.

'$Id: rbt_service.py 67531 2010-07-08 23:02:16Z jshilkaitis $'

import fwk_service
from soaplib.wsgi_soap import SimpleWSGISoapApp
from soaplib.service import soapmethod
from soaplib.serializers.primitive import *
from soaplib.serializers.binary import Attachment
from service_utils import rbt_ensure_auth, rbt_soapmethod, ServiceError, StatsArray, Datapoint, TopConversation, TopSrcHost, TopDestHost, TopApplication, check_rbm_permissions, RBM_WRITE, RBM_READ, RBM_ACTION
import Mgmt
import common
import os

# NOTE: The WSDL revision must be incremented on ANY change to the
# SteelheadService interface.  This includes addition/removal of entire
# API calls and changes to parameters of existing API calls.  The WSDL revision
# must also be bumped by a significant number (e.g. 1000) for new major/minor
# releases for reasons similar to why we leave gaps in mgmtd module numbers.

SH_WSDL_VERSION = 1001

class SteelheadService(fwk_service.FrameworkService, SimpleWSGISoapApp):
    """
    Class implementing all Steelhead-specific SOAP server RPC calls.
    """

    def __start_sport(self):
        val = Mgmt.get_value('/pm/monitor/process/sport/state')

        if val is None:
            raise ServiceError, "Could not determine the service's state"

        if val != 'running':
            code, msg, bindings = Mgmt.action(
                '/rbt/sport/main/action/restart_service')

            if code != 0:
                raise ServiceError, msg

    def __stop_sport(self):
        val = Mgmt.get_value('/pm/monitor/process/sport/state')

        if val is None:
            raise ServiceError, "Could not determine the service's state"

        if val == 'running':
            code, msg, bindings = Mgmt.action(
                '/rbt/sport/status/action/unset_restart_needed')

            if code != 0:
                raise ServiceError, msg

            code, msg, bindings = Mgmt.action(
                '/pm/actions/terminate_process',
                ('process_name', 'string', 'sport'))

            if code != 0:
                raise ServiceError, msg

            # XXX/jshilkaitis: cr_stop waits for sport to stop running for
            # some reason.  It's difficult to do that here because the CLI
            # can provide feedback during the wait, while the SOAP server
            # can not.  Some limited testing shows that sport does the right
            # thing if given a stop, immediately followed by the start, so
            # apparently the waiting is just aesthetic.


    # modeled after cr_start in cli_rbt_service_cmds.c
    @rbt_soapmethod()
    @rbt_ensure_auth
    def start_optimization_service(self):
        """
        start_optimization_service(auth) -> None

        Start the optimization service.

        Exceptions:
        start_optimization_serviceFault - Could not determine service state
        """
        self.__start_sport()

    # modeled after cr_stop in cli_rbt_service_cmds.c
    @rbt_soapmethod()
    @rbt_ensure_auth
    def stop_optimization_service(self):
        """
        stop_optimization_service(auth) -> None

        Stop the optimization service.

        Exceptions:
        stop_optimization_serviceFault - Could not determine service state
        """
        self.__stop_sport()

    @rbt_soapmethod(Boolean)
    @rbt_ensure_auth
    def restart_optimization_service(self, clean_datastore):
        """
        start_optimization_service(auth, clean_datastore) -> None

        Restart the optimization service, potentially cleaning the Data Store.

        Parameters:
        clean_datastore (bool) - true to clean the datastore,
                                 false to leave the datastore as is

        Exceptions:
        restart_optimization_serviceFault - Could not determine service state
        """
        self.__stop_sport()

        if clean_datastore:
            # XXX/jshilkaitis: should we error if "touch" fails?
            file('/var/opt/rbt/.clean', 'w') # approximates /bin/touch
            file('/var/opt/rbt/.datastore_notif', 'w')

            try:
                os.stat('/var/opt/rbt/.gen_store_id')
            except:
                pass
            else:
                code, msg, bindings = Mgmt.action(
                    '/rbt/sport/datastore/action/generate_store_id')

                if code != 0:
                    raise ServiceError, msg
        else:
            try:
                os.remove('/var/opt/rbt/.gen_store_id')
            except:
                pass

        self.__start_sport()

    @rbt_soapmethod(Boolean)
    @rbt_ensure_auth
    def enable_rsp(self, enable):
        """
        enable_rsp(auth, enable) -> None

        Turn RSP on and off.

        Parameters:
        enable (bool) - true to turn on RSP, false to turn off RSP

        Exceptions:
        enable_rspFault - RSP not supported
        enable_rspFault - RSP not installed
        enable_rspFault - installed RSP release is not supported
        enable_rspFault - RSP not fully shut down
        """
        code, msg = Mgmt.set(
            ('/rbt/rsp2/config/enable', 'bool', enable)
            )

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(DateTime, DateTime, Integer, _returns=StatsArray)
    @rbt_ensure_auth
    def get_bandwidth_optimization_stats(self, start_time, end_time, port):
        # XXX/jshilkaitis: in and out from the perspective of the client or
        # server, not from the SH's persepective.
        """
        get_bandwidth_optimization_stats(auth, start_time, end_time, port) ->
        [
            [WAN-side inbound bytes],
            [WAN-side outbound bytes],
            [LAN-side inbound bytes],
            [LAN-side outbound bytes]
        ]

        Fetch the system's bandwidth optimization statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        port (integer) - any port in the range [1-65535] or 0 for the
                         sum of all ports

        Exceptions:
        get_bandwidth_optimization_statsFault - Datetime not in known format
        get_bandwidth_optimization_statsFault - Invalid port
        """
        # XXX/TODO: should be a CLIENT type error
        if 0 > port or port > (2**16 - 1):
            raise ServiceError, 'Port must be in the range [0, 65535]'

        return self.get_stats_internal('bw_optimization', 4,
                                       start_time, end_time, port)

    @rbt_soapmethod(DateTime, DateTime, Integer, _returns=StatsArray)
    @rbt_ensure_auth
    def get_throughput_max_stats(self, start_time, end_time, port):
        # XXX/jshilkaitis: in and out from the perspective of the client or
        # server, not from the SH's persepective.
        """
        get_throughput_max_stats(auth, start_time, end_time, port) ->
        [
            [WAN-side inbound bytes],
            [WAN-side outbound bytes],
            [LAN-side inbound bytes],
            [LAN-side outbound bytes]
        ]

        Fetch the system's maximum (peak) throughput statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        port (integer) - any port in the range [1-65535] or 0 for the
                         sum of all ports

        Exceptions:
        get_throughput_max_statsFault - Datetime not in known format
        get_throughput_max_statsFault - Invalid port
        """
        # XXX/TODO: should be a CLIENT type error
        if 0 > port or port > (2**16 - 1):
            raise ServiceError, 'Port must be in the range [0, 65535]'

        return self.get_stats_internal('th_max', 4, start_time, end_time, port)

    @rbt_soapmethod(DateTime, DateTime, Integer, _returns=StatsArray)
    @rbt_ensure_auth
    def get_throughput_p95_stats(self, start_time, end_time, port):
        # XXX/jshilkaitis: in and out from the perspective of the client or
        # server, not from the SH's persepective.
        """
        get_throughput_p95_stats(auth, start_time, end_time, port) ->
        [
            [WAN-side inbound bytes],
            [WAN-side outbound bytes],
            [LAN-side inbound bytes],
            [LAN-side outbound bytes]
        ]

        Fetch the system's p95 throughput statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        port (integer) - any port in the range [1-65535] or 0 for the
                         sum of all ports

        Exceptions:
        get_throughput_p95_statsFault - Datetime not in known format
        get_throughput_p95_statsFault - Invalid port
        """
        # XXX/TODO: should be a CLIENT type error
        if 0 > port or port > (2**16 - 1):
            raise ServiceError, 'Port must be in the range [0, 65535]'

        return self.get_stats_internal('th_p95', 4, start_time, end_time, port)

    @rbt_soapmethod(DateTime, DateTime, Integer, _returns=StatsArray)
    @rbt_ensure_auth
    def get_passthrough_stats(self, start_time, end_time, port):
        """
        get_passthrough_stats(auth, start_time, end_time, port) ->
        [
            [passthrough bytes]
        ]

        Fetch the system's passthrough statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        port (integer) - any port in the range [1-65535] or 0 for the
                         sum of all ports

        Exceptions:
        get_passthrough_statsFault - Datetime not in known format
        get_passthrough_statsFault - Invalid port
        """
        # XXX/TODO: should be a CLIENT type error
        if 0 > port or port > (2**16 - 1):
            raise ServiceError, 'Port must be in the range [0, 65535]'

        return self.get_stats_internal('passthrough', 1,
                                       start_time, end_time, port)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_conn_pooling_stats(self, start_time, end_time):
        """
        get_conn_pooling_stats(auth, start_time, end_time) ->
        [
            [total connection requests],
            [reused connections]
        ]

        Fetch the system's connection pooling statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_conn_pooling_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('conn_pooling', 2, start_time, end_time)

    # XXX/TODO: explicit IpAddress serializer? use string for now
    @rbt_soapmethod(DateTime, DateTime, String, _returns=StatsArray)
    @rbt_ensure_auth
    def get_nfs_stats(self, start_time, end_time, server_ip):
        """
        get_nfs_stats(auth, start_time, end_time, server_ip) ->
        [
            [local responses],
            [delayed responses],
            [remote responses],
            [total calls]
        ]

        Fetch the system's NFS statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        server_ip (string) - IP address of the server whose stats are desired
                             or 'all' or '0.0.0.0' for the sum of all servers

        Exceptions:
        get_nfs_statsFault - Datetime not in known format
        get_nfs_statsFault - Invalid server IP
        """
        if server_ip == 'all':
            server_ip_int = 0
        else:
            try:
                server_ip_int = common.lc_str_to_ipv4addr(server_ip)
            except:
                raise ServiceError, "Invalid IP address: '%s'" % server_ip

        return self.get_stats_internal('nfs', 4,
                                       start_time, end_time, server_ip_int)

    @rbt_soapmethod(DateTime, DateTime, String, _returns=StatsArray)
    @rbt_ensure_auth
    def get_pfs_stats(self, start_time, end_time, share_name):
        """
        get_pfs_stats(auth, start_time, end_time, share_name) ->
        [
            [share size],
            [bytes received],
            [bytes sent]
        ]

        Fetch the system's PFS statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        share_name (string) - share whose stats are desired or 'all' for the
                               sum of all shares

        Exceptions:
        get_pfs_statsFault - Datetime not in known format
        get_pfs_statsFault - Unknown share name
        """
        if share_name == 'all':
            share_id = 0
        else:
            share_id = Mgmt.get_value('/rbt/rcu/share/%s/config/id'
                                      % share_name)

            if share_id is None:
                raise ServiceError, 'Unknown share name: %s' % share_name

        return self.get_stats_internal('pfs', 3,
                                       start_time, end_time, share_id)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_opt_conn_history_max_stats(self, start_time, end_time):
        """
        get_opt_conn_history_max_stats(auth, start_time, end_time) ->
        [
            [optimized connections],
            [half-open connections],
            [half-closed connections],
            [flowing connections]
        ]

        Fetch the system's maximum (peak) optimized connection history
        statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_opt_conn_history_max_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('opt_conn_history_max', 4,
                                       start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_opt_conn_history_sum_stats(self, start_time, end_time):
        """
        get_opt_conn_history_sum_stats(auth, start_time, end_time) ->
        [
            [optimized connections],
            [half-open connections],
            [half-closed connections],
            [flowing connections]
        ]

        Fetch the system's summed optimized connection history statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_opt_conn_history_sum_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('opt_conn_history_sum', 4,
                                       start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_pass_conn_history_max_stats(self, start_time, end_time):
        """
        get_pass_conn_history_max_stats(auth, start_time, end_time) ->
        [
            [optimized connections],
            [passthrough connections],
            [active connections],
            [forwarded connections]
        ]

        Fetch the system's maximum (peak) passthrough connection history
        statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_pass_conn_history_max_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('pass_conn_history_max', 4,
                                       start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_pass_conn_history_sum_stats(self, start_time, end_time):
        """
        get_pass_conn_history_sum_stats(auth, start_time, end_time) ->
        [
            [optimized connections],
            [passthrough connections],
            [active connections],
            [forwarded connections]
        ]

        Fetch the system's summed passthrough connection history statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_pass_conn_history_sum_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('pass_conn_history_sum', 4,
                                       start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_datastore_hits_stats(self, start_time, end_time):
        """
        get_datastore_hits_stats(auth, start_time, end_time) ->
        [
            [datastore hits],
            [datastore misses]
        ]

        Fetch the system's datastore hits statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_datastore_hits_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('datastore_hits', 2,
                                       start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_ssl_sum_stats(self, start_time, end_time):
        """
        get_ssl_sum_stats(auth, start_time, end_time) ->
        [
            [total session requests],
            [established sessions]
        ]

        Fetch the system's average ssl statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_ssl_sum_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('ssl_sum', 2, start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_ssl_max_stats(self, start_time, end_time):
        """
        get_ssl_max_stats(auth, start_time, end_time) ->
        [
            [total session requests],
            [established sessions]
        ]

        Fetch the system's maximum (peak) ssl statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_ssl_max_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('ssl_max', 2, start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_http_request_stats(self, start_time, end_time):
        """
        get_http_request_stats(auth, start_time, end_time) ->
        [
            [page requests],
            [pages optimized]
        ]

        Fetch the system's http request statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_http_request_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('http_requests', 2,
                                       start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_http_prefetch_stats(self, start_time, end_time):
        # XXX/jshilkaitis: need to update this to handle bug 42943,
        # prefetch subclass ID change
        """
        get_http_prefetch_stats(auth, start_time, end_time) ->
        [
            [parse-and-prefetch hits],
            [misses],
            [metadata cache hits],
            [url-learning hits]
        ]

        Fetch the system's http prefetch statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_http_prefetch_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('http_prefetch', 4,
                                       start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, String, _returns=StatsArray)
    @rbt_ensure_auth
    def get_qos_stats(self, start_time, end_time, qos_class):
        """
        get_passthrough_stats(auth, start_time, end_time, qos_class) ->
        [
            [packets sent],
            [packets dropped],
            [bits sent],
            [bits dropped]
        ]

        Fetch the system's QoS statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        qos_class (string) - name of qos class whose stats are desired
                             or 'all'

        Exceptions:
        get_qos_statsFault - Datetime not in known format
        get_qos_statsFault - QoS class does not exist
        get_qos_statsFault - Internal error.  Failed to map class to id.
        """
        classid = None

        # the default class is guaranteed to exist, so this is always safe
        check_rbm_permissions('/rbt/hfsc/config/class/default/params/classid',
                              RBM_READ)

        if qos_class == 'all':
            classid = "0"
        # elif qos_class == 'unknown':
            # XXX/jshilkaitis: figure out how to deal with this
            # pass
        else:
            # convert class name to class id
            classid = Mgmt.get_value('/rbt/hfsc/config/class/%s/params/classid'
                                     % qos_class)

        if classid is None:
            raise ServiceError, 'QoS class "%s" does not exist' % qos_class

        check_rbm_permissions('/rbt/hfsc/action/get_family_ids',
                              RBM_ACTION)

        # handle hierarchical QoS classes
        code, msg, bindings = Mgmt.action('/rbt/hfsc/action/get_family_ids',
                                          ('parent_id', 'uint16', classid))

        if code != 0:
            raise ServiceError, 'Unable to map class name "%s" to class id.' \
                  % qos_class

        if bindings == {}:
            family_ids = classid
        else:
            family_ids = bindings['family_ids']

        data_dict = {0:{}, 1:{}, 2:{}, 3:{}}

        # all datapoints with the same timestamp have equal durations
        gran_dict = {}

        # merge the datapoints for each class into a summary dict
        for cid in family_ids.split(','):
            stats_array = self.get_stats_internal('qos', 4,
                                                  start_time, end_time, cid)

            for i in range(4):
                curr_dict = data_dict[i]
                sub_array = stats_array[i]
                for dp in sub_array:
                    curr_dict[dp.time] = curr_dict.get(dp.time, 0) + dp.value
                    gran_dict[dp.time] = dp.duration

        results = []
        sorted_times = gran_dict.keys()
        sorted_times.sort()

        # turn the summary dict into a list of datapoints, sorted by time
        for i in range(4):
            curr_dict = data_dict[i]
            curr_result_array = []

            for t in sorted_times:
                d = Datapoint()
                d.time = t
                d.value = curr_dict[t]
                d.duration = gran_dict[t]
                curr_result_array.append(d)

            results.append(curr_result_array)

        return results

    @rbt_soapmethod(DateTime, DateTime, Integer, _returns=StatsArray)
    @rbt_ensure_auth
    def get_dns_event_stats(self, start_time, end_time, stat_type):
        """
        get_dns_event_stats(auth, start_time, end_time, stat_type) ->
        [
            [values]
        ]

        Fetch the system's DNS event statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        stat_type (integer) - index of the desired DNS value
                              0: success
                              1: referral
                              2: nxrrset
                              3: nxdomain
                              4: recursion
                              5: failure
                              6: miss

        Exceptions:
        get_dns_event_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('dns_event', 1, start_time, end_time,
                                       stat_type)

    @rbt_soapmethod(DateTime, DateTime, Integer, _returns=StatsArray)
    @rbt_ensure_auth
    def get_dns_value_stats(self, start_time, end_time, stat_type):
        """
        get_dns_value_stats(auth, start_time, end_time, stat_type) ->
        [
            [values]
        ]

        Fetch the system's DNS value statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        stat_type (integer) - index of the desired DNS value
                              0: cache entry count
                              1: cache size in bytes

        Exceptions:
        get_dns_value_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('dns_value', 1, start_time, end_time,
                                       stat_type)

    @rbt_soapmethod(DateTime, DateTime, String, _returns=StatsArray)
    @rbt_ensure_auth
    def get_conn_forwarding_stats(self, start_time, end_time, neighbor_ip):
        """
        get_conn_forwarding_stats(auth, start_time, end_time, neighbor_ip) ->
        [
            [packets sent],
            [bytes sent]
        ]

        Fetch the system's connection forwarding statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        neighbor_ip (string) - IP address of the neighbor whose stats are
                               desired or 'all' or '0.0.0.0' for the sum of
                               all neighbors

        Exceptions:
        get_conn_forwarding_statsFault - Datetime not in known format
        get_conn_forwarding_statsFault - Invalid neighbor address
        """
        if neighbor_ip == 'all':
            neighbor_ip_int = 0
        else:
            try:
                neighbor_ip_int = common.lc_str_to_ipv4addr(neighbor_ip)
            except:
                raise ServiceError, "Invalid IP address: '%s'" % neighbor_ip

        return self.get_stats_internal('neighbor', 2,
                                       start_time, end_time, neighbor_ip_int)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_datastore_read_write_cluster_stats(self, start_time, end_time):
        """
        get_datastore_read_write_cluster_stats(auth, start_time, end_time) ->
        [
            [datastore cluster reads],
            [datastore cluster writes]
        ]

        Fetch the system's Datastore cluster read/write statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_datastore_read_write_cluster_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('rw_cluster', 2, start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_datastore_read_write_page_stats(self, start_time, end_time):
        """
        get_datastore_read_write_page_stats(auth, start_time, end_time) ->
        [
            [datastore page reads],
            [datastore page writes]
        ]

        Fetch the system's Datastore page read/write statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_datastore_read_write_page_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('rw_pages', 2, start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_datastore_segment_cost_stats(self, start_time, end_time):
        """
        get_datastore_segment_cost_stats(auth, start_time, end_time) ->
        [
            [segment cost in milliseconds],
        ]

        Fetch the system's Datastore segment cost statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_datastore_segment_cost_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('segcost', 1, start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_datastore_avg_page_utilization_stats(self, start_time, end_time):
        """
        get_datastore_avg_page_utilization_stats(auth, start_time, end_time) ->
        [
            [average page utilization percentage]
        ]

        Fetch the system's Datastore average page utilization statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_datastore_avg_page_utilization_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('segstore_page_util_avg', 1,
                                start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_datastore_adaptive_sdr_stats(self, start_time, end_time):
        """
        get_datastore_adaptive_sdr_stats(auth, start_time, end_time) ->
        [
            [percentage of time lz compression used]
            [percentage of time lz compression used due to in-path rules]
            [percentage of time in-memory-SDR used]
            [percentage of time in-memory-SDR used due to in-path rules]
        ]

        Fetch the system's Datastore adaptive SDR statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_datastore_adaptive_sdr_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('auto_lz_pct', 4, start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, _returns=StatsArray)
    @rbt_ensure_auth
    def get_datastore_disk_load_stats(self, start_time, end_time):
        """
        get_datastore_disk_load_stats(auth, start_time, end_time) ->
        [
            [load]
        ]

        Fetch the system's Datastore disk load statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period

        Exceptions:
        get_datastore_disk_load_statsFault - Datetime not in known format
        """
        return self.get_stats_internal('disk_load', 1, start_time, end_time)

    @rbt_soapmethod(DateTime, DateTime, String, String, _returns=StatsArray)
    @rbt_ensure_auth
    def get_rsp_vni_stats(self, start_time, end_time, opt_vni, side):
        """
        get_rsp_vni_stats(auth, start_time, end_time, opt_vni, side) ->
        [
            [ingress bytes],
            [egress bytes],
            [ingress packets],
            [egress packets]
        ]

        Fetch the system's RSP VNI statistics.

        Parameters:
        start_time (datetime) - start of the stats query period
        end_time (datetime) - end of the stats query period
        opt_vni (string) - name of vni whose stats are desired
        side (string) - side of the vni whose stats are desired
                        (lan, wan, or pkg)

        Exceptions:
        get_rsp_vni_statsFault - Datetime not in known format
        get_rsp_vni_statsFault - Invalid optimization VNI side
        get_rsp_vni_statsFault - Invalid optimization VNI
        """
        offset_dict = {
            'lan' : 0,
            'wan' : 10,
            'pkg' : 20,
            }

        try:
            offset = offset_dict[side]
        except KeyError:
            raise ServiceError, '%s is not a valid optimization VNI side' % side

        id = Mgmt.get_value('/rbt/rsp2/state/vni/opt/%s/stats_id' % opt_vni)

        if id is None:
            raise ServiceError, '%s is not a valid optimization vni' % opt_vni

        vni_id = int(id) + offset

        return self.get_stats_internal('rsp', 4, start_time, end_time, vni_id)

    def __get_top_talkers_list(self, node_path, value_type):
        """
        Internal function to support top talkers queries.

        Iterate subtree on node_path and use the results to generate
        a result list of value_type instances.
        """
        temp_result = {}

        bindings = Mgmt.iterate(node_path, subtree=True)

        for b in bindings:
            if Mgmt.bn_name_pattern_match(b[0], node_path + '/*/*'):
                parts = Mgmt.bn_name_to_parts(b[0])
                idx = int(parts[3]) - 1 # iterate results are 1-based
                attr_name = parts[4]

                curr_val = temp_result.setdefault(idx, value_type())

                setattr(curr_val, attr_name, b[2])

        return [temp_result[i] for i in xrange(len(temp_result))]

    @rbt_soapmethod(_returns=Array(TopConversation))
    @rbt_ensure_auth
    def get_top_conversations(self):
        """
        get_top_conversations(auth) -> [TopConversation]

        Fetch the system's most recent top conversations snapshot.

        NOTE: Each snapshot covers a 5-minute period if the top talkers
        collection period is 24 hours and a 10-minute period if the
        top talkers collection period is 48 hours.

        Exceptions: None
        """
        return self.__get_top_talkers_list('/stats/state/top_talkers',
                                           TopConversation)

    @rbt_soapmethod(_returns=Array(TopSrcHost))
    @rbt_ensure_auth
    def get_top_senders(self):
        """
        get_top_senders(auth) -> [TopSrcHost]

        Fetch the system's most recent top senders snapshot.

        NOTE: Each snapshot covers a 5-minute period if the top talkers
        collection period is 24 hours and a 10-minute period if the
        top talkers collection period is 48 hours.

        Exceptions: None
        """
        return self.__get_top_talkers_list('/stats/state/top_src_hosts',
                                           TopSrcHost)

    @rbt_soapmethod(_returns=Array(TopDestHost))
    @rbt_ensure_auth
    def get_top_receivers(self):
        """
        get_top_receivers(auth) -> [TopDestHost]

        Fetch the system's most recent top receivers snapshot.

        NOTE: Each snapshot covers a 5-minute period if the top talkers
        collection period is 24 hours and a 10-minute period if the
        top talkers collection period is 48 hours.

        Exceptions: None
        """
        return self.__get_top_talkers_list('/stats/state/top_dest_hosts',
                                           TopDestHost)

    @rbt_soapmethod(_returns=Array(TopApplication))
    @rbt_ensure_auth
    def get_top_applications(self):
        """
        get_top_applications(auth) -> [TopApplication]

        Fetch the system's most recent top applications snapshot.

        NOTE: Each snapshot covers a 5-minute period if the top talkers
        collection period is 24 hours and a 10-minute period if the
        top talkers collection period is 48 hours.

        Exceptions: None
        """
        return self.__get_top_talkers_list('/stats/state/top_app_ports',
                                           TopApplication)

    @rbt_soapmethod(Boolean)
    @rbt_ensure_auth
    def enable_top_talkers(self, enable):
        """
        enable_top_talkers(auth, enable) -> None

        Turn Top Talkers on or off.

        Parameters:
        enable (bool) - true to enable Top Talkers, false to disable Top Talkers

        Exceptions:
        enable_top_talkersFault - NetFlow must be enabled before Top Talkers can be enabled
        """
        code, msg = Mgmt.set(
            ('/rbt/sport/netflow/config/top_talkers/enable', 'bool', enable)
            )

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(Integer)
    @rbt_ensure_auth
    def set_top_talkers_interval(self, interval):
        """
        set_top_talkers_interval(auth, interval) -> None

        Set the Top Talkers collection period.

        Parameters:
        interval (integer) - Interval in hours (must be 24 or 48)

        Exceptions:
        set_top_talkers_intervalFault - Interval must be 24 or 48 hours
        """
        if interval != 24 and interval != 48:
            raise ServiceError, 'Top Talkers interval must be 24 or 48 hours'

        # convert collection period to snapshot interval (24->300, 48->600)
        interval = interval / 24 * 300

        code, msg = Mgmt.set(
            ('/rbt/sport/netflow/config/top_talkers/snapshot_interval',
             'duration_sec', interval)
            )

        if code != 0:
            raise ServiceError, msg

    @rbt_soapmethod(Boolean)
    @rbt_ensure_auth
    def enable_netflow(self, enable):
        """
        enable_netflow(auth, enable) -> None

        Turn NetFlow support on or off.

        Parameters:
        enable (bool) - true to enable NetFlow, false to disable NetFlow

        Exceptions:
        enable_netflow - Top Talkers must be disabled before NetFlow can be disabled
        """
        code, msg = Mgmt.set(
            ('/rbt/sport/netflow/config/enable', 'bool', enable)
            )

        if code != 0:
            raise ServiceError, msg

    @soapmethod(_returns=Integer)
    # This function should not require auth.  See bug 52587
    def get_wsdl_version(self):
        """
        get_wsdl_version() -> int

        Return the SOAP server's WSDL version.  This is used to check
        client/server compatibility.

        Parameters: None

        Exceptions: None
        """
        return fwk_service.FRAMEWORK_WSDL_VERSION + SH_WSDL_VERSION

service = SteelheadService
