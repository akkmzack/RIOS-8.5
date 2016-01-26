#!/usr/bin/python

# (C) Copyright 2003-2011 Riverbed Technology, Inc.
# All Rights Reserved. Confidential.

import Mgmt
import sys
import optparse
import traceback
from easyConfig import SysLogger, CustomLogger, Test, ModifyConfigNodes, \
                       JoinDomain, TestDNS, AddReplUser, AutoConfRepl


class InputArgs:
    def __init__(self,conf_type,admin_name,admin_pass,domain_name,dc_name,
                 join_type,shortdom,repl_user_dom,repl_user_name,
                 repl_user_pass,repl_isrodc,test_mode=False):
        self.conf_type      = conf_type
        self.admin_name     = admin_name
        self.admin_pass     = admin_pass
        self.domain_name    = domain_name
        self.dc_name        = dc_name
        self.join_type      = join_type
        self.shortdom       = shortdom
        self.repl_user_dom  = repl_user_dom
        self.repl_user_name = repl_user_name
        self.repl_user_pass = repl_user_pass
        self.repl_isrodc    = repl_isrodc
        self.test_mode      = test_mode


class AutoConfEasyAuth(Test):
    
    #allowed configuration types
    _conf_type_separator = ','
    _conf_types = [ 'emapi','smbsigning','smb2signing', 'smb3signing', 'all']

    #allowed join types
    _join_types = [ 'bdc', 'rodc']

    _repl_domain_prefix = '/rbt/sport/domain_auth/state/replication/domain'

    class NodeAliasMap:
        """class to maintain config nodes that need to be enabled,
        based on the type of auto configuration to be performed
        node_list   : is a list of (node name, node type, node value)
        node_alias  : holds name of the node to be used in log messages
        peer_enable : does the node need to be enabled on peer as well
        """
        def __init__(self, type):
            self.node_list       = []
            self.node_alias      = []
            self.peer_enable     = []
            if type is not None:
                if 'emapi' in type or 'all' in type :
                    self.node_list   += [ ['/rbt/sport/blade/exchange/config/mapi2k7/encrypted/enable', 'bool', 'true'],
                                          ['/rbt/sport/blade/exchange/config/mapi2k7/encrypted/force_ntlm_auth', 'bool' ,'true'],
                                          ['/rbt/sport/blade/exchange/config/native_krb/enable', 'bool', 'true'] ]
                    self.node_alias  += ['Encrypted MAPI',
                                         'Encrypted MAPI NTLM',
                                         'Encrypted MAPI Native Kerberos']
                    self.peer_enable += [True,
                                         True,
                                         True]

                if 'smbsigning' in type or 'all' in type :
                    self.node_list   += [ ['/rbt/sport/smbsigning/config/enable', 'bool', 'true'],
                                          ['/rbt/sport/smbsigning/config/mode_type', 'string', 'transparent'],
                                          ['/rbt/sport/smbsigning/config/native_krb', 'bool', 'true'] ]
                    self.node_alias  += ['SMB Signing',
                                         'SMB Signing Mode',
                                         'SMB Signing Native Kerberos']
                    self.peer_enable += [False,
                                         False,
                                         False]
            
                if 'smb3signing' in type or 'all' in type :
                    self.node_list   += [['/rbt/sport/smb2/config/smb3/enable', 'bool', 'true']]
                    self.node_alias  += ['SMB3']
                    self.peer_enable += [True]

                if 'smb2signing' in type or 'smb3signing' in type or 'all' in type :
                    self.node_list   += [['/rbt/sport/smb2/config/enable', 'bool', 'true'],
                                         ['/rbt/sport/smb2signing/config/enable', 'bool', 'true'],
                                         ['/rbt/sport/smb2signing/config/mode_type', 'string', 'transparent'],
                                         ['/rbt/sport/smb2signing/config/native_krb', 'bool', 'true'] ]
                    self.node_alias  += ['SMB2',
                                         'SMB2/3 Signing',
                                         'SMB2/3 Signing Mode',
                                         'SMB2/3 Signing Native Kerberos']
                    self.peer_enable += [True,
                                         False,
                                         False,
                                         False]

    def __init__(self, cmd_line_args, log_file=None):
        
        Test.__init__(self, log_file)
        
        self.inp_args            = cmd_line_args
        self.result              = 'Auto-Conf Easy Auth result:\n'
        
        #dictionary of param name, param values for testing DNS
        testdns_params      = { 'realm'           : cmd_line_args.domain_name,
                                'process_timeout' : 75}
        #instantiate test DNS object
        self.testdns             = TestDNS(testdns_params, log_file)
            
        #dictionary of param name, param values for join domain
        domainjoin_params        = {'realm'        : cmd_line_args.domain_name,
                                    'login'        : cmd_line_args.admin_name,
                                    'passwd'       : cmd_line_args.admin_pass,
                                    'join_type'    : cmd_line_args.join_type,
                                    'dc_list'      : cmd_line_args.dc_name,
                                    'workgroup'    : cmd_line_args.shortdom,
                                    'join_timeout' : 60}
        #instantiate JoinDomain object
        self.domainjoin          = JoinDomain(domainjoin_params, log_file)

        #initialize node list
        self.node_alias_map      = AutoConfEasyAuth.NodeAliasMap(cmd_line_args.conf_type)
        #instatiate ModifyConfigNodes object
        self.setconfig           = ModifyConfigNodes(self.node_alias_map.node_list, \
                                        self.node_alias_map.node_alias, \
                                        log_file)
        addrepl_params       = {'domain'       : cmd_line_args.domain_name,
                                'user'         : cmd_line_args.repl_user_name,
                                'user_domain'  : cmd_line_args.repl_user_dom,
                                'clr_password' : cmd_line_args.repl_user_pass,
                                'rodc'         : cmd_line_args.repl_isrodc,
                                'dcname'       : cmd_line_args.dc_name }
        self.addrepl             = AddReplUser(addrepl_params, log_file);
        #dictionary of param name, param values for auto conf
        confrepl_params          = { 'realm'           : cmd_line_args.domain_name,
                                     'admin'           : cmd_line_args.admin_name,
                                     'adminpass'       : cmd_line_args.admin_pass,
                                     'dc'              : cmd_line_args.dc_name,
                                     'process_timeout' : 45 } 
        #instantiate ModifyConfigNodes object
        self.confrepl            = AutoConfRepl(confrepl_params, log_file)
        
    def _add_restart_peer_enable_msg(self):
        for index, value in enumerate(self.node_alias_map.peer_enable):
            if value :
                output = 'Please make sure ' \
                         + self.node_alias_map.node_alias[index]\
                         + ' is enabled on the peers\n'
                self.result += output
                self.log_file.warn(output)

        if self.setconfig.restart_needed :
            output = 'You must restart the optimization' \
                         + ' service for your changes to take' \
                         + ' effect.\n'
            self.result += output
            self.log_file.warn(output)

    def _is_repl_deployed(self):
        is_deployed = False
        deployed_repl_domains_list, domain_details = \
                  AutoConfEasyAuth.get_node_children(\
                                        AutoConfEasyAuth._repl_domain_prefix)

        if len(deployed_repl_domains_list):
            is_deployed = any( AutoConfEasyAuth.strequal_ic(\
                                deployed_domain, self.inp_args.domain_name) \
                            for deployed_domain in deployed_repl_domains_list)

        return is_deployed

    def _handle_no_repl_domain(self):
        ret_code = AutoConfEasyAuth.success
        if not self._is_repl_deployed():
            modify_node_list = []
            self.log_file.info("Turning off native-krb nodes")
            for alias in self.node_alias_map.node_alias :
                #if no replication domain reset native-krb nodes
                if 'Kerberos' in alias :
                    index = self.node_alias_map.node_alias.index(alias)
                    node_details = self.node_alias_map.node_list[index]
                    #set the value of krb nodes to false
                    node_details[ModifyConfigNodes.node_value_index] = 'false'
                    modify_node_list.append(node_details)
                    self.node_alias_map.peer_enable[index] = False
            ret_code = self.setconfig.modify_set_nodes(modify_node_list)
            
        return ret_code

    def _handle_repl_ut_mode(self):
        ret_code = AutoConfEasyAuth.success
        if self.inp_args.domain_name == "INVALIDTESTDOM.COM":
            #forcing rollback in unit test mode 
            ret_code = AutoConfEasyAuth.error
        else:
            #testing scenario when no repl user is deployed on SH
            if not self._is_repl_deployed():
                self.confrepl.result = 'WARN: Replication domain: ' \
                                        + self.inp_args.domain_name + ' not '\
                                        + 'found. Not going to attempt to ' \
                                        + 'auto-configure replication user in AD\n'  
        
        return ret_code

    def _easyauth_auto_conf(self):
        ret_code = AutoConfEasyAuth.success
        # the easy auth auto configuration involves 4 steps

        ret_code = self.is_process_running('domaind')
        ret_code = ret_code or self.is_process_running('rcud')
        ret_code = ret_code or self.is_process_running('sport')

        if ret_code == AutoConfEasyAuth.success :

            #####Step 1: test DNS#####
            self.log_file.info('Testing DNS Configuration')
            self.log_file.info('Join Domain: ' + self.inp_args.domain_name)
            if self.inp_args.test_mode == False:
                ret_code = self.testdns.run()

            if ret_code == AutoConfEasyAuth.success :
                output = 'DNS Test Passed\n'
                self.result += output
                self.log_file.notice(output)

                #####Step 2: Join/Re-join domain#####
                self.log_file.info('Join/Re-Join the Domain')
                if self.inp_args.test_mode == False:
                    ret_code = self.domainjoin.run()

                if ret_code == AutoConfEasyAuth.success :
                    output='Successfully joined domain: ' + self.inp_args.domain_name + '\n'
                    self.result += output
                    self.log_file.notice(output)

                    #####Step 3: Enable Config Nodes #####
                    self.log_file.info('Enable nodes for ' \
                            + self.inp_args.conf_type + ' auto-conf')
                    ret_code = self.setconfig.run()

                    if ret_code == AutoConfEasyAuth.success:
                        output = 'Successfully enabled nodes for ' \
                                    + self.inp_args.conf_type + ' auto-conf \n'
                        self.result += output
                        self.log_file.notice(output)


                        #####Step 4: Add Replication user if provided
                        if self.inp_args.repl_user_dom is not None and \
                           self.inp_args.repl_user_pass is not None and \
                           self.inp_args.repl_user_pass is not None:
                            self.log_file.info('Add Replication User')
                            ret_code = self.addrepl.run()
                            if ret_code == AutoConfEasyAuth.success :
                                output='Successfully added replication user: ' \
                                        + self.inp_args.repl_user_name + '\n'
                                self.result += output
                                self.log_file.notice(output)
                            else : 
                                output='Adding Replication user failed\n'
                                self.result +=output
                                self.log_file.warn(output)


                        #####Step 5: Auto-Configure Replication User in AD #####
                        self.log_file.info('Auto-Configure Replication User in AD')
                        if self.inp_args.test_mode == False:
                            ret_code = self.confrepl.run()
                        else:
                            ret_code = self._handle_repl_ut_mode()

                        if ret_code == AutoConfEasyAuth.success :
                            if self.confrepl.result :     
                                self.result += self.confrepl.result
                                self._handle_no_repl_domain()
                            else :
                                output = 'Auto-Conf of Replication user' \
                                         + ' in AD succeeded\n'
                                self.result += output
                                self.log_file.notice(output)
                            
                            self._add_restart_peer_enable_msg()

                            return ret_code

                        else :
                            output = 'Auto-Conf of Replication user Failed\n'
                    else :
                        output = 'Enabling config nodes Failed\n'
                else :
                    output = 'Encountered problems when trying to ' \
                              + 'join/rejoin domain: '\
                              + self.inp_args.domain_name + '\n'
            else :
                output = 'DNS Test failed\n'
        else :
            output = 'Unable to Connect to Domain-Health provider rcud or sport\n'

        self.result = output
        self.log_file.error(output)

        return ret_code

    def _is_valid_conf_type(self):
        inp_conf_type = self.inp_args.conf_type
        if AutoConfEasyAuth._conf_type_separator in inp_conf_type :
            input_confs = inp_conf_type.split(AutoConfEasyAuth._conf_type_separator)
            for conf_type in input_confs:
                if not conf_type in AutoConfEasyAuth._conf_types :
                    return False
        else :
            if not inp_conf_type in AutoConfEasyAuth._conf_types :
                return False
        return True
                     
    
    def validate_params(self):
        """validate parameters that were initialized on object instantiation

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """ 

        ret_code = AutoConfEasyAuth.success

        if (self.inp_args.conf_type == None) or \
           (self.inp_args.domain_name == None) or \
           (self.inp_args.admin_name == None) or \
           (self.inp_args.admin_pass == None) or \
           (self.inp_args.dc_name == None) or \
           (self.inp_args.join_type == None) or \
           (not self._is_valid_conf_type()) or \
           ((self.inp_args.join_type).lower() not in AutoConfEasyAuth._join_types) :
               self.log_file.error('Invalid input parameters')
               ret_code = AutoConfEasyAuth.invalid
           
        return ret_code


    #if input arguments are validated start Easy Auth Auto-Conf
    def run(self):
        """issue an operation an instantiated object to auto-configure auth settings

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """

        ret_code = AutoConfEasyAuth.success

        ret_code = self.validate_params()

        if ret_code == AutoConfEasyAuth.success :
            self.log_file.info('Starting AUTO-CONF EASY AUTH')
            msg = 'Input Arguments: \n' \
                  + ' Configuration type: ' + self.inp_args.conf_type + '\n' \
                  + ' Domain Name: ' + self.inp_args.domain_name + '\n' \
                  + ' Admin User: ' + self.inp_args.admin_name + '\n' \
                  + ' Domain Controller: ' + self.inp_args.dc_name + '\n' \
                  + ' Join Type: ' + self.inp_args.join_type + '\n'
            if self.inp_args.shortdom is not None:
                msg += ' Short Domain Name: ' + self.inp_args.shortdom + '\n'
            if self.inp_args.repl_user_name is not None:
                msg += ' Replication User: ' + self.inp_args.repl_user_name + '\n'
                if self.inp_args.repl_user_dom is not None:
                    msg += ' Replication User Domain: ' + self.inp_args.repl_user_dom \
                           + '\n' + ' Is RODC: ' + self.inp_args.repl_isrodc + '\n'
            self.log_file.info(msg)

            ret_code = self._easyauth_auto_conf()
        return ret_code

    def rollback(self):
        """Rollsback state to what it was before the auto-configuration was issued"""

        self.log_file.notice('Rolling back to original state')
        self.confrepl.rollback()
        self.addrepl.rollback()
        self.setconfig.rollback()
        self.domainjoin.rollback()
        self.testdns.rollback()


