#!/usr/bin/env python

MDDBREQ = '/opt/tms/bin/mddbreq'
DB = None
DEST_DIR = '/var/opt/rcu/old_conf'
BACKUP_DIR = '/var/opt/rcu/backup'

SAMBA_CONF_GLOBAL_TEMPLATE = '''\
[global]

   server signing = %s

   workgroup = %s
   realm = %s
   nt acl support = yes

   server string = Proxy File Services

   log file = /var/log/samba/smbd.log

   max log size = %s

   log level = %s

   security = ADS

   %s
   encrypt passwords = yes

   socket options = TCP_NODELAY SO_RCVBUF=8192 SO_SNDBUF=8192

   admin users = @root

   idmap uid = 16777216-33554431
   idmap gid = 16777216-33554431
   template shell = /bin/false
   winbind use default domain = no
   winbind enum users = yes
   winbind enum groups = yes

   deadtime = %s
'''

KRB5_CONF_TEMPLATE = '''\
[logging]
    default = SYSLOG
    kdc = SYSLOG
    admin_server = SYSLOG

[libdefaults]
    default_realm = %s
    dns_lookup_realm = true
    dns_lookup_kdc = true

[realms]
    %s = {
        default_domain = %s
        %s
    }

[domain_realm]
    .%s = %s
    %s = %s

[kdc]
    profile = /var/kerberos/krb5kdc/kdc.conf

[appdefaults]
    pam = {
        debug = false
            ticket_lifetime = 36000
            renew_lifetime = 36000
            forwardable = true
            krb4_convert = false
    }
'''

RCU_CONF_TEMPLATE = '''\
maintenance_freq = 5
start = %s
'''

RCU_CONF_SHARE_TEMPLATE = '''\
[%s]

path = /proxy/%s
remote_path = %s
remote_server_name = %s
remote_server_port = %s
share_mode = %s
sync_frequency = %s
syncing = %s
'''

# get values from configuration database

def get_node_value(node):
    '''Retrieve a single node from DB.'''
    from commands import getstatusoutput
    code, value = getstatusoutput('%s -v %s query get - %s' %
                                  (MDDBREQ, DB, node))
    if code != 0:
        raise Exception('bad output')
    return value

def get_subtree_key_values(node):
    '''Retrieve all children of a node from the DB.'''
    from commands import getstatusoutput
    code, value = getstatusoutput('%s %s query iterate "" %s' %
                                  (MDDBREQ, DB, node))
    if code != 0:
        raise Exception('bad output')
    if value == '':
        return {}

    records = value.split('\n\n')
    key_values = {}
    for rec in records:
        name, attrib, type, value = [ x.split(':', 1)[1].strip()
                                      for x in rec.split('\n', 3) ]
        key_values[name] = value
    return key_values

# generate configuration files

def krb_realms():
    domain_name = get_node_value('/rbt/samba/config/domain_name')
    return '.%s     %s\n' % (domain_name, domain_name)

def krb5_conf():
    domain_name = get_node_value('/rbt/samba/config/domain_name')
    domain_name_upper = domain_name.upper()
    domain_name_lower = domain_name.lower()
    dc_name = get_node_value('/rbt/samba/config/dc_name')

    return KRB5_CONF_TEMPLATE % (
                domain_name_upper, domain_name_upper, domain_name_lower,
                dc_name, domain_name_lower, domain_name_upper,
                domain_name_lower, domain_name_upper)

def rcu_conf():
    start = get_node_value('/rbt/samba/config/smb/auto_launch')

    output = RCU_CONF_TEMPLATE % start

    for share_node in get_subtree_key_values('/rbt/samba/config/share'):
        share = get_subtree_key_values(share_node)

        local_name = share_node.split('/')[-1]
        remote_path  = share[share_node + '/remote_path']
        share_server = share[share_node + '/server']
        port         = share[share_node + '/port']
        share_mode   = share[share_node + '/mode']
        freq         = share[share_node + '/freq']
        syncing      = share[share_node + '/enable']

        output += '\n'
        output += RCU_CONF_SHARE_TEMPLATE % (
                    local_name, local_name, remote_path, share_server, port,
                    share_mode, freq, syncing)

    return output

def samba_conf():
    output = samba_global_conf()
    for share_node in get_subtree_key_values('/rbt/samba/config/share'):
        output += '\n'
        output += samba_share_conf(share_node)
    return output

def samba_global_conf():
    security_signature = get_node_value('/rbt/samba/config/security_signature')
    realm = get_node_value('/rbt/samba/config/domain_name')
    workgroup = realm.split('.', 1)[0]
    max_log_size = get_node_value('/rbt/samba/config/log_size')
    log_level = get_node_value('/rbt/samba/config/log_level')
    password_server = get_node_value('/rbt/samba/config/dc_name')
    deadtime = get_node_value('/rbt/samba/config/deadtime')

    return SAMBA_CONF_GLOBAL_TEMPLATE % (
                security_signature, workgroup, realm, max_log_size, log_level,
                password_server, deadtime)

def samba_share_conf(share_node):
    share = get_subtree_key_values(share_node)
    local_name = share_node.split('/')[-1]
    comment = share[share_node + '/comment']
    share_mode = share[share_node + '/mode']
    share_enabled = share[share_node + '/enable'] == 'true'

    output = []
    output += ['[%s]' % local_name]
    output += ['   comment = %s' % comment]
    output += ['   path = /proxy/%s' % local_name]
    if share_mode == 'broadcast':
        output += ['   writeable = no']
        output += ['   write list = rcud, administrator']
    else:
        output += ['   writeable = yes']
    output += ['   guest ok = no']
    output += ['   public = no']
    if share_enabled:
        output += ['   preexec = /sbin/smb_preexec.pl %%u %%m yes']
    else:
        output += ['   preexec = /sbin/smb_preexec.pl %%u %%m no']
    output += ['   preexec close = yes']
    if not share_enabled:
        output += ['   hosts allow = 127.0.0.1']
    if share_mode != 'local':
        output += ['   vfs objects = rbt_audit']
    output += ['\n']
    return '\n'.join(output)

def main():
    from errno import EEXIST
    from os import mkdir
    global DB

    try:
        f = file('/config/db/active')
        s = f.read()
        if s.endswith('\n'):
            s = s[:-1]
        f.close()
        DB = s
    except IOError, e:
        print 'Could not file active config db'
        return

    for directory in DEST_DIR, BACKUP_DIR:
        try:
            mkdir(directory)
        except OSError, e:
            if e.errno != EEXIST:
                raise

    conf_files = [
        ('rcu.conf',   rcu_conf), 
        ('smb.conf',   samba_conf),
        ('krb.realms', krb_realms),
        ('krb5.conf',  krb5_conf),
    ]
    for filename, func in conf_files:
        try:
            f = file(DEST_DIR + '/' + filename, 'w')
            f.write(func())
            f.close()
        except IOError, e:
            print e

if __name__ == '__main__':
    main()
