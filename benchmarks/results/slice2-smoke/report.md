# Tracefix benchmark: slice2

Every number comes from a run, a receipt, a prepare record or the developer's label
(scripts/bench/report.py). Rates show n/N. Headline sections read each task's first
repeat. Set aside: COUNTEREXAMPLEs whose only causes are regressions in test files
the PR's own test patch changed; the gold, partial and separation sections leave
them out.

Agent fixes: OpenHands patches our own hidden-test runs show wrong
(agent_wrong) or right (agent_ok). Correct fixes are gold and agent_ok;
differs_from_gold: an agent_ok finding that passes on gold.

## Funnel

| | |
|---|---|
| cases | 150 |
| prepared | 15 |
| excluded | base_suite_cannot_run: 4, fail_to_pass_passes_on_base: 1 |
| ready | 10 |
| ready_with_partial | 6 |
| agents | agent_ok: hidden_tests_pass: 8, agent_wrong: hidden_tests_pass (not run): 1, agent_wrong: no_effect: 5, agent_wrong: partial: 1, agent_wrong: unsettled (not run): 1 |
| isolation_at_prepare | strict: 10 |
| setup_commit_needed | 5 |
| runs | gold: receipt: 5, partial: receipt: 3, agent_wrong: receipt: 2, agent_ok: receipt: 4 |
| receipt_status | ok: 14 |
| exit_codes | 0: 14 |
| isolation | strict: 14 |
| stage_errors | none |

## Splits

| | |
|---|---|
| dev | 5 |

## Set aside

| | |
|---|---|
| gold | 1/5 (20%) |
| partial | 1/3 (33%) |
| agent_wrong | 0/2 (0%) |
| agent_ok | 0/4 (0%) |
| tasks | python-cmd2__cmd2-115 |

## Gold

| | |
|---|---|
| levels | COUNTEREXAMPLE: 0, L0: 0, L1: 4, L2: 0, L3: 0, L4: 0 |
| counterexample | 0/4 (0%) |
| false_alarm | 0/4 (0%) |
| real_bug_in_gold | 0/4 (0%) |
| false_alarm_proposed | 0/4 (0%) |
| unreviewed | 0/4 (0%) |
| at_least_l2 | 0/4 (0%) |
| at_least_l3 | 0/4 (0%) |
| l4 | 0/4 (0%) |

## Partial

| | |
|---|---|
| levels | COUNTEREXAMPLE: 1, L0: 1, L1: 0, L2: 0, L3: 0, L4: 0 |
| detection | 1/2 (50%) |
| not_green_lit | 2/2 (100%) |
| false_pass_l2 | 0/2 (0%) |
| false_pass_l3 | 0/2 (0%) |
| leftover_found | 1/2 (50%) |
| real_bug_by_label | 0/2 (0%) |
| unreviewed | 0/2 (0%) |

## Separation

| | |
|---|---|
| gold_above | 2/2 (100%) |
| same | 0/2 (0%) |
| gold_below | 0/2 (0%) |

## Agent wrong

| | |
|---|---|
| levels | COUNTEREXAMPLE: 1, L0: 0, L1: 1, L2: 0, L3: 0, L4: 0 |
| detection | 1/2 (50%) |
| not_green_lit | 2/2 (100%) |
| false_pass_l2 | 0/2 (0%) |
| false_pass_l3 | 0/2 (0%) |
| leftover_found | 0/2 (0%) |
| real_bug_by_label | 0/2 (0%) |
| unreviewed | 1/2 (50%) |

## Agent ok

| | |
|---|---|
| levels | COUNTEREXAMPLE: 0, L0: 0, L1: 3, L2: 1, L3: 0, L4: 0 |
| counterexample | 0/4 (0%) |
| false_alarm | 0/4 (0%) |
| real_bug_in_gold | 0/4 (0%) |
| false_alarm_proposed | 0/4 (0%) |
| unreviewed | 0/4 (0%) |
| at_least_l2 | 1/4 (25%) |
| at_least_l3 | 0/4 (0%) |
| l4 | 0/4 (0%) |
| differs_from_gold | 0/4 (0%) |

## Correct fixes

| | |
|---|---|
| levels | COUNTEREXAMPLE: 0, L0: 0, L1: 7, L2: 1, L3: 0, L4: 0 |
| counterexample | 0/8 (0%) |
| false_alarm | 0/8 (0%) |
| real_bug_in_gold | 0/8 (0%) |
| false_alarm_proposed | 0/8 (0%) |
| unreviewed | 0/8 (0%) |
| at_least_l2 | 1/8 (12%) |
| at_least_l3 | 0/8 (0%) |
| l4 | 0/8 (0%) |

