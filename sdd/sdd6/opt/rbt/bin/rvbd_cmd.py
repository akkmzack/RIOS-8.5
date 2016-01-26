#!/usr/bin/env python
#
# -*- python -*-
#
# (C) Copyright 2003-2009 Riverbed Technology, Inc.
# All rights reserved. Confidential.
#
"""rvbd_cmd - Classes related to invoking commands on VA"""
#------------------------------------------------------------------------------
# NOTE: How to debug vadebug with the python debugger.
# python
# import pdb
# import rvbd_cmd
# from rvbd_cmd import *
# # Replace the string below with the command line parameters
# sys.argv.extend("shell ls 10.1.36.211".split())
# sys.argv[0] = "./rvbd_cmd.py"
# pdb.Pdb().run("rvbd_cmd._rvbd_cmd_main()")
#------------------------------------------------------------------------------
import fcntl, os, re, sys, time
from optparse import OptionParser

try :
    import paramiko
except ImportErrror:
    print "Can not import parmiko.  Get and install it as below:"
    print " wget http://apt.sw.be/redhat/el4/en/i386/rpmforge/RPMS" \
          "/python-paramiko-1.7.6-1.el4.rf.noarch.rpm"
    print " wget http://apt.sw.be/redhat/el4/en/i386/rpmforge/RPMS" \
          "/rpmforge-release-0.5.2-2.el4.rf.i386.rpm"
    print " rpm -Uvh rpmforge-release-0.5.2-2.el4.rf.i386.rpm"
    print " yum install python-paramiko-1.7.6-1.el4.rf.noarch.rpm"
    raise ImportError

from socket import *

#------------------------------------------------------------------------------
# Uncomment one of each of these.

# Select the second to debug rvbd_cmd.py called from io_analyzer.sh.
_debug = 0                              # -O Debug option setting
#_debug = 256

# Of .read and .recv
#_size=1
#_size=256
_size=4096

def _report_config():
    global _debug
    global _size
    print >>sys.stderr, \
          "CONFIG: _debug=%d, _size=%d" % (_debug, _size)

#------------------------------------------------------------------------------
# Regular expressions to recogninze the various VA shell prompts
_prompt_command_server = "(cmd> ?|cmdsvr> ?)"

_prompt_shell = "\\[[^\\]\n]+ [^\\]\n]+\\]# ?"
_prompt_cli_basic = "\\S+ > ?"
_prompt_cli_enable = "\\S+ # ?"
_prompt_cli_config = "\\S+ \\(config\\) # ?"

# Combinations
_prompt_cli_any = "(%s|%s|%s)" % (
    _prompt_cli_basic, _prompt_cli_enable, _prompt_cli_config )
_prompt_shell_or_cli = "(%s|%s|%s|%s)" % (
    _prompt_shell, _prompt_cli_basic, _prompt_cli_enable, _prompt_cli_config )
_prompt_command_server_or_cli = "(%s|%s|%s|%s)" % (
    _prompt_command_server, _prompt_cli_basic, _prompt_cli_enable,
    _prompt_cli_config )
_prompt_any = "(%s|%s|%s|%s|%s)" % (
    _prompt_shell, _prompt_cli_basic, _prompt_cli_enable, _prompt_cli_config,
    _prompt_command_server )

