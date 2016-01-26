#
#  Filename:  $Source$
#  Revision:  $Revision: 20516 $
#  Date:      $Date: 2007-03-20 12:14:53 -0700 (Tue, 20 Mar 2007) $
#  Author:    $Author: gaul $
# 
#  (C) Copyright 2003-2007 Riverbed Technology, Inc.  
#  All rights reserved.
#

SSL_DIR='/var/opt/rbt/ssl'
DECRYPTED_DIR='/var/opt/rbt/decrypted'

# symlink
mkdir -m 0755 "${DECRYPTED_DIR}/ssl"
ln -s "${DECRYPTED_DIR}/ssl" "$SSL_DIR"

# set up SSL directories
mkdir -m 0755 "${SSL_DIR}/ca"
mkdir -m 0755 "${SSL_DIR}/server"
mkdir -m 0755 "${SSL_DIR}/tunnel"
mkdir -m 0755 "${SSL_DIR}/tunnel/ca"
mkdir -m 0755 "${SSL_DIR}/tunnel/cert"

# install well-known CA certificates
cp /opt/rbt/share/ca/* "${SSL_DIR}/ca"
