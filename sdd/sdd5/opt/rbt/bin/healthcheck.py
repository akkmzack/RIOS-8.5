#!/usr/bin/python

# Script to monitor the health of appliances by executing commands
# that dump state and then forwarding the state via some transport
# e.g. email or http.

import signal, xml.dom.minidom, os, sys, fcntl, re, copy, random, difflib, Mgmt

# Bump the major version if the data format changes
VERSION ='1.1'

# Protect against stuckness. Give up after 60 seconds.
def alarm_handler(signum, frame):
    print "Health check is taking too long to complete"
    os._exit(1)

signal.signal(signal.SIGALRM, alarm_handler)
signal.alarm(60)

# Use advisory file locking which clears when the process exits. This
# protects against parallel invocation and against stuck commands left
# dangling by the previous alarm.
f = open("/var/run/healthcheck.lock", "w")
fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)

# Functions and Classes

class BigBeat:
    def __init__(self):
        self.data = ""

    def begin(self, date):
        # mimic the sysinfo header details
        thishost = hcsystem("uname -n")
        rios_version = hcsystem(". /opt/tms/release/build_version.sh && echo $BUILD_PROD_RELEASE")
        model = hcsystem("/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/model")
        serial = hcsystem("/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/serialnum")

        header = """

<bigbeat
 bb_version="%s"
 serial="%s"
 date="%s"
 host="%s"
 model="%s"
 version="%s"
 level="%s"
 >

"""
        header = header % (VERSION, serial, date, thishost, model, rios_version, options.level)
        self.data = header

    def end(self):
        self.data = self.data + "</bigbeat>\n"

    def begin_section(self, name):
        self.data = self.data + "<section name=\"%s\">\n" % name        

    def end_section(self):
        self.data = self.data + "</section>\n"

    def begin_file(self, name):
        self.data = self.data + "<file name=\"%s\">\n" % escape(name)

    def end_file(self):
        self.data = self.data + "</file>\n"

    def add_exec(self, execStr):
        self.data = self.data + "<exec>%s</exec>\n" % escape(execStr)

    def add_output(self, output):
        self.data = self.data + "<output>%s</output>\n" % escape(output)

    def add_diff(self, diff, date):
        self.data = self.data + "<diff with=\"%s\">%s</diff>\n" % (date, escape(diff))

    def worth_diff(self, diff, output):
        # for a diff to save space the length must be less than the
        # length of the original with 41 and 17 character XML wrappers
        # taken into account.
        return len(diff) + 41 < len(output) + 17

class BigBeatHistory:
    def __init__(self):
        self.file = "bb_history.xml"
        self.history = []

    def load(self):
        if not os.path.isfile(self.file):
            return True
        
        historyDOM = xml.dom.minidom.parse(self.file)
        for command in historyDOM.getElementsByTagName("command"):
            section_name = command.getAttribute("section_name")
            file_name = command.getAttribute("file_name")
            date = command.getAttribute("date")
            output = ""
            elements = command.getElementsByTagName("output")
            for element in elements:
                for node in element.childNodes:
                    output = output + node.data
            self.history.append([section_name, file_name, date, output])

    def output(self, section, file=""):
        for command in self.history:
            if section == command[0] and file == command[1]:
                return [command[2], command[3]]
        return ["", ""]

    def update(self, section, date, output, file=""):
        for command in self.history:
            if section == command[0] and file == command[1]:
                command[2] = date
                command[3] = output
                return True
        self.history.append([section, file, date, output])
        return True

    def save(self):
        h = open("bb_history.xml", "w")
        h.write("<history>\n")
        for command in self.history:
            cmd = """
<command section_name="%s"
         file_name="%s"
         date="%s">
""" % (command[0], escape(command[1]), command[2])
            h.write(cmd)
            h.write("<output>%s</output>\n" % escape(command[3]))
            h.write("</command>\n")
        h.write("</history>\n")
        h.close()

# send_ssmtp() - This is the default way to send the data. It uses the
# same default as autosupport sysdumps. See afail.sh.

def send_ssmtp(working_file, to_file = False, file = ""):
    assert options.recipient != ""
    assert options.subject != ""

    if options.compression == "none":
        mime = "text/xml"
    elif options.compression == "gzip":
        mime = "application/x-gzip"
    else:
        raise Exception, "unsupported compression: " + options.compression

    opts = ""
    if to_file:
        assert file
        opts = "-o " + file

    # Bug 57989: Use a unique filename for xmit. via a softlink to reduce leakage risk
    thishost = hcsystem("uname -n")
    date = hcsystem("date '+%Y%m%d-%H%M%S'")
    serial = hcsystem("/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/serialnum")
    unique_file = 'bigbeat-' + serial + '-' + date + '.gz'
    hcsystem("ln -s " + working_file + " " + unique_file);

    mailcmd = "makemail.sh %s -s \"%s\" -t \"%s\" -S \"-C /etc/ssmtp-auto.conf\" -m %s %s" % (opts, options.subject, options.recipient, mime, unique_file)

    if options.verbose:
        print "About to: " + mailcmd

    send = hcsystem(mailcmd)
    if options.verbose:
        print send,    

    os.remove(unique_file)

