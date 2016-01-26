#!/bin/bash

MODEL_DIR='/opt/hal/lib/specs/model'

curr_model=`/opt/tms/bin/hald_model | awk '{print $1}'`
model_file="${MODEL_DIR}/model_${curr_model}.sh"
if [ -x $model_file ]; then
    source ${model_file}
else
    echo "-1"
    exit 1
fi

echo "${MODEL_FTS_DISKSIZE_MB}"

exit 0
