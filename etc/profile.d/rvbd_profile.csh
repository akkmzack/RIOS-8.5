
if (! $?PATH) then
	setenv PATH "/bin:/usr/bin"
endif

limit coredumpsize unlimited

if ( $?tcsh ) then
	bindkey "^[[3~" delete-char
endif