# send_http() - This is a mythical transport if we were posting to a
# sane backend.

def send_http(working_file):
    assert options.url != ""

    thishost = hcsystem("uname -n")

    args = ""
    if options.proxy:
        args += "-x " + options.proxy

    send = hcsystem("curl " + args + " -F host=" + thishost + " -F filename=" + working_file + " -F file=@" + working_file + " -F Submit=Submit " + options.url)
    if options.verbose:
        print send,

# send_autosupport_gw() - This is the weird way of sending where we
# HTTP post to a script that expects an email body and emails it
# on. This leverages existing live(ish) production scripts to get the
# data in with the least amount of disruption.

def send_autosupport_gw(working_file):
    assert options.url != ""
    assert options.recipient != ""
    assert options.subject != ""

    args = ""
    if options.proxy:
        args += "-x " + options.proxy

    if os.path.isfile("email.txt"):
        os.remove("email.txt")

    send_ssmtp(working_file, to_file = True, file = "email.txt")

    url = options.url + "?to=" + options.recipient

    send = hcsystem("curl " + args + " --data-binary @email.txt " + url)
    if options.verbose:
        print send,

    os.remove("email.txt")

# hcsystem(cmd) - simple system command that is expected to return a
# single line of output and 0 exit status.
def hcsystem(run, allowed_exits = [0]):
    cmd = os.popen("%s 2>&1" % run)
    data = cmd.read()
    es = cmd.close()
    if es is None:
        es = 0
    es = os.WEXITSTATUS(es)
    assert es in allowed_exits, "Command returned a non allowed exit (%d): %s" % (es, data)
    return data.rstrip()

def gzip_data(data_in, data_compressed):
    gzip = os.popen("cat " + data_in + " | gzip -c 2>&1")
    gzip_data = gzip.read()
    es = gzip.close()
    assert es == None, "Cannot compress data (%d): %s" % (os.WEXITSTATUS(es), gzip_data)
    data = open(data_compressed, "w")
    data.write(gzip_data)
    data.close()

class Command:
    def __init__(self, name, execStr, freeform, ok_if_sport_running, ok_if_high_load, level, handles_stderr, files):
        self.name = name
        self.execStr = execStr
        self.freeform = freeform
        self.ok_if_sport_running = ok_if_sport_running
        self.ok_if_high_load = ok_if_high_load
        self.level = level
        self.handles_stderr = handles_stderr
        self.files = files
        self.file = ""
        self.output = ""
        self.es = 0

    def run(self):
        (self.output, self.es) = self.hook_run()

    def expand_over_files(self):
        kids = []
        execStr = self.files
        filelist = hcsystem(execStr)
        for file in filelist.splitlines():
            fileInst = copy.copy(self)
            nameFromFile = file.replace(" ", "_").replace("/", "_")
            fileInst.name = fileInst.name + "_" + nameFromFile
            fileInst.execStr = fileInst.execStr.replace("FILE", file)
            fileInst.file = file
            kids.append(fileInst)
        if len(kids) == 0:
            raise Exception, "No files found"
        return kids

class CLICommand(Command):

    def hook_run(self):
        cli = os.popen4("cli -e --no-history")
        cli[0].write("en\nconf t\n")
        cli[0].write("no cli session paging enable\n")
        cli[0].write(self.execStr + "\n")
        cli[0].write("exit\nexit\n")
        cli[0].close()
        output = cli[1].read()
        cli[1].close()
        return (output, 0)

class ShellCommand(Command):

    def hook_run(self):

        execStr = self.execStr
        # Allow complex commands to take care of stderr their own way
        if not self.handles_stderr:
            execStr += " 2>&1"
        
        cmd = os.popen(execStr)
        output = cmd.read()
        es = cmd.close()
        if es is None:
            es = 0
        return (output, os.WEXITSTATUS(es))

def Command_create(name, execStr, env, freeform, ok_if_sport_running, ok_if_high_load, level, handles_stderr, files):
    if env == 'cli':
        return CLICommand(name, execStr, freeform, ok_if_sport_running, ok_if_high_load, level, handles_stderr, files)
    elif env == 'shell':
        return ShellCommand(name, execStr, freeform, ok_if_sport_running, ok_if_high_load, level, handles_stderr, files)
    else:
        raise Exception, "env should be cli or shell, not " + env

