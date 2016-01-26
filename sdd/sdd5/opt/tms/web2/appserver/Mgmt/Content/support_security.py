## Copyright 2006, Riverbed Technoloy, Inc., All rights reserved.
## Author: Robin Schaufler
##
## support_security.psp
##
## support for security operations

import sys
import random
import string
from crypt import crypt
import common
import HTTPUtils
import Logging
import Nodes
import OSUtils
import RBA
import RbtUtils
import RVBDUtils
import UserConfig
from gclclient import NonZeroReturnCodeException

import FormUtils
from FormUtils import resetNodesFromConfigForm, \
                      setNodesFromConfigForm, \
                      getPrefixedField, \
                      getPrefixedFieldNames, \
                      deleteNodesFromConfigForm, \
                      ipv4IsValid, \
                      bogusPassword

from PagePresentation import PagePresentation
from XMLContent import XMLContent


## Return a list of authenticated users.
#
#  A list of authenticated users contains users of the following
#  account type:
#      - Special Accounts    : 'root'
#      - Capability Accounts : 'admin', 'monitor'
#      - Service Accounts    : 'statsd', 'sshd', 'apache' ...
#      - RBM Accounts
#
# The list of authenticated users on a CMC's policy page doesn't
# contain the Special and Service Accounts. The Special and
# Service Accounts are not configurable from a CMC.
#
# @param rbmOnly
#     Boolean flag for filtering. RBM accounts only.
#
# @return
#     A list of authenticated users for the appliance or policy
#     page.
#
def getAuthUsersRaw(self, rbmOnly):

    # Get all authenticated users
    authBase = self.cmcPolicyRetarget('/auth/passwd/user')
    users = Nodes.getMgmtSetEntries(self.mgmt, authBase)
    policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(self.fields)

    # Get only RBM account authenticated users
    if rbmOnly:
        # Get the list of existing RBM Users
        if policyName:
            # The CMC User Permission Policy Page contains
            # only Capability and RBM accounts.
            return [u for u in users.iterkeys()
                       if u not in ('admin', 'monitor')]
        else:
            # RBM accounts on the appliances are identified with
            # the 'is_rbm' node.
            return [u for u in users.iterkeys()
                       if 'true' == users[u].get('is_rbm')]

    # Return all authenticated users
    return users.keys()