def main(args):
    """Main function
        * parse input args
        * start easy auth Auto-Conf
    """

    output         = ''
    result         = ''
    fail_string    = 'Auto-conf FAILED\n'
    success_string = 'Auto-conf Successfully completed\n'
    ret_code       = AutoConfEasyAuth.success

    usage  = 'Usage: %prog options [logfile]'
    parser = optparse.OptionParser(usage=usage, description ='Easy Auth Auto-Conf utility')
    parser.add_option('-t', '--testname', dest = 'test_name',
                            help = 'DomainHealth Test name', default = 'autoconf_easyauth')
    parser.add_option('-C', '--Conf-type', dest = 'conf_type', 
                            help = 'Auto-Configuration type: emapi/smbsigning/smb2signing/emapi,smbsigning/emapi,smb2signing/smbsigning,smb2signing/emapi,smbsigning,smb2signing/all', default = None)
    parser.add_option('-D', '--Domain', dest = 'join_domain',
                            help = 'Join-Domain name', default = None)
    parser.add_option('-A', '--AdminUser', dest = 'admin_user',
                            help = 'Domain Administrator', default = None)
    parser.add_option('-P', '--password', dest = 'admin_password',
                            help = 'Admin User password', default = None)
    parser.add_option('-d', '--DC' , dest ='dc',
                            help = 'Domain Controller hostname', default = None)
    parser.add_option('-j', '--Join-type', dest = 'join_type',
                            help = 'Join type: bdc/rodc', default = None )
    parser.add_option('-s', '--ShortDomain', dest = 'shortdom',
                            help = 'Short Domain name', default = None )
    parser.add_option('-u', '--ReplicationUser', dest = 'repl_user_name',
                            help = 'Replication User name', default = None )
    parser.add_option('-p', '--ReplicationPassword', dest = 'repl_user_pass',
                            help = 'Replication User password', default = None )
    parser.add_option('-R', '--ReplicationDomain', dest = 'repl_user_dom',
                            help = 'Replication User domain', default = None )
    parser.add_option('-r', '--IsRodc', dest = 'repl_isrodc',
                            help = 'Is RODC', default = 'false' )
    parser.add_option('-l', '--loglevel', dest = 'log_level',
                            help = 'Set Minimum logging level', default = 'info' )
    parser.add_option('-m', '--test_mode', action="store_true", dest = 'test_mode',
                            help = 'Run script in test mode', default = False) 
    options, arguments = parser.parse_args()

    if len(arguments) == 0 :
        param_logfile = '/var/log/domaind/autoconf-easyauth'
    else : 
        param_logfile = arguments[0]
   
    inp_args = InputArgs(options.conf_type,
                          options.admin_user,
                          options.admin_password,
                          options.join_domain,
                          options.dc,
                          options.join_type,
                          options.shortdom,
                          options.repl_user_dom,
                          options.repl_user_name,
                          options.repl_user_pass,
                          options.repl_isrodc,
                          options.test_mode)
        
    log_handle = 'domaind/configure/' + options.test_name
    log_file = CustomLogger(log_handle, param_logfile, options.log_level)
    easyauth = AutoConfEasyAuth(inp_args, log_file)

    #open Mgmt session
    Mgmt.open()

    try:
        ret_code = easyauth.run()

        if ret_code == AutoConfEasyAuth.success :
            output = easyauth.inp_args.conf_type + ' ' + success_string
            easyauth.log_file.notice(output)
        else :
            if ret_code == AutoConfEasyAuth.invalid :
                output = 'Options validation for test failed, testname: ' \
                                    + options.test_name + '\n' + fail_string
                easyauth.log_file.error(output)
    except:
        ret_code = AutoConfEasyAuth.error
        output = 'Caught exception while running ' + options.test_name
        output += ': ' + str(sys.exc_info()[1]) + '\n' 
        easyauth.log_file.error(output)
        
    easyauth.result += output

    if ret_code == AutoConfEasyAuth.error:
        easyauth.rollback()
        if easyauth.setconfig.restart_needed :
            output = 'You may need to restart the optimization' + \
                            ' service for the changes to be reverted properly.\n'
            easyauth.result += output
        output = easyauth.inp_args.conf_type + ' ' + fail_string
        easyauth.log_file.error(output)
        easyauth.result += output


    #close Mgmt sessiom
    Mgmt.close()
    
    print >> sys.stdout, easyauth.result

    if ret_code == AutoConfEasyAuth.invalid :
        parser.print_help() # display usage 
    
 

if __name__ == '__main__':
        main(sys.argv)
        