# from saxutils.py (not in RiOS 5.5)

def __dict_replace(s, d):
    """Replace substrings of a string using a dictionary."""
    for key, value in d.items():
        s = s.replace(key, value)
    return s

def escape(data, entities={}):
    """Escape &, <, and > in a string of data.

    You can escape other strings of data by passing a dictionary as
    the optional entities parameter.  The keys and values must all be
    strings; each key will be replaced with its corresponding value.
    """

    # must do ampersand first
    data = data.replace("&", "&amp;")
    data = data.replace(">", "&gt;")
    data = data.replace("<", "&lt;")
    if entities:
        data = __dict_replace(data, entities)
    return data

# CRON

def do_install():
    assert options.full_interval
    assert options.min_interval
    crontab = "/var/spool/cron/admin"

    # Spread the time each server sends to a different point within
    # the hour/week/month to smooth the load on the receiver.
    week = random.randint(0,7)
    month = random.randint(0,28)
    minute = random.randint(0,59)

    # Map simple(r) frequency terms to crontab form. Ensure that min
    # and full do not happen at the same time.
    min_cron_map = { 'hourly':            '0-3,5-23 * * *',
                     'every 6 hours':     '0,6,12,18 * * *',
                     'daily':             '4 * * *',
                     'weekly':            '4 * * ' + str(week) }

    full_cron_map = { 'daily':             '5 * * *',
                      'weekly':            '5 * * ' + str(week),
                      'monthly':           '5 ' + str(month) + ' * *' }

    min_interval = min_cron_map[options.min_interval]
    full_interval = full_cron_map[options.full_interval]
    
    # Ignore badly defined intervals
    if not min_interval or not full_interval:
        if options.verbose:
            print "Not changing the crontab due to an incorrect interval setting"
        return True

    f = open("crontab.hc", "w")

    if os.path.isfile(crontab):
        # clear out existing config
        hcsystem("sed -e \"/BEGIN healthcheck/,/END healthcheck/d\" < " + crontab + " > crontab.clean")
        hcsystem("cp crontab.clean " + crontab)
    else:
        # create a new crontab with a simple header (avoids problems with crontab -e editing)
        f.write("# healthcheck header\n\n")

    cron = """\
# BEGIN healthcheck
HOME=/var/home/root
MAIL=/var/spool/mail/admin
PATH=/usr/local/bin:/opt/tms/bin:/usr/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/X11R6/bin:/var/home/root/bin
SHELL=/bin/bash
# full run: %s
%s %s /opt/rbt/bin/healthcheck.py --everything -v > /var/log/healthcheck.log 2>&1
# minimal run: %s
%s %s /opt/rbt/bin/healthcheck.py -v > /var/log/healthcheck.log 2>&1
# END healthcheck
""" % (options.full_interval, minute, full_interval, options.min_interval, minute, min_interval)
    f.write(cron)
    f.close()

    hcsystem("cat crontab.hc >> " + crontab)

def do_update():
    assert options.full_interval
    assert options.min_interval
    crontab = "/var/spool/cron/admin"
    if os.path.isfile(crontab):
        f = open(crontab, "r")
        configured = False
        full = ""
        minimal = ""
        for l in f.readlines():
            if re.search("BEGIN healthcheck", l):
                configured = True
            full_re = re.search("full run\:\s(.*)", l)
            minimal_re = re.search("minimal run\:\s(.*)", l)
            if full_re:
                full = full_re.group(1)
            elif minimal_re:
                minimal = minimal_re.group(1)
        if configured:
            if full and full != options.full_interval:
                if options.verbose:
                    print "Updating CRON config due to interval changes"
                do_install()
            elif minimal and minimal != options.min_interval:
                if options.verbose:
                    print "Updating CRON config due to interval changes"
                do_install()

# Command line & Config. Configuration settings (or defaults) come
# from mgmt. The command line can override.

HC = '/rbt/support/healthcheck'
md_bool_map = {'true':True, 'false':False}
try:
    Mgmt.open()
    enable_default=md_bool_map[Mgmt.get_value(HC + '/enable')]
    transport_default=Mgmt.get_value(HC + '/transport')
    url_default=Mgmt.get_value(HC + '/url')
    recipient_default=Mgmt.get_value(HC + '/recipient')
    proxy_default=Mgmt.get_value(HC + '/proxy')
    full_interval_default=Mgmt.get_value(HC + '/full_interval')
    min_interval_default=Mgmt.get_value(HC + '/min_interval')
    level_default=Mgmt.get_value(HC + '/level')
    Mgmt.close()