#------------------------------------------------------------------------------
# Perform a command-server command
def _recv_from_net(sock, prompt=_prompt_any, remove_prompt=True,
                   recvsize=_size):
    global _debug                   # In
    global _prompt_command_server
    if (_debug & 256) != 0:
        print >>sys.stderr, \
        "_recv_from_net(sock=%s, prompt='%s', remove_promt=%s, recvsize=%d)" %(
            sock, prompt, remove_prompt, recvsize)
    if prompt != None:
        pattern = "(" + prompt + ")$"
        regex = re.compile(pattern, re.DOTALL)
        if (_debug & 256) != 0:
            print >>sys.stderr, "_recv_from_net: pattern is '%s'" % pattern
    result = ""
    times_zero = 0
    while True:
        if (_debug & 256) != 0:
            len_result = len(result)
            if len_result > 256:
                print >>sys.stderr, \
                      "_recv_from_net: Got %d, Receiving %d, Have %d" % (
                    len_buf, recvsize, len_result)

            elif len_result > 0:
                print >>sys.stderr, \
                      "_recv_from_net: Got %d, Receiving %d, Have %d '%s'" % (
                    len_buf, recvsize, len_result, result )
            else:
                print >>sys.stderr, \
                      "_recv_from_net: Receiving %d, Have %d '%s'" % (
                    recvsize, len_result, result )
        buf = sock.recv(recvsize)
        len_buf = len(buf)
        if len_buf == 0:
            times_zero += 1
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "_recv_from_net: Got 0 for %d times, so far %d '%s'" % (
                    times_zero, len_result, result )
            if times_zero == 5:
                break
            else:
                continue
        result += buf
        if (_debug & 256) != 0:
            len_result = len(result)
            if len_result <= 256:
                print >>sys.stderr, \
                      "_recv_from_net: Got %d '%s', so far %d '%s'" % (
                    len_buf, buf, len_result, result )
            else:
                print >>sys.stderr, \
                      "_recv_from_net: Got %d '%s', so far %d" % (
                    len_buf, buf, len_result)
        if prompt != None:
            if len_buf >= 100:
                to_search = buf
            else:
                to_search = result
            if regex.search(to_search):
                if (_debug & 256) != 0:
                    print >>sys.stderr, "_recv_from_net: Matched prompt"
                break
    if (prompt != None) and remove_prompt:
        m = regex.search(result)
        if m:
            prompt = m.group(1)
            len_result = len(result) - len(prompt)
            result = result[0:len_result]
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "_recv_from_net: Removed prompt: '%s' leaving '%s'" % (
                    prompt, result)
    assert type(result) == type(""), "Invalid type"
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "_recv_from_net: Returned %d '%s', remove_prompt:%s" % (
            len(result), result, remove_prompt)
    return result

# Perform a command-server command
def do_net_cmd(cmd, sock, remove_prompt=True, recvsize=_size):
    """Perform a command-server command to socket SOCK."""
    global _debug                   # In
    global _prompt_command_server
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_net_cmd(cmd='%s', sock=%s, remove_prompt=%s, recvsize=%d)" %(
            cmd, sock, remove_prompt, recvsize)
    sock.send(cmd + "\n")
#    print >>sys.stderr, "Sleeping...  For command via socket to execute" # New
#    time.sleep(2)
    result = _recv_from_net(sock, _prompt_command_server, remove_prompt,
                            recvsize)
    return result

def _open_socket(msg, ip, port, timeout=100):
    global _debug                   # In
    sock = socket(AF_INET, SOCK_STREAM)
    err = sock.connect_ex((ip, int(port)))
    if err != 0:
        print >>sys.stderr, "Could not telnet to %s: %s:%s" % (
            msg, ip, port)
        return None
    sock.settimeout(timeout)
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "Opened socket %s: %s:%s timeout %s returned '%s'" % (
            msg, ip, port, timeout, sock)
    print >>sys.stderr, "Sleeping...  For socket opened" # Old
    time.sleep(2)
    return sock

def open_socket_for_command_server(msg, ip, port=7980,
                                   timeout=100, recvsize=_size):
    global _debug                   # In
    sock = _open_socket(msg, ip, port, timeout)
    if sock != None:
        if (_debug & 256) != 0:
            print >>sys.stderr, \
                  "open_socket_for_command_server: Receiving %d" % recvsize
        buf = sock.recv(recvsize)
        if (_debug & 256) != 0:
            print >>sys.stderr, \
                  "open_socket_for_command_server: Got %d '%s'" % (
                len(buf), buf)
        if (not buf.endswith("cmd> ")) and (not buf.endswith("cmdsvr> ")):
            print >>sys.stderr, \
                  "Wrong greeting from %s command server: %s" % (msg, buf)
            if (_debug & 256) != 0:
                print >>sys.stderr, "Closing socket '%s'" % sock
            sock.close()
            sock = None
    return sock

