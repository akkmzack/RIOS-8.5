#!/bin/bash

MDDBREQ='/opt/tms/bin/mddbreq'
DB_PATH='/config/mfg/mfdb'
MODEL_DIR='/opt/hal/lib/specs/model'

curr_model=`/opt/tms/bin/hald_model | awk '{print $1}'`
model_file="${MODEL_DIR}/model_${curr_model}.sh"
if [ -x $model_file ]; then
    source ${model_file}
else
    echo "Model file for ${curr_model} not found on appliance. Operation aborted!"
    exit 1
fi

$MDDBREQ $DB_PATH set modify - /rbt/mfd/store/ftssize uint32 $MODEL_FTS_DISKSIZE_MB
store_dev=`$MDDBREQ -v $DB_PATH query get - /rbt/mfd/store/dev`

/sbin/sfdisk -d /dev/disk0 > /tmp/part_table
old_val=`/bin/cat /tmp/part_table | grep "${store_dev}" | /usr/bin/awk -F= '{print $3}' | /usr/bin/awk -F, '{print $1}' | /usr/bin/tr -d ' '`
new_val=$((MODEL_FTS_DISKSIZE_MB * 1024 * 2))

if [ "x${new_val}" == "x" ]; then
    echo "Resizing ${curr_model} store partition aborted!"
    exit 1
fi

/bin/sed s/${old_val}/${new_val}/g /tmp/part_table > /tmp/part_table_new
if [ $? -ne 0 ]; then
    echo "Error changing size in partition table. Abort"
    exit 1
fi

/sbin/sfdisk -q -uM --force --no-reread /dev/disk0 < /tmp/part_table_new > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error applying modified partition table. Abort"
    exit 1
fi

exit 0
