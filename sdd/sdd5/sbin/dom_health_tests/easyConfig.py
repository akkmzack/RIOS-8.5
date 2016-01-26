#!/usr/bin/python

# (C) Copyright 2003-2011 Riverbed Technology, Inc.
# All Rights Reserved. Confidential.

import sys
import logging, logging.handlers
import os
import time
import traceback
import subprocess
import signal
from time import gmtime, strftime

class Logger(object):
    """Class to use python logger to log the following types of messages:
    * NOTICE
    * DEBUG
    * INFO
    * ERROR
    * WARN
    * CRITICAL
    * ALERT
    * EMERGENCY
    Subclasses can use the following methods
    notice()
    debug()
    info()
    error()
    warn()
    alert()
    emergency()
    """
    def __init__(self,name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        logging.addLevelName(29, "NOTICE")
        logging.addLevelName(51, "ALERT")
        logging.addLevelName(52, "EMERGENCY")
    
    def notice (self, msg):
        """Log a notice message
        """
        self.logger.log(29, msg)

    def debug(self, msg):
        """Log a debug message
        """
        self.logger.debug (msg)

    def info (self, msg):
        """Log an info message
        """
        self.logger.info (msg)

    def error(self, msg):
        """Log an error message
        """
        self.logger.error (msg)

    def warn (self, msg):
        """Log a warning message
        """
        self.logger.warn (msg)

    def critical (self, msg):
        """Log a critical message
        """
        self.logger.critical (msg)

    def alert (self, msg):
        """Log an alert message
        """
        self.logger.log(51, msg)

    def emergency (self, msg):
        """Log an emergency message
        """
        self.logger.log(52,msg)


class SysLogger(Logger):
    """Class to log messages to syslog
    """
    def __init__(self,name):
        """takes an argument 'name' to be used as Logger name
        """
        self.logger = logging.getLogger(name)
        hdlr        = logging.handlers.SysLogHandler("/dev/log")
        formatter   = logging.Formatter('%(name)s[%(process)d]: [%(name)s.%(levelname)s]: %(message)s')
        hdlr.setFormatter(formatter)
        self.logger.addHandler(hdlr)
        self.logger.setLevel(logging.INFO)
    
class CustomLogger(Logger):
    """Class to log messages to specified log file
    the file gets rolled over everytime an instance of this class is
    instantiated , and logs from last 5 instantiations are saved.
    """
    def __init__(self,name,logfile,loglevel='INFO'):
        """takes two arguments 
        name    -> Logger name
        logfile -> name of file we want to log to
        """
        rollover     = False
        if os.path.isfile(logfile):
            rollover = True

        self.logger  = logging.getLogger(name)
        datefmt      = '%b %d %H:%M:%S' 
        format       = logging.Formatter('[%(asctime)s %(process)d  -1 %(name)s %(levelname)s] {- -}  %(message)s', datefmt)
        hdlr         = logging.handlers.RotatingFileHandler(logfile, backupCount=5) 
        hdlr.setFormatter(format)

        if rollover:
            hdlr.doRollover()

        self.logger.addHandler(hdlr)
        logging.addLevelName(29, "NOTICE")
        
        level = logging.DEBUG
        loglevel_map = { 'DEBUG'     : logging.DEBUG,
                         'INFO'      : logging.INFO,
                         'NOTICE'    : 29,
                         'WARNING'   : logging.WARNING,
                         'CRIT'      : logging.CRITICAL,
                         'ERR'       : logging.ERROR,
                         'ALERT'     : 51,
                         'EMERG'     : 52} 
        if loglevel.upper() in loglevel_map:
            level = loglevel_map[loglevel.upper()]

        self.logger.setLevel(level)


class TimeoutFunctionException(Exception): 
    """Exception to raise on a timeout""" 
    pass 

class TimeoutFunction(object): 
    """Class to issue a timeout signal after a specified function has been 
    polled on for a specified time
    """
    def __init__(self, function_name, timeout_value=60, poll_interval=1, is_cmdexec=False): 
        """Initialize the Timeout object

        takes three arguments
          function_name -> name of function to timeout on
          timeout_value -> value in seconds that we want the function to run
                           before the function timesout
          poll_interval -> interval in seconds to poll the function on,
          is_cmdexec    -> True if its a command that needs to be 
                           executed using using the subprocess module
    
        """
        self.function_name = function_name 
        self.timeout_value = timeout_value
        self.endtime       = time.time() + timeout_value
        self.poll_interval = poll_interval
        self.is_cmdexec    = is_cmdexec

    
    def __call__(self, *args, **kwargs): 
        """signals alarm on timeout"""
        poll_func = self.function_name
        ret_code = 0
        error = ''
        output = ''
        process = None
        if self.is_cmdexec:
            command = self.function_name.split()
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            poll_func = getattr(process, 'poll')
        while poll_func() == None :
            if time.time() >= self.endtime :
                if self.is_cmdexec :
                    process.kill()
                    os.waitpid(-1, os.WNOHANG)
                raise TimeoutFunctionException()
            time.sleep(self.poll_interval)
        if self.is_cmdexec :
            ret_code = process.returncode
            output, error = process.communicate()
        return ret_code, output, error 

class Test(object):
    """provides a set of static and member functions to be universally used
    by Classes who inherit from Test

    Any invoked run() of a test returns an error code
    3 error codes are defined
        0 indicates success
        1 indicates failure
        2 indicates invalid parameters
    NOTE: You have to initialize a python Mgmt session using open()
    This must be done before issuing any Mgmt requests.
    """
    success, error, invalid  = 0, 1, 2 

    def __init__(self, log_handle=None, name='domaind/easy_config'):
        """Initialize the Test object.
        
        Subclasses should override this function if they have any additional
        state that needs to be initialized.
        """
        self.result = ''

        if isinstance(log_handle, CustomLogger):
            self.log_file = log_handle
        else :
            self.log_file = SysLogger(name)

    @staticmethod
    def strequal_ic(str1,str2):
        """do a case insensitive string compare on 2 strings
        takes 2 arguments:
            str1 -> string 1
            str2 -> string 2
        returns:
            (isequal) -> True if the 2 strings are equal and false otherwise
        """
        return str1.upper() == str2.upper()
    
             
    @staticmethod
    def get_node_value(node_name):
        """get value of a specified node
        
        takes one argument:
            node_name -> name of the node you want the value of
        returns:
            (value) -> value of the node_name
        """
	import Mgmt
        value = Mgmt.get_value(node_name)
        return value

    @staticmethod
    def set_bool_node_value(node_name,value):
        """Sets value of a bool node to true/false 

        takes two arguments:
            node_name -> name of the node to be set
            value     -> value the 'node_name' needs to be set to
        returns:
            (return code, error message)
            in case of an error it returns a non-zero error code 
            and error message otherwise it returns zero for success
            and an empty error message.
        """

	import Mgmt
        code, msg = Mgmt.set((node_name,'bool', value))
        return code,msg
    
    @staticmethod
    def set_node_value(node_name, node_type, node_value):
        """Sets value of node_name  of type node_type
           to node_value

        takes 3 arguments:
            node_name  -> name of the node to be set
            node_value -> value the 'node_name' needs to be set to
            node_type  -> type of 'node_name'
        returns:
            (return code, error message)
            in case of an error it returns a non-zero error code 
            and error message otherwise it returns zero for success
            and an empty error message.
        """

	import Mgmt
        code, msg = Mgmt.set((node_name, node_type, node_value))
        return code,msg
    
    @staticmethod
    def get_node_children(node_prefix):
        """Get all immediate children of node_prefix
        takes 1 arguments:
            node_prefix   -> prefix of the node
        returns:
            (code, message, bindings)
            children     -> names of all immediate children of the given
                            node_prefix
            details      -> dictionary of children and corresponding
                            values
        """
	import Mgmt
        children, details =  Mgmt.get_children(node_prefix)
        return children, details
    
    @staticmethod
    def trigger_action(action_name,action_params):
        """invoke an action with its binding params
        takes 2 arguments:
            action_name   -> name of the action to be triggered
            action_params -> varargs of bindings
        returns:
            (code, message, bindings)
            code     -> non zero in case of failure, zero otherwise
            msg      -> return message
            bindings -> dictionary keyed by parameter name
        """
	import Mgmt
        code, msg, bindings =  Mgmt.action(action_name,action_params)
        return code, msg, bindings
    
    
    @staticmethod
    def run_shell_cmd(cmd):
        """execute a shell command
        takes 1 argument:
            cmd -> the command to be executed
        returns:
            (code, output message , error message)
        """
        import subprocess
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        output, error = p.communicate()
        return p.returncode, output , error

    @staticmethod
    def execute_cmd(cmd_args):
        """execute command
        takes 1 argument:
            cmd_args -> list of command args
        returns:
            (code, output message , error message)
        """
        ret_code = 0
        output = ''
        error = ''
        import subprocess
        if isinstance(cmd_args,list) and cmd_args is not None:
            p = subprocess.Popen(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = p.communicate()
            ret_code = p.returncode
        else:
            ret_code = 1
            error = 'Invalid input provided to execute_cmd,' \
                        + ' expected a non-empty list of cmd arguments'
        return ret_code, output , error

    def is_process_running(self,process_name):
        ret_code      = Test.success
        process_state = Test.get_node_value('/pm/monitor/process/'\
                                        + process_name + '/state')

        if process_state != 'running' :
            ret_code = Test.error
        return ret_code

    def is_secure_vault_locked(self):
        sv_unlocked = Test.get_node_value('/secure_vault/state/unlocked')
        migration_done = Test.get_node_value('/rbt/sport/domain_auth/local/'\
                                                    + 'config/migration_done')
        if sv_unlocked == 'false' and migration_done == 'true' :
            return True
        return False


    def validate_params(self) :
        """validate parametes initialized during object instantiation

        Subclasses should override this function if they need to validate 
        parameters that were initialized on object instantiation
        """

        pass

    def run(self) :
        """issue an operation an instantiated object

        Subclasses should override this function based on the operation to
        be performed
        """
        pass

    def rollback(self) :
        """undo any changes that were made after an operation was issued 
        using an instance of run()

        Subclasses should override this function if they need a mecahnism
        to undo any changes introduced my an instance of the class object
        """
        pass

    #when config changes are made to the DB we need to issue a message to the user

class ModifyConfigNodes(Test):
    """ Class that is a subclass of Test used to set a list of
    config nodes
    """
    node_name_index  = 0
    node_type_index  = 1
    node_value_index = 2
    # nodes to be modfied should be a list of (node name, node value, 
    # node type)
    _node_details_size = 3

    def __init__(self, node_list, alias_list, log_handle=None):
        """initialize ModifyConfigNodes object

        takes 3 arguments:
            node_list   -> list of node_details that need to be modified 
                           each node_detail is a list of the (node name,
                           node type, node value)
            node_alias  -> list of corresponding node_alias'
            log_handle  -> if this is passed in, it logs the messages
                           using the passed in log handler, otherwise
                           defaults to logging the messages to syslog
        """
        self.node_list         = node_list
        self.node_alias        = alias_list
        self.orig_val          = []
        """if the config was changed and restart is requires this
        attribute is set to 1
        """
        self.restart_needed    = False
        
        Test.__init__(self, log_handle)

    def _set_node_to_value(self, node_details, rollback = False):
        ret_code = ModifyConfigNodes.success
        node_index = self.node_list.index(node_details)
        node_name, node_type, node_value = node_details
        current_val = ModifyConfigNodes.get_node_value(node_name)
        operation = 'Set '
        if current_val != node_value :
            ret_code, message = ModifyConfigNodes.set_node_value( \
                                            node_name, node_type, node_value)
            if ret_code:
                ret_code = ModifyConfigNodes.error
                msg = 'Encountered problems while setting' \
                                        + self.node_alias[node_index]  \
                                        +' to ' + node_value + ': ' + message
                self.log_file.error(msg)
            else :
                if not rollback :
                    is_restart_needed = ModifyConfigNodes.get_node_value( \
                                          '/rbt/sport/status/restart_needed')
                    if is_restart_needed == 'true':
                        self.restart_needed = True
                else :
                    operation = 'Reverted '
                msg = operation + self.node_alias[node_index] + ' to ' + node_value
                self.log_file.notice(msg)
        else :
            msg = self.node_alias[node_index] 
            if rollback:
                msg += ' value was never changed'
            else:    
                msg += ' already ' + node_value
            self.log_file.info(msg)
        return ret_code

    def validate_params(self):
        """validate parameters that were initialized on object instantiation"""
        
        ret_code = ModifyConfigNodes.success
        msg = ''
        #reset orig_val list every run, to account for any external changes on the
        #node
        self.orig_val = []
        if isinstance(self.node_list,list) and isinstance(self.node_alias, list) \
                                and (len(self.node_list) == len(self.node_alias)):
            for index, node_details in enumerate(self.node_list) :
                if len(node_details) == ModifyConfigNodes._node_details_size:
                    node_name = node_details[ModifyConfigNodes.node_name_index]
                    orig_node_value = ModifyConfigNodes.get_node_value(node_name)
                    if orig_node_value is not None :
                        #save original values
                        self.orig_val.append(orig_node_value)
                    else :
                        ret_code = ModifyConfigNodes.invalid
                        self.log_file.error('Invalid config node provided for ' \
                                                            + self.node_alias[index])
                        break
                else :
                        ret_code = ModifyConfigNodes.invalid
                        self.log_file.error('Invalid format for provided node details, ' +\
                                            'expecting a list of ' + \
                                            '(node_name, node_value, node_type) values')

        else:
            ret_code = ModifyConfigNodes.invalid
            self.log_file.error('Invalid input params')

        return ret_code


    def run(self):
        """issue an operation an instantiated object to set a list of nodes

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """
        ret_code  = ModifyConfigNodes.success
        ret_code  = self.validate_params() 
       
        if ret_code == ModifyConfigNodes.success :
            for node_details in self.node_list :
                ret_code = self._set_node_to_value(node_details)
                if ret_code == ModifyConfigNodes.error :
                    break
        return ret_code

    def modify_set_nodes(self, node_list):
        """issue an operation an instantiated object to modify values of
           already Enabled/disabled nodes

        takes 2 arguments:
            node_list -> a list of nodes that is a subset of nodes that need 
                         to be modified after it has been set
            value -> sets the list of nodes to this value
        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """
        ret_code = ModifyConfigNodes.success
        # we want to modify node values only if they have been set by a run()
        if self.orig_val:
            if isinstance(node_list, list) :
                for node_details in node_list :
                    if len(node_details) == ModifyConfigNodes._node_details_size:
                        if node_details[ModifyConfigNodes.node_name_index] in \
                            (orig_node_details[ModifyConfigNodes.node_name_index] 
                                       for orig_node_details in self.node_list) :
                            ret_code = self._set_node_to_value(node_details)
                            if ret_code == ModifyConfigNodes.error :
                                break
                        else :
                            ret_code = ModifyConfigNodes.error
                            self.log_file.error('Invalid config node provided for ' \
                                                    + 'modification ' + node)
                    else:
                        ret_code = ModifyConfigNodes.invalid
                        self.log_file.error('Invalid format for provided node details, ' +\
                                            'expecting a list of ' + \
                                            '(node name, node type, node value) values')
            else :
                ret_code = ModifyConfigNodes.error
                self.log_file.warning('Expecting a list of node_details to modify')
        else :
            self.log_file.warning('No nodes were set, nothing to modify')
        return ret_code

 
    def rollback(self):
        """Rollsback values of nodes in the node_list to their original values
        
        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """
        ret_code = ModifyConfigNodes.success
        
        #only if input parameters were validated and orig_val was 
        #populated we rollback
        if self.orig_val :
            #set values back to original values in reverse order 
            for index,orig_node_val in reversed(list(enumerate(self.orig_val))) :
                node_details = self.node_list[index]
                node_details[ModifyConfigNodes.node_value_index] = orig_node_val
                ret_code = self._set_node_to_value(node_details, True)
            
            #reset original values after rollback 
            self.orig_val = []
            if self.restart_needed :
                output = 'You may need to restart the optimization' + \
                        ' service for the changes to be reverted properly.\n'
                self.log_file.warn(output)

        return ret_code

class JoinDomain(Test):
    """Class that is a subclass of the class test that allows join operations
    """
    
    class _JoinStatus: 
        NOT_CONFIGURED          =  'Not configured'
        IN_DOMAIN               =  'In a domain'
        JOIN_DOMAIN_IN_PROG     =  'Joining a domain...'
        LEAVE_DOMAIN_IN_PROG    =  'Leaving a domain...'
        DOMAIN_ACTION_CANCELLED =  'Domain action canceled'
        IN_WORKGROUP            =  'In a workgroup'   

    class _JoinOperation:
        JOIN   = 'join'
        REJOIN = 'rejoin'
        LEAVE  = 'leave'

    _RRAD = '/rbt/rcu/action/domain_config'
    _RRDS = '/rbt/rcu/domain/status'
    _RRAC = '/rbt/rcu/action/cancel_action'

    _join_params = ['realm','login','passwd','join_type']

    _optional_join_params = ['workgroup', 'dc_list', 'netbios_name']

    _join_timeout_param = 'join_timeout'

    def __init__(self, input_args, log_handle=None):   

        self.input_params = input_args
        #dictionary to save the original state of the domain
        #gets populated in the join/rejoin domain step if 
        #we were joined to the domain before we start auto-conf
        self.orig_domain_state   = {'realm'        : None,
                                    'workgroup'    : None,
                                    'dc_list'      : None,
                                    'join_type'    : None,
                                    'netbios_name' : None }

        #dictionary that holds bindingname:bindingvalue input params
        #needed for the join_rejoin action
        self.jr_action_params = []

        authtest_params       = { 'user'     : input_args['login'],
                                  'password' : input_args['passwd'] }
        self.authtest         = AuthTest(authtest_params, log_handle)

        self.timeout_secs     = 90
        self.poll_secs        = 10


        Test.__init__(self, log_handle)
 
            
    def _get_domain_status(self):
        status = JoinDomain.get_node_value(JoinDomain._RRDS)
        return status

    def _is_dc_in_orig_dclist(self):
        orig_dc_str = self.orig_domain_state['dc_list']
        if orig_dc_str :
            orig_dc_list = orig_dc_str.split()
            if 'dc_list' in self.input_params and \
                    self.input_params['dc_list'] in orig_dc_list :
                return True
        return False

    def _construct_and_append_dc_list(self):
        #special handling for dc_list , we need to , append the dc_name to join
        #parms if we are joining or append to original dc list if we are
        #rejoining or replace '*' in the dc list with provided dc name
        param = 'dc_list'
        if param in self.input_params :
            value = ''
            dclist_delim = ','
            if self.orig_domain_state[param] :
                default_dclist = '*'
                orig_dc_list = self.orig_domain_state[param].split()
                if default_dclist in orig_dc_list : 
                    orig_dc_list.remove(default_dclist)
                if orig_dc_list :
                    value = dclist_delim.join(orig_dc_list) 
            if not self._is_dc_in_orig_dclist() :
                if len(value) :
                    value = value + dclist_delim
                value = value + self.input_params[param]
            self.jr_action_params.\
                        append((param, 'string', value))

    def _append_optional_params(self):
        for param in JoinDomain._optional_join_params:
            if param == 'dc_list' :
                self._construct_and_append_dc_list()
            else:
                if param in self.input_params and self.input_params[param] :
                        self.jr_action_params.\
                            append((param, 'string', self.input_params[param]))
    
    def _append_orig_params_on_rejoin(self):
        #append optional params
        self._append_optional_params()
        #make sure if we need to rejoin then all the original settings are 
        #preserved
        for param, value in self.orig_domain_state.iteritems() :
            if param not in self.input_params and value :
                self.jr_action_params.\
                     append((param, 'string', value))

    def _domain_cancel(self, domain_name):
        #cancel ongoing join/rejoin/cancel action
        ret_code             = JoinDomain.success
        domain_cancel_params = []

        self.log_file.notice('Cancel ongoing action on domain ' + domain_name)
        
        domain_cancel_params.append(('type', 'string', 'domain'))
        ret_code, message, bindings = JoinDomain.trigger_action(JoinDomain._RRAC,\
                                                            domain_cancel_params)
        if ret_code :
            msg = 'Encountered errors while triggering ' \
                                             +'domain cancel action: ' + message
            self.log_file.error(msg)
        return ret_code

    def _check_operation_completion(self):
        #returns error if join is still in progress and success if completed 
        ret_code = JoinDomain.success
        domain_status = self._get_domain_status()
        if( domain_status == JoinDomain._JoinStatus.JOIN_DOMAIN_IN_PROG or \
            domain_status == JoinDomain._JoinStatus.LEAVE_DOMAIN_IN_PROG ) : 
            ret_code = None
        return ret_code

    def _get_operation_result(self):
        #get result of issued domain operation
        ret_code = JoinDomain.success
        domain_status = self._get_domain_status()

        self.log_file.info('Current Domain Status: ' +  domain_status )

        if domain_status == JoinDomain._JoinStatus.JOIN_DOMAIN_IN_PROG or \
            domain_status == JoinDomain._JoinStatus.LEAVE_DOMAIN_IN_PROG : 
            msg = 'Join/re-join/leave in progress, waiting for ' \
                           + 'operation to complete'
            self.log_file.notice(msg)
            poll_function = TimeoutFunction(self._check_operation_completion,\
                                            self.timeout_secs , self.poll_secs ) 
            try :
                poll_function()
            except TimeoutFunctionException:
                msg = 'Issued join operation timed out.' \
                           + ' Canceling operation'
                self.log_file.error(msg)
                self._domain_cancel(self.input_params["realm"])
                ret_code = JoinDomain.error
            else:
                domain_status = self._get_domain_status()
                msg = 'Issued join operation completed.' \
                           + ' Domain Status: ' + domain_status
                self.log_file.notice(msg)
            
        return ret_code, domain_status
    
    
    def _trigger_domain_operation(self, action_type):
        #invoke joining or rejoining domain action 
        
        ret_code = JoinDomain.success
        if action_type == JoinDomain._JoinOperation.LEAVE :
            #clear any previous population of the action params
            self.jr_action_params = []
            #append user name and passwd to ensure account is deleted on a leave
            self.jr_action_params.append(\
                          ('login', 'string', self.input_params['login']))
            self.jr_action_params.append(\
                          ('passwd', 'string', self.input_params['passwd']))
        
        #need to append action_type : join/rejoin
        self.jr_action_params.append(('type', 'string', action_type))
        
        self.log_file.info('Try to ' + action_type + ' domain ' \
                                               + self.input_params['realm'])
        ret_code, msg, bindings = JoinDomain.trigger_action( \
                                     JoinDomain._RRAD,self.jr_action_params)
            
        if ret_code == JoinDomain.success :
            ret_code, result = self._get_operation_result()
            
            if action_type != JoinDomain._JoinOperation.LEAVE \
                       and result == JoinDomain._JoinStatus.NOT_CONFIGURED :
                msg = JoinDomain.get_node_value(\
                                    '/rbt/rcu/state/domain_join_error_msg')
                self.log_file.error(msg)
                ret_code = JoinDomain.error

        else :
            ret_code = JoinDomain.error
            self.log_file.error('Encountered errors while triggering ' \
                             + action_type + 'ing domain action: ' + msg)

        return ret_code, msg
    
    def _handle_failure_on_rollback(self, action_type, error_msg):
        """This is to protect against failures during rollback, 
           this function currently takes care of one possible situation that 
           we could encounter while trying to leave a domain ,
           when encrypted MAPI is enabled.
        """
        eMAPI_enabled_cannot_leave = 'Cannot leave domain while MAPI' \
                                         + ' encryption is enabled\n'
        eMAPI_enable_node  = \
                 '/rbt/sport/blade/exchange/config/mapi2k7/encrypted/enable'
        if action_type == JoinDomain._JoinOperation.LEAVE and \
           error_msg == eMAPI_enabled_cannot_leave :
            #temporarily disable node
            self.log_file.info('temporarily disable encrypted MAPI')
            JoinDomain.set_bool_node_value(eMAPI_enable_node, 'false')
               
            #issue leave once node is disabled
            ret_code, msg = self._trigger_domain_operation(action_type)
               
            #set node back to true 
            self.log_file.info('enable encrypted MAPI')
            JoinDomain.set_bool_node_value(eMAPI_enable_node, 'true')
            
            return ret_code


    def validate_params(self):
        """validate parameters that were initialized on object instantiation

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """ 
        ret_code = JoinDomain.success
        self.jr_action_params = []
        if self.input_params and isinstance(self.input_params, dict) :
            for param in JoinDomain._join_params:
                if param not in self.input_params:
                    self.log_file.error('Missng input parameters')
                    ret_code = JoinDomain.invalid
                    break
                else:
                    if self.input_params[param] is not None:
                        self.jr_action_params.\
                        append((param, 'string', self.input_params[param]))
            #check if process_timeout param was received
            if JoinDomain._join_timeout_param in self.input_params :
                self.timeout_secs = \
                     int(self.input_params[JoinDomain._join_timeout_param])
        else:
            ret_code = JoinDomain.invalid
            self.log_file.error('Class instatiated with invalid parameters')
        return ret_code 

    def run(self):
        """issue an operation an instantiated object to Join to a Domain

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """
        domain_config_prefix     = '/rbt/rcu/domain/config/'
        action_type              = None
        ret_code                 = JoinDomain.success
        msg                      = ' '

        ret_code = self.validate_params()
        if ret_code == JoinDomain.success :
            #if a preiviously issued domain operation is in progress
            #wait till thar is complete before we issue our join 
            #operation
            ret_code, domain_status = self._get_operation_result()

        if ret_code == self.success :
            if domain_status == JoinDomain._JoinStatus.NOT_CONFIGURED :
                action_type = JoinDomain._JoinOperation.JOIN
                #append optional params
                self._append_optional_params()
            else :
                for node_suffix, value in self.orig_domain_state.iteritems() :
                    value = JoinDomain.get_node_value(domain_config_prefix + node_suffix)
                    if value != '' :
                        self.orig_domain_state[node_suffix] = value

                #if already joined to a different domain we need to quit 
                if (not JoinDomain.strequal_ic(self.orig_domain_state['realm'],self.input_params['realm'])) :
                    msg = ('Cannot join domain: ' + self.input_params['realm'] \
                                    + ' because steelhead is already in a domain: '
                                    + self.orig_domain_state['realm'])
                    self.jr_action_params = [] #to ensure no rollback is required
                    self.log_file.error(msg)
                    ret_code = JoinDomain.error
                else :
                    orig_join_type = self.orig_domain_state['join_type'] 
                    #if domain is already joined as workstation or
                    #if domain was orignally joined with a different join type or 
                    #if dc name is not in dc-list
                    #we need to rejoin 
                    if (not JoinDomain.strequal_ic(orig_join_type, self.input_params['join_type'])) or \
                            (not self._is_dc_in_orig_dclist()) :
                        #before attempting a re-join we want to authenticate the
                        #user to ensure we have valid credentials to perform the rejoin 
                        ret_code = self.authtest.run()
                        if ret_code == JoinDomain.success :
                            action_type = JoinDomain._JoinOperation.REJOIN
                            self._append_orig_params_on_rejoin()
                        else :
                            msg = 'Invalid user credentials, not going to' \
                                    + ' attempt to rejoin to ' \
                                    +  self.input_params['realm']
                            #to ensure no rollback is required
                            self.jr_action_params = [] 
                            self.log_file.error(msg)
                    else :
                        self.log_file.notice('Already joined to ' \
                                               + self.input_params['realm'])
                        #to ensure no rollback is required
                        self.jr_action_params = []

            if (action_type is not None) and (ret_code == JoinDomain.success) :
                ret_code, msg = self._trigger_domain_operation(action_type)
                if ret_code == JoinDomain.error :
                    #to ensure no rollback is required
                    self.jr_action_params = []

           
        return ret_code

    def rollback(self):
        """Rollsback domain to original state

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """

        ret_code      = JoinDomain.success
        action_type   = JoinDomain._JoinOperation.LEAVE

        #if action params is empty, the params were never validated, 
        #nothing to rollback
        if self.jr_action_params:
            self.log_file.notice('Rolling back domain to original state')
            if self.orig_domain_state['realm'] is not None :
                action_type = JoinDomain._JoinOperation.REJOIN
                #repopulate action params with original values 
                self.jr_action_params = []
                self.jr_action_params.append( \
                        ('login','string', self.input_params["login"]))
                self.jr_action_params.append( \
                        ('passwd','string', self.input_params["passwd"]))
                for bname, bvalue in self.orig_domain_state.iteritems():
                    if bvalue is not None:
                        self.jr_action_params.append((bname, 'string', bvalue))
        
            ret_code, msg = self._trigger_domain_operation(action_type)
            if ret_code :
                ret_code = self._handle_failure_on_rollback(action_type, msg) 
            #reset action params after rollback 
            self.jr_action_params = []

        return ret_code


class AddReplUser(Test):
    """Class that is a subclass of the class test that allows 
       adding replication users
    """
    _RSDAR = '/rbt/sport/domain_auth/action/encrypt_password_r'
    _RSDADR = '/rbt/sport/domain_auth/action/delete_replication_domain'

    _addrepl_params = ['domain','user_domain','user','clr_password', 'dcname'] 
    
    def __init__(self, input_args, log_handle=None):   

        self.input_params          = input_args
        #dictionary that holds bindingname:bindingvalue input params
        #needed for the join_rejoin action
        self.addrepl_action_params = []
        self.added_repl            = False
        Test.__init__(self, log_handle)
    
    def validate_params(self):
        """validate parameters that were initialized on object instantiation

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """ 
        ret_code = AddReplUser.success
        is_rodc  = 'false'
        self.addrepl_action_params = []
        if self.input_params and isinstance(self.input_params, dict) :
            for param in AddReplUser._addrepl_params:
                if param not in self.input_params:
                    self.log_file.error('Missng input parameters')
                    ret_code = AddReplUser.invalid
                    break
                else:
                    if self.input_params[param] is not None:
                        self.addrepl_action_params.\
                        append((param, 'string', self.input_params[param]))
                    
            if 'rodc' in self.input_params:
                is_rodc = self.input_params['rodc']
            self.addrepl_action_params.\
                append(('rodc', 'bool', is_rodc))

        else:
            ret_code = AddReplUser.invalid
            self.log_file.error('Class instatiated with invalid parameters')
        return ret_code 

    def run(self):
        ret_code = AddReplUser.success
        ret_code = self.validate_params()
        if ret_code == AddReplUser.success :
            self.log_file.info('Try to add replication user ' \
                      + self.input_params['user'] \
                      + ' for  domain ' + self.input_params['domain'])
            ret_code, msg, bindings = AddReplUser.trigger_action( \
                        AddReplUser._RSDAR,self.addrepl_action_params)
            
            if ret_code == AddReplUser.success :
                #to keep track if we need to undo this add on rollback
                self.added_repl = True
                self.log_file.notice('Successfully added replication'
                      + ' user ' + self.input_params['user'] \
                      + ' for  domain ' + self.input_params['domain'])
            else :
                ret_code = AddReplUser.error
                self.log_file.error('Encountered errors while trying' 
                            + ' to add replication user ' \
                            + self.input_params['user'] + ': '  + msg)

        return ret_code
    
    def rollback(self):
        """Rollsback domain to original state

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """
        self.addrepl_action_params =[]
        ret_code = AddReplUser.success
        if self.added_repl: #need to delete only if it was successfully added
            self.addrepl_action_params.\
              append(('domain', 'string', self.input_params['domain']))
            self.log_file.info('Try to delete replication user ' \
                        + self.input_params['user'] \
                        + ' for  domain ' + self.input_params['domain'])
            ret_code, msg, bindings = AddReplUser.trigger_action( \
                        AddReplUser._RSDADR,self.addrepl_action_params)
            
            if ret_code == AddReplUser.success :
                self.log_file.notice('Successfully removed replication' \
                                + ' user ' + self.input_params['user'] \
                        + ' for  domain ' + self.input_params['domain'])
            else :
                ret_code = AddReplUser.error
                self.log_file.error('Encountered errors while trying to' \
                        + ' remove replication user ' \
                        + self.input_params['user'] + ': '  + msg)
        return ret_code

class DomaindTests(Test):
    
    class _DomaindTestResult:
        NOTSTARTED = 'NOT STARTED'
        INPROGRESS = 'IN PROGRESS'
        SUCCESS    = 'SUCCESS'
        FAILED     = 'FAILED'

    _ACTIONPREFIX  = '/rbt/sport/domain_auth/action/domaind/' 
    _STATUSPREFIX  = '/rbt/sport/domain_auth/state/domaind/status/'

    _timeout_param = 'process_timeout'

    def __init__(self, test_name, test_params, input_params, log_handle=None):
        self.test_name       = test_name
        self.action_params   = []
        self._test_params    = test_params
        self.input_params    = input_params
        self.timeout_secs    = 60
        self.poll_secs       = 3

        if isinstance(log_handle, Logger):
            self.log_file = log_handle
        else :
            self.log_file = SysLogger('domaind/easy_config/' + self.test_name)
        Test.__init__(self, log_handle)
    

    def _get_domaind_test_status(self):
        #get status of issued test/auto-conf
        status = DomaindTests.get_node_value(DomaindTests._STATUSPREFIX + self.test_name )
        return status
   
    def _check_domaind_test_completion(self):
        #returns error if test is still in progress and success otherwise
        ret_code = self.success
        status = self._get_domaind_test_status()
        if status== DomaindTests._DomaindTestResult.INPROGRESS :
            ret_code = None
        return ret_code

    def _trigger_domaind_action(self):
        #trigger test/auto-conf
        ret_code = DomaindTests.success
        ret_code, msg, bindings = DomaindTests.trigger_action( \
              DomaindTests._ACTIONPREFIX + self.test_name , self.action_params)
        if ret_code != DomaindTests.success:
            self.log_file.error('Encountered error while triggering action: ' \
                                                                         + msg)
            ret_code = DomaindTests.error
        return ret_code
    
    def _get_result(self):
        #get result of triggered test/auto-conf
        ret_code = DomaindTests.success
        msg = ''
        result = DomaindTests._DomaindTestResult.NOTSTARTED
        poll_function = TimeoutFunction(self._check_domaind_test_completion \
                                          , self.timeout_secs, self.poll_secs) 
        try :
            poll_function()
        except TimeoutFunctionException:
            msg = 'taking too long to complete action' \
                           + ' exiting'
            ret_code = DomaindTests.error
        else :
            result = self._get_domaind_test_status()
            msg = 'Action completed.' \
                           + ' Result: ' + result + '\n'
            if result == DomaindTests._DomaindTestResult.FAILED :
                ret_code = DomaindTests.error

        return ret_code, msg

    def validate_params(self):
        """validate parameters that were initialized on object instantiation

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """
        ret_code = DomaindTests.success
        msg      = ''

        self.action_params = []

        if isinstance(self.input_params, dict):
            if self._test_params :
                for param in self._test_params:
                    if param not in self.input_params:
                        ret_code = DomaindTests.invalid
                        msg = 'Missng action parameters, cannot trigger action'
                        self.log_file.error(msg)
                        break
                    else:
                        if self.input_params[param] is not None:
                            self.action_params.append((param, \
                                          'string', self.input_params[param]))
            #check if process_timeout param was received
            if DomaindTests._timeout_param in self.input_params :
                self.timeout_secs = \
                           int(self.input_params[DomaindTests._timeout_param])
                self.action_params.append((DomaindTests._timeout_param, \
                                            'uint32', str(self.timeout_secs)))
        else :
            ret_code = DomaindTests.invalid
            msg = 'Object instantiated with invalid paramters expected dictionary'\
                    + ' of input parameters and log_handle'
            self.log_file.error(msg)

        return ret_code

    def run(self):
        """issue a test/auto-conf

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """
        ret_code = DomaindTests.success
        msg      = ''
        
        #get result before we trigger the action just to ensure that any
        #previous runs are queried and complete
        ret_code, msg  = self._get_result()

        ret_code = self._trigger_domaind_action()
        if ret_code == DomaindTests.success :
                ret_code, msg = self._get_result()

        if ret_code :
            self.log_file.error(msg)
        return ret_code

class TestDNS(DomaindTests):
    """ test DNS settings"""

    _test_params = ['realm']
    _test_name   = 'testdns/extended'

    def __init__(self, inp_params, log_handle=None):
        DomaindTests.__init__(self, TestDNS._test_name, \
                                    TestDNS._test_params, inp_params, log_handle)

    def run(self):
        """issue a DNS test

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """
        ret_code = TestDNS.success
        ret_code = self.validate_params()
        if ret_code == TestDNS.success:
            ret_code = DomaindTests.run(self)

        return ret_code

class AuthTest(DomaindTests):
    """ test autentication credentials of user"""

    _test_params = ['user', 'password']
    _test_name   = 'authtest/extended'

    def __init__(self, inp_params, log_handle=None):
        DomaindTests.__init__(self, AuthTest._test_name, \
                                    AuthTest._test_params, inp_params, log_handle)

    def run(self):
        """issue a DNS test

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """
        ret_code = AuthTest.success
        ret_code = self.validate_params()
        if ret_code == AuthTest.success:
            ret_code = DomaindTests.run(self)
        return ret_code

class AutoConfRepl(DomaindTests):
    """issue Auto-Configuration of a replication user in the AD"""

    _autoconf_params = ['realm','admin','adminpass','dc']
    _autoconf_name   = 'confrepl/extended'

    def __init__(self, inp_params, log_handle=None):
        DomaindTests.__init__(self, AutoConfRepl._autoconf_name, \
                           AutoConfRepl._autoconf_params, inp_params, log_handle)

    def run(self):
        """issue an Auto-Configuration of a replication user in the AD

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """
        ret_code    = AutoConfRepl.success
        repl_domain = None
        ret_code    = self.validate_params()

        if ret_code == AutoConfRepl.success :
            if self.is_secure_vault_locked() :
                msg = 'Secure Vault must be unlocked before auto-configuring '\
                                                        + 'replication users.'
                self.log_file.warn(msg) 
                self.result += 'WARN: Secure Vault Locked. Not going to ' \
                                + 'attempt to auto-configure replication '\
                                + 'user in AD\n'
                return ret_code

            input_domain_name = self.input_params['realm']
            deployed_repl_domains_list, domain_details = AutoConfRepl.get_node_children(\
                        '/rbt/sport/domain_auth/state/replication/domain')

            if len(deployed_repl_domains_list):
                for deployed_domain in deployed_repl_domains_list:
                    if AutoConfRepl.strequal_ic(deployed_domain, input_domain_name):
                        repl_domain = deployed_domain
                        break;
                            
            if repl_domain is None :
                msg = 'Replication domain: '\
                                            + input_domain_name + ' not found. '
                self.log_file.warn(msg)
                self.result += 'WARN: ' + msg
                msg = 'Not going to attempt to auto-configure ' \
                                            + 'replication user in AD'
                self.log_file.warn(msg)
                self.result += msg + '\n'

            else :
                repl_user = AutoConfRepl.get_node_value(\
                            '/rbt/sport/domain_auth/state/replication/domain/'\
                                                         + repl_domain + '/user')
                self.log_file.info('Auto-Conf Replication User ' + repl_user + \
                                                        ' on ' + input_domain_name)
                         
                ret_code  = DomaindTests.run(self)
        return ret_code
    
if __name__ == "__main__":
    pass