#------------------------------------------------------------------------------
def _do_ssh_cmd_with_prompt(cmd, files, prompt=_prompt_any, remove_prompt=True,
                            close_files=False, recvsize=_size):
    """Perform a shell, command-server, or cli command via ssh via paramiko."""
    global _debug                   # In
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_ssh_cmd_via_paramiko(cmd='%s', files='%s', prompt='%s'," \
              " remove_prompt=%s, recvsize=%d)" % (
            cmd, files, prompt, remove_prompt, recvsize)
    tty = files.get('tty', None)
    if tty == None:
        return None
    tty.send(cmd + "\n")
    if close_files:
        tty.shutdown_read();
#   print >>sys.stderr, "Sleeping... For command via paramiko to execute" # New
#   time.sleep(2)
    result = _recv_from_net(tty, prompt, remove_prompt, recvsize)
    if close_files:
        close_ssh(files)
    return result
    
#------------------------------------------------------------------------------
def _spawn_ssh_paramiko(ssh_ip, login=None, password="",
                        bufsize=4096, timeout=100):
    """Spawn ssh (via paramiko) and return FILES object for the above."""
    global _debug
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "_spawn_ssh_paramiko(ssh_ip='%s', login='%s', len(password)=%d," \
              " bufsize=%d, timeout=%d)" % (
            ssh_ip, login, len(password), bufsize, timeout)
    client = paramiko.SSHClient()
    client.load_system_host_keys()

    except1 = None
    try :
        client.connect(ssh_ip, username=login, password=password,
                       timeout=timeout)
    except paramiko.BadHostKeyException, except1:
        print >>sys.stderr, \
              "Bad Host Key(%s): Could not connect to ssh at %s@%s" % (
            except1, login, ssh_ip)
        return None
    except paramiko.AuthenticationException, except1:
        print >>sys.stderr, \
              "Authentication error(%s): Could not connect to ssh at %s@%s" % (
            except1, login, ssh_ip)
        return None
    except paramiko.SSHException, except1:
        print >>sys.stderr, \
              "SSH error(%s): Could not connect to ssh at %s@%s" % (
            except1, login, ssh_ip)
        return None
    except socket.error, except1:
        print >>sys.stderr, \
              "Socket error(%s): Could not connect to ssh at %s@%s" % (
            except1, login, ssh_ip)
        return None

    try :
        tty = client.invoke_shell()
    except paramiko.SSHException, except1:
        print >>sys.stderr, \
              "SSH error(%s): Could not invoke shell on %s@%s" % (
            except1, login, ssh_ip)
        client.close()
        return None
        
    result = { 'client': client, 'bufsize': bufsize, 'tty': tty }
    return result

def spawn_ssh(ssh_ip, login=None, password="",
              bufsize=4096, timeout=100):
    global _debug
    global _prompt_any
    # Open ssh connection
    files = _spawn_ssh_paramiko(ssh_ip, login, password, bufsize, timeout)
    if files == None:
        print >>sys.stderr, \
              "Failed: spawn_ssh to '%s', login='%s', len(password)=%d," \
              " bufsize=%d, timeout=%d" % (
            ssh_ip, login, len(password), bufsize, timeout)
        return None
    tty = files.get('tty', None)
    if tty == None:
        files.close()
        return files
    print >>sys.stderr, "Sleeping...  For ssh connection to initialize" # Old
    time.sleep(2)
    # Read prompt of ssh connection
    output = _recv_from_net(tty, prompt=_prompt_any,
                            remove_prompt=False, recvsize=bufsize)
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "spawn_ssh read after connection returned '%s'" % output
    return files

def close_ssh(files):
    """Close files FILES returned by spawn_ssh."""
    global _debug
    if (_debug & 256) != 0:
        print >>sys.stderr, "close_ssh(files='%s')" % files
    if files == None:
        return
    client = files.get('client', None)
    if client == None:
        return
    tty = files.get('tty', None)
    if tty != None:
        tty.shutdown(2);
        if (_debug & 256) != 0:
            print >>sys.stderr, "close_ssh: Shutdown tty"
        del(files['tty'])
    client.close()
    if (_debug & 256) != 0:
        print >>sys.stderr, "close_ssh: Closed client"
    del(files['client'])