## Separation agent wrong

| | |
|---|---|
| gold_above | 1/2 (50%) |
| same | 1/2 (50%) |
| gold_below | 0/2 (0%) |

## By split

### dev

| | |
|---|---|
| correct_false_alarm | 0/8 (0%) |
| correct_unreviewed | 0/8 (0%) |
| partial_caught | 1/2 (50%) |
| partial_not_green_lit | 2/2 (100%) |
| partial_leftover_found | 1/2 (50%) |
| agent_wrong_caught | 1/2 (50%) |
| agent_wrong_not_green_lit | 2/2 (100%) |
| agent_wrong_leftover_found | 0/2 (0%) |

### held_out

| | |
|---|---|
| correct_false_alarm | 0/0 |
| correct_unreviewed | 0/0 |
| partial_caught | 0/0 |
| partial_not_green_lit | 0/0 |
| partial_leftover_found | 0/0 |
| agent_wrong_caught | 0/0 |
| agent_wrong_not_green_lit | 0/0 |
| agent_wrong_leftover_found | 0/0 |

## By python

### 3.9/3.10

| | |
|---|---|
| correct_false_alarm | 0/8 (0%) |
| correct_unreviewed | 0/8 (0%) |
| partial_caught | 1/2 (50%) |
| partial_not_green_lit | 2/2 (100%) |
| partial_leftover_found | 1/2 (50%) |
| agent_wrong_caught | 1/2 (50%) |
| agent_wrong_not_green_lit | 2/2 (100%) |
| agent_wrong_leftover_found | 0/2 (0%) |

### 3.11+

| | |
|---|---|
| correct_false_alarm | 0/0 |
| correct_unreviewed | 0/0 |
| partial_caught | 0/0 |
| partial_not_green_lit | 0/0 |
| partial_leftover_found | 0/0 |
| agent_wrong_caught | 0/0 |
| agent_wrong_not_green_lit | 0/0 |
| agent_wrong_leftover_found | 0/0 |

## Reproducer

| | |
|---|---|
| statuses | reproduced: 5 |
| fail_to_pass | 5/5 (100%) |
| fix_does_not_fix | 0/5 (0%) |

## Guard

### gold

| | |
|---|---|
| statuses | inconclusive: 1, not_guarded: 4 |
| guarded | 0/5 (0%) |
| kill_rate | mean 0.547, median 0.667, p90 0.75, max 0.75 (n=5) |
| crash_only_kills | 0/12 (0%) |

### partial

| | |
|---|---|
| statuses | not_guarded: 2, skipped: 1 |
| guarded | 0/3 (0%) |
| kill_rate | mean 0.55, median 0.55, p90 0.6, max 0.6 (n=2) |
| crash_only_kills | 0/6 (0%) |

### agent_wrong

| | |
|---|---|
| statuses | not_guarded: 2 |
| guarded | 0/2 (0%) |
| kill_rate | mean 0.714, median 0.714, p90 0.714, max 0.714 (n=2) |
| crash_only_kills | 0/10 (0%) |

### agent_ok

| | |
|---|---|
| statuses | guarded: 1, not_guarded: 3 |
| guarded | 1/4 (25%) |
| kill_rate | mean 0.657, median 0.732, p90 0.833, max 0.833 (n=4) |
| crash_only_kills | 0/14 (0%) |

## Break my fix

### gold

| | |
|---|---|
| statuses | inconclusive: 3, none_found: 2 |
| skip_reasons | Break My Fix can't run in the project's Python: the project's Python has Hypothesis N.N, older than N, the oldest Tracefix is tested with: upgrade it there (pyt: 2, the attack ran no input: 1 |
| targets | 5 |
| inputs_per_target | 262.0 |
| pre_existing | 0 |
| first_l4_blocker | none |

### partial

| | |
|---|---|
| statuses | found: 1, inconclusive: 1, none_found: 1 |
| skip_reasons | Break My Fix can't run in the project's Python: the project's Python has Hypothesis N.N, older than N, the oldest Tracefix is tested with: upgrade it there (pyt: 1 |
| targets | 3 |
| inputs_per_target | 140.7 |
| pre_existing | 0 |
| first_l4_blocker | none |

### agent_wrong

| | |
|---|---|
| statuses | found: 1, inconclusive: 1 |
| skip_reasons | the attack ran no input: 1 |
| targets | 2 |
| inputs_per_target | 193.0 |
| pre_existing | 0 |
| first_l4_blocker | none |

