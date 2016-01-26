# /etc/cshrc
#
# csh configuration for all shell invocations.

# by default, we want this to get set.
# Even for non-interactive, non-login shells.
[ "`id -gn`" = "`id -un`" -a `id -u` -gt 99 ]
if $status then
	umask 022
else
	umask 002
endif

if ($?prompt) then
  if ($?tcsh) then
    set prompt='[%n@%m %c]$ ' 
  else
    set prompt=\[`id -nu`@`hostname -s`\]\$\ 
  endif
endif

unset dspmbyte

if ( -d /etc/profile.d ) then
	set nonomatch
        foreach i ( /etc/profile.d/*.csh )
		if ( -r $i ) then
               		source $i
		endif
        end
	unset i nonomatch
endif
