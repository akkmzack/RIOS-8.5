#!/usr/bin/python

# (C) Copyright 2003-2011 Riverbed Technology, Inc.
# All Rights Reserved. Confidential.



import sys
import optparse
import traceback
import subprocess
from easyConfig import SysLogger, CustomLogger, Test


class InputArgs(object):
    def __init__(self,user,password,shortdom,realm,userrealm,server,service,enduser,iperror,replserver,replkrb):
        self.user       = user
        self.password   = password
        self.shortdom   = shortdom
        self.realm      = realm
        self.userrealm  = userrealm
        self.server     = server
        self.service    = service
        self.enduser    = enduser
        self.iperror    = iperror
        self.replserver = replserver
        self.replkrb    = replkrb

class TestAuthentication(Test):

    _SAMBA_WBINFO_AUTH  = '/usr/local/samba/bin/wbinfo -a'

    def __init__(self, cmd_line_args, log_file=None):
        
        Test.__init__(self, log_file)
        
        self.inp_args              = cmd_line_args
        self.result                = 'Test authentication result: \n\n'
        self.user_with_domain_info = None
        self.cmd_args              = TestAuthentication._SAMBA_WBINFO_AUTH.split()

    def _authentication_test(self):
        ret_code = TestAuthentication.success
        self.cmd_args +=  [ self.user_with_domain_info + '%' \
                                 + self.inp_args.password ]


        output = 'Testing authentication of '+ self.user_with_domain_info \
                      + ' on the joined Domain Controller \n'
        self.result += output
        self.log_file.info(output)

        ret_code , msg, err = TestAuthentication.execute_cmd(self.cmd_args)
        if ret_code == TestAuthentication.success:
            self.result += msg 
            self.log_file.notice(msg)
        else: 
            output = 'Error trying to authenticate: ' + self.user_with_domain_info \
                    + '\n' + err
            ret_code = TestAuthentication.error
            self.result = output
            self.log_file.error(output)
            
        return ret_code 
    
    def validate_params(self):
        """validate parameters that were initialized on object instantiation

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """ 

        ret_code = TestAuthentication.success

        if (self.inp_args.user == None) or \
           (self.inp_args.password == None) :
            self.log_file.error('Invalid input parameters')
            ret_code = TestAuthentication.invalid
        else:
            self.user_with_domain_info = self.inp_args.user
            if self.inp_args.shortdom != None:
                self.user_with_domain_info = self.inp_args.shortdom + '\\' \
                                              + self.inp_args.user
            if self.inp_args.realm != None:
                self.user_with_domain_info = self.inp_args.user + '@' \
                                              + self.inp_args.realm
        return ret_code


    #if input arguments are validated start Authentication test
    def run(self):
        """issue an operation on an instantiated object to test authentication

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """

        ret_code = TestAuthentication.success

        ret_code = self.validate_params()

        if ret_code == TestAuthentication.success :
            self.log_file.info('Starting Authentication test')
            self.log_file.info('Input Arguments: \n' \
                             + ' User: ' + self.inp_args.user + '\n' \
                             + ' Short Domain: ' + str(self.inp_args.shortdom) + '\n')
            ret_code = self._authentication_test()
        return ret_code