### agent_ok

| | |
|---|---|
| statuses | inconclusive: 3, none_found: 1 |
| skip_reasons | Break My Fix can't run in the project's Python: the project's Python has Hypothesis N.N, older than N, the oldest Tracefix is tested with: upgrade it there (pyt: 2, the attack ran no input: 1 |
| targets | 3 |
| inputs_per_target | 135.7 |
| pre_existing | 0 |
| first_l4_blocker | none |

## Behaviour diff

### gold

| | |
|---|---|
| statuses | inconclusive: 5 |
| l3_gate_open | 0/5 (0%) |
| first_l3_blocker | none |

### partial

| | |
|---|---|
| statuses | inconclusive: 3 |
| l3_gate_open | 0/3 (0%) |
| first_l3_blocker | none |

### agent_wrong

| | |
|---|---|
| statuses | inconclusive: 2 |
| l3_gate_open | 0/2 (0%) |
| first_l3_blocker | none |

### agent_ok

| | |
|---|---|
| statuses | inconclusive: 4 |
| l3_gate_open | 0/4 (0%) |
| first_l3_blocker | <name>: before the fix it was not a method defined in class AutoSummClassDocumenter: 1 |

## Report only

### gold

| | |
|---|---|
| fix_line_coverage | repro: 8/13 (62%) |
| regressions | found: 1, none_found: 3, skipped: 1 |

### partial

| | |
|---|---|
| fix_line_coverage | repro: 5/8 (62%) |
| regressions | found: 2, none_found: 1 |

### agent_wrong

| | |
|---|---|
| fix_line_coverage | pr_test: 0/11 (0%), repro: 18/20 (90%) |
| regressions | none_found: 2 |

### agent_ok

| | |
|---|---|
| fix_line_coverage | pr_test: 5/96 (5%), repro: 12/105 (11%) |
| regressions | none_found: 3, skipped: 1 |

## Cost and time

| | |
|---|---|
| usd_per_run | mean 0.163, median 0.144, p90 0.35, max 0.379 (n=14) |
| usd_unknown | 0 |
| usd_spent_live | 2.28 |
| usd_spent_known | 2.28 |
| live_attempts_cost_unknown | 0 |
| calls | mean 5.143, median 5.0, p90 7.0, max 7.0 (n=14) |
| tokens | mean 32164.071, median 30807.5, p90 55699.0, max 67088.0 (n=14) |
| seconds_per_run | mean 233.992, median 151.219, p90 750.313, max 796.938 (n=14) |
| seconds_per_stage | behaviour_diff: mean 3.532, median 2.0, p90 10.24, max 18.63 (n=14), break_my_fix: mean 35.291, median 30.755, p90 100.11, max 110.09 (n=14), environment: mean 9.92, median 4.58, p90 41.51, max 41.66 (n=14), fix_line_coverage: mean 1.864, median 1.935, p90 4.39, max 5.2 (n=14), guard: mean 122.82, median 62.885, p90 404.64, max 450.29 (n=14), import_check: mean 3.649, median 3.665, p90 4.3, max 4.31 (n=14), integrity: mean 0.023, median 0.015, p90 0.04, max 0.09 (n=14), regressions: mean 28.667, median 4.555, p90 169.78, max 169.92 (n=14), reproduce: mean 23.496, median 19.635, p90 33.53, max 59.63 (n=14) |

## Stability

| | |
|---|---|
| groups | 0 |
| level_flips | 0/0 |
| counterexample_flips | 0/0 |
| guard_flips | 0/0 |
| finding_flips | 0/0 |

## Findings

| task | run | # | call | outcome | replay on gold | label |
|---|---|---|---|---|---|---|
| kpetremann__mqtt-exporter-37 | agent_wrong-r1 | 1 | _normalize_name_in_topic_msg(topic='shellies/living-room-3em/emeter/0/power', payload='10') | returns ('shellies/living-room-3em', {'power': '10'}) | still_fails | unreviewed |
| kpetremann__mqtt-exporter-37 | v1-r1 | 1 | _normalize_name_in_topic_msg(topic='shellies/power', payload='1') | raises AttributeError: module 'mqtt_exporter.settings' has no attribute 'KEEP_FULL_TOPIC' | fixed | unreviewed |
| python-cmd2__cmd2-115 | gold-r1 | - | (the run's level, not a finding) | regression: tests/test_cmd2.py::test_base_help passed before the fix and fails after it (and 10 more) | - | unreviewed |
