#!//bin/bash
	
#For each of these core dirs, 
#if they contain>10 cores the old ones are deleted 	   
for dir in /var/log/samba/cores/{winbindd,smbd,nmbd}
do
    ls ${dir}/*core* --sort=time \
  | awk 'NR>10{print}' \
  | xargs rm
done