class TestTryRepl(Test):

    _SAMBA_WBINFO_VAMPIRE  = '/usr/local/samba/bin/wbinfo'

    def __init__(self, cmd_line_args, log_file=None):
        
        Test.__init__(self, log_file)
        
        self.inp_args              = cmd_line_args
        self.result                = 'Test Replication Try-Repl result:\n\n'
        self.cmd_args              = [ TestTryRepl._SAMBA_WBINFO_VAMPIRE ]

    def _tryrepl_test(self):
        ret_code = TestTryRepl.success
        self.cmd_args += [ '--vampire=' \
                           + self.inp_args.realm + ':' +self.inp_args.shortdom \
                           + '\\' + self.inp_args.replserver \
                           + ',' + self.inp_args.userrealm \
                           + ':' + self.inp_args.userrealm \
                           + '\\' + self.inp_args.user \
                           + '%' + self.inp_args.password ]
        
        if self.inp_args.replkrb == True:
            self.cmd_args += ['--kerberos']


        output = 'Testing ability to replicate a server account\n'
        self.result += output
        self.log_file.info(output)

        ret_code , msg, err = TestTryRepl.execute_cmd(self.cmd_args)
        if ret_code == TestTryRepl.success:
            self.result += msg 
            self.log_file.notice(msg)
        else: 
            output = err 
            ret_code = TestTryRepl.error
            self.result = output
            self.log_file.error(output)
            
        return ret_code 
    
    def validate_params(self):
        """validate parameters that were initialized on object instantiation

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """ 

        ret_code = TestTryRepl.success

        if (self.inp_args.user == None) or \
           (self.inp_args.password == None) or \
           (self.inp_args.shortdom == None) or \
           (self.inp_args.replserver == None) or \
           (self.inp_args.realm == None) or \
           (self.inp_args.userrealm == None):
            self.log_file.error('Invalid input parameters')
            ret_code = TestTryRepl.invalid
        else:
            self.inp_args.realm = self.inp_args.realm.upper()
            self.inp_args.userrealm = self.inp_args.userrealm.upper()
            self.inp_args.shortdom = self.inp_args.shortdom.upper()
        return ret_code


    #if input arguments are validated start Authentication test
    def run(self):
        """issue an operation on an instantiated object to test ability to replicate a server account

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """

        ret_code = TestTryRepl.success

        ret_code = self.validate_params()

        if ret_code == TestTryRepl.success :
            self.log_file.info('Starting Replicating server account test')
            self.log_file.info('Input Arguments: \n' \
                             + ' User: ' + self.inp_args.user + '\n' \
                             + ' User Realm: ' + self.inp_args.userrealm + '\n'
                             + ' Short Domain: ' + self.inp_args.shortdom + '\n'
                             + ' Replication server: ' + self.inp_args.replserver + '\n'
                             + ' Domain/Realm: ' + self.inp_args.realm + '\n')
            ret_code = self._tryrepl_test()
        return ret_code