#------------------------------------------------------------------------------
def _open_cli(files):
    """Prepare files FILES for a cli configure terminal command."""
    global _debug
    global _prompt_any
    global _prompt_command_server
    global _prompt_shell
    global _prompt_cli_basic
    global _prompt_cli_enable
    global _prompt_cli_config
    if (_debug & 256) != 0:
        print >>sys.stderr, "_open_cli: Get prompt"
    output = _do_ssh_cmd_with_prompt(" ", files, _prompt_any, False)
    if (_debug & 256) != 0:
        print >>sys.stderr, "_open_cli: prompt is '%s'" % output
    if re.search(_prompt_cli_config, output):
        if (_debug & 256) != 0:
            print >>sys.stderr, "_open_cli: Already at cli config"
            print >>sys.stderr, "_open_cli returned True"
        return True
    if re.search(_prompt_command_server, output):
        if (_debug & 256) != 0:
            print >>sys.stderr, "_open_cli: Exiting command server"
        output = _do_ssh_cmd_with_prompt("exit", files, _prompt_any, False)
    if re.search(_prompt_shell, output):
        if (_debug & 256) != 0:
            print >>sys.stderr, "_open_cli: Starting cli basic"
        output = _do_ssh_cmd_with_prompt("cli", files, _prompt_any, False)
    if re.search(_prompt_cli_basic, output):
        if (_debug & 256) != 0:
            print >>sys.stderr, "_open_cli: Entering cli enable"
        output = _do_ssh_cmd_with_prompt("enable", files, _prompt_any, False)
    if re.search(_prompt_cli_enable, output):
        if (_debug & 256) != 0:
            print >>sys.stderr, "_open_cli: Entering cli configure"
        output = _do_ssh_cmd_with_prompt("configure terminal",
                                         files, _prompt_any, False)
    if re.search(_prompt_cli_config, output):
        result = True
    else:
        result = False
    if (_debug & 256) != 0:
        print >>sys.stderr, "_open_cli returned %s" % result
    return result
    
def _exit_to_shell(files):
    """Prepare files FILES for a shell command."""
    global _debug
    global _prompt_any
    global _prompt_shell
    global _prompt_command_server_or_cli
    regex_shell = re.compile("(.*)" + _prompt_shell + "$")
    regex_command_server_or_cli = re.compile(
        "(.*)" + _prompt_command_server_or_cli + "$")
    if (_debug & 256) != 0:
        print >>sys.stderr, "_exit_to_shell: Get prompt"
    output = _do_ssh_cmd_with_prompt(" ", files, _prompt_any, False)
    if (_debug & 256) != 0:
        print >>sys.stderr, "_exit_to_shell: prompt is '%s'" % output
    while True:
        if regex_shell.search(output):
            if (_debug & 256) != 0:
                print >>sys.stderr, "_exit_to_shell: At shell"
            result = True
            break
        elif regex_command_server_or_cli.search(output):
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "_exit_to_shell: Exiting command-server or shell: '%s'" \
                      % output
            output = _do_ssh_cmd_with_prompt("exit", files, _prompt_any, False)
        else:
            print >>sys.stderr, "_exit_to_shell: Wrong prompt: '%s'" % output
            result = False
            break
    if (_debug & 256) != 0:
        print >>sys.stderr, "_exit_to_shell returned %s" % result
    return result

def _open_command_server(files, port=7980):
    """Prepare files FILES for a command-server command."""
    global _debug
    global _prompt_any
    global _prompt_command_server
    global _prompt_shell
    if (_debug & 256) != 0:
        print >>sys.stderr, "_open_command_server: Get prompt"
    output = _do_ssh_cmd_with_prompt(" ", files, _prompt_any, False)
    if (_debug & 256) != 0:
        print >>sys.stderr, "_open_command_server: prompt is '%s'" % output
    if re.search(_prompt_command_server, output):
        if (_debug & 256) != 0:
            print >>sys.stderr, \
                  "_open_command_server: Already at command-server"
            print >>sys.stderr, \
                  "_open_command_server returned True"
        return True
    if not re.search(_prompt_shell, output):
        if (_debug & 256) != 0:
            print >>sys.stderr, "_open_command_server: Calling _exit_to_shell"
        if not _exit_to_shell(files):
            if (_debug & 256) != 0:
                print >>sys.stderr, "_open_command_server returned False"
            return False
    if (_debug & 256) != 0:
        print >>sys.stderr, "_open_command_server: Starting command-server"
    output = _do_ssh_cmd_with_prompt("rbcmd --port=%d" % port,
                                     files, _prompt_any, False)
    if (_debug & 256) != 0:
        print >>sys.stderr, "_open_command_server: prompt is '%s'" % output
    if re.search(_prompt_command_server, output):
        result = True
    else:
        result = False
    if (_debug & 256) != 0:
        print >>sys.stderr, "_open_command_server returned %s" % result
    return result

