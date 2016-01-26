import subprocess

bool_map={'false':False, 'true':True}

def to_bool(val):
    return bool_map[val.strip().lower()]

def get_command_output(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (val,err) = p.communicate()
    return (val.strip(),err)

MDREQ = '/opt/tms/bin/mdreq '
GET = '-v query get - '
ITERATE = '-v query iterate - '

glb_rate_pacing_cmd = MDREQ + GET+ "/rbt/sport/vegas/config/rate_cap_enabled"
num_of_rule_cmd = MDREQ + ITERATE + "/rbt/sport/transport/config/rule"
sei_rate_pacing_cmd = MDREQ + GET + "/rbt/sport/transport/config/rule/"

(rate,err) = get_command_output(glb_rate_pacing_cmd)
rate_pacing = to_bool(rate)
if not rate_pacing:
    (rule_num,err) = get_command_output(num_of_rule_cmd)
    rule_num = rule_num.split("\n")

    for rules in rule_num:
        (rp, err) = get_command_output(sei_rate_pacing_cmd+rules+'/rate_cap_enabled')
        if to_bool(rp):
            rate_pacing = True
            break
print rate_pacing

