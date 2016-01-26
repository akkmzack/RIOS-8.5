# /etc/csh.login

# System wide environment and startup programs, for login setup

if (! $?PATH) then
	setenv PATH "/bin:/usr/bin"
endif

limit coredumpsize unlimited

setenv HOSTNAME `/bin/hostname`
set history=1000

if ( -f $HOME/.inputrc ) then
	setenv INPUTRC /etc/inputrc
endif

if ( $?tcsh ) then
	bindkey "^[[3~" delete-char
endif
