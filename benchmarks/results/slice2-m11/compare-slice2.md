# Tracefix benchmark: slice2-m11 against slice2

Arm B against arm A on the same units (task, kind, repeat), from the runs, receipts,
prepare records and the developer's labels (scripts/bench/report.py). Wrong fixes:
b_only counts units where only B found the leftover (a_only the reverse); the sign
test is one-sided (B better), exact, on those discordant units. Misses: why a wrong
fix's leftover was not found, from the receipt and the prepare record. Blind: the
report-only shadow test, and what a rule capping at L1 when it fails on head would
do; no level reads it. Doubt: the report-only flags on findings, and what a rule not
counting them would do, per flag; no level reads it. Tricky strings: findings whose
shown input holds one (by value). Live spend: what the spend guard counted, retries
included. Seconds: the paired runs' times; seconds_with_timeouts adds the arm's own
timed-out runs (no receipt, so no pair) at the seconds they ran.

## all

### pairs

| | |
|---|---|
| wrong_fixes | 48 |
| correct_fixes | 85 |

### wrong_fixes

| | |
|---|---|
| b_only | 1 |
| a_only | 0 |
| sign_test_p | 1/2 (0.5000) |

### not_green_lit

| | |
|---|---|
| partial | b_only: 0, a_only: 0, sign_test_p: 1/1 (1.0000) |
| agent_wrong | b_only: 0, a_only: 0, sign_test_p: 1/1 (1.0000) |

### levels

| | |
|---|---|
| agent_ok | up: 0, down: 2, same: 36 |
| agent_wrong | up: 0, down: 0, same: 20 |
| gold | up: 4, down: 4, same: 39 |
| partial | up: 0, down: 0, same: 28 |

### a

| | |
|---|---|
| leftover_found | 3/48 (6%) |
| false_alarm | 8/85 (9%) |
| unreviewed | 0/85 (0%) |
| unpaired | 1 |
| set_aside | 11 |
| misses | leftover outside every function: 2, leftover's function a target, not attacked: 1, leftover's function not a target: 2, no input ran: 1, no_effect: nothing attackable left: 39 |
| reachable_misses | 2 |
| headline | correct_false_alarm: 8/85 (9%), correct_unreviewed: 0/85 (0%), agent_ok_false_alarm: 2/38 (5%), partial_caught: 19/28 (68%), partial_not_green_lit: 26/28 (93%), partial_leftover_found: 3/28 (11%), agent_wrong_caught: 6/20 (30%), agent_wrong_not_green_lit: 16/20 (80%), agent_wrong_leftover_found: 0/20 (0%) |
| gold_at_least_l2 | 12/47 (26%) |
| guard_mutants | valid_mutants: mean 5.061, median 5.0, p90 8.0, max 10.0 (n=115), gold_valid_mutants: mean 4.733, median 4.0, p90 7.0, max 9.0 (n=45), valid_mutants_not_stopped: mean 5.061, median 5.0, p90 8.0, max 10.0 (n=115), gold_valid_mutants_not_stopped: mean 4.733, median 4.0, p90 7.0, max 9.0 (n=45), one_mutant_from_flipping: 49/115 (43%), gold_one_mutant_from_flipping: 23/45 (51%) |
| no_input | 33/144 (23%) |
| seconds | mean 442.331, median 217.415, p90 847.985, max 4852.969 (n=144) |
| timeouts | 0 |
| seconds_with_timeouts | mean 442.331, median 217.415, p90 847.985, max 4852.969 (n=144) |
| blind | statuses: none, rule_would_cap_at_l1: none |
| doubt | findings: agent_ok: none, agent_wrong: none, gold: none, partial: none, pre_existing: agent_ok: none, agent_wrong: none, gold: none, partial: none, rules: any: would_leave_counterexample: agent_ok: 0/5 (0%), agent_wrong: 0/6 (0%), gold: 0/10 (0%), partial: 0/19 (0%), false_alarms_gone: 0/8 (0%), real_bug_findings_dropped: 0/10 (0%), leftovers_lost: 0/3 (0%), os_limit: would_leave_counterexample: agent_ok: 0/5 (0%), agent_wrong: 0/6 (0%), gold: 0/10 (0%), partial: 0/19 (0%), false_alarms_gone: 0/8 (0%), real_bug_findings_dropped: 0/10 (0%), leftovers_lost: 0/3 (0%), finished_object: would_leave_counterexample: agent_ok: 0/5 (0%), agent_wrong: 0/6 (0%), gold: 0/10 (0%), partial: 0/19 (0%), false_alarms_gone: 0/8 (0%), real_bug_findings_dropped: 0/10 (0%), leftovers_lost: 0/3 (0%), refused: would_leave_counterexample: agent_ok: 0/5 (0%), agent_wrong: 0/6 (0%), gold: 0/10 (0%), partial: 0/19 (0%), false_alarms_gone: 0/8 (0%), real_bug_findings_dropped: 0/10 (0%), leftovers_lost: 0/3 (0%) |
| tricky_strings | findings: agent_ok: 0/4 (0%), agent_wrong: 0/5 (0%), gold: 0/10 (0%), partial: 0/9 (0%), pre_existing: agent_ok: 0/1 (0%), agent_wrong: 0/1 (0%), gold: 0/0, partial: 0/1 (0%), labels: agent_ok: none, agent_wrong: none, gold: none, partial: none, leftovers_only_through_them: 0/3 (0%) |