#------------------------------------------------------------------------------
def _add_login(ip, login):
    login_ip = ip.split("@")
    len_login_ip = len(login_ip)
    if len_login_ip == 1:
        ip = "%s@%s" % ( login, ip )
    elif len_login_ip != 2:
        print >>sys.stderr, "Invalid login@ip: %s" % ip
    return ip

def _remove_login(ip, login):
    login_ip = ip.split("@")
    len_login_ip = len(login_ip)
    if len_login_ip == 2:
        ip = login_ip[1]
        login = login_ip[0]
    elif len_login_ip != 1:
        print >>sys.stderr, "Invalid login@ip: %s" % ip
    return ip, login

def do_ssh_cmdsvr_cmd(cmd, files, port=7980, remove_prompt=True):
    """Perform a command-server command."""
    global _debug
    global _prompt_command_server
    global _prompt_any
    if (_debug & 256) != 0:
        print >>sys.stderr, "do_ssh_cmdsvr_cmd: Calling _open_command_server"
    # Open the command-server
    if not _open_command_server(files, port):
        if (_debug & 256) != 0:
            print >>sys.stderr, "do_ssh_cmdsvr_cmd returned 'None'"
        return None
    # Execute the command
    result = _do_ssh_cmd_with_prompt(cmd, files,
                                     _prompt_any, # _prompt_command_server???
                                     remove_prompt)
    if (_debug & 256) != 0:
        print >>sys.stderr, "do_ssh_cmdsvr_cmd returned '%s'" % result
    return result

def do_ssh_shell_cmd(cmd, files, remove_prompt=True):
    """Perform a shell command."""
    global _debug
    global _prompt_shell
    global _prompt_any
    if (_debug & 256) != 0:
        print >>sys.stderr, "do_ssh_shell_cmd: Calling _exit_to_shell"
    # Exit to the shell
    if not _exit_to_shell(files):
        if (_debug & 256) != 0:
            print >>sys.stderr, "do_ssh_shell_cmd returned 'None'"
        return None
    # Execute the command
    result = _do_ssh_cmd_with_prompt(cmd, files,
                                     _prompt_any, # _prompt_shell???
                                     remove_prompt)
    if (_debug & 256) != 0:
        print >>sys.stderr, "do_ssh_shell_cmd returned '%s'" % result
    return result

def do_ssh_cli_cmd(cmd, files, remove_prompt=True):
    """Perform a cli configure terminal command."""
    global _debug
    global _prompt_cli_any
    global _prompt_any
    if (_debug & 256) != 0:
        print >>sys.stderr, "do_ssh_cli_cmd: Calling _open_cli"
    # Open the cli
    if not _open_cli(files):
        if (_debug & 256) != 0:
            print >>sys.stderr, "do_ssh_cli_cmd returned 'None'"
        return None
    # Execute the command
    result = _do_ssh_cmd_with_prompt(cmd, files,
                                     _prompt_any, # _prompt_cli_any???
                                     remove_prompt)
    if (_debug & 256) != 0:
        print >>sys.stderr, "do_ssh_cli_cmd returned '%s'" % result
    return result
    
#------------------------------------------------------------------------------
def get_command_server(files):
    """Return 'show command-server' output: (ip, port)"""
    global _debug
    if (_debug & 256) != 0:
        print >>sys.stderr, "get_command_server('%s')" % files
    output = do_ssh_cli_cmd("show command-server", files)
    if output != None:
        pattern = "Command server address+\\s+:\\s+(\\S+)\\s*[\r\n]+" \
                      ".*Command server port\\s+:\\s+([0-9]+)\\s"
        if (_debug & 256) != 0:
            print >>sys.stderr, \
                  "get_command_server: pattern is '%s'" % pattern
        m = re.search(pattern, output, re.DOTALL)
        if m:
            ip = m.group(1)
            port = int(m.group(2))
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "get_command_server: Matched pattern: '%s'" % output
        else:
            ip = None
            port = None
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "get_command_server: Did not match: '%s'" % output
    else:                               # Could not connect to cli.
        ip = None
        port = None
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "get_command_server returned: (ip='%s', port=%s)" % (ip, port)
    return (ip, port)