except:
    # Mgmt cannot be accessed at boot so we muddle along with command
    # line only to allow the boot install. The first run after boot
    # will fix the scheduling to any user defined values or
    # md_support.xml defaults.
    enable_default=False
    transport_default='autosupport_gw'
    url_default=''
    recipient_default=''
    proxy_default=''
    full_interval_default='daily'
    min_interval_default='hourly'
    level_default=''

from optparse import OptionParser
parser = OptionParser()
parser.add_option("-E", "--enable", dest="enable", action="store_true",
                  help="Do the health check, this script will not do anything by default", default=enable_default)
parser.add_option("-r", "--runfile", dest="runfile", 
                  help="XML file giving the commands to run", default="/opt/rbt/etc/hc_commands.xml")
parser.add_option("-e", "--everything", dest="everything", action="store_true",
                  help="Send everything even if the output from a command has not changed since its prior run", default=False)
parser.add_option("-t", "--transport", dest="transport", default=transport_default,
                  help="How does the data get sent?")
parser.add_option("-z", "--compression", dest="compression", default="gzip",
                  help="gzip or none")
parser.add_option("-T", "--recipient", dest="recipient", default=recipient_default,
                  help="Where to for email")
parser.add_option("-s", "--subject", dest="subject", default="bigbeat",
                  help="Subject for email")
parser.add_option("-u", "--url", dest="url", default=url_default,
                  help="URL for HTTP transport")
parser.add_option("-p", "--proxy", dest="proxy", default=proxy_default,
                  help="Go through a proxy (a.b.c.d[:x])")
parser.add_option("-f", "--full-interval", dest="full_interval", default=full_interval_default,
                  help="The CRON interval spec for when to send out a full report")
parser.add_option("-m", "--min-interval", dest="min_interval", default=min_interval_default,
                  help="The CRON interval spec for when to send out a minimal report (only what has changed)")
parser.add_option("-d", "--diff", dest="diff", action="store_true",
                  help="Send a unified diff as the command output from the previous run if it is shorter than this runs output", default=True)
parser.add_option("", "--nodiff", dest="diff", action="store_false")
parser.add_option("-v", "--verbose", dest="verbose", action="store_true",
                  help="Explain what is going on", default=False)
parser.add_option("-q", "--quiet", dest="quiet", action="store_true",
                  help="Output nothing, useful for collecting clean XML", default=False)
parser.add_option("-l", "--level", dest="level", 
                  help="Only run commands that are at or below this level. Levels are quiet, normal, verbose.", default=level_default)
parser.add_option("-i", "--install", dest="install", action="store_true",
                  help="install as a CRONjob", default=False)
parser.add_option("-D", "--testing-config", dest="testing_config", action="store_true",
                  help="Dump the options that come from mgmt and exit", default=False)

(options, args) = parser.parse_args()

if not options.enable:
    print "Health check is disabled"
    sys.exit(1)

assert options.transport != ""
assert options.compression != "" and (options.compression == "none" or options.compression == "gzip")

if options.testing_config:
    for attr in ('enable', 'level', 'transport', 'url', 'proxy', 'recipient', 'min_interval', 'full_interval'):
        print attr + ":" + str(getattr(options, attr))
    sys.exit(0)

# Commands - sanity check and safe defaults

commandsDOM = xml.dom.minidom.parse(options.runfile)
commands = []
dupecheck_name = []
dupecheck_exec = []

for command in commandsDOM.getElementsByTagName("command"):

    name = command.getAttribute("name")
    assert dupecheck_name.count(name) == 0
    dupecheck_name.append(name)
    
    files = command.getAttribute("files")
    if files == "":
        elements = command.getElementsByTagName("files")
        for element in elements:
            for node in element.childNodes:
                files = files + node.data

    execStr = command.getAttribute("exec")
    if execStr == "":
        execs = command.getElementsByTagName("exec")
        for element in execs:
            for node in element.childNodes:
                execStr = execStr + node.data
        freeform = True
    else:
        freeform = False
    if not files:
        # check for duplicate commands. allow dupes for file iterators.
        assert dupecheck_exec.count(execStr) == 0
        dupecheck_exec.append(execStr)
    
    env = command.getAttribute("env")
    if not env:
        env = "shell"

    ok_if_sport_running = command.getAttribute("ok_if_sport_running")
    if not ok_if_sport_running:
        ok_if_sport_running = False
    else:
        ok_if_sport_running = ok_if_sport_running == "True"

    ok_if_high_load = command.getAttribute("ok_if_high_load")
    if not ok_if_high_load:
        ok_if_high_load = False
    else:
        ok_if_high_load = ok_if_high_load == "True"

    level = command.getAttribute("level")
    if not level:
        level = 'normal'

    handles_stderr = command.getAttribute("handles_stderr")
    if not handles_stderr:
        handles_stderr = False
    else:
        handles_stderr = handles_stderr == "True"

    cmd = Command_create(name, execStr, env, freeform, ok_if_sport_running, ok_if_high_load, level, handles_stderr, files)
    commands.append(cmd)

    if options.verbose:
        print "Added command: %s" % cmd.name