### b

| | |
|---|---|
| leftover_found | 4/48 (8%) |
| false_alarm | 7/85 (8%) |
| unreviewed | 0/85 (0%) |
| unpaired | 0 |
| set_aside | 11 |
| misses | leftover outside every function: 2, leftover's function a target, not attacked: 1, leftover's function not a target: 2, no input ran: 1, no_effect: nothing attackable left: 38 |
| reachable_misses | 2 |
| headline | correct_false_alarm: 7/85 (8%), correct_unreviewed: 0/85 (0%), agent_ok_false_alarm: 2/38 (5%), partial_caught: 19/28 (68%), partial_not_green_lit: 26/28 (93%), partial_leftover_found: 4/28 (14%), agent_wrong_caught: 6/20 (30%), agent_wrong_not_green_lit: 16/20 (80%), agent_wrong_leftover_found: 0/20 (0%) |
| gold_at_least_l2 | 11/47 (23%) |
| guard_mutants | valid_mutants: mean 5.102, median 5.0, p90 8.0, max 9.0 (n=118), gold_valid_mutants: mean 5.208, median 5.0, p90 8.0, max 9.0 (n=48), valid_mutants_not_stopped: mean 7.077, median 7.0, p90 9.0, max 9.0 (n=39), gold_valid_mutants_not_stopped: mean 6.895, median 7.0, p90 9.0, max 9.0 (n=19), one_mutant_from_flipping: 87/118 (74%), gold_one_mutant_from_flipping: 35/48 (73%) |
| no_input | 31/144 (22%) |
| seconds | mean 402.984, median 190.227, p90 848.906, max 4286.046 (n=144) |
| timeouts | 1 |
| seconds_with_timeouts | mean 449.866, median 194.016, p90 882.922, max 7200.766 (n=145) |
| blind | statuses: agent_ok: fails_differently: 2, fails_on_head: 2, not_reproduced_on_base: 1, not_run: 1, reproduced: 32, agent_wrong: fails_differently: 1, fails_on_head: 7, not_reproduced_on_base: 1, not_run: 1, reproduced: 10, gold: fails_differently: 3, fails_on_head: 6, not_reproduced_on_base: 1, not_run: 4, reproduced: 33, partial: fails_differently: 7, fails_on_head: 4, not_run: 16, reproduced: 1, rule_would_cap_at_l1: agent_ok: 0/8 (0%), agent_wrong: 2/4 (50%), gold: 3/11 (27%), partial: 2/2 (100%) |
| doubt | findings: agent_ok: finished_object: 1, refused: 1, agent_wrong: os_limit: 1, refused: 1, gold: finished_object: 1, refused: 2, partial: os_limit: 1, pre_existing: agent_ok: refused: 1, agent_wrong: none, gold: none, partial: none, rules: any: would_leave_counterexample: agent_ok: 2/5 (40%), agent_wrong: 2/6 (33%), gold: 1/9 (11%), partial: 0/19 (0%), false_alarms_gone: 3/7 (43%), real_bug_findings_dropped: 0/9 (0%), leftovers_lost: 0/4 (0%), os_limit: would_leave_counterexample: agent_ok: 0/5 (0%), agent_wrong: 1/6 (17%), gold: 0/9 (0%), partial: 0/19 (0%), false_alarms_gone: 0/7 (0%), real_bug_findings_dropped: 0/9 (0%), leftovers_lost: 0/4 (0%), finished_object: would_leave_counterexample: agent_ok: 1/5 (20%), agent_wrong: 0/6 (0%), gold: 1/9 (11%), partial: 0/19 (0%), false_alarms_gone: 2/7 (29%), real_bug_findings_dropped: 0/9 (0%), leftovers_lost: 0/4 (0%), refused: would_leave_counterexample: agent_ok: 1/5 (20%), agent_wrong: 1/6 (17%), gold: 0/9 (0%), partial: 0/19 (0%), false_alarms_gone: 1/7 (14%), real_bug_findings_dropped: 0/9 (0%), leftovers_lost: 0/4 (0%) |
| tricky_strings | findings: agent_ok: 0/4 (0%), agent_wrong: 1/5 (20%), gold: 1/9 (11%), partial: 0/7 (0%), pre_existing: agent_ok: 0/1 (0%), agent_wrong: 0/1 (0%), gold: 0/0, partial: 0/1 (0%), labels: agent_ok: none, agent_wrong: false_alarm: 1, gold: false_alarm: 1, partial: none, leftovers_only_through_them: 0/4 (0%) |