class gui_Security(PagePresentation):
    # actions handled here
    actionList = [
        'changeAccountPassword',
        'resetUserConfig',
        'setupAuthPolicy',
        'setupSecurity_capabilityAccounts',
        'setupSecurity_auth',
        'setupSecurity_globalRadius',
        'setupSecurity_radiusServers',
        'setupSecurity_globalTacacs',
        'setupSecurity_tacacsServers',
        'setupSecurity_usersAction',
        'setupVault']

    def changeAccountPassword(self):
        account = self.fields['account']
        password = self.fields['password']
        oldPassword = self.fields.get('oldPassword') or None
        node = '/auth/passwd/user/%s/password' % account
        OSUtils.log(Logging.LOG_NOTICE, 'Changing password for %s' % account)
        if password == '':
            self.setNodes((node, 'string', ''))
        else:
            policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(self.fields)
            if policyType:
                self.setNodes((node, 'string', self.encryptPassword(password)))
            else:
                # The old password is required only when Account Control is
                # enabled and the minimum difference between passwords it
                # set to a value > 0. If the oldPassword value doesn't exist,
                # it implies that it isn't required.

                if oldPassword:
                    self.sendAction('/auth/passwd/user/action/set_passwd',
                                   ('username', 'string', account),
                                   ('password', 'string', password),
                                   ('old_password', 'string', oldPassword))
                else:
                    self.sendAction('/auth/passwd/user/action/set_passwd',
                                   ('username', 'string', account),
                                   ('password', 'string', password))
        self.setActionMessage('Password changed.')

    def resetUserConfig(self):
        UserConfig.resetConfig(self.session())
        self.setActionMessage('Restored default preferences for this account.')

    def setupAuthPolicy(self):
        fields = self.request().fields()
        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)
        prefix = pathPrefix + '/aaa/auth/config/policies/'
        enableAuthPolicy = 'enableAccCtrl' in fields
        bindings = [
            (prefix + 'enable',
             'bool',
             enableAuthPolicy and 'true' or 'false')
        ]
        if enableAuthPolicy:

            # Login attempts before lockout
            bindings.append((prefix + 'max_retry',
                'int32',
                fields.get('maxRetry') or '-1'))

            # Timeout for user re-login after locout
            bindings.append((prefix + 'retry_unlock_time',
                'duration_sec',
                 fields['retryUnlockTime']))

            # Days before password expires
            bindings.append((prefix + 'pass_expire',
                'int32',
                fields.get('passwordExpiryDays') or '-1'))

            # Days to warn user of an expiring password
            bindings.append((prefix + 'pass_expire_warn',
                'uint32',
                fields['passwordExpiryWarn']))

            # Days to lock account after password expires
            bindings.append((prefix + 'pass_lock',
                'int32',
                fields.get('passwordLockDays') or '-1'))

            # Maximum number of adjacent repeating characters
            bindings.append((prefix + 'pass_max_char_repeat',
                'uint32',
                fields['maximumRepeatingChars']))

            # Minimum interval for password reuse
            bindings.append((prefix + 'pass_min_reuse_interval',
                'uint32',
                fields['minimumInterval']))

            # Minimum interval for changing passwords
            bindings.append((prefix + 'pass_change_interval',
                'int32',
                fields['passwordChangeDays']))

            # Minimum password length
            bindings.append((prefix + 'pass_min_len',
                'uint32',
                fields['minimumPasswordLength']))

            # Minimum Uppercase Characters
            bindings.append((prefix + 'pass_min_ucredit',
                'uint32',
                fields['minimumUpperCase']))

            # Minimum Lowercase Characters
            bindings.append((prefix + 'pass_min_lcredit',
                'uint32',
                fields['minimumLowerCase']))

            # Minimum Numerical Characters
            bindings.append((prefix + 'pass_min_dcredit',
                'uint32',
                fields['minimumNumerical']))

            # Minimum Special Characters
            bindings.append((prefix + 'pass_min_ocredit',
                'uint32',
                fields['minimumSpecial']))

            # Minimum character difference between passwords
            bindings.append((prefix + 'pass_min_char_diff',
                'uint32',
                fields['minimumDifference']))

            # Prevent dictionary words
            bindings.append((prefix + 'pass_no_dict_word',
                'bool',
                'noDictWords' in fields and 'true' or 'false'))
        self.setNodes(*bindings)

    def setupSecurity_capabilityAccounts(self):

        # From Andy and Ka-Hing on why setting passwords on CMC is so
        # complicated:
        #
        # There are two problems. One requires special casing the
        # admin account, the other requires special casing all other
        # accounts.
        #
        # 1: admin
        #
        # The admin account is generally used by the CMC to connect
        # with managed appliances.
        #
        # The goal is to update the password the CMC uses in its
        # registration when the appliance's admin password changes. It
        # would be silly if we forced the user to update the
        # registration manually when an appliance's password is
        # changed from the CMC.
        #
        # Therefore, we "two-way" encrypt the password, so that at
        # push-time we can update the appliance's password in the
        # registration after a policy containing the password change
        # is successfully pushed.
        #
        # (This doesn't help if a non-admin account is used to connect
        # to the SH, of course.  We could two-way encrypt every
        # password and sort it which one's used for registration when
        # the policy is pushed, but two-way encryption is less secure
        # than a one-way hash so it was deemed preferable to use a
        # one-way hash whenever possible. That said, we are two-way
        # encrypting admin's password, which is the most important
        # password anyway.)
        #
        # We also don't do SHA encryption on the admin account because
        # the DES/SHA decision is made by the backend when the
        # password is pushed.
        #
        # 2: other accounts
        #
        # In 5.x, some customer required that we add SHA-encrypted
        # passwords to the SH.
        #
        # In order for the CMC to support configuration of SHA
        # passwords, it must hash passwords configured in the policy
        # in both the new (SHA) and old (DES) encryption schemes.
        # Then, at push-time, the CMC can push the password with the
        # appropriate encryption scheme based on whether SHA passwords
        # are enabled on the CMC.

        if 'editCapabilityAccount' in self.fields:
            base = self.cmcPolicyRetarget('/auth/passwd/user')
            account = self.fields['editCapabilityAccount_account']
            assert account in ('admin', 'monitor')

            if 'editCapabilityAccount_changepw' in self.fields:
                OSUtils.log(Logging.LOG_NOTICE, 'Changing password for %s' % account)
                password = self.fields['editCapabilityAccount_password']
                if password:
                    policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(self.fields)
                    if policyType:
                        # Handle users passwords for CMC's policy pages
                        if account == 'admin':
                            # Special handling for 'admin' password
                            self.setNodes(('%s/%s/password' % (base, account),
                                           'string',
                                           RbtUtils.decryptPasswordTwoWay(password)),
                                          ('%s/%s/password_2way' % (base, account),
                                           'bool', 'true'))
                        else:
                            # Users on CMC's policy pages requires the SHA512 encrypted password
                            self.setNodes(('%s/%s/password_sha512' % (base, account),
                                           'string',
                                           common.sha_encrypt_password(False, password)),
                                          ('%s/%s/password' % (base, account),
                                           'string',
                                           self.encryptPassword(password)))
                    else:
                        # Handle appliance level user passwords
                        self.sendAction('/auth/passwd/user/action/set_passwd',
                                       ('username', 'string', account),
                                       ('password', 'string', password))
                else:
                    # Disable password use
                    self.setNodes(('%s/%s/password' % (base, account), 'string', ''))

            # Prevent admin from having enable state changed.
            if ('admin' != account):
                self.setNodes(('%s/%s/enable' % (base, account),
                               'bool',
                               self.fields.get('editCapabilityAccount_enable', 'false')))
        if 'clearCapabilityLoginStats' in self.fields:
            account = self.fields['editCapabilityAccount_account']
            self.sendAction('/auth/passwd/user/action/reset_login_failure',
                            ('username', 'string', account))
    def setupSecurity_auth(self):
        fields = self.request().fields()
        mgmt = self.session().value('mgmt')
        cmc = 'editPolicy' in self.fields
        base = self.cmcPolicyRetarget('/aaa')

        # Apply any nodes on the page.
        FormUtils.setNodesFromConfigForm(mgmt, fields)

        if 'alwaysFback' in self.fields:
            self.setNodes((base + '/authen_always_fback', 'bool', 'false'))
        else:
            self.setNodes((base + '/authen_always_fback', 'bool', 'true'))

        authenticationOrder = fields.get('fallbackAuthenticationOrder', None)
        if authenticationOrder is None:
            authenticationOrder = fields['noFallbackAuthenticationOrder']

        authenticationOrder = authenticationOrder.split(',')

        # Authentication methods have an ordinal and a name.
        authenticationMethods = mgmt.getSubtree(base + '/auth_method')
        authenticationMethods = [int(k[:k.find('/')])
                                 for k in authenticationMethods.keys()
                                 if -1 < k.find('/name')]
        authenticationMethods.sort()
        authenticationMethods.reverse()

        MAX_METHODS = 3 # Max number of authentication methods set at any one time.
        for i in range(MAX_METHODS):
            if i < len(authenticationOrder):
                mgmt.set((base + '/auth_method/%d/name' % (i + 1),
                          'string', authenticationOrder[i]))
            else:
                mgmt.delete(base +'/auth_method/%d' % (i + 1))

    def setupSecurity_globalRadius(self):
        fields = self.request().fields()
        mgmt = self.session().value('mgmt')
        if 'apply' in fields.keys():
            self.setupGlobalServer(mgmt, 'radius', fields)

    def setupSecurity_radiusServers(self):
        cmc = 'editPolicy' in self.fields
        base = self.cmcPolicyRetarget('/radius/server')
        radiusSpec = {'enable': 'bool',
                      'address': 'hostname',
                      'auth-port': 'uint16',
                      'auth-type': 'string',
                      'key': 'string',
                      'timeout': 'duration_sec',
                      'retransmit': 'int32'}
        id, val = getPrefixedField('controlRadius_', self.fields)
        if id:
            id = 'server/%s' % id
            base = self.cmcPolicyRetarget('/radius/%s/enable' % id)
            setting = (base, 'bool', ('enabled' == val) and 'true' or 'false')
            self.mgmt.set(setting)
        elif 'addRadius' in self.fields:
            address = self.fields.get('radiusAdd_address')
            authPort = self.fields.get('radiusAdd_auth-port')
            authType = self.fields.get('radiusAdd_auth-type')
            timeout = self.fields.get('radiusAdd_timeout')
            if not timeout:
                # use the global default instead
                # backend defines this case using INT32_MAX which is 2147483647
                timeout = '2147483647'
            retransmit = self.fields.get('radiusAdd_retransmit')
            if not retransmit:
                # use the global default instead
                # backend defines this case using -1
                retransmit = '-1'
            enable = self.fields.get('radiusAdd_enable', 'false')
            key = self.fields.get('radiusAdd_key', '')
            if cmc:
                indexes = Nodes.getMgmtLocalChildrenNames(self.mgmt, base)
                index = max(map(int, indexes) or [0]) + 1

                vals = self.sendAction('/radius/action/encrypt_key', ('key', 'string', key))
                if vals:
                    key = vals.get('key')

                obj = {'address': address,
                       'auth-port': authPort,
                       'auth-type': authType,
                       'timeout': timeout,
                       'retransmit': retransmit,
                       'key': key,
                       'enable': enable}
                Nodes.editNodeSequence(self.mgmt, base, radiusSpec, 'add', index, obj)
            else:    # SH
                self.sendAction('/radius/action/server/add',
                                ('address', 'hostname', address),
                                ('auth-port', 'uint16', authPort),
                                ('auth-type', 'string', authType),
                                ('timeout', 'duration_sec', timeout),
                                ('retransmit', 'int32', retransmit),
                                ('key', 'string', key),
                                ('enable', 'bool', enable))
        elif 'editRadius' in self.fields:
            index = self.fields.get('radiusEdit_ord')
            address = self.fields.get('radiusEdit_address')
            authPort = self.fields.get('radiusEdit_auth-port')
            authType = self.fields.get('radiusEdit_auth-type')
            timeout = self.fields.get('radiusEdit_timeout')
            if not timeout:
                # use the global default instead
                # backend defines this case using INT32_MAX which is 2147483647
                timeout = '2147483647'
            retransmit = self.fields.get('radiusEdit_retransmit')
            if not retransmit:
                # use the global default instead
                # backend defines this case using -1
                retransmit = '-1'
            enable = self.fields.get('radiusEdit_enable', 'false')
            key = self.fields.get('radiusEdit_key', '')
            if cmc:
                # CMC sets policy nodes rather than asking mgmt actions
                # to set them.
                #
                # If the key field is the bogusPassword,
                # that means keep the original key.
                # If the key field is non-empty, encrypt it,
                # and set the new key to the encrypted value.
                # If the key field is empty, set the new key to empty,
                # to use the default key.
                originalKey = Nodes.present(self.mgmt,
                                            '%s/%s/key' % (base, index))
                if key == bogusPassword:
                    key = originalKey
                elif key:
                    vals = self.sendAction('/radius/action/encrypt_key',
                                           ('key', 'string', key))
                    if vals:
                        key = vals.get('key')
                    # Don't know why vals would ever be empty.
                    else:
                        key = ''
                else:
                    key = ''

                obj = {'address': address,
                       'auth-port': authPort,
                       'auth-type': authType,
                       'timeout': timeout,
                       'retransmit': retransmit,
                       'key': key,
                       'enable': enable}

                Nodes.editNodeSequence(self.mgmt, base, radiusSpec, 'edit', int(index), obj)
            else:    # SH
                params = [('server_idx', 'uint32', index),
                          ('address', 'hostname', address),
                          ('auth-port', 'uint16', authPort),
                          ('auth-type', 'string', authType),
                          ('timeout', 'duration_sec', timeout),
                          ('retransmit', 'int32', retransmit),
                          ('enable', 'bool', enable)]

                if key != bogusPassword:
                    params.append(('key', 'string', key))

                self.sendAction('/radius/action/server/modify', *params)
        elif 'removeRadius' in self.fields:
            ids = getPrefixedFieldNames('radius_', self.fields)
            ids = map(int, ids)
            ids.sort()
            ids.reverse()
            if cmc:
                for id in ids:
                    Nodes.editNodeSequence(self.mgmt, base, radiusSpec, 'remove', id)
            else:  # SH
                for id in ids:
                    self.sendAction('/radius/action/server/delete',
                                    ('server_idx', 'uint32', str(id)))

    def setupSecurity_globalTacacs(self):
        fields = self.request().fields()
        mgmt = self.session().value('mgmt')
        if 'apply' in fields.keys():
            self.setupGlobalServer(mgmt, 'tacacs', fields)

    # Setup the global default key, timeout, and retry values for
    # method = radius or tacacs.
    def setupGlobalServer(self, mgmt, method, fields):
        prefix = '%sGlobal_' % method
        postdata = {
            'key-usage': fields.pop(prefix + 'key-usage', ""),
            'key': fields.pop(prefix + 'key', ""),
            'conf': fields.pop(prefix + 'conf', "")}
        base = self.cmcPolicyRetarget('/%s/global/key' % method)
        doKeyAction = 'true' == postdata.get('key-usage', "")
        keyParam = self.decideKeyHandling(postdata, 'Global')
        if keyParam is None:
            # Leave the key unchanged.
            pass
        elif keyParam is False:
            # Set to no password.
            mgmt.set((base, 'string', ""))
        else:
            self.setEncodedGlobalKey(mgmt, method, keyParam)
        FormUtils.setNodesFromConfigForm(mgmt, fields)

    # Set the encoded global key in the back end one way for CMC,
    # another for SH.
    def setEncodedGlobalKey(self, mgmt, method, keyParam):
        if 'editPolicy' in self.fields:
            base = self.cmcPolicyRetarget('/%s/global/key' % method)
            vals = self.sendAction('/%s/action/encrypt_key' % method,
                                   ('key', 'string', keyParam))
            # If encryption has failed, don't set anything.
            if vals:
                enc_key = vals.get('key')
                if enc_key and enc_key != bogusPassword:
                    mgmt.set((base, 'string', enc_key))
        else:
            self.sendAction('/%s/action/global/set_key' % method,
                            ('key', 'string', keyParam))

    def decideKeyHandling(self, fields, op):
        """gui.decideKeyHandling(fields, keyNamePrefix)
Update fields and return one of the following:
None if the key should remain unchanged.
False to set it to no key at all.
a string to set the key.
        """
        # If key-usage is unchecked, the user wants no key, so return False.
        keyParam = False
        if 'true' == fields.pop('key-usage', ""):
            # checkbox is checked.
            key = fields['key']
            # If key is bogus, leave key node unchanged
            # unless it is a new entry.
            if bogusPassword == key:
                keyParam = None
                if 'Add' == op:
                    # JavaScript validator should have caught this already.
                    raise ValueError, \
                        "To override the global key, please enter a" \
                        + " server-specific key."
            else:
                keyParam = key
        return keyParam

    def setupSecurity_tacacsServers(self):
        cmc = 'editPolicy' in self.fields
        base = self.cmcPolicyRetarget('/tacacs/server')
        tacacsSpec = {'enable': 'bool',
                      'address': 'hostname',
                      'auth-port': 'uint16',
                      'auth-type': 'string',
                      'key': 'string',
                      'timeout': 'duration_sec',
                      'retransmit': 'int32'}
        id, val = getPrefixedField('controlTacacs_', self.fields)
        if id:
            id = 'server/%s' % id
            base = self.cmcPolicyRetarget('/tacacs/%s/enable' % id)
            setting = (base, 'bool', ('enabled' == val) and 'true' or 'false')
            self.mgmt.set(setting)
        elif 'addTacacs' in self.fields:
            address = self.fields.get('tacacsAdd_address')
            authPort = self.fields.get('tacacsAdd_auth-port')
            authType = self.fields.get('tacacsAdd_auth-type')
            timeout = self.fields.get('tacacsAdd_timeout')
            if not timeout:
                # use the global default instead
                # backend defines this case using INT32_MAX which is 2147483647
                timeout = '2147483647'
            retransmit = self.fields.get('tacacsAdd_retransmit')
            if not retransmit:
                # use the global default instead
                # backend defines this case using -1
                retransmit = '-1'
            enable = self.fields.get('tacacsAdd_enable', 'false')
            key = self.fields.get('tacacsAdd_key', '')
            if cmc:
                indexes = Nodes.getMgmtLocalChildrenNames(self.mgmt, base)
                index = max(map(int, indexes) or [0]) + 1

                vals = self.sendAction('/tacacs/action/encrypt_key',
                                       ('key', 'string', key))
                if vals:
                    key = vals.get('key')

                obj = {'address': address,
                       'auth-port': authPort,
                       'auth-type': authType,
                       'timeout': timeout,
                       'retransmit': retransmit,
                       'key': key,
                       'enable': enable}
                Nodes.editNodeSequence(self.mgmt, base, tacacsSpec, 'add', index, obj)
            else:    # SH
                self.sendAction('/tacacs/action/server/add',
                                ('address', 'hostname', address),
                                ('auth-port', 'uint16', authPort),
                                ('auth-type', 'string', authType),
                                ('timeout', 'duration_sec', timeout),
                                ('retransmit', 'int32', retransmit),
                                ('key', 'string', key),
                                ('enable', 'bool', enable))
        elif 'editTacacs' in self.fields:
            index = self.fields.get('tacacsEdit_ord')
            address = self.fields.get('tacacsEdit_address')
            authType = self.fields.get('tacacsEdit_auth-type')
            authPort = self.fields.get('tacacsEdit_auth-port')
            timeout = self.fields.get('tacacsEdit_timeout')
            if not timeout:
                # use the global default instead
                # backend defines this case using INT32_MAX which is 2147483647
                timeout = '2147483647'
            retransmit = self.fields.get('tacacsEdit_retransmit')
            if not retransmit:
                # use the global default instead
                # backend defines this case using -1
                retransmit = '-1'
            enable = self.fields.get('tacacsEdit_enable', 'false')
            key = self.fields.get('tacacsEdit_key', '')
            if cmc:
                # CMC sets policy nodes rather than asking mgmt actions
                # to set them.
                #
                # If the key field is the bogusPassword,
                # that means keep the original key.
                # If the key field is non-empty, encrypt it,
                # and set the new key to the encrypted value.
                # If the key field is empty, set the new key to empty,
                # to use the default key.
                originalKey = Nodes.present(self.mgmt,
                                            '%s/%s/key' % (base, index))
                if key == bogusPassword:
                    key = originalKey
                elif key:
                    vals = self.sendAction('/tacacs/action/encrypt_key',
                                           ('key', 'string', key))
                    if vals:
                        key = vals.get('key')
                    # Don't know why vals would ever be empty.
                    else:
                        key = ''
                else:
                    key = ''

                obj = {'address': address,
                       'auth-port': authPort,
                       'auth-type': authType,
                       'timeout': timeout,
                       'retransmit': retransmit,
                       'key': key,
                       'enable': enable}

                Nodes.editNodeSequence(self.mgmt, base, tacacsSpec, 'edit', int(index), obj)
            else:    # SH
                params = [('server_idx', 'uint32', index),
                          ('address', 'hostname', address),
                          ('auth-port', 'uint16', authPort),
                          ('auth-type', 'string', authType),
                          ('timeout', 'duration_sec', timeout),
                          ('retransmit', 'int32', retransmit),
                          ('enable', 'bool', enable)]

                if key != bogusPassword:
                    params.append(('key', 'string', key))

                self.sendAction('/tacacs/action/server/modify', *params)
        elif 'removeTacacs' in self.fields:
            ids = getPrefixedFieldNames('tacacs_', self.fields)
            ids = map(int, ids)
            ids.sort()
            ids.reverse()
            if cmc:
                for id in ids:
                    Nodes.editNodeSequence(self.mgmt, base, tacacsSpec, 'remove', id)
            else:  # SH
                for id in ids:
                    self.sendAction('/tacacs/action/server/delete',
                                    ('server_idx', 'uint32', str(id)))

    def setupSecurity_usersAction(self):
        fields = self.request().fields()
        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(fields)

        # From the given list of (role, perm) pairs
        # removes the group roles and instead adds the
        # component roles for that group
        def expandGroupRoles(rolePermissions):
            groupToRoles = {}
            for group, name, comment, roles in RBA.roleGroupList :
                groupToRoles[group] = roles

            expandedRolePerms = []
            for (role, perm) in rolePermissions:
                roleName = role.replace('-', '')
                if roleName in groupToRoles:
                    # Expand the group role into list of component roles
                    expandedRolePerms += [(compRole, perm)
                                         for compRole in groupToRoles[roleName]]
                else:
                    # Just add the role
                    expandedRolePerms.append((role, perm))
            return expandedRolePerms

        if 'addRbmUser' in fields:

            account = fields['addRbmUser_account']

            # Check for existing accounts
            if account in getAuthUsersRaw(self, False):
                formError = "Unable to add user '" + account + "'. Account already exists."
                self.setFormError(formError)
                return

            prefix = self.cmcPolicyRetarget('/auth/passwd/user/%s/%%s' % account)
            password = fields.get('addRbmUser_password')
            if password:
                if policyType:
                    # Users on CMC's policy pages requires the SHA512 encrypted password
                    self.setNodes((prefix % 'password_sha512', 'string',
                                   common.sha_encrypt_password(False, password)))
                    self.setNodes((prefix % 'password', 'string',
                                   self.encryptPassword(password)))
                else:
                    self.sendAction('/auth/passwd/user/action/set_passwd',
                                    ('username', 'string', account),
                                    ('password', 'string', password))
            else:
                self.setNodes((prefix % 'password', 'string', ''))

            # Set enable and password for the new account.
            self.setNodes((prefix % 'enable', 'bool',
                           fields.get('addRbmUser_enable', 'false')))

            # Get the role permission field names
            rolePermissions = getPrefixedFieldNames('addRole_', fields)
            # Pair the field names with their values
            rolePermissions = [(k, fields['addRole_' + k])
                               for k in rolePermissions]

            # Only assign those which specify read or write permission.
            assignedPermissions = [(k, v) for k, v in rolePermissions
                                   if v in ['read', 'write']]

            # Replace grouped roles by its component roles
            assignedPermissions = expandGroupRoles(assignedPermissions)

            # Prefix the field names for cmc,
            # constrain to read and write permission assignments,
            # and tuplize for setNodes.
            permPrefix = '/rbm/config/user/%s/role/%%s/permissions' % account
            rolePermissions = [(self.cmcPolicyRetarget(permPrefix % k),
                                'string', v)
                               for k, v in assignedPermissions]
            self.setNodes(*rolePermissions)

        elif 'editRbmUser' in fields:


            account = fields['editRbmUser_account']

            # Valid RBM account check
            if account not in getAuthUsersRaw(self, True):
                formError = "Unable to edit user '" + account + "'. Invalid role-based account name."
                self.setFormError(formError)
                return

            prefix = self.cmcPolicyRetarget('/auth/passwd/user/%s/%%s' % account)

            # Set enable and password for the edited account.
            if 'editRbmUser_changepw' in self.fields:
                password = self.fields.get('editRbmUser_password')
                if password:
                    if policyType:
                        # Users on CMC's policy pages requires the SHA512 encrypted password
                        self.setNodes((prefix % 'password_sha512', 'string',
                                       common.sha_encrypt_password(False, password)))
                        self.setNodes((prefix % 'password', 'string',
                                       self.encryptPassword(password)))
                    else:
                        self.sendAction('/auth/passwd/user/action/set_passwd',
                                        ('username', 'string', account),
                                        ('password', 'string', password))
                else:
                    self.setNodes((prefix % 'password', 'string', ''))

            self.setNodes((prefix % 'enable', 'bool',
                           fields.get('editRbmUser_enable', 'false')))

            ##
            # Assign and remove permissions.
            ##

            # Get all the role permission field names.
            rolePermissions = getPrefixedFieldNames('editRole_',
                                                     fields)
            # Pair all the role names to their values.
            rolePermissions = [(k, fields['editRole_' + k])
                                  for k in rolePermissions]
            # Only assign those which specify read or write permission.
            assignedPermissions = [(k, v) for k, v in rolePermissions
                                   if v in ['read', 'write']]

            # Replace grouped roles by its component roles
            assignedPermissions = expandGroupRoles(assignedPermissions)

            # Prefix the field names for cmc and tuplize for setNodes.
            permPrefix = '/rbm/config/user/%s/role/%%s/permissions' % account
            assignedPermissions = [(self.cmcPolicyRetarget(permPrefix % k),
                                    'string', v)
                                    for k, v in assignedPermissions]
            self.setNodes(*assignedPermissions)

            # Get the list of currently assigned role names.
            rolePrefix = self.cmcPolicyRetarget('/rbm/config/user/%s/role' % account)
            userRoles = [k for k in
                         self.mgmt.getSubtree(rolePrefix).keys()
                         if not k.endswith('/permissions')]

            # Get all roles which have deny permission
            removedPermissions = expandGroupRoles([(k, v) for k, v in rolePermissions
                                  if v == 'deny'])
            # Only select those roles which previously had
            # a non-deny permission for removal.
            removedPermissions = [k for (k,v) in removedPermissions
                                  if k in userRoles]

            # Do the removal.
            for roleName in removedPermissions:
                self.deleteNodes(rolePrefix + '/' + roleName)

        elif 'removeRbmUsers' in fields.keys():

            accounts = getPrefixedFieldNames('ck_', self.fields)

            # Valid RBM account check
            for account in accounts:
                if account not in getAuthUsersRaw(self, True):
                    formError = "Unable to remove user '" + account + "'. Invalid role-based account name."
                    self.setFormError(formError)
                    return

            deleteNodesFromConfigForm(self.mgmt,
                                      self.cmcPolicyRetarget('/auth/passwd/user'),
                                      'ck_',
                                      self.fields)
            # re-use setupSecurity_localPasswords when it has been improved.
        elif 'clearRbmLoginStats' in fields.keys():
            account = fields['editRbmUser_account']
            self.sendAction('/auth/passwd/user/action/reset_login_failure',
                            ('username', 'string', account))
    # the Secure Vault page
    def setupVault(self):
        if 'unlockVault' in self.fields:
            password = self.fields.get('unlockVault_password')
            self.sendAction('/secure_vault/action/unlock',
                            ('password', 'string', password))
        elif 'changeVaultPassword' in self.fields:
            # set the password
            oldPassword = self.fields.get('vaultPassword_oldPassword', '')
            newPassword = self.fields.get('vaultPassword_newPassword', '')
            self.sendAction('/secure_vault/action/change_password',
                            ('old_password', 'string', oldPassword),
                            ('new_password', 'string', newPassword))

    #### Utilities ####

    def encryptPassword(self, password):
        name, pre, isCmcPolicyOrApp = Nodes.cmcDecodeNodeMode(self.fields)
        useSha = 'true' == Nodes.present(self.mgmt,
            '/rbt/support/config/sha_password/enable')
        if useSha and not isCmcPolicyOrApp:
            return common.sha_encrypt_password(False, password)
        else:
            lick = string.letters + './'
            salt = '$1$' + ''.join(random.sample(lick, 8))
            return crypt(password, salt)


