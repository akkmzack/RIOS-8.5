#!/usr/bin/env python

import os, sys, signal, commands, string, time, errno
import syslog

_timeout = 5
_prg_to_exec = ""
_child_pid = -1
_core_dump_timeout = 20

#this function handles the case where the child process finishes
#execution before the timeout occurs. the parent process goes
#into a sleep for the timeout duration, and is made runnable 
#if the child finishes early. if _child_pid actually finished
#we exit from the program here.
def child_handler(signum, frame):
    child,status = os.waitpid(_child_pid, os.WNOHANG)
    syslog.syslog(syslog.LOG_INFO,
                  "In sigchld handler, waitpid(%d) returned "%_child_pid + str(child) + "," + str(status))
    if (child, status) != (0, 0):
        # Child actually exited
        # Post-process the exit status
        if (os.WIFEXITED(status)):
            status = os.WEXITSTATUS(status)
        elif (os.WIFSIGNALED(status)):
            status = -os.WTERMSIG(status)

        syslog.syslog(syslog.LOG_INFO,
                      "Child process ended. Exiting TimedExec with status %d" % (status))
        sys.exit(status)


# START
if len(sys.argv) >= 4:
    if sys.argv[1] == "-t":
        _timeout     = int(sys.argv[2])
        _prg_to_exec = sys.argv[3:len(sys.argv)]

if len(_prg_to_exec) == 0:
    if len(sys.argv) >= 2:
        _prg_to_exec = sys.argv[1:len(sys.argv)]

if len(_prg_to_exec) == 0:
    print "Usage: %s [-t timeout] program [program args..]"%sys.argv[0]
    sys.exit(1)

syslog.openlog("timed_exec[%u]" % os.getpid())
signal.signal(signal.SIGCHLD, child_handler)

_child_pid = os.fork()
if (_child_pid == 0):
    # child inherits parent signal mask across fork and exec
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    os.setpgrp();	# Start a new process group
    os.execvp(_prg_to_exec[0], _prg_to_exec)
    print "!!!!!!!!!! ERROR if you see this !!"
    sys.exit(1)

time.sleep(_timeout)
syslog.syslog(syslog.LOG_INFO,
              "Child [%d] timed out after %d seconds "%(_child_pid,_timeout))

sys.stdout.flush()

#now we are timed out, and child has not finished (because otherwise we
#would have gotten called into the SIGCHLD handler). The child is the leader
# of a process group, so we can just killpg() the child, sending SIGQUIT.

retries = 0
while True:
    try:
        if (retries > 5):
            syslog.syslog(syslog.LOG_WARNING, "Sending SIGKILL to " + str(_child_pid))
            os.killpg(_child_pid, signal.SIGKILL)
            break
        else:
            syslog.syslog(syslog.LOG_WARNING,
                          "Retry %d, Sending SIGQUIT to "%retries + str(_child_pid))
            os.killpg(_child_pid, signal.SIGQUIT)
            retries = retries + 1
            syslog.syslog(syslog.LOG_INFO, "waiting for coredump")
            time.sleep(_core_dump_timeout)

    except IOError, e:
        syslog.syslog(syslog.LOG_INFO, "Got exception: ", os.strerror(e.errno))
        if e.errno == errno.ESRCH or e.errno == errno.ECHILD:
            syslog.syslog(syslog.LOG_INFO,
                          "Ignoring [", os.strerror(e.errno),"] as our SIGCHLD handler reaped it")
            pass
        else:
            raise

    except OSError, e:
        syslog.syslog(syslog.LOG_INFO, "Got exception: ", os.strerror(e.errno))
        if e.errno == errno.ESRCH or e.errno == errno.ECHILD:
            syslog.syslog(syslog.LOG_INFO,
                          "Ignoring [", os.strerror(e.errno),"] as our SIGCHLD handler reaped it")
            pass
        else:
            raise