def set_command_server(files, ip, port=7980):
    """Set command-server ip and port"""
    global _debug
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "set_command_server(files='%s', ip=%s, port=%s)" % (
            files, ip, port)
    if ip == None:
        ip = "0.0.0.0"
        port = 0
    if port == None:
        port = 7980
    command = 'command-server modify ip %s port %s' % (ip, port)
    result = do_ssh_cli_cmd(command, files)
    if (_debug & 256) != 0:
        print >>sys.stderr, "set_command_server returned '%s'" % result
    print >>sys.stderr, "Sleeping...  For command-server to initialize" # Old
    time.sleep(2)
    return result
    
def set_command_server_local(files, port=7980):
    """Set command-server ip local and port"""
    return set_command_server(files, "127.0.0.1", port)
    
def set_command_server_off(files, port=7980):
    """Set command-server ip off and port"""
    return set_command_server(files, "0.0.0.0", port)
    
#------------------------------------------------------------------------------
def do_rbcmd_via_ssh(svr_command, files, svr_port=7980, remove_prompt=True):
    global _debug
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_ssh(svr_command='%s', svr_port=%d," \
              " remove_prompt=%s)" %(svr_command, svr_port, remove_prompt)
    # Get and Enable command-server
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_ssh: Calling get_command_server"
    original_svr_ip, original_svr_port = get_command_server(files)
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_ssh: Calling set_command_server"
    output = set_command_server_local(files, svr_port)
    # Execute svr command
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_ssh_and_socket: Calling do_ssh_cmdsvr_cmd"
    result = do_ssh_cmdsvr_cmd(svr_command, files, svr_port, remove_prompt)
    # Restore command-server
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_ssh: Calling set_command_server"
    output = set_command_server(files, original_svr_ip, original_svr_port)
    if (_debug & 256) != 0:
        print >>sys.stderr, "do_rbcmd_via_ssh returned '%s'" % result
    return result

def do_rbcmd_via_socket(command, ip, port=7980,
                        timeout=10, remove_prompt=True, msg=""):
    global _debug
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_socket(command='%s', port=%d, timeout=%d," \
              " remove_prompt=%s, msg=%s)" %(
            command, port, timeout, remove_prompt, msg)
    sock = open_socket_for_command_server(msg, ip, port, timeout)
    if sock != None:
        if (_debug & 256) != 0:
            print >>sys.stderr, "do_rbcmd_via_socket: Calling do_net_cmd"
        result = do_net_cmd(command, sock, remove_prompt)
        if (_debug & 256) != 0:
            print >>sys.stderr, "Closing socket '%s'" % sock
        sock.close()
    else:
        result = None
    if (_debug & 256) != 0:
        print >>sys.stderr, "do_rbcmd_via_socket returned '%s'" % result
    return result

def do_rbcmd_via_ssh_and_socket(svr_command,
                                ssh_ip, login="admin", password="",
                                svr_ip=None, svr_port=7980,
                                timeout=100, remove_prompt=True, msg=""):
    global _debug
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_ssh_and_socket(svr_command='%s', ssh_ip='%s'," \
              " login='%s', svr_ip='%s', svr_port=%d, timeout=%d," \
              " remove_prompt=%s, msg=%s)" %(
            svr_command, ssh_ip, login, svr_ip, svr_port,
            timeout, remove_prompt, msg)
    if svr_ip == None:
        svr_ip = ssh_ip
    # Get and Enable command-server
    files = spawn_ssh(ssh_ip, login, password, timeout=timeout)
    if files == None:
        return None
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_ssh_and_socket: Calling get_command_server"
    original_svr_ip, original_svr_port = get_command_server(files)
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_ssh_and_socket: Calling set_command_server"
    output = set_command_server(files, svr_ip, svr_port)
    # Execute svr_command
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_ssh_and_socket: Calling do_rbcmd_via_socket"
    result = do_rbcmd_via_socket(svr_command, svr_ip, svr_port,
                                 timeout, remove_prompt, msg)
    # Restore command-server
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_ssh_and_socket: Calling set_command_server"
    output = set_command_server(files, original_svr_ip, original_svr_port)
    close_ssh(files)
    files = None
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "do_rbcmd_via_ssh_and_socket returned '%s'" % result
    return result
    
