#!/bin/sh

# Print the Whitewater cloud backend/protocol type.
#
# See heartbeat.xml for where this is used.
#
# The output of this script should be the protocol_type as a string and an
# empty string if there's an error trying to get the protocol_type.
#
# On ERROR: If there is an error with the `mdreq` command the
# 'exec' output should be an empty string.  This is where the
# hacks come in:
#
#     # Simulate `mdreq` with `echo`.  Here we simulate `mdreq`
#     # returning no value on error.  See that STDOUT receives '0':
#     bash> echo $(( `echo` ))
#     0
#    
#     # If we add '* 1' and we see that STDOUT receives '' (but
#     # STDERR gets an error we will want to hide):
#     bash> echo $(( `echo` * 1 ))
#     -bash: * 1 : syntax error: operand expected (error token is "* 1 ")
#    
#     # Simply redirecting to /dev/null doesn't hide the error:
#     bash> echo $(( `echo` * 1 )) 2>/dev/null
#     -bash: * 1 : syntax error: operand expected (error token is "* 1 ")
#    
#     # So we run the command in a sub shell and redirect it's
#     # STDERR to hide the error:
#     bash> sh -c 'echo $(( `echo` * 1 ))' 2>/dev/null

sh -c '
    CLOUD_PROTO=( S3 Atmos Nirvanix Posix Rackspace Asure Swift Google HP Dummy Glacier)
    echo ${CLOUD_PROTO[ $((`/opt/tms/bin/mdreq -v query get - /rbt/rfsd/config/cloud/protocol_type` * 1)) ]}
' 2>/dev/null