class TestConstDelegation(Test):


    #allowed service types
    _service_types        = [ 'cifs', 'exchangeMDB']
    _HEIM_TOOLS_BIN       = '/usr/heimdal/bin'
    _DELEGATED_USER       = 'user'
    _IMPERSONATED_USER    = 'impersonate'
    _IMPERSONATION_TICKET = 'impersonation'
    _SERVICE_TICKET       = 'service'




    def __init__(self, cmd_line_args, log_file=None):

        Test.__init__(self, log_file)

        self.inp_args     = cmd_line_args
        self.result       = 'Test delegation server-privs result:\n\n'
        self.fuser        = None
        self.fserver      = None
        self.fenduser     = None
        self.cmd_args     = []

    def _run_command(self,cmd_args):
        ret_code, output, err = TestConstDelegation.execute_cmd(cmd_args)
        if err:
            self.log_file.error(err)
            ret_code = TestConstDelegation.error
        return ret_code, output, err
    
    def _is_dir(self, dir_name):
        import os.path
        return os.path.isdir(dir_name)

    def _create_temp_dir(self):
        import tempfile
        ret_code = TestConstDelegation.success
        dir_name = tempfile.mkdtemp(prefix='.krbcdtmp')
        if not self._is_dir(dir_name) :
            ret_code = TestConstDelegation.error
        return ret_code, dir_name

    def _remove_temp_dir(self, temp_dir):
        import shutil
        ret_code = TestConstDelegation.success
        shutil.rmtree(temp_dir)
        if self._is_dir(temp_dir) :
            ret_code = TestConstDelegation.error
        return ret_code

    def _write_passwd_to_temp_file(self, temp_dir):
        passwd_file = open(temp_dir + '/pass' , 'w')
        passwd_file.write(self.inp_args.password)
        passwd_file.close()

    def _delegate_user_CC(self, temp_dir, type):
        deleg_user_CC_cmd_args = [TestConstDelegation._HEIM_TOOLS_BIN + '/klist',  '-c', \
                                  temp_dir + '/' + type + '_cc']
        ret_code, output, err = self._run_command(deleg_user_CC_cmd_args)
        return ret_code, output, err

    def _run_kinit(self, temp_dir):
        run_kinit_args = [TestConstDelegation._HEIM_TOOLS_BIN + '/kinit',
                          '--forwardable', 
                          '--cache=' + temp_dir + '/user_cc',
                          '--password-file=' + temp_dir + '/pass',
                          self.fuser]
        ret_code, output, err = self._run_command(run_kinit_args)
        return ret_code, output, err

    def _get_ticket(self, temp_dir, ticket_type ):
        run_kgetcred_args = [ TestConstDelegation._HEIM_TOOLS_BIN + '/kgetcred',
                              '--cache=' + temp_dir + '/user_cc']
        if ticket_type == TestConstDelegation._IMPERSONATION_TICKET:
            run_kgetcred_args += ['--impersonate='+ self.fenduser,
                                  '--out-cache=' + temp_dir + '/impersonate_cc',
                                  '--forwardable' ,
                                  self.fuser]
        elif ticket_type == TestConstDelegation._SERVICE_TICKET:
            run_kgetcred_args += ['--delegation-credential-cache=' + temp_dir \
                                   + '/impersonate_cc',
                                   '--forwardable',
                                   '--out-cache=' + temp_dir + '/service_cc',
                                   self.inp_args.service + '/' + self.fserver]
        ret_code, output, err = self._run_command(run_kgetcred_args)
        return ret_code, output, err

    def _log_cmd_exec_messages(self, output_msg, error_msg, cmd_ret, cmd_output, cmd_err):
        if cmd_ret:
            if cmd_err :
                 error_msg += ': ' + cmd_err
            if error_msg:
                self.result += error_msg
                self.log_file.error(error_msg)
        else:
            output_msg += cmd_output + '\n'
            if output_msg:
                self.result += output_msg
                self.log_file.notice(output_msg)

    def _constdeleg_test(self):
        ret_code = TestConstDelegation.success
        temp_dir = ''
        output   = ''
        impersonation_ticket_err = False
        service_ticket_err = False

        ret_code, temp_dir = self._create_temp_dir();

        if ret_code == TestConstDelegation.success:
            self._write_passwd_to_temp_file(temp_dir)
            output += 'Testing constrained delegation for:\nUser: ' + self.fuser + '\n' \
                      + 'Server: ' + self.fserver + '\n' \
                      + 'Service: ' + self.inp_args.service + '\n' \
                      + 'EndUser: ' + self.fenduser + '\n\n'
            self.result += output
            self.log_file.info(output)
            ret_code , msg, err = self._run_kinit(temp_dir)
            if ret_code == TestConstDelegation.success:
                self.log_file.info('Trying to obtain impersonation ticket for ' + self.fenduser)
                ret_code , msg, err = \
                           self._get_ticket(temp_dir,TestConstDelegation._IMPERSONATION_TICKET)
                if ret_code == TestConstDelegation.success:
                    self.log_file.notice('Successfully obtained impersonation ticket')
                    self.log_file.notice('Trying to obtain service ticket for '\
                                           + self.inp_args.service + '/' + self.fserver)
                    ret_code , msg, err = \
                               self._get_ticket(temp_dir, TestConstDelegation._SERVICE_TICKET)
                    if ret_code == TestConstDelegation.success:
                        self.log_file.notice('Successfully obtained service ticket')
                        self._remove_temp_dir(temp_dir)
                        if ret_code == TestConstDelegation.success:
                            output = 'Constrained delegation settings are fine.\n'
                            self.result += output
                            self.log_file.notice(output)
                            return ret_code
                    else:
                        service_ticket_err = True
                        error = 'Error in obtaining service ticket for ' \
                                      +  self.inp_args.service + '/' + self.fserver + '\n'
                else:
                    impersonation_ticket_err = True
                    error = 'Error in obtaining impersonation ticket for ' + self.fenduser + '\n'
            else:
                error = 'Error in kinit. Could not obtain initial TGT for ' + self.fuser + '\n'

            self.result = error
            self.log_file.error(error)
            if impersonation_ticket_err == True or service_ticket_err == True:
                output = 'Delegate user\'s CC: '
                error  = 'Error trying to get Delegate user\'s CC'
                ret , msg , err = \
                      self._delegate_user_CC(temp_dir,TestConstDelegation._DELEGATED_USER)
                self._log_cmd_exec_messages(output, error, ret, msg, err)
                if service_ticket_err == True:
                    output = 'Impersonated user\'s CC: '
                    error  = 'Error trying to get Delegate user\'s CC'
                    ret , msg , err = \
                          self._delegate_user_CC(temp_dir,TestConstDelegation._IMPERSONATED_USER)
                    self._log_cmd_exec_messages(output, error, ret, msg, err)
            self. _remove_temp_dir(temp_dir)
            
            error = 'Constrained delegation settings are broken.\n'
            self.log_file.error(error)

        return ret_code

    def validate_params(self):
        """validate parameters that were initialized on object instantiation

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """

        ret_code = TestConstDelegation.success

        if (self.inp_args.user == None) or \
           (self.inp_args.password == None) or \
           (self.inp_args.server == None) or \
           (self.inp_args.service == None) or \
           (self.inp_args.realm == None) or \
           (self.inp_args.service not in TestConstDelegation._service_types) :
            self.log_file.error('Invalid input parameters')
            ret_code = TestConstDelegation.invalid
        else:
            self.inp_args.realm      = self.inp_args.realm.upper()
            self.fuser               = self.inp_args.user + '@' + self.inp_args.realm
            self.fserver             = self.inp_args.server + '.' \
                                       + self.inp_args.realm \
                                       + '@' + self.inp_args.realm
            if self.inp_args.enduser == None or self.inp_args.enduser == '':
                self.inp_args.enduser = self.inp_args.user
                self.log_file.notice('Using delegate user: ' + self.inp_args.user +' as the end user')
            self.fenduser            = self.inp_args.enduser + '@' + self.inp_args.realm

        return ret_code


    #if input arguments are validated start Constrained delegation test
    def run(self):
        """issue an operation on an instantiated object to start a constrained delegation test

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """

        ret_code = TestConstDelegation.success

        ret_code = self.validate_params()

        if ret_code == TestConstDelegation.success :
            self.log_file.info('Starting Test delegation privileges for server: ' + self.inp_args.server)
            self.log_file.info('Input Arguments: \n' \
                             + ' User: ' + self.inp_args.user + '\n' \
                             + ' Domain Name: ' + self.inp_args.realm + '\n' \
                             + ' Server Name: ' + self.inp_args.server + '\n' \
                             + ' Service: ' + self.inp_args.service + '\n' \
                             + ' Enduser: ' + self.inp_args.enduser + '\n' )
            if self.inp_args.iperror is None :
                ret_code = self._constdeleg_test()
            else :
                ret_code = TestConstDelegation.error
                self.result += self.inp_args.iperror + '\n'
                self.log_file.error(self.inp_args.iperror)
        return ret_code

