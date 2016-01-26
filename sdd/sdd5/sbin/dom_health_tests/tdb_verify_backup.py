#!/usr/bin/python

# (C) Copyright 2003-2011 Riverbed Technology, Inc.
# All Rights Reserved. Confidential.



import sys
import optparse
import traceback
import subprocess
import shutil
import os
import fcntl
from easyConfig import SysLogger, CustomLogger, Test, TimeoutFunction, TimeoutFunctionException

class TDBManager(Test):

    TDB_CMD                  = '/usr/local/samba/bin/tdbbackup'
    MAX_SIZE                 = 209715200 # 200MB
    CORRUPT_TDB_FILES_DIR    = '/var/log/rcu/tdb_corrupt'
    TDB_FILES_LIST           = [ '/var/samba/private/secrets.tdb',
                                 '/var/samba/var/locks/account_policy.tdb',
                                 '/var/samba/var/locks/brlock.tdb',
                                 '/var/samba/var/locks/connections.tdb',
                                 '/var/samba/var/locks/gencache.tdb',
                                 '/var/samba/var/locks/group_mapping.tdb',
                                 '/var/samba/var/locks/idmap_cache.tdb',
                                 '/var/samba/var/locks/locking.tdb',
                                 '/var/samba/var/locks/messages.tdb',
                                 '/var/samba/var/locks/netsamlogon_cache.tdb',
                                 '/var/samba/var/locks/ntdrivers.tdb',
                                 '/var/samba/var/locks/ntforms.tdb',
                                 '/var/samba/var/locks/ntprinters.tdb',
                                 '/var/samba/var/locks/sessionid.tdb',
                                 '/var/samba/var/locks/share_info.tdb',
                                 '/var/samba/var/locks/unexpected.tdb',
                                 '/var/samba/var/locks/winbindd_cache.tdb',
                                 '/var/samba/var/locks/winbindd_idmap.tdb',
                                 '/var/samba/var/locks/notify.tdb"']
    TDB_FILES_RETAIN_LIST    = [ 'var/samba/private/secrets.tdb',
                                 '/var/samba/var/locks/winbindd_idmap.tdb']
    RESTART_ACTION           = '/pm/actions/restart_process'
    JOIN_STATUS_NODE         = '/rbt/rcu/domain/status'
    JOINED_STATUS            = 'In a domain'
    CMD_EXEC_TIMEOUT         = 45
    RESTORE_CMD_EXEC_TIMEOUT = 300
    CMD_EXEC_POLL            = 1

    def __init__(self, log_file=None, loghandle_name=None):
        Test.__init__(self, log_file, loghandle_name)
        self.is_tdb_file_corrupted = False
	unit_test_mode             = False

    @staticmethod
    def is_duplicate_task(task):
        task_name = os.path.basename(task)
        lock_file = os.path.join('/var/run', task_name + '.lockfile')
        lock_file_fd = os.open(lock_file, os.O_CREAT | os.O_TRUNC | os.O_WRONLY)
        try:
            fcntl.flock(lock_file_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            return True
        return False
    
    def is_joined_to_domain(self):
        if self.unit_test_mode :
	   return True
        return (TDBManager.JOINED_STATUS == TDBManager.get_node_value( \
                                                 TDBManager.JOIN_STATUS_NODE))

    @staticmethod
    def is_file_exists(filename):
        return os.path.exists(filename)
    
    @staticmethod
    def file_size(filename):
        file_size = 0
        if os.path.exists(filename) :
            file_stat = os.stat(filename)
            file_size = file_stat.st_size
        return file_size
    
    def remove_tdb_file(self, file_name) :
        if file_name not in TDBManager.TDB_FILES_RETAIN_LIST :
            self.log_file.warn('Removing and regenerating: ' + file_name)
            os.remove(file_name)

    def is_tdb_size_greater_than_max(self, file_name):
        is_corrupt = False
        # if tdb file is > 200 MB, log an error
        if TDBManager.file_size(file_name) > TDBManager.MAX_SIZE :
            self.log_file.error('Skipping file: ' + file_name \
                                   + ' File size is > ' + TDBManager.MAX_SIZE \
                                                  + ' Bytes, may be corrupted')
            self.remove_tdb_file(file_name)
            self.is_tdb_file_corrupted = True
            is_corrupt = True
        return is_corrupt
    
    def run_cmd_with_timeout(self, command, timeout):
        ret_code = TDBManager.success
        output = None
        error = None
        command_exec = TimeoutFunction(command, timeout, \
                                                TDBManager.CMD_EXEC_POLL, True)
        try:
            ret_code, output, error = command_exec()
        except TimeoutFunctionException:
            ret_code = None
            self.log_file.info( 'Timing Out!!! command=' + command \
                                                    + ' did not complete in '\
                                                    + str(timeout) + 'secs')
        else:
            if error is not None and len(error) :
                self.log_file.error(error)
                
        return ret_code

    def log_success(self, cmd_name, file_name):
        self.log_file.info( 'TDB ' + cmd_name + ' on file: ' \
                                                   + file_name + ' successful')

    def log_corruption(self, cmd_name, file_name):
        self.is_tdb_file_corrupted = True
        self.log_file.warn('TDB ' + cmd_name + ' failed!!!.' \
                            + ' Corruption detected in tdb file: ' + file_name)
        if file_name in TDBManager.TDB_FILES_RETAIN_LIST :
            self.log_file.warn('Domain state may be invalid ' \
                           + 'because of corruption in tdb file: ' + file_name)

    def move_corrupt_file(self, src_filepath):
        self.log_file.error(src_filepath + ' might be ' \
                                                     + 'corrupt, moving it...')
        dst_filename = os.path.basename(src_filepath)
        dst_filedir = TDBManager.CORRUPT_TDB_FILES_DIR
        if not os.path.exists(dst_filedir) :
            os.mkdir(dst_filedir)
        dst_filepath = os.path.join(dst_filedir, dst_filename)
        shutil.move(src_filepath, dst_filepath)
        
    def check_tdb_file(self, file_name):
        # corruption check command
        corruption_check_cmd = TDBManager.TDB_CMD + ' -c ' + file_name
        self.log_file.debug(corruption_check_cmd)
        ret_code = self.run_cmd_with_timeout(corruption_check_cmd,\
                                                   TDBManager.CMD_EXEC_TIMEOUT)
        return ret_code

    def is_tdb_corrupt(self, file_name):
        # not corrupt if file does not exist
        if not TDBManager.is_file_exists(file_name) :
            return False
        if self.is_tdb_size_greater_than_max(file_name) :
            return True
        cmd_name = 'corruption check'
        ret_code = self.check_tdb_file(file_name)
        if(ret_code == TDBManager.success) :
            self.log_success(cmd_name, file_name)
            return False
        self.log_corruption(cmd_name, file_name)
        if ret_code != TDBManager.error :
            self.move_corrupt_file(tdb_file)
        return True

    def backup_tdb_file(self, file_name):
        # backup file 
        backup_cmd = TDBManager.TDB_CMD + ' ' + file_name
        self.log_file.debug(backup_cmd)
        ret_code = self.run_cmd_with_timeout(backup_cmd, \
                                                   TDBManager.CMD_EXEC_TIMEOUT)
        return ret_code

    # backup if not corrupt, returns True if backup succeded and False
    # is backup failed or file was corrupt to start with
    def try_tdb_backup(self, is_corrupt, file_name):
        if not TDBManager.is_file_exists(file_name) or is_corrupt :
            return False
        cmd_name = 'backup'
        ret_code = self.backup_tdb_file(file_name)
        if ret_code == TDBManager.success :
            self.log_success(cmd_name, file_name)
            return True
        self.log_corruption(cmd_name, file_name)
        self.move_corrupt_file(file_name)
        return False


    def restore_tdb_file(self, file_name):
        # verify and restore
        verify_cmd = TDBManager.TDB_CMD + ' -v ' + file_name
        self.log_file.debug(verify_cmd)
        ret_code = self.run_cmd_with_timeout(verify_cmd, \
                                          TDBManager.RESTORE_CMD_EXEC_TIMEOUT)
        return ret_code

    #restore if corrupt, returns True if file was restored, false otherwise
    def try_tdb_restore(self, is_backed_up, file_name) :
        if not TDBManager.is_file_exists(file_name) or is_backed_up :
            return True
        cmd_name = 'recovery from backup'
        ret_code = self.restore_tdb_file(file_name)
        if ret_code == TDBManager.success or \
            self.check_tdb_file(file_name) == TDBManager.success :
            self.log_success(cmd_name, file_name)
            return True
        self.log_corruption(cmd_name, file_name)
        self.move_corrupt_file(file_name)
        return False
    
    def restart_process(self, process_name):
        ret_code = self.is_process_running(process_name)
        if ret_code == TDBManager.success :
            action_param = [('process_name', 'string', process_name)]
            ret_code, msg, bindings = TDBManager.trigger_action( \
                                       TDBManager.RESTART_ACTION, action_param)
        return ret_code 
    
    def restart_smbd_process(self):
        ret_code = self.restart_process('smb')

    def restart_winbindd_process(self):
        ret_code = self.restart_process('winbind')

    def restart_samba_processes(self):
        self.restart_smbd_process()
        self.restart_winbindd_process()
   
    def run(self):
       ret_code = TDBManager.success
       recover_tdb_file = False
       is_restored = []

       if not self.is_joined_to_domain() :
           self.log_file.notice('Not joined to domain exiting...')
           return ret_code
       
       is_restored = map(self.try_tdb_restore, \
                        map(self.try_tdb_backup, \
                          map(self.is_tdb_corrupt, TDBManager.TDB_FILES_LIST) \
                                                 , TDBManager.TDB_FILES_LIST)\
                                                   , TDBManager.TDB_FILES_LIST)

       if self.is_tdb_file_corrupted :
           if False in is_restored :
               self.log_file.error('One or more corrupted files could not be restored.')
               ret_code = TDBManager.error
           else :
               self.log_file.notice('Corrupted files successfully restored.')
           self.log_file.info('Restarting smb processes...')
           if not self.unit_test_mode :
           	self.restart_samba_processes()

       return ret_code


def main(args):
    """Main function
        * start verification and backup 
    """

    ret_code       = Test.success
    task_name      = 'TDB file verification and backup utility'
    loghandle_name = 'domain_auth/tdb_verify_backup'
    log_file       = None
    success_msg    = 'TDB file verification and backup successfully completed.'
    fail_msg       = 'TDB file verification and backup encountered problems.'
    result         = ''

    usage  = 'Usage: %prog [-l <log_level> logfile]'
    parser = optparse.OptionParser(usage=usage, description=task_name)
    parser.add_option('-l', '--loglevel', dest = 'loglevel',
                            help = 'Minimum log level', default = 'info' )
    parser.add_option('-m', '--test_mode', action="store_true", dest = 'test_mode',
                            help = 'Run script in test mode', default = False) 

    options, arguments = parser.parse_args()
        
    if len(arguments) == 0 :
        param_logfile = None
    else : 
        param_logfile = arguments[0]
        log_file = CustomLogger(loghandle_name, param_logfile, options.loglevel)
   

    tdbmanager = TDBManager(log_file, loghandle_name)
    
    tdbmanager.unit_test_mode = options.test_mode
        
    if TDBManager.is_duplicate_task(args[0]):
        output = 'Cannot run ' + task_name \
                                      + ' while an existing run is in progress.\n'
        result += output
        tdbmanager.log_file.error(output)
        ret_code = TDBManager.error

    else :
        if not tdbmanager.unit_test_mode :
	    import Mgmt
	    # open Mgmt session
            Mgmt.open()

        try:
            ret_code = tdbmanager.run()
            if ret_code == TDBManager.success :
                result += success_msg
                tdbmanager.log_file.notice(success_msg)
        except:
            ret_code = TDBManager.error
            output = 'Caught exception while running ' + task_name \
                                        + ' : ' + str(sys.exc_info()[1]) + '\n' 
            tdbmanager.log_file.error(output)
        
        if not tdbmanager.unit_test_mode :
            # close Mgmt session
            Mgmt.close()

    if ret_code == TDBManager.error :
        result += fail_msg
        tdbmanager.log_file.error(fail_msg)

    print >> sys.stdout, result

    return ret_code

if __name__ == '__main__':
    ret_code = main(sys.argv)
    if ret_code is not Test.success:
	sys.exit(1)
	
        
