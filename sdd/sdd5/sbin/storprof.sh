cleanup()
{
    exit $1
}

get_root_partition()
{
    ROOT_DEV_LINE=`blkid -t LABEL=ROOT_${PARTITION_NUM}`

    ROOT_DEV=`echo ${ROOT_DEV_LINE} | /bin/cut -d ":" -f1`
}

# ==================================================
# Get list of storage profiles supported from the file /opt/hal/lib/specs/specs_storage_profiles
# ==================================================
get_stor_profiles_list()
{
    # get the model name
    MODEL_NAME=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/flex/model`
    
    # get the line corresponding to the model from specs_storage_profiles file
    # this line is of the form <model>: storage_profiles="<stor_prof_1> <stor_prof_2> ... "
    MODEL_LINE=`/bin/grep "^${MODEL_NAME}:" ${SPECS_STOR_PROFILES}`
    
    # get the content of the above line i.e. the part after the colon. storage_profiles="<stor_prof_1> <stor_prof_2> ... "
    MODEL_LINE_CONTENT=`echo ${MODEL_LINE} | /bin/cut -d ":" -f2`
    
    #Now MODEL_LINEi_CONTENT is the line containing the MODEL's storage profiles. Now parse this to get the stor_prof's !
    STOR_PROF_LIST=`echo ${MODEL_LINE_CONTENT} | /bin/cut -d "=" -f2 | /bin/cut -d "\"" -f2`
}   

# ==================================================
# Check if current storage profile is present in the list of storage profiles for that model
# ==================================================
do_check_curr_prof_in_list()
{
    # Now the list of storage profiles supported for that model is present in STOR_PROF_LIST
    # and the current storage profile is present in CURR_STOR_PROFILE
    CURR_PROF_IN_LIST=0

    # If current storage profile doesnt exist return; allow upgrade
    if [ "x${CURR_STOR_PROFILE}" = "x${STOR_PROF_LIST}" ]; then
        CURR_PROF_IN_LIST=1
        return
    fi

    # If curr storage profile is not blank, check if  its present in the list
    for i in ${STOR_PROF_LIST}; do
        if [ "x${i}" = "x${CURR_STOR_PROFILE}" ]; then
            CURR_PROF_IN_LIST=1
        fi
    done
}

# ==================================================
# Check if storage profile is present in upgraded image
# ==================================================
do_check_storage_profile()
{
    # Get current storage profile of current image
    CURR_STOR_PROFILE=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/resman/profile`

    # Get the specs_storage_profiles file from /var
    SPECS_STOR_PROFILES=/var/opt/tms/hal/${PARTITION_NUM}/specs_storage_profiles

    # Check if specs_storage_profiles files exists in this image
    if [ -f "${SPECS_STOR_PROFILES}" ]; then

        # Get to-be-upgraded-to image's supported storage profiles list
        # This list is got from the file /opt/hal/lib/specs/specs_storage_profiles
        # corresponding to the current model

        get_stor_profiles_list

        # check if current storage profile is present in the above list
        do_check_curr_prof_in_list

        if [ ${CURR_PROF_IN_LIST} -eq 0 ]; then
            # Then current storage profile is not present in the list. Abort image upgrade.
            echo "Current Storage profile is not supported by to-be-upgraded-to image. Aborting image upgrade."
            cleanup 1  # lc_err_upgrade_stor_profile_mismatch
        fi
    fi
}

PARTITION_NUM=$1

main()
{
    do_check_storage_profile
    cleanup 0
}

main