class TestJoin(Test):

    _NET_ADS_TESTJOIN  = '/usr/local/samba/bin/net ads testjoin -d10'
    _DEBUG_LOGS_TESTJOIN = '/var/log/domaind/net_ads_testjoin'

    def __init__(self, cmd_line_args, log_file=None):
        
        Test.__init__(self, log_file)
        self.testjoin_logs              = open(TestJoin._DEBUG_LOGS_TESTJOIN, 'w') 
        self.result                = 'Test Join result:\n\n'
        self.cmd_args              = TestJoin._NET_ADS_TESTJOIN.split()
   
    def _testjoin(self):
            
        output = 'Testing if SH is joined to a domain\n'
        self.result += output
        self.log_file.info(output)

        ret_code , msg, logs = TestJoin.execute_cmd(self.cmd_args)
        if ret_code == TestJoin.success:
            self.result += msg 
            self.log_file.notice(msg)
        else: 
            ret_code = TestJoin.error
            self.result = msg
            self.log_file.error(msg)
            self.log_file.notice('Please check ' + TestJoin._DEBUG_LOGS_TESTJOIN + ' for detailed logs')
        print >> self.testjoin_logs, logs
        self.testjoin_logs.close()
        return ret_code 

    #start domain join test (no params to validate)
    def run(self):
        """issue an operation on an instantiated object to start a domain join test

        returns:
            (ret_code)
            ret_code -> zero on success and non-zero on error
        """

        ret_code = TestJoin.success

        self.log_file.info('Starting Domain Join Test')
        ret_code = self._testjoin()
        return ret_code