### live_spend_usd

| | |
|---|---|
| a | 60.56 |
| b | 10.58 |

## dev

### pairs

| | |
|---|---|
| wrong_fixes | 48 |
| correct_fixes | 85 |

### wrong_fixes

| | |
|---|---|
| b_only | 1 |
| a_only | 0 |
| sign_test_p | 1/2 (0.5000) |

### not_green_lit

| | |
|---|---|
| partial | b_only: 0, a_only: 0, sign_test_p: 1/1 (1.0000) |
| agent_wrong | b_only: 0, a_only: 0, sign_test_p: 1/1 (1.0000) |

### levels

| | |
|---|---|
| agent_ok | up: 0, down: 2, same: 36 |
| agent_wrong | up: 0, down: 0, same: 20 |
| gold | up: 4, down: 4, same: 39 |
| partial | up: 0, down: 0, same: 28 |

### a

| | |
|---|---|
| leftover_found | 3/48 (6%) |
| false_alarm | 8/85 (9%) |
| unreviewed | 0/85 (0%) |
| unpaired | 1 |
| set_aside | 11 |
| misses | leftover outside every function: 2, leftover's function a target, not attacked: 1, leftover's function not a target: 2, no input ran: 1, no_effect: nothing attackable left: 39 |
| reachable_misses | 2 |
| headline | correct_false_alarm: 8/85 (9%), correct_unreviewed: 0/85 (0%), agent_ok_false_alarm: 2/38 (5%), partial_caught: 19/28 (68%), partial_not_green_lit: 26/28 (93%), partial_leftover_found: 3/28 (11%), agent_wrong_caught: 6/20 (30%), agent_wrong_not_green_lit: 16/20 (80%), agent_wrong_leftover_found: 0/20 (0%) |
| gold_at_least_l2 | 12/47 (26%) |
| guard_mutants | valid_mutants: mean 5.061, median 5.0, p90 8.0, max 10.0 (n=115), gold_valid_mutants: mean 4.733, median 4.0, p90 7.0, max 9.0 (n=45), valid_mutants_not_stopped: mean 5.061, median 5.0, p90 8.0, max 10.0 (n=115), gold_valid_mutants_not_stopped: mean 4.733, median 4.0, p90 7.0, max 9.0 (n=45), one_mutant_from_flipping: 49/115 (43%), gold_one_mutant_from_flipping: 23/45 (51%) |
| no_input | 33/144 (23%) |
| seconds | mean 442.331, median 217.415, p90 847.985, max 4852.969 (n=144) |
| timeouts | 0 |
| seconds_with_timeouts | mean 442.331, median 217.415, p90 847.985, max 4852.969 (n=144) |
| blind | statuses: none, rule_would_cap_at_l1: none |
| doubt | findings: agent_ok: none, agent_wrong: none, gold: none, partial: none, pre_existing: agent_ok: none, agent_wrong: none, gold: none, partial: none, rules: any: would_leave_counterexample: agent_ok: 0/5 (0%), agent_wrong: 0/6 (0%), gold: 0/10 (0%), partial: 0/19 (0%), false_alarms_gone: 0/8 (0%), real_bug_findings_dropped: 0/10 (0%), leftovers_lost: 0/3 (0%), os_limit: would_leave_counterexample: agent_ok: 0/5 (0%), agent_wrong: 0/6 (0%), gold: 0/10 (0%), partial: 0/19 (0%), false_alarms_gone: 0/8 (0%), real_bug_findings_dropped: 0/10 (0%), leftovers_lost: 0/3 (0%), finished_object: would_leave_counterexample: agent_ok: 0/5 (0%), agent_wrong: 0/6 (0%), gold: 0/10 (0%), partial: 0/19 (0%), false_alarms_gone: 0/8 (0%), real_bug_findings_dropped: 0/10 (0%), leftovers_lost: 0/3 (0%), refused: would_leave_counterexample: agent_ok: 0/5 (0%), agent_wrong: 0/6 (0%), gold: 0/10 (0%), partial: 0/19 (0%), false_alarms_gone: 0/8 (0%), real_bug_findings_dropped: 0/10 (0%), leftovers_lost: 0/3 (0%) |
| tricky_strings | findings: agent_ok: 0/4 (0%), agent_wrong: 0/5 (0%), gold: 0/10 (0%), partial: 0/9 (0%), pre_existing: agent_ok: 0/1 (0%), agent_wrong: 0/1 (0%), gold: 0/0, partial: 0/1 (0%), labels: agent_ok: none, agent_wrong: none, gold: none, partial: none, leftovers_only_through_them: 0/3 (0%) |