def do_cmd(shell, command, ip_port, login=None, password="",
           command_svr_port=7980, timeout=100, remove_prompt=True, msg=""):
    global _debug
    global _shells
    if (_debug & 256) != 0:
        print "do_cmd(shell=%s, command='%s', ip_port='%s', login='%s'," \
              " len(password)=%d, command_svr_port=%d, timeout=%d," \
              " remove_prompt=%s, msg=%s)" % (
            shell, command, ip_port, login, len(password), command_svr_port,
            timeout, remove_prompt, msg)
        _report_config()
    ip_port_tuple = ip_port.split(":")
    len_ip_port_tuple = len(ip_port_tuple)
    if len_ip_port_tuple == 1:          # ssh to shell - IP or DNS
        if login == None:
            if shell == "cli":
                login = "admin"
            else:
                login = "root"
        ssh_ip = ip_port_tuple[0]
        ssh_ip, login = _remove_login(ssh_ip, login)
        files = spawn_ssh(ssh_ip, login, password, timeout=timeout)
        if files == None:
            return None
        if shell == "shell":
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "do_cmd: Calling do_ssh_shell_cmd"
            result = do_ssh_shell_cmd(command, files, remove_prompt)
        elif shell == "cli":
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "do_cmd: Calling do_ssh_cli_cmd"
            result = do_ssh_cli_cmd(command, files, remove_prompt)
        elif shell == "rbcmd":
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "do_cmd: Calling do_rbcmd_via_ssh"
            result = do_rbcmd_via_ssh(command, files,
                                      command_svr_port, remove_prompt)
        else:
            print >>sys.stderr, "Wrong shell type: %s" % shell
            result = None
        close_ssh(files)
    elif len_ip_port_tuple == 2:        # Command server - IP or DMS, Port
        svr_ip = ip_port_tuple[0]
        svr_port = ip_port_tuple[1]
        if svr_port == "":
            svr_port = command_svr_port
        else:
            svr_port = int(svr_port)
        if shell == "rbcmd":
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "do_cmd: Calling do_rbcmd_via_socket"
            result = do_rbcmd_via_socket(command, svr_ip, svr_port,
                                         timeout, remove_prompt, msg)
        else:
            print >>sys.stderr, "Wrong shell type: %s" % shell
            result = None
    # ssh to cli - ssh IP or DNS, Command-server IP, Port
    elif len_ip_port_tuple == 3:
        if login == None:
            if shell == "shell":
                login = "root"
            else:
                login = "admin"
        ssh_ip = ip_port_tuple[0]
        ssh_ip, login = _remove_login(ssh_ip, login)
        svr_ip = ip_port_tuple[1]
        if svr_ip == "":
            svr_ip = ssh_ip
        svr_port = ip_port_tuple[2]
        if svr_port == "":
            svr_port = command_svr_port
        else:
            svr_port = int(svr_port)
        if shell == "shell":
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "do_cmd: Calling do_ssh_shell_cmd"
            files = spawn_ssh(ssh_ip, login, password, timeout=timeout)
            if files == None:
                return None
            result = do_ssh_shell_cmd(command, files, remove_prompt)
            close_ssh(files)
        elif shell == "cli":
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "do_cmd: Calling do_ssh_cli_cmd"
            files = spawn_ssh(ssh_ip, login, password, timeout=timeout)
            if files == None:
                return None
            result = do_ssh_cli_cmd(command, files, remove_prompt)
            close_ssh(files)
        elif shell == "rbcmd":
            if (_debug & 256) != 0:
                print >>sys.stderr, \
                      "do_cmd: Calling do_rbdcmd_via_ssh_and_socket"
            result = do_rbcmd_via_ssh_and_socket(command, ssh_ip,
                                                 login, password,
                                                 svr_ip, svr_port,
                                                 timeout,
                                                 remove_prompt, msg)
        else:
            print >>sys.stderr, "Wrong shell type: %s" % shell
            result = None
    else:
        result = None                   # Wrong length
    if (_debug & 256) != 0:
        print >>sys.stderr, "do_cmd returned '%s'" % result
    return result