def main(args):
    """Main function
        * parse input args
        * start test
    """

    output         = ''
    result         = ''
    output_prefix  = ''
    fail_string    = ' FAILED\n'
    success_string = ' Succeeded\n'
    ret_code       = Test.success
    logfile_prefix = '/var/log/domaind/'

    #dictionary of testnames mapped to a list of values pertaining to the class
    #the list holds at index [0] -> a verbose alias of the test name
    #                        [1] -> logfile to log messages to for the test
    #                        [2] -> name of the class to instatiate based on test name
    alias_index     = 0
    logfile_index   = 1
    classname_index = 2
    test_name_map   = { 'test_const_deleg' : [ 'Delegation server-privs test',
                                               'testdelegationserver-privs',
                                               TestConstDelegation ]       ,
                        'auth_test'        : [ 'Authentication Test',
                                               'testauthentication',
                                               TestAuthentication ]        ,
                        'repl_test'        : [ 'Replicating server account Test',
                                               'testreplicationtry-repl',
                                               TestTryRepl ]                    ,
                        'join_test'        : [ 'Domain Join Test',
                                               'testjoin',
                                               TestJoin ]                      }

    usage  = 'Usage: %prog --testname <test name> options [logfile] \n\n\
      This utiliy currently supports 4 tests that be invoked as following:\n\n\
      Delegation server-privs test:\n\
        %prog -t test_const_deleg -u <user name> -p <password> -S <server name> -v <service> -r <domain name> [-e <end user>] [-i <ip-error>] [-l <log_level> logfile]\n\n\
      Authentication Test:\n\
        %prog -t auth_test -u <user name> -p <password> [-s <short domain>] [-r <domain_name>] [ -l <log_level> logfile]\n\n\
      Replicating server account test:\n\
        %prog -t repl_test -r <domain name> -s <short domain> -f <replication server> -u <user name> -p <password> -w <user realm> [-k] [-l <log_level> logfile]\n\n\
      Domain Join Test:\n\
        %prog -t join_test [-l <log_level> logfile]\n'

    parser = optparse.OptionParser(usage=usage, description ='Domaind Health Test utility')
    parser.add_option('-t', '--testname', dest = 'test_name',
                            help = 'DomainHealth Test name', default = None )
    parser.add_option('-u', '--user', dest = 'user', 
                            help = 'User name', default = None)
    parser.add_option('-p', '--password', dest = 'password',
                            help = 'User\'s password.', default = None)
    
    parser.add_option('-s', '--shortdom', dest = 'shortdom',
                            help = 'Short domain name.', default = None)
    parser.add_option('-r', '--realm', dest = 'realm',
                            help = 'Realm/Domain.', default = None )
    parser.add_option('-w', '--user-realm', dest = 'user_realm',
                            help = 'Realm/Domain of the user.', default = None )
    parser.add_option('-S', '--servername', dest = 'server',
                            help = 'Windows CIFS/Exchange server.', default = None )
    parser.add_option('-v', '--service', dest = 'service',
                            help = 'Admin Service name [cifs|exchangeMDB]. Default: cifs', default = 'cifs')  
    parser.add_option('-e', '--enduser' , dest ='enduser',
                            help = 'Optional EndUser (Default : -u).', default = None)
    parser.add_option('-i', '--iperror' , dest ='iperror',
                            help = 'Optional server-IP validation error string', default = None)
    parser.add_option('-f', '--replicationserver', dest = 'replserver',
                            help = 'Replication Server.', default = None )
    parser.add_option('-l', '--loglevel', dest = 'loglevel',
                            help = 'Minimum log level', default = 'info' )
    parser.add_option('-k', '--repl_krb', action="store_true", dest = 'replkrb',
                            help = 'Kerberos', default = False) 


    options, arguments = parser.parse_args()

    if options.test_name is None or \
       options.test_name not in test_name_map.keys():
           print >> sys.stdout, 'Test invoked with invalid test name'
           return Test.invalid

    if len(arguments) == 0 :
        param_logfile = None
    else : 
        param_logfile = arguments[0]

    inp_args = InputArgs(options.user,
                         options.password,
                         options.shortdom,
                         options.realm,
                         options.user_realm,
                         options.server,
                         options.service,
                         options.enduser,
                         options.iperror,
                         options.replserver,
                         options.replkrb)
 

    output_prefix  =  test_name_map.get(options.test_name)[alias_index]
    fail_string    =  output_prefix + fail_string
    success_string =  output_prefix + success_string
    if param_logfile is None:
        param_logfile = logfile_prefix + test_name_map.get(options.test_name)[logfile_index]
    log_file = CustomLogger('domain_auth/' + options.test_name, param_logfile, options.loglevel)
    cls = test_name_map.get(options.test_name)[classname_index]
    domainhealthtest = cls(inp_args, log_file)
    ret_code = domainhealthtest.run()

    if ret_code == Test.success :
        output = success_string
        domainhealthtest.log_file.notice(output)
    else :
        if ret_code == Test.invalid :
            output = 'Options validation for test failed, testname: ' \
                                    + options.test_name + '\n' + fail_string
        else :
            output = fail_string
        domainhealthtest.log_file.error(output)
    domainhealthtest.result += output

    print >> sys.stdout, domainhealthtest.result
    return ret_code


if __name__ == '__main__':
    ret_code = main(sys.argv)
    if ret_code is not Test.success:
	sys.exit(1)
	
        