class xml_Security(XMLContent):
    # actions handled here
    dispatchList = ['radiusServers',
                    'tacacsServers',
                    'rbmprofiles',
                    'roles',
                    'rbmUsers',
                    'localUser',
                    'capabilityAccounts',
                    'setupFirewall',
                    'firewallRules',
                    'firewallTest']

    dogKickerList = ['setupFirewall',
                     'firewallTest']

    def tacacsServers(self):
        self.methodServers('tacacs')

    def radiusServers(self):
        self.methodServers('radius')

    def methodServers(self, method):
        mgmt = self.mgmt
        methodMapBase = self.cmcPolicyRetarget('/%s/server' % method)
        globalBase = self.cmcPolicyRetarget('/%s/global/' % method)
        result = self.doc.createElement(method)

        methodMap = Nodes.getMgmtTabularSubtree(
            mgmt, methodMapBase, Nodes.parentKeyStringIntCmp)
        defaultTimeout = '(%s)' % Nodes.present(mgmt,
            globalBase + 'timeout', '3')
        defaultRetransmit = '(%s)' % Nodes.present(mgmt,
            globalBase + 'retransmit', '1')
        for eachServer in methodMap:
            serverEl = self.createServerElement(
                defaultTimeout, defaultRetransmit, eachServer)
            if serverEl:
                result.appendChild(serverEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    def createServerElement(self,
        defaultTimeout, defaultRetransmit, serverMap):
        """createServerElement(defaultTimeout, defaultRetransmit, serverMap)
defaultTimeout and defaultRetransmit are strings containing numbers
enclosed in parentheses.
serverMap is a dict containing keys:
parentKey, address, auth-port, key, timeout, retransmit, status.
        """
        if 'address' not in serverMap:
            return None
        if serverMap.get('timeout', '2147483647') == '2147483647':
            serverMap['timeout'] = defaultTimeout
        if serverMap.get('retransmit', '-1') == '-1':
            serverMap['retransmit'] = defaultRetransmit
        if serverMap['key']:
            serverMap['key'] = "(Specific)"
        else:
            serverMap['key'] = "(Default)"
        serverMap['status'] = ('true' == serverMap['enable']) \
            and 'enabled' or 'disabled'
        serverMap['auth-type'] = serverMap.get('auth-type', "").upper()
        serverEl = self.doc.createElement('server')
        serverEl.setAttribute('ord', serverMap['parentKey'])
        serverEl.setAttribute('ip', serverMap['address'])
        serverEl.setAttribute('port', serverMap['auth-port'])
        serverEl.setAttribute('type', serverMap['auth-type'])
        serverEl.setAttribute('key', serverMap['key'])
        serverEl.setAttribute('timeout', serverMap['timeout'])
        serverEl.setAttribute('retries', serverMap['retransmit'])
        serverEl.setAttribute('status', serverMap['status'])
        return serverEl

    def _setPrettyLoginFailureDetails(self, userEl, loginDetails, user):
        # Login failure details are available only if the user's account is enabled.
        if 'true' == Nodes.present(self.mgmt, '/auth/passwd/user/%s/enable' % user):
            failureCount = loginDetails['/auth/passwd/user/%s/state/login_failure/count' % user]
            userEl.setAttribute('login_failure_count', failureCount)

            lockout = loginDetails['/auth/passwd/user/%s/state/login_failure/lock' % user]
            userEl.setAttribute('login_failure_lockout', lockout == 'true' and 'Yes' or 'No')

            pwdExpiry = loginDetails['/auth/passwd/user/%s/state/expire_in_days' % user]
            if pwdExpiry == '-2':
                pwdStatus = 'Never Expire'
            elif pwdExpiry == '-1':

                # If the password has expired, we check to see if it is locked.
                # The '/auth/passwd/user/<user>/state/lock_in_days' node returns a
                # '-1' if the password has expired and is locked.

                if '-1' == loginDetails['/auth/passwd/user/%s/state/lock_in_days' % user]:
                    pwdStatus = 'Expired and Locked'
                else:
                    pwdStatus = 'Expired'
            else:
                pwdStatus = 'Expires in %s day(s)' % pwdExpiry
            userEl.setAttribute('password_status', pwdStatus)

            if failureCount == '0':
                failureFrom = 'None'
            else:
                failureDate = loginDetails['/auth/passwd/user/%s/state/login_failure/date' % user]
                failureSource = loginDetails['/auth/passwd/user/%s/state/login_failure/source' % user]
                failureFrom = failureDate + ' from ' + failureSource
            userEl.setAttribute('login_failure_from', failureFrom)
        else:
            userEl.setAttribute('login_failure_count', 'N/A')
            userEl.setAttribute('login_failure_lockout', 'N/A')
            userEl.setAttribute('password_expiry', 'N/A')
            userEl.setAttribute('login_failure_from', 'N/A')

    # <rbmUsers>
    #   <user name="" enable="" gecos="" gid=""
    #         home_dir="" shell="" uid="" login_failure_count=""
    #         login_failure_from="" login_failure_lockout=""
    #         password_expiry="">
    #     <permission name="" value="" />
    #     ...
    #   </user>
    #   ...
    # </rbmUsers>
    def rbmUsers(self):
        # Get info on authenticated users
        base = self.cmcPolicyRetarget('/auth/passwd/user')
        users = Nodes.getMgmtSetEntries(self.mgmt, base)
        # Get a list of RBM Users
        rbmUserList = getAuthUsersRaw(self, True)
        rbmUserList.sort(FormUtils.alphanumericCompare)
        result = self.doc.createElement('rbmUsers')
        nodes = ['/auth/passwd/user/%s/state/login_failure/%s' % (u, f)
            for u in rbmUserList
            for f in ('count', 'lock', 'date', 'source')]
        for u in rbmUserList:
            nodes.append('/auth/passwd/user/%s/state/expire_in_days' % u)
            nodes.append('/auth/passwd/user/%s/state/lock_in_days' % u)
        loginDetails = self.mgmt.getMultiple(*nodes)
        for u in rbmUserList:
            userEl = self.doc.createElement('user')
            userEl.setAttribute('name', u)
            self.xmlizeAttributes(userEl, users[u],
                                  ('enable',
                                   'gecos',
                                   'gid',
                                   'home_dir',
                                   'shell',
                                   'uid'))

            self._setPrettyLoginFailureDetails(userEl, loginDetails, u)

            roleBase = self.cmcPolicyRetarget('/rbm/config/user/%s/role' % u)
            permissions = [(k[:-len('/permissions')], v) for k, v in
                          self.mgmt.getSubtree(roleBase).items()
                          if k.endswith('/permissions')]
            permissions.sort()
            for k, v in permissions:
                permissionEl = self.doc.createElement('permission')
                permissionEl.setAttribute('name', k)
                permissionEl.setAttribute('value', v)
                userEl.appendChild(permissionEl)
            result.appendChild(userEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # <capabilityAccounts>
    #   <capabilityAccount name="" password="" enable="" />
    #       login_failure_count="" login_failure_from=""
    #       login_failure_lockout="" password_expiry="">
    # </capabilityAccounts>
    def capabilityAccounts(self):
        base = self.cmcPolicyRetarget('/auth/passwd/user')
        result = self.doc.createElement('users')

        nodes = ['/auth/passwd/user/%s/state/login_failure/%s' % (u, f)
            for u in ('admin', 'monitor')
            for f in ('count', 'lock', 'date', 'source')]
        for u in ('admin', 'monitor'):
            nodes.append('/auth/passwd/user/%s/state/expire_in_days' % u)
            nodes.append('/auth/passwd/user/%s/state/lock_in_days' % u)
        loginDetails = self.mgmt.getMultiple(*nodes)

        for user in ('admin', 'monitor'):
            el = self.doc.createElement('capabilityAccount')
            el.setAttribute('name', user)

            self._setPrettyLoginFailureDetails(el, loginDetails, user)

            enabled = Nodes.present(self.mgmt, base + '/' + user + '/enable', '')
            el.setAttribute('enable', enabled)
            result.appendChild(el)

        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # <localUser>
    #   <permission name="<rolename>" value="Deny|Read-Only|Read/Write" />
    #   ...
    # </localUser>
    def localUser(self):
        ses = self.session()
        userName = ses.value('localId')
        result = self.doc.createElement('localUser')

        # collect the roles
        roles = {}
        for k, v in self.mgmt.getSubtree('/rbm/config/user/%s/role' % userName).items():
            if k.endswith('/permissions'):
                roles[k[:-len('/permissions')]] = RBA.rolePermissionMap[v]

        policyName, pathPrefix, policyType = Nodes.cmcDecodeNodeMode(self.fields)
        isCMCUser = RVBDUtils.isCMC() and not policyType

        # sort ard create XML elements
        sortedRoles = RBA.getSortedRoleSubset(roles.keys(), isCMCUser)
        for groupName, groupRoles in sortedRoles:
            for mgmtdName, prettyName in groupRoles:
                permissionEl = self.doc.createElement('permission')
                permissionEl.setAttribute(
                    'name', '%s: %s' % (groupName, prettyName))
                permissionEl.setAttribute('value', roles[mgmtdName])
                result.appendChild(permissionEl)
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()

    # Set up the firewall.  If the action fails, the returned XML node
    # will have an attribute called 'errorMsg' which contains a
    # human-friendly string describing the error.
    def setupFirewall(self):

        def internal(responseEl, **fields):

            # create an object to store the disconnect check
            # parameters which are needed for every firewall operation
            request = self.request()
            disconnectCheckParams = DisconnectCheckParams(
                remoteIp=request.remoteAddress(),
                serverIp=request.serverDictionary().get('SERVER_ADDR', ''),
                serverPort=request._environ.get('SERVER_PORT', '80'),
                service=request.isSecure() and 'https' or 'http',
                override='override' in fields and 'true' or 'false',
                responseEl=responseEl)

            # create a rule list object through which we can
            # manipulate the firewall
            policy, pathPrefix, mode = Nodes.cmcDecodeNodeMode(fields)
            ruleList = FirewallRuleList(
                self.mgmt, cmcPathPrefix=pathPrefix or None)

            # enable or disable the firewall
            if 'apply' in fields:
                ruleList.enableFirewall(
                    'firewallEnable' in fields, disconnectCheckParams)

            elif 'addFirewallRule' in fields:
                ord = fields.get('addRule_index')
                ruleList.add(
                    FirewallRule(fieldInfo=(fields, 'addRule_')),
                    ord and int(ord) or None,
                    disconnectCheckParams)

            elif 'editFirewallRule' in fields:
                ruleList.replace(
                    FirewallRule(fieldInfo=(fields, 'editRule_')),
                    int(fields['editRule_id']),
                    disconnectCheckParams)

            elif 'removeFirewallRules' in fields:
                ords = map(int, getPrefixedFieldNames('selectedRule_', fields))
                ruleList.delete(ords, disconnectCheckParams)

            elif 'moveFirewallRules' in fields:

                # Figure out where we're moving to.  This is the
                # desired final (1-based) position.
                ignore, toOrd = getPrefixedField('toRule_', fields)
                toOrd = int(toOrd)

                # Determine which rows to move.  These indices are
                # also 1-based.
                moveOrds = getPrefixedFieldNames('selectedRule_', fields)
                moveOrds = map(int, moveOrds)

                ruleList.move(moveOrds, toOrd, disconnectCheckParams)

            else:
                assert False, 'unknown action'

        self.remoteCallWrapper(internal)

    ## XML data for the Firewall rules table.
    #
    # - <tt><firewall-rules></tt>
    #   - <tt><rule></tt>*
    #     - <tt>id</tt>:  The 1-based index of this rule, if
    #       configurable, or <tt>''</tt> if it's immutable.
    #     - <tt>action</tt>
    #     - <tt>desc</tt>
    #     - <tt>interface</tt>
    #     - <tt>interfacePretty</tt>
    #     - <tt>service</tt>
    #     - <tt>servicePretty</tt>
    #     - <tt>protocol</tt>
    #     - <tt>log</tt>
    #     - <tt>logPretty</tt>
    #     - <tt>srcNetwork</tt>
    #     - <tt>srcNetworkPretty</tt>
    #     - <tt>dstPort</tt>
    def firewallRules(self):

        # this is run twice
        def tablizeRules(ruleList, movable):
            ord = 1
            for r in ruleList:
                table.addEntry(
                    id=movable and ord or '',
                    **r.getXmlAttrs())
                ord += 1

        table = self.getXmlTable(None, tagNames=('firewall-rules', 'rule'))
        table.open(self.request())
        tablizeRules(
            FirewallRuleList(self.mgmt, defaultRules=True), False)

        policy, pathPrefix, mode = Nodes.cmcDecodeNodeMode(self.fields)
        tablizeRules(
            FirewallRuleList(self.mgmt, cmcPathPrefix=pathPrefix or None), True)
        table.close()

    # The firewall test at the bottom of the Firewall page.
    def firewallTest(self):
        srcIp = self.fields.get('srcIp')
        srcPort = self.fields.get('srcPort')
        protocol = self.fields.get('protocol')
        interface = self.fields.get('interface')
        dstPort = self.fields.get('dstPort')

        response = 'Error testing rule.'
        try:
            response = self.sendAction('/net/firewall/action/test_firewall',
                                       ('protocol', 'uint16', protocol),
                                       ('source', 'ipv4addr', srcIp),
                                       ('source_port', 'uint16', srcPort),
                                       ('interface', 'string', interface),
                                       ('destination_port', 'uint16', dstPort))
        except NonZeroReturnCodeException, x:
            OSUtils.log(Logging.LOG_ERR, 'Exception testing rule: ' + str(x))
        result = self.doc.createElement('testResponse')
        result.appendChild(self.doc.createTextNode(str(response)))
        self.doc.documentElement.appendChild(result)
        self.writeXmlDoc()


## Encapsulates a firewall rule.
class FirewallRule(object):


    ## Constructor.
    #
    # A FirewallRule instance can be initialized using information
    # from the appliance configuration or from submitted form data.
    # nodeSubtree should be supplied to the constructor in the first
    # case and fieldInfo in the latter.
    #
    # @param nodeSubtree
    #   A map from node paths to values.  The keys are strings like
    #   'action' and 'source/network'.  Obviously, the caller is
    #   responsible for performing the query.
    # @param fieldInfo
    #   A (fields, prefix) pair.  fields is a dictionary containing
    #   the submitted form data and prefix is a string that prefixes
    #   each field name.  Note that the names of the fields that we
    #   examine match the NodeEntry objects in the .psp file.
    def __init__(self, nodeSubtree=None, fieldInfo=None):
        if nodeSubtree:
            self.__initFromNodes(nodeSubtree)
        else:
            self.__initFromFields(*fieldInfo)


    ## Initialize from existing config.
    def __initFromNodes(self, nodeSubtree):
        self.action = nodeSubtree['action']
        self.description = nodeSubtree.get('description')
        self.interface = nodeSubtree.get('interface')
        self.service = nodeSubtree.get('service')
        self.protocol = nodeSubtree.get('protocol')
        self.noLog = nodeSubtree.get('nolog')
        self.srcNetwork = nodeSubtree.get('source/network')
        self.dstPortStart = nodeSubtree.get('destination/port/start')
        self.dstPortEnd = nodeSubtree.get('destination/port/end')


    ## Initialize from form data.
    def __initFromFields(self, fields, prefix):

        self.action = fields[prefix + 'action']
        self.description = fields[prefix + 'desc']
        self.interface = fields[prefix + 'interface']
        self.service = fields.get(prefix + 'service')
        self.protocol = fields.get(prefix + 'protocol')
        self.noLog = fields.get(prefix + 'log') and 'false' or 'true'
        self.srcNetwork = fields[prefix + 'srcSubnet'] or '0.0.0.0/0'

        # destination port
        if prefix + 'dstPort' in fields:
            dstPortStr = fields[prefix + 'dstPort'] or '0'
            if dstPortStr.find('-') == -1:
                self.dstPortStart = dstPortStr
                self.dstPortEnd = dstPortStr
            else:
                self.dstPortStart, self.dstPortEnd = dstPortStr.split('-')
        else:
            self.dstPortStart = None
            self.dstPortEnd = None


    ## Return a list of 3-tuples representing nodes to set or action
    ## parameters.
    #
    # @param rulePrefix
    #   If we're configuring a CMC policy, this is the prefix for the
    #   node paths.  It should look something like
    #   <tt>/path/to/table/0</tt>.
    #
    # @return
    #   A list of (path|name, type, value) tuples.  If rulePrefix is
    #   supplied, the returned list contains nodes that should be set.
    #   Otherwise, the list contains parameters that can be passed to
    #   an action to add or edit the rule.
    def getConfigParameters(self, rulePrefix=''):

        nodes = []
        params = []

        if self.action != None:
            nodes.append(
                (rulePrefix + '/action', 'string', self.action))
            params.append(('action', 'string', self.action))
        if self.description != None:
            nodes.append(
                (rulePrefix + '/description', 'string', self.description))
            params.append(('description', 'string', self.description))
        if self.interface != None:
            nodes.append(
                (rulePrefix + '/interface', 'string', self.interface))
            params.append(('interface', 'string', self.interface))
        if self.service != None:
            nodes.append(
                (rulePrefix + '/service', 'string', self.service))
            params.append(('service', 'string', self.service))
        if self.protocol != None:
            nodes.append(
                (rulePrefix + '/protocol', 'uint8', self.protocol))
            params.append(('protocol', 'uint8', self.protocol))
        if self.noLog != None and self.action != 'allow':  # N/A in allow mode
            nodes.append(
                (rulePrefix + '/nolog', 'bool', self.noLog))
            params.append(('nolog', 'bool', self.noLog))
        if self.srcNetwork != None:
            nodes.append((
                rulePrefix + '/source/network',
                'ipv4prefix',
                self.srcNetwork))
            params.append(('source_network', 'ipv4prefix', self.srcNetwork))
        if self.dstPortStart:
            nodes.append((
                rulePrefix + '/destination/port/start',
                'uint16',
                self.dstPortStart))
            nodes.append((
                rulePrefix + '/destination/port/end',
                'uint16',
                self.dstPortEnd))
            params.append((
                'destination_port',
                'string',
                '%s-%s' % (self.dstPortStart, self.dstPortEnd)))

        if rulePrefix:
            return nodes
        else:
            return params


    ## Return the rule attributes in a form suitable for
    ## XmlTable.addEntry().
    #
    # The contents in the returned dictionary match the attributes
    # required by the AET on the firewall page.
    #
    # @return
    #   A dictionary containing the following:
    #   - action
    #   - desc
    #   - interface
    #   - interfacePretty
    #   - service
    #   - servicePretty
    #   - protocol
    #   - log
    #   - srcNetwork
    #   - srcNetworkPretty
    #   - dstPort
    def getXmlAttrs(self):

        PROTOCOL_NAMES = {
            '0': '*',
            '1': 'ICMP',
            '6': 'TCP',
            '17': 'UDP',
        }

        def formatServicePretty():
            if self.service:
                return self.service
            else:
                protocolName = PROTOCOL_NAMES.get(self.protocol)
                portRange = formatPortRange()
                if portRange in ('', '0'):
                    portRange = '*'
                if protocolName == '*' and portRange == '*':
                    return '*'
                else:
                    return '%s:%s' % (protocolName, portRange)

        def formatPortRange():
            if self.dstPortStart != self.dstPortEnd:
                return '%s-%s' % (self.dstPortStart, self.dstPortEnd)
            elif self.dstPortEnd in ('0', None):
                return ''
            else:
                return self.dstPortStart

        # Set the values and css class for the "Log Packets" column.
        log = (self.noLog == 'true') and 'false' or 'true'
        if self.action == 'allow':
            logPretty = 'N/A'
            logPrettyTdClass = 'dimmed'
        else:
            logPretty = (self.noLog == 'true') and 'No' or 'Yes'
            logPrettyTdClass = ''

        return {
            'action':           self.action,
            'desc':             self.description,
            'interface':        self.interface,
            'interfacePretty':  self.interface or '*',
            'service':          self.service,
            'servicePretty':    formatServicePretty(),
            'protocol':         self.protocol,
            'log':              log,
            'logPretty':        logPretty,
            'logPrettyTdClass': logPrettyTdClass,
            'srcNetwork':       self.srcNetwork,
            'srcNetworkPretty': self.srcNetwork or '0.0.0.0/0',
            'dstPort':          formatPortRange(),
        }


## A struct-like class for use with the FirewallRuleList methods that
## modify the configuration.
#
# This encapsulates the information required to perform the disconnect
# check and return the error message if the check fails.
class DisconnectCheckParams(object):


    ## Constructor.
    #
    # @param clientIp
    #   The IP address of the client.
    # @param serverIp
    #   The IP address on the server that the client connected to.
    # @param serverPort
    #   The port on the server that the client connected to.  (This
    #   should be a string.)
    # @param service
    #   The name of the service that the client is using.
    # @param override
    #   'true' to override the safety check and 'false' otherwise.
    # @param responseEl
    #   The XML element used to return the safety check error.  If the
    #   action triggers the check, the error message will be stored in
    #   an attribute named 'errorMsg'.
    def __init__(self, **kwargs):
        self.remoteIp = kwargs['remoteIp']
        self.serverIp = kwargs['serverIp']
        self.serverPort = kwargs['serverPort']
        self.service = kwargs['service']
        self.override = kwargs['override']
        self.responseEl = kwargs['responseEl']


## Abstraction for an ordered list of firewall rules.
#
# Use this class to add, edit, remove, and move rules.  This also
# allows the firewall to be enabled or disabled.
class FirewallRuleList(object):


    ## Constructor.
    #
    # A FirewallRuleList instance is initialized based on existing
    # configuration.  Its contents mirror the configuration of the
    # device or CMC policy.
    #
    # @param mgmt
    # @param defaultRules
    #   True if this instance should represent the default (immutable)
    #   rules or False if it should represent the configurable rules.
    # @param cmcPathPrefix
    #   If this instance should represent a CMC policy, pass in the
    #   path prefix for that policy.  Otherwise, this defaults to
    #   None.
    def __init__(
            self,
            mgmt,
            defaultRules=False,
            cmcPathPrefix=None):

        self.__mgmt = mgmt
        self.__editingCmcPolicy = (cmcPathPrefix != None)
        self.__defaultRules = defaultRules

        # __aclPrefix is the path to the non-rule config nodes
        if self.__editingCmcPolicy:
            self.__aclPrefix = cmcPathPrefix + '/net/firewall/config'
        else:
            self.__aclPrefix = '/net/firewall/config'

        # __aclRulePrefix is the path to the rules
        if self.__defaultRules:
            self.__aclRulePrefix = '/net/firewall/state/default_rules'
        else:
            self.__aclRulePrefix = self.__aclPrefix + '/tables/inbound/rules'

        # read the config and create a FirewallRule instance for each
        # rule that we find
        nodeTree = Nodes.getMgmtSetEntriesDeep(
            self.__mgmt, self.__aclRulePrefix)
        ords = nodeTree.keys()
        ords.sort(key=int)
        self.__rules = [FirewallRule(nodeSubtree=nodeTree[o]) for o in ords]



    ## Allow iteration over the list of rules.
    def __iter__(self):
        return self.__rules.__iter__()


    ## Write the contents of this object to the CMC policy nodes.
    #
    # When editing a CMC policy, we're responsible for setting the
    # firewall nodes explicitly.  This method makes the nodes match
    # the rules that are represented by this rule list object.
    def __rewriteCmcPolicyNodes(self):

        # default rules are read-only
        assert not self.__defaultRules

        # we shouldn't be calling this if we're not editing a policy
        assert self.__editingCmcPolicy

        # easiest way is to delete everything and write it back out
        nodes = [(self.__aclRulePrefix + '/*', 'none', '')]
        for i in range(len(self.__rules)):
            rulePrefix = '%s/%i' % (self.__aclRulePrefix, i + 1)
            nodes.extend(self.__rules[i].getConfigParameters(rulePrefix))
        Nodes.set(self.__mgmt, *nodes)


    ## Helper function for performing a firewall-related action.
    #
    # When we're configuring the firewall on the device itself (as
    # opposed to a CMC policy) we do it via actions that take certain
    # special parameters that are used to perform a disconnect check.
    #
    # If the disconnect check fails, we save the error message in an
    # XML attribute called 'errorMsg'.  (Actually, all errors are
    # saved in this manner, not just disconnect check failures.  But
    # by design no other errors should occur.)
    #
    # @param action
    #   The action node.
    # @param disconnectCheckParams
    #   A DisconnectCheckParams object.
    # @param params
    #   A variable number of (name, type, value) triples.
    def __wrapAction(self, action, disconnectCheckParams, *params):

        # default rules are read-only
        assert not self.__defaultRules

        try:
            checkParams = [
                ('action_ip', 'ipv4addr', disconnectCheckParams.remoteIp),
                ('server_ip', 'ipv4addr', disconnectCheckParams.serverIp),
                ('action_port', 'uint16', disconnectCheckParams.serverPort),
                ('action_service', 'string', disconnectCheckParams.service),
                ('action_override', 'bool', disconnectCheckParams.override),
            ]
            Nodes.action(self.__mgmt, action, *(checkParams + list(params)))

        except NonZeroReturnCodeException, e:
            disconnectCheckParams.responseEl.setAttribute('errorMsg', str(e))


    ## Enable or disable the firewall.
    #
    # This affects the entire firewall, not just the rules that are
    # encapsulated by this list.  (In other words, this will enable or
    # disable both the default and configurable rules.)
    #
    # @param enable
    #   True to enable and False to disable.
    # @param disconnectCheckParams
    #   A DisconnectCheckParams object containing the safety check
    #   parameters.
    def enableFirewall(self, enable, disconnectCheckParams):
        if self.__editingCmcPolicy:
            path = self.__aclPrefix + '/enable'
            enable = enable and 'true' or 'false'
            Nodes.set(self.__mgmt, (path, 'bool', enable))
        else:
            self.__wrapAction(
                '/net/firewall/action/set_enabled',
                disconnectCheckParams,
                ('enable', 'bool', enable and 'true' or 'false'))


    ## Add a rule.
    #
    # @param rule
    #   The FirewallRule object to add.
    # @param ord
    #   The location where the new rule should appear.  This should be
    #   an integer representing a 1-based index or None.  If None is
    #   supplied, the rule is placed at the end of the list.
    # @param disconnectCheckParams
    #   A DisconnectCheckParams object containing the safety check
    #   parameters.
    def add(self, rule, ord, disconnectCheckParams):

        if ord == None:
            ord = len(self.__rules) + 1
        assert ord <= (len(self.__rules) + 1), 'invalid ordinal'

        self.__rules.insert(ord - 1, rule)

        if self.__editingCmcPolicy:
            self.__rewriteCmcPolicyNodes()
        else:
            self.__wrapAction(
                '/net/firewall/action/add_rule',
                disconnectCheckParams,
                *(rule.getConfigParameters() + [('idx', 'uint16', ord)]))


    ## Replace/edit a rule.
    #
    # @param rule
    #   The new FirewallRule to add.
    # @param ord
    #   The 1-based index of the rule to replace.
    # @param disconnectCheckParams
    #   A DisconnectCheckParams object containing the safety check
    #   parameters.
    def replace(self, rule, ord, disconnectCheckParams):

        assert ord <= len(self.__rules), 'invalid ordinal'

        del self.__rules[ord - 1]
        self.__rules.insert(ord - 1, rule)

        if self.__editingCmcPolicy:
            self.__rewriteCmcPolicyNodes()
        else:
            self.__wrapAction(
                '/net/firewall/action/edit_rule',
                disconnectCheckParams,
                *(rule.getConfigParameters() + [('idx', 'uint16', ord)]))


    ## Delete rules.
    #
    # @param deleteOrds
    #   A list of 1-based indices representing rules to delete.
    # @param disconnectCheckParams
    #   A DisconnectCheckParams object containing the safety check
    #   parameters.
    def delete(self, deleteOrds, disconnectCheckParams):

        deleteOrds.sort(reverse=True)
        for o in deleteOrds:
            del self.__rules[o - 1]

        if self.__editingCmcPolicy:
            self.__rewriteCmcPolicyNodes()

        # The interface for deleting rules is a little funny.  If we
        # have more than one rule to remove, the additional ones must
        # be supplied as a comma-separated list to the multiple_index
        # parameter.
        else:

            deleteOrds = map(str, deleteOrds)
            params = [('idx', 'uint16', str(deleteOrds[0]))]

            if len(deleteOrds) > 1:
                params.append(
                    ('multiple_index', 'string', ','.join(deleteOrds[1:])))

            self.__wrapAction(
                '/net/firewall/action/delete_rule',
                disconnectCheckParams,
                *params)


    ## Move rules.
    #
    # @param moveOrds
    #   A list of 1-based indices indicating which rules to move.
    # @param toOrd
    #   The 1-based index indicating where the rules should be moved
    #   to.  This will be the final starting position of the block of
    #   rules that are being moved.
    # @param disconnectCheckParams
    #   A DisconnectCheckParams object containing the safety check
    #   parameters.
    def move(self, moveOrds, toOrd, disconnectCheckParams):


        # Helper function that rearranges the internal rule list so
        # that its order matches what was requested.
        def adjustInternalRuleList():

            # We're going to remove the rules that are being moved
            # from our internal list and store them temporarily in
            # movedRules.  We do this in reverse order for reasons
            # that will be more obvious later.
            movedRules = []
            moveOrds.sort(reverse=True)

            # make a copy of the toOrd because the value we need when
            # we modify the rule list is different from the one used
            # by the action
            listToOrd = toOrd

            for o in moveOrds:

                # Add to movedRules and remove from our internal list.
                movedRules.append(self.__rules[o - 1])
                del self.__rules[o - 1]

                # We use listToOrd later to indicate the insertion
                # point into the shortened internal list so we need to
                # decrement it each time we remove something that
                # appears before listToOrd.  This must be done in
                # order of descending ords.
                if o < listToOrd:
                    listToOrd -= 1

            # Insert the rules that we're moving back into the
            # internal list.  Again, it's convenient that movedRules
            # is in reverse order as inserting them all into the same
            # position does another reversal, resulting in a correctly
            # ordered list.
            for r in movedRules:
                self.__rules.insert(listToOrd - 1, r)


        adjustInternalRuleList()

        if self.__editingCmcPolicy:
            self.__rewriteCmcPolicyNodes()

        # The move action is quirky in the same way that the remove
        # action is (with the multiple_index).
        else:

            moveOrds.sort()

            # If the first row we're moving (the from_idx) is before
            # the place we're moving it to, toOrd must be decremented.
            # Not entirely sure why.  cwong told me to.
            if moveOrds[0] < toOrd:
                toOrd -= 1

            moveOrds = map(str, moveOrds)
            params = [
                ('from_idx', 'uint16', moveOrds[0]),
                ('to_idx', 'uint16', str(toOrd)),
            ]

            if len(moveOrds) > 1:
                params.append(
                    ('multiple_index', 'string', ','.join(moveOrds[1:])))

            self.__wrapAction(
                '/net/firewall/action/move_rule',
                disconnectCheckParams,
                *params)