### b

| | |
|---|---|
| leftover_found | 4/48 (8%) |
| false_alarm | 7/85 (8%) |
| unreviewed | 0/85 (0%) |
| unpaired | 0 |
| set_aside | 11 |
| misses | leftover outside every function: 2, leftover's function a target, not attacked: 1, leftover's function not a target: 2, no input ran: 1, no_effect: nothing attackable left: 38 |
| reachable_misses | 2 |
| headline | correct_false_alarm: 7/85 (8%), correct_unreviewed: 0/85 (0%), agent_ok_false_alarm: 2/38 (5%), partial_caught: 19/28 (68%), partial_not_green_lit: 26/28 (93%), partial_leftover_found: 4/28 (14%), agent_wrong_caught: 6/20 (30%), agent_wrong_not_green_lit: 16/20 (80%), agent_wrong_leftover_found: 0/20 (0%) |
| gold_at_least_l2 | 11/47 (23%) |
| guard_mutants | valid_mutants: mean 5.102, median 5.0, p90 8.0, max 9.0 (n=118), gold_valid_mutants: mean 5.208, median 5.0, p90 8.0, max 9.0 (n=48), valid_mutants_not_stopped: mean 7.077, median 7.0, p90 9.0, max 9.0 (n=39), gold_valid_mutants_not_stopped: mean 6.895, median 7.0, p90 9.0, max 9.0 (n=19), one_mutant_from_flipping: 87/118 (74%), gold_one_mutant_from_flipping: 35/48 (73%) |
| no_input | 31/144 (22%) |
| seconds | mean 402.984, median 190.227, p90 848.906, max 4286.046 (n=144) |
| timeouts | 1 |
| seconds_with_timeouts | mean 449.866, median 194.016, p90 882.922, max 7200.766 (n=145) |
| blind | statuses: agent_ok: fails_differently: 2, fails_on_head: 2, not_reproduced_on_base: 1, not_run: 1, reproduced: 32, agent_wrong: fails_differently: 1, fails_on_head: 7, not_reproduced_on_base: 1, not_run: 1, reproduced: 10, gold: fails_differently: 3, fails_on_head: 6, not_reproduced_on_base: 1, not_run: 4, reproduced: 33, partial: fails_differently: 7, fails_on_head: 4, not_run: 16, reproduced: 1, rule_would_cap_at_l1: agent_ok: 0/8 (0%), agent_wrong: 2/4 (50%), gold: 3/11 (27%), partial: 2/2 (100%) |
| doubt | findings: agent_ok: finished_object: 1, refused: 1, agent_wrong: os_limit: 1, refused: 1, gold: finished_object: 1, refused: 2, partial: os_limit: 1, pre_existing: agent_ok: refused: 1, agent_wrong: none, gold: none, partial: none, rules: any: would_leave_counterexample: agent_ok: 2/5 (40%), agent_wrong: 2/6 (33%), gold: 1/9 (11%), partial: 0/19 (0%), false_alarms_gone: 3/7 (43%), real_bug_findings_dropped: 0/9 (0%), leftovers_lost: 0/4 (0%), os_limit: would_leave_counterexample: agent_ok: 0/5 (0%), agent_wrong: 1/6 (17%), gold: 0/9 (0%), partial: 0/19 (0%), false_alarms_gone: 0/7 (0%), real_bug_findings_dropped: 0/9 (0%), leftovers_lost: 0/4 (0%), finished_object: would_leave_counterexample: agent_ok: 1/5 (20%), agent_wrong: 0/6 (0%), gold: 1/9 (11%), partial: 0/19 (0%), false_alarms_gone: 2/7 (29%), real_bug_findings_dropped: 0/9 (0%), leftovers_lost: 0/4 (0%), refused: would_leave_counterexample: agent_ok: 1/5 (20%), agent_wrong: 1/6 (17%), gold: 0/9 (0%), partial: 0/19 (0%), false_alarms_gone: 1/7 (14%), real_bug_findings_dropped: 0/9 (0%), leftovers_lost: 0/4 (0%) |
| tricky_strings | findings: agent_ok: 0/4 (0%), agent_wrong: 1/5 (20%), gold: 1/9 (11%), partial: 0/7 (0%), pre_existing: agent_ok: 0/1 (0%), agent_wrong: 0/1 (0%), gold: 0/0, partial: 0/1 (0%), labels: agent_ok: none, agent_wrong: false_alarm: 1, gold: false_alarm: 1, partial: none, leftovers_only_through_them: 0/4 (0%) |