# MAIN

# Use a safe working dir
working_dir = "/var/log/healthcheck";
try:
    stat = os.stat(working_dir)
except OSError:
    os.makedirs(working_dir, 0755)
os.chdir(working_dir)

# Install or update CRON
if options.install:
    do_install()
    sys.exit(0)

do_update()

# Check for a running sport
ps = hcsystem("ps axwwwf | grep sport | grep -v grep", [0,1])
if ps and re.search("sport", ps):
    sport_running = True
else:
    sport_running = False
if options.verbose:
    print "Sport running: %s" % str(sport_running)

# Check for high load
load = hcsystem("uptime")
if not load:
    raise Exception, "Could not figure out load"

if int(re.search('load average: (\d+)\.', load).group(1)) < 5:
    high_load = False
else:
    high_load = True
if options.verbose:
    print "High load: %s" % str(high_load)

# Start new beat and load old history
thisdate = hcsystem("date '+%Y-%m-%d %H:%M:%S %z'")
bb = BigBeat()
bb.begin(thisdate)
history = BigBeatHistory()
history.load()

# Run each command and add its output to the data file
for cmd in commands:

    if high_load and not cmd.ok_if_high_load:
        if options.verbose:
            print "Skipping %s due to high load" % cmd.name
        continue

    if sport_running and not cmd.ok_if_sport_running:
        if options.verbose:
            print "Skipping %s because sport is running" % cmd.name
        continue

    # Restrict what is sent based on verbosity level
    if options.level == 'quiet' and cmd.level != 'quiet':
        if options.verbose:
            print "Skipping %s because its verbosity level is > quiet" % cmd.name        
        continue

    if options.level == 'normal' and cmd.level == 'verbose':
        if options.verbose:
            print "Skipping %s because its verbosity level is > normal" % cmd.name        
        continue

    # Extrapolate over files
    if cmd.files:
        try:
            kids = cmd.expand_over_files()
        except Exception, detail:
            cmd.output = "error getting files: %s" % str(detail)
            kids = [cmd]
    else:
        kids = [cmd]

    # Run commands
    for inst in kids:
        try:
            if not inst.output:
                inst.run()
        except Exception, detail:
            inst.output = "error running command: %s" % str(detail)
    
    # Record output
    bb.begin_section(cmd.name)

    for inst in kids:
        if inst.file:
            bb.begin_file(inst.file)

        bb.add_exec(inst.execStr)

        diff = False
        prior_date = ""
        if not options.everything and options.diff:
            prior_date, prior_output = history.output(cmd.name, inst.file)
            if prior_date != "":
                if prior_output != inst.output:
                    diff = ''.join(difflib.unified_diff(prior_output.splitlines(True), inst.output.splitlines(True)))
                else:
                    diff = ""

        # diff or full output
        if not options.everything and options.diff and diff != False and bb.worth_diff(diff, inst.output):
            bb.add_diff(diff, prior_date)
        else:
            bb.add_output(inst.output)
            history.update(cmd.name, thisdate, inst.output, inst.file)

        if inst.file:
            bb.end_file();

    bb.end_section()

bb.end()
history.save()

# Write to file
data_plain = "bigbeat.txt"
data = open(data_plain, "w")
data.write(bb.data)
data.close()

# Compress?
data_xmit = data_plain
if options.compression == "gzip":
    data_xmit = "bigbeat.txt.gz"
    gzip_data(data_plain, data_xmit)

# Send it off to HQ
if options.transport == "ssmtp":
    send_ssmtp(data_xmit)
elif options.transport == "http":
    send_http(data_xmit)
elif options.transport == "autosupport_gw":
    send_autosupport_gw(data_xmit)
elif options.transport == "stdout":    
    sys.stdout.write(open(data_xmit, "r").read())
else:
    raise Exception, "unsupported transport: %s" % options.transport

# Clean up
for file in (data_plain, data_xmit):
    if os.path.isfile(file):
        os.remove(file)

# Something for the log
if not options.quiet:
    print "Health check complete."