#------------------------------------------------------------------------------
def _test_prompt(prompt_name, prompt, message, value):
    global _debug
#    pattern = "^(((.|\n)+?\n)|)(" + prompt + ")$"
    pattern = "(.*?)(" + prompt + ")$"
    regexp = re.compile(pattern, re.DOTALL)
    if (_debug & 256) != 0:
        print >>sys.stderr, "_test_prompt: pattern is '%s'" % pattern
    if regexp.search(value):
        print "%s - '%s': Matches %s '%s'" % (
            message, value, prompt_name, prompt)
    else:
        print "%s - '%s': Does not match %s" % (message, value, prompt_name)

def _rvbd_cmd_main():
    global _debug
    # Parse parameters
    len_sys_argv = len(sys.argv)
    global _prompt_command_server
    global _prompt_shell
    global _prompt_cli_basic
    global _prompt_cli_enable
    global _prompt_cli_config
    global _prompt_cli_any
    global _prompt_shell_or_cli
    global _prompt_command_server_or_cli
    global _prompt_any
    usage = "Usage:\n" \
            "* Test regexps - %prog message string\n" \
            "* Do command - %prog [options] shell command ip_port" \
            " [password [login [svr_port [timeout [remove_prompt" \
            "[message]]]]]]"
    parser = OptionParser(usage=usage)
    parser.add_option("-q", "--quiet", action="store_true", dest="quiet",
                      help="Do not print result of command.")
    parser.add_option("-O", "--options", type="int", dest="options",
                      default=_debug, help="Options.[default %default]")
    (options, args) = parser.parse_args()

    _debug = options.options

    len_args = len(args)
    if len_args == 2:
        message = args[0]
        value = args[1]
        _test_prompt("command_server", _prompt_command_server,
                     message, value)
        _test_prompt("shell", _prompt_shell, message, value)
        _test_prompt("cli_basic", _prompt_cli_basic, message, value)
        _test_prompt("cli_enable", _prompt_cli_enable,
                     message, value)
        _test_prompt("cli_config", _prompt_cli_config,
                     message, value)
        _test_prompt("cli_any", _prompt_cli_any, message, value)
        _test_prompt("shell_or_cli", _prompt_shell_or_cli,
                     message, value)
        _test_prompt("command_server_or_cli", _prompt_command_server_or_cli,
                     message, value)
        _test_prompt("any", _prompt_any, message, value)
        return 0

    if len_args < 3:
        parser.print_help()
        return -1
    shell = args[0]
    command = args[1]
    ip_port = args[2]
    if len_args >= 4:
        password = args[3]
    else:
        password = ""
    if len_args >= 5:
        login = args[4]
    else:
        login = None
    if len_args >= 6:
        command_svr_port = int(args[5])
    else:
        command_svr_port = 7980
    if len_args >= 7:
        timeout = int(args[6])
    else:
        timeout = 100
    if len_args >= 8:
        remove_prompt = int(args[7])
    else:
        remove_prompt = True
    if len_args >= 9:
        msg = args[8]
    else:
        msg = ""
    if (_debug & 256) != 0:
        print >>sys.stderr, \
              "_rvbd_cmd_main: shell='%s', command='%s', ip_port='%s'," \
              " len(password)=%d, login='%s', command_svr_port=%d," \
              " timeout=%d, remove_prompt=%s, msg='%s'" % (
            shell, command, ip_port, len(password), login, command_svr_port,
            timeout, remove_prompt, msg)
    result = do_cmd(shell, command, ip_port, login, password, command_svr_port,
                    timeout, remove_prompt, msg)
    if (not options.quiet) or ((_debug & 256) != 0):
        print "_rvbd_cmd_main result from '%s' on '%s' is '%s'" % (
            shell, ip_port, result)
    if result == None:
        return -2
    return 0

#------------------------------------------------------------------------------
if (__name__ == "__main__") and sys.argv[0].endswith("rvbd_cmd.py"):
    exit_status = _rvbd_cmd_main()
    sys.exit(exit_status)
