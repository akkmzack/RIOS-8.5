#!/bin/sh

#
# (C) Copyright 2003-2009 Riverbed Technology, Inc.
# All rights reserved.
# $Id: sshaskpassfd.sh 81214 2011-05-03 00:09:51Z aanantha $
#
# SSH Askpass script that allows a password to be fed into openssh
# via a specified file descriptor.

if [ -n "$SSH_ASKPASS_FD" ]
then
	read -r password <&$SSH_ASKPASS_FD
	echo "$password"
	exit 0
else
	echo "SSH_ASKPASS_FD not set!" >&2
	exit 1
fi
