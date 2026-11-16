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
| prepared | 111 |
| excluded | base_suite_cannot_run: 45, base_suite_too_slow: 5, fail_to_pass_passes_on_base: 1, hidden_tests_fail_on_gold: 4 |
| ready | 56 |
| ready_with_partial | 32 |
| agents | agent_ok: does_not_apply (not run): 2, agent_ok: hidden_tests_pass: 40, agent_wrong: does_not_apply (not run): 1, agent_wrong: hidden_tests_pass (not run): 1, agent_wrong: no_effect: 21, agent_wrong: partial: 3, agent_wrong: unsettled (not run): 1 |
| isolation_at_prepare | strict: 56 |
| setup_commit_needed | 21 |
| runs | gold: receipt: 54, partial: receipt: 30, agent_wrong: receipt: 22, agent_ok: receipt: 39 |
| receipt_status | ok: 145 |
| exit_codes | 0: 145 |
| isolation | strict: 145 |
| stage_errors | none |

## Splits

| | |
|---|---|
| dev | 54 |

## Set aside

| | |
|---|---|
| gold | 7/54 (13%) |
| partial | 2/30 (7%) |
| agent_wrong | 2/22 (9%) |
| agent_ok | 1/39 (3%) |
| tasks | NREL__hescore-hpxml-149, aburrell__ocbpy-144, disqus__python-phabricator-64, encode__httpx-653, nipreps__nibabies-395, python-cmd2__cmd2-115, scipp__scippnexus-106 |

## Gold

| | |
|---|---|
| levels | COUNTEREXAMPLE: 10, L0: 3, L1: 22, L2: 12, L3: 0, L4: 0 |
| counterexample | 10/47 (21%) |
| false_alarm | 6/47 (13%) |
| real_bug_in_gold | 3/47 (6%) |
| false_alarm_proposed | 0/47 (0%) |
| unreviewed | 0/47 (0%) |
| at_least_l2 | 12/47 (26%) |
| at_least_l3 | 0/47 (0%) |
| l4 | 0/47 (0%) |

## Partial

| | |
|---|---|
| levels | COUNTEREXAMPLE: 19, L0: 4, L1: 3, L2: 2, L3: 0, L4: 0 |
| detection | 19/28 (68%) |
| not_green_lit | 26/28 (93%) |
| false_pass_l2 | 2/28 (7%) |
| false_pass_l3 | 0/28 (0%) |
| leftover_found | 3/28 (11%) |
| real_bug_by_label | 2/28 (7%) |
| unreviewed | 0/28 (0%) |

## Separation

| | |
|---|---|
| gold_above | 16/24 (67%) |
| same | 5/24 (21%) |
| gold_below | 3/24 (12%) |

## Agent wrong

| | |
|---|---|
| levels | COUNTEREXAMPLE: 6, L0: 0, L1: 10, L2: 4, L3: 0, L4: 0 |
| detection | 6/20 (30%) |
| not_green_lit | 16/20 (80%) |
| false_pass_l2 | 4/20 (20%) |
| false_pass_l3 | 0/20 (0%) |
| leftover_found | 0/20 (0%) |
| real_bug_by_label | 2/20 (10%) |
| unreviewed | 0/20 (0%) |

## Agent ok

| | |
|---|---|
| levels | COUNTEREXAMPLE: 5, L0: 1, L1: 22, L2: 10, L3: 0, L4: 0 |
| counterexample | 5/38 (13%) |
| false_alarm | 2/38 (5%) |
| real_bug_in_gold | 3/38 (8%) |
| false_alarm_proposed | 0/38 (0%) |
| unreviewed | 0/38 (0%) |
| at_least_l2 | 10/38 (26%) |
| at_least_l3 | 0/38 (0%) |
| l4 | 0/38 (0%) |
| differs_from_gold | 0/38 (0%) |

## Correct fixes

| | |
|---|---|
| levels | COUNTEREXAMPLE: 15, L0: 4, L1: 44, L2: 22, L3: 0, L4: 0 |
| counterexample | 15/85 (18%) |
| false_alarm | 8/85 (9%) |
| real_bug_in_gold | 6/85 (7%) |
| false_alarm_proposed | 0/85 (0%) |
| unreviewed | 0/85 (0%) |
| at_least_l2 | 22/85 (26%) |
| at_least_l3 | 0/85 (0%) |
| l4 | 0/85 (0%) |

## Separation agent wrong

| | |
|---|---|
| gold_above | 3/17 (18%) |
| same | 8/17 (47%) |
| gold_below | 6/17 (35%) |

## By split

### dev

| | |
|---|---|
| correct_false_alarm | 8/85 (9%) |
| correct_unreviewed | 0/85 (0%) |
| agent_ok_false_alarm | 2/38 (5%) |
| partial_caught | 19/28 (68%) |
| partial_not_green_lit | 26/28 (93%) |
| partial_leftover_found | 3/28 (11%) |
| agent_wrong_caught | 6/20 (30%) |
| agent_wrong_not_green_lit | 16/20 (80%) |
| agent_wrong_leftover_found | 0/20 (0%) |

### held_out

| | |
|---|---|
| correct_false_alarm | 0/0 |
| correct_unreviewed | 0/0 |
| agent_ok_false_alarm | 0/0 |
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
| correct_false_alarm | 8/83 (10%) |
| correct_unreviewed | 0/83 (0%) |
| agent_ok_false_alarm | 2/37 (5%) |
| partial_caught | 19/28 (68%) |
| partial_not_green_lit | 26/28 (93%) |
| partial_leftover_found | 3/28 (11%) |
| agent_wrong_caught | 6/20 (30%) |
| agent_wrong_not_green_lit | 16/20 (80%) |
| agent_wrong_leftover_found | 0/20 (0%) |

### 3.11+

| | |
|---|---|
| correct_false_alarm | 0/2 (0%) |
| correct_unreviewed | 0/2 (0%) |
| agent_ok_false_alarm | 0/1 (0%) |
| partial_caught | 0/0 |
| partial_not_green_lit | 0/0 |
| partial_leftover_found | 0/0 |
| agent_wrong_caught | 0/0 |
| agent_wrong_not_green_lit | 0/0 |
| agent_wrong_leftover_found | 0/0 |

## Reproducer

| | |
|---|---|
| statuses | fix_does_not_fix: 2, not_reproduced: 3, reproduced: 49 |
| fail_to_pass | 49/54 (91%) |
| fix_does_not_fix | 2/54 (4%) |

## Guard

### gold

| | |
|---|---|
| statuses | guarded: 14, inconclusive: 3, not_guarded: 32, skipped: 5 |
| guarded | 14/54 (26%) |
| kill_rate | mean 0.595, median 0.667, p90 1.0, max 1.0 (n=49) |
| crash_only_kills | 2/123 (2%) |

### partial

| | |
|---|---|
| statuses | guarded: 3, inconclusive: 1, not_guarded: 10, skipped: 16 |
| guarded | 3/30 (10%) |
| kill_rate | mean 0.552, median 0.55, p90 1.0, max 1.0 (n=14) |
| crash_only_kills | 1/36 (3%) |

### agent_wrong

| | |
|---|---|
| statuses | guarded: 6, inconclusive: 1, not_guarded: 14, skipped: 1 |
| guarded | 6/22 (27%) |
| kill_rate | mean 0.474, median 0.4, p90 0.875, max 1.0 (n=21) |
| crash_only_kills | 0/58 (0%) |

### agent_ok

| | |
|---|---|
| statuses | guarded: 10, inconclusive: 1, not_guarded: 27, skipped: 1 |
| guarded | 10/39 (26%) |
| kill_rate | mean 0.636, median 0.633, p90 1.0, max 1.0 (n=38) |
| crash_only_kills | 0/114 (0%) |

## Break my fix

### gold

| | |
|---|---|
| statuses | found: 8, inconclusive: 18, none_found: 17, skipped: 11 |
| skip_reasons | no candidate checked counts, but N could not be checked: 1, no target could be attacked: asdf/asdf.py could not be imported as a module here (tried asdf.asdf, asdf): 1, no target could be attacked: its objects' code can't run here: DataFrame is not the module's own name or plain data: 1, no target could be attacked: its objects' code can't run here: Frequency is not the module's own name or plain data: 1, the attack on ContextRegistry.disable_contexts did not finish: 1, the attack on DualBoundary.set_good_ind did not finish: 1, the attack ran no input: 12, the fix changes no function Break My Fix can call: 4, the fix changes no function Break My Fix can call (Command.handle.display_properties: a nested function: it can't be imported, not attacked yet; Command.handle.: 1, the fix changes no function Break My Fix can call (Faker.__deepcopy__: a special method (such as __init__ or __eq__): not called yet; Faker.__getattr__: a speci: 1, the fix changes no function Break My Fix can call (PackageURL.__hash__: a special method (such as __init__ or __eq__): not called yet): 1, the fix changes no function Break My Fix can call (Query.from_string.process_string: a nested function: it can't be imported, not attacked yet; WildcardRegex.__: 1, the fix changes no function Break My Fix can call (URL.__init__: a special method (such as __init__ or __eq__): not called yet): 1, the fix changes no function Break My Fix can call (get_pypi_packages: it takes no parameters to vary): 1, the fix changes no function Break My Fix can call (main: it takes no parameters to vary; ReportseffParameters.__init__: a special method (such as __init__ or __: 1 |
| targets | 104 |
| inputs_per_target | 55.0 |
| pre_existing | 0 |
| first_l4_blocker | none |

### partial

| | |
|---|---|
| statuses | found: 7, inconclusive: 6, none_found: 7, skipped: 10 |
| skip_reasons | no candidate checked counts, but N could not be checked: 1, no target could be attacked: its objects' code can't run here: DataFrame is not the module's own name or plain data: 1, the attack ran no input: 4, the fix changes no function Break My Fix can call: 7, the fix changes no function Break My Fix can call (Faker.__deepcopy__: a special method (such as __init__ or __eq__): not called yet; Faker.__getattr__: a speci: 1, the fix changes no function Break My Fix can call (ReportseffParameters.__init__: a special method (such as __init__ or __eq__): not called yet): 1, the fix changes no function Break My Fix can call (WildcardRegex.__init__: a special method (such as __init__ or __eq__): not called yet): 1 |
| targets | 60 |
| inputs_per_target | 54.6 |
| pre_existing | 1 |
| first_l4_blocker | none |

### agent_wrong

| | |
|---|---|
| statuses | found: 4, inconclusive: 9, none_found: 5, skipped: 4 |
| skip_reasons | no target could be attacked: TypeError: unhashable type: 'list': 1, the attack ran no input: 8, the fix changes no function Break My Fix can call: 1, the fix changes no function Break My Fix can call (Command.handle.display_properties: a nested function: it can't be imported, not attacked yet): 1, the fix changes no function Break My Fix can call (debug_dual_boundary_pairing: it takes no parameters to vary; debug_specific_timestamp: it takes no parameters: 1, the fix changes no function Break My Fix can call (demonstrate_click_behavior: it takes no parameters to vary; test_color_parameter_default: it takes no paramet: 1 |
| targets | 31 |
| inputs_per_target | 55.9 |
| pre_existing | 1 |
| first_l4_blocker | none |

### agent_ok

| | |
|---|---|
| statuses | found: 4, inconclusive: 14, none_found: 14, skipped: 7 |
| skip_reasons | every property was contradicted or could not run: 1, no target could be attacked: TypeError: unhashable type: 'list': 1, no target could be attacked: asdf/asdf.py could not be imported as a module here (tried asdf.asdf, asdf): 1, no target could be attacked: its objects' code can't run here: DataFrame is not the module's own name or plain data: 1, the attack on ContextRegistry.disable_contexts did not finish: 1, the attack ran no input: 9, the fix changes no function Break My Fix can call: 2, the fix changes no function Break My Fix can call (PackageURL.__hash__: a special method (such as __init__ or __eq__): not called yet): 1, the fix changes no function Break My Fix can call (URL.__init__: a special method (such as __init__ or __eq__): not called yet; test_params_merge: it takes no p: 1, the fix changes no function Break My Fix can call (cleanup_dummy_files: it takes no parameters to vary; test_freesurfer_algorithm: it takes no parameters to var: 1, the fix changes no function Break My Fix can call (get_pypi_packages: it takes no parameters to vary): 1, the fix changes no function Break My Fix can call (main: it takes no parameters to vary; ReportseffParameters.__init__: a special method (such as __init__ or __: 1 |
| targets | 60 |
| inputs_per_target | 116.3 |
| pre_existing | 1 |
| first_l4_blocker | none |

## Behaviour diff

### gold

| | |
|---|---|
| statuses | compared: 7, inconclusive: 31, partial: 7, skipped: 9 |
| l3_gate_open | 2/54 (4%) |
| first_l3_blocker | <name>: module-level code that computes a value changed (line N); what uses it is not compared: 3, <name>: not compared (a special method (such as __init__ or __eq__): not called yet): 1, <name>: the comparison did not finish: 7, N input(s) changed from 'raises IndexError' to 'returns tuple' and nothing explains it (not the reproduction test, the issue or a docstring example): 1 |

### partial

| | |
|---|---|
| statuses | compared: 1, inconclusive: 13, partial: 6, skipped: 10 |
| l3_gate_open | 0/30 (0%) |
| first_l3_blocker | <name>: not compared (a special method (such as __init__ or __eq__): not called yet): 1, <name>: the comparison did not finish: 1 |

### agent_wrong

| | |
|---|---|
| statuses | compared: 1, inconclusive: 10, partial: 2, skipped: 9 |
| l3_gate_open | 0/22 (0%) |
| first_l3_blocker | <name>: before the fix it was not a method defined in class UpdateCommand: 1, <name>: module-level code that computes a value changed (line N, N, N, N, N); what uses it is not compared: 1, <name>: no input could be compared: 1, process: the comparison did not finish: 1 |

### agent_ok

| | |
|---|---|
| statuses | compared: 5, inconclusive: 24, partial: 3, skipped: 7 |
| l3_gate_open | 2/39 (5%) |
| first_l3_blocker | <name>: before the fix it was not a method defined in class AutoSummClassDocumenter: 1, <name>: not compared (a special method (such as __init__ or __eq__): not called yet): 1, <name>: not compared (past the cap of N functions): 1, <name>: the comparison did not finish: 6, N input(s) changed from 'raises IndexError' to 'returns tuple' and nothing explains it (not the reproduction test, the issue or a docstring example): 1 |

## Report only

### gold

| | |
|---|---|
| fix_line_coverage | repro: 387/611 (63%) |
| regressions | found: 10, none_found: 41, skipped: 3 |

### partial

| | |
|---|---|
| fix_line_coverage | repro: 105/243 (43%) |
| regressions | found: 12, none_found: 17, skipped: 1 |

### agent_wrong

| | |
|---|---|
| fix_line_coverage | pr_test: 112/1535 (7%), repro: 308/1451 (21%) |
| regressions | found: 3, none_found: 17, skipped: 2 |

### agent_ok

| | |
|---|---|
| fix_line_coverage | pr_test: 109/958 (11%), repro: 216/1211 (18%) |
| regressions | found: 2, inconclusive: 1, none_found: 33, skipped: 3 |

## Cost and time

| | |
|---|---|
| usd_per_run | mean 0.231, median 0.208, p90 0.446, max 0.724 (n=145) |
| usd_unknown | 0 |
| usd_spent_live | 60.56 |
| usd_spent_known | 33.56 |
| live_attempts_cost_unknown | 9 |
| calls | mean 5.807, median 6.0, p90 8.0, max 9.0 (n=145) |
| tokens | mean 46981.0, median 40917.0, p90 91858.0, max 131332.0 (n=145) |
| seconds_per_run | mean 475.239, median 219.25, p90 989.953, max 5214.063 (n=145) |
| seconds_per_stage | behaviour_diff: mean 19.679, median 3.83, p90 27.88, max 984.16 (n=145), break_my_fix: mean 62.363, median 47.7, p90 112.81, max 953.68 (n=145), environment: mean 21.361, median 8.12, p90 67.65, max 148.94 (n=145), fix_line_coverage: mean 3.942, median 2.67, p90 8.49, max 49.86 (n=145), guard: mean 270.112, median 90.45, p90 586.58, max 4658.48 (n=145), import_check: mean 5.294, median 4.33, p90 7.3, max 24.51 (n=145), integrity: mean 0.127, median 0.02, p90 0.09, max 6.99 (n=145), regressions: mean 51.523, median 14.03, p90 110.98, max 591.51 (n=145), reproduce: mean 36.344, median 26.21, p90 66.2, max 198.39 (n=145) |

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
| Diaoul__babelfish-50 | agent_wrong-r1 | 1 | fromietf(ietf='00') | raises LanguageReverseError: '00' | still_fails | false_alarm (developer) |
| Diaoul__babelfish-50 | gold-r1 | - | (the run's level, not a finding) | regression: tests/test_country.py::test_hash_eq passed before the fix and fails after it (and 1 more) | - | false_alarm (developer) |
| Diaoul__babelfish-50 | gold-r1 | 1 | fromietf(ietf='__') | raises LanguageReverseError: '__' | - | false_alarm (developer) |
| Diaoul__babelfish-50 | gold-r1 | 2 | fromietf(ietf='script') | raises ValueError: 'script' is not a valid language | - | false_alarm (developer) |
| Lucas-C__pre-commit-hooks-98 | gold-r1 | 1 | try_update_year_range(src_file_content=['/* Copyright (c) 2012-2023 Dummy             */\n', '/*********************************************/\n', '/* @copyright Copyright (c) 2012-2023 Dummy  */\n', '<?php\n'], src_filepath='file.php', license_header_index=10, license_length=3) | raises IndexError: list index out of range | - | false_alarm (developer) |
| Lucas-C__pre-commit-hooks-98 | gold-r1 | 2 | try_update_year_range(src_file_content=['/* Copyright (c) 2012-2023 Dummy             */\n', '/*********************************************/\n', '/* @copyright Copyright (c) 2012-2023 Dummy  */\n', '<?php\n'], src_filepath='file.php', license_header_index=0, license_length=-1) | returns (['/* Copyright (c) 2012-2023 Dummy             */\n', '/*********************************************/\n', '/* @copyright Copyright (c) 2012-2023 Dummy  */\n', '<?php\n'], False) | - | false_alarm (developer) |
| NREL__hescore-hpxml-149 | agent_ok-r1 | - | (the run's level, not a finding) | regression: tests/test_translation.py::TestOtherHouses.test_external_id_passthru passed before the fix and fails after it (and 1 more) | - | false_alarm (developer) |
| NREL__hescore-hpxml-149 | gold-r1 | - | (the run's level, not a finding) | regression: tests/test_translation.py::TestOtherHouses.test_external_id_passthru passed before the fix and fails after it (and 1 more) | - | false_alarm (developer) |
| abhinavsingh__proxy.py-137 | gold-r1 | - | (the run's level, not a finding) | the fix does not fix the bug: the reproduction test fails the same way before and after it | - | real_bug (developer) |
| abhinavsingh__proxy.py-137 | gold-r1 | 1 | parse(self='HttpParser(parser_type=1)', raw=b'\r\n') | raises IndexError: list index out of range | - | real_bug (developer) |
| abhinavsingh__proxy.py-137 | v1-r1 | 1 | parse(self='HttpParser(parser_type=1)', raw=b'\r\n') | raises IndexError: list index out of range | still_fails | real_bug (developer) |
| aburrell__ocbpy-144 | gold-r1 | - | (the run's level, not a finding) | regression: ocbpy/tests/test_boundary_dual.py::TestDualBoundaryMethodsGeneral.test_custom_ind_selection passed before the fix and fails after it (and 1 more) | - | false_alarm (developer) |
| aburrell__ocbpy-144 | v0-r1 | 1 | set_good_ind(self='DualBoundary(stime=datetime.datetime(2002, 10, 30), etime=datetime.datetime(2002, 11, 1), hemisphere=1)') | returns None | fixed | unreviewed |
| asdf-format__asdf-1575 | agent_ok-r1 | - | (the run's level, not a finding) | regression: asdf/_tests/test_info.py::test_info_module passed before the fix and fails after it | - | real_bug (developer) |
| astropy__photutils-1943 | gold-r1 | 1 | find_peaks(data=[[0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 6.0, 0.0], [0.0, 0.0, 5.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0]], threshold=1.0, border_width=2) | raises NoDetectionsWarning: No local peaks were found. | - | false_alarm (developer) |
| astropy__photutils-1943 | v1-r1 | 1 | find_peaks(data=[[0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]], threshold=0.0) | raises NoDetectionsWarning: Input data is constant. No local peaks can be found. | still_fails | false_alarm (developer) |
| astropy__photutils-1943 | v1-r1 | 2 | find_peaks(data=[[0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 5.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 9.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0]], threshold=1.0, border_width=1) | returns <QTable length=2>   id  x_peak y_peak peak_value int64 int64  int64   float64   ----- ------ ------ ----------     1      1      1        5.0     2      3      3        9.0 | still_fails | false_alarm (developer) |
| clld__clldutils-27 | agent_wrong-r1 | 1 | badge(subject='', status='', color='green', message='1-2', label='a-b', fmt='svg', markdown=False) | returns 'https://img.shields.io/badge/a-b-1-2-green.svg' | still_fails | real_bug (developer) |
| clld__clldutils-27 | agent_wrong-r1 | 2 | badge(subject='', status='', color='green', message='X-X', label='', fmt='svg', markdown=False) | returns 'https://img.shields.io/badge/X-X-green.svg' | still_fails | real_bug (developer) |
| clld__clldutils-27 | gold-r1 | 1 | badge(subject='a b', status='c', color='blue', markdown=False) | returns 'https://img.shields.io/badge/a%20b-c-blue.svg' | - | false_alarm (developer) |
| disqus__python-phabricator-64 | gold-r1 | - | (the run's level, not a finding) | regression: phabricator/tests/test_phabricator.py::PhabricatorTest.test_endpoint_shadowing passed before the fix and fails after it | - | false_alarm (developer) |
| django__asgiref-211 | v0-r1 | 1 | get_or_create_application_instance(self='StatelessServer(StatelessServer, max_applications=0)', scope_id='a', scope={'type': 'testprotocol'}) | raises NameError: name 'guarantee_single_callable' is not defined | fails_differently | real_bug (developer) |
| encode__httpx-653 | gold-r1 | - | (the run's level, not a finding) | regression: tests/models/test_url.py::test_url_params passed before the fix and fails after it | - | false_alarm (developer) |
| encode__httpx-883 | gold-r1 | - | (the run's level, not a finding) | the fix does not fix the bug: the reproduction test fails the same way before and after it (and 11 more) | - | unclear (developer) |
| fox-it__dissect.cstruct-88 | agent_ok-r1 | 1 | tokenize(self="ExpressionTokenizer(expression='#define B 1\\n#define C 2\\n#define A\\t(B + C)\\t// comment\\n')") | raises ExpressionTokenizerError: Tokenizer does not recognize following token '#' | still_fails | false_alarm (developer) |
| kpetremann__mqtt-exporter-37 | agent_wrong-r1 | 1 | _normalize_name_in_topic_msg(topic='shellies/shelly/emeter/0/power', payload='123.45') | returns ('shellies/shelly', {'power': '123.45'}) | still_fails | real_bug (developer) |
| kpetremann__mqtt-exporter-37 | v1-r1 | 1 | _normalize_name_in_topic_msg(topic='shellies/room/sensor/temperature', payload='20.00') | raises AttributeError: module 'mqtt_exporter.settings' has no attribute 'KEEP_FULL_TOPIC' | fixed | unreviewed |
| nipreps__nibabies-395 | agent_wrong-r1 | 1 | parse_bids_for_age_months(bids_root='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', subject_id='100619') | raises OSError: [Errno 36] File name too long: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa | still_fails | false_alarm (developer) |
| nipreps__nibabies-395 | gold-r1 | - | (the run's level, not a finding) | regression: nibabies/utils/tests/test_bids.py::test_get_age_from_tsv[session_id-x1-data0-False-None] passed before the fix and fails after it | - | false_alarm (developer) |
| nipreps__nibabies-395 | v0-r1 | 1 | parse_bids_for_age_months(bids_root='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', subject_id='sub-100619') | raises OSError: [Errno 36] File name too long: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa | still_fails | false_alarm (developer) |
| omni-us__jsonargparse-263 | agent_ok-r1 | 1 | yaml_load(stream='on:') | raises TypeError: unsupported operand type(s) for +: 'bool' and 'str' | still_fails | real_bug (developer) |
| omni-us__jsonargparse-263 | gold-r1 | 1 | yaml_load(stream='null:') | raises TypeError: unsupported operand type(s) for +: 'NoneType' and 'str' | - | real_bug (developer) |
| open-contracting__ocdskit-51 | gold-r1 | - | (the run's level, not a finding) | regression: tests/commands/test_mapping_sheet.py::test_command passed before the fix and fails after it | - | false_alarm (developer) |
| python-cmd2__cmd2-115 | gold-r1 | - | (the run's level, not a finding) | regression: tests/test_cmd2.py::test_base_help passed before the fix and fails after it (and 10 more) | - | false_alarm (developer) |
| robotpy__robotpy-cppheaderparser-44 | agent_ok-r1 | 1 | finalize(self="CppHeader('\\ntypedef C A;\\n\\nclass B\\n{\\npublic:\\n   A aMethod();\\n}\\n', 'string')") | raises AttributeError: 'CppHeader' object has no attribute '_precomp_macro_buf' | still_fails | false_alarm (developer) |
| robotpy__robotpy-cppheaderparser-44 | gold-r1 | 1 | finalize(self="CppHeader('\\ntypedef C A;\\n\\nclass B\\n{\\npublic:\\n   A aMethod();\\n};\\n', 'string')") | raises AttributeError: 'CppHeader' object has no attribute '_precomp_macro_buf' | - | false_alarm (developer) |
| scipp__scippnexus-106 | gold-r1 | - | (the run's level, not a finding) | regression: tests/nxtransformations_test.py::test_chain_with_single_values_and_different_unit passed before the fix and fails after it (and 2 more) | - | false_alarm (developer) |
| smdabdoub__kraken-biom-9 | v0-r1 | 1 | parse_kraken_report(kdata=[{'pct_reads': '0.00', 'clade_reads': '10', 'taxon_reads': '0', 'rank': '-', 'ncbi_tax': '1', 'sci_name': 'root'}, {'pct_reads': '0.00', 'clade_reads': '10', 'taxon_reads': '0', 'rank': 'D', 'ncbi_tax': '2759', 'sci_name': '  Eukaryota'}, {'pct_reads': '0.00', 'clade_reads': '1', 'taxon_reads': '0', 'rank': 'P', 'ncbi_tax': '3041', 'sci_name': '    Chlorophyta'}, {'pct_reads': '0.00', 'clade_reads': '1', 'taxon_reads': '1', 'rank': 'C', 'ncbi_tax': '75966', 'sci_name': '      Trebouxiophyceae'}, {'pct_reads': '0.00', 'clade_reads': '1', 'taxon_reads': '0', 'rank': '-', 'ncbi_tax': '33682', 'sci_name': '    Euglenozoa'}, {'pct_reads': '0.00', 'clade_reads': '1', 'taxon_reads': '0', 'rank': 'O', 'ncbi_tax': '5653', 'sci_name': '      Kinetoplastida'}, {'pct_reads': '0.00', 'clade_reads': '1', 'taxon_reads': '0', 'rank': 'F', 'ncbi_tax': '5654', 'sci_name': '        Trypanosomatidae'}, {'pct_reads': '0.00', 'clade_reads': '1', 'taxon_reads': '0', 'rank': 'G', 'ncbi_tax': '5690', 'sci_name': '          Trypanosoma'}, {'pct_reads': '0.00', 'clade_reads': '1', 'taxon_reads': '0', 'rank': '-', 'ncbi_tax': '47570', 'sci_name': '            Schizotrypanum'}, {'pct_reads': '0.00', 'clade_reads': '1', 'taxon_reads': '0', 'rank': 'S', 'ncbi_tax': '5693', 'sci_name': '              Trypanosoma cruzi'}, {'pct_reads': '0.00', 'clade_reads': '1', 'taxon_reads': '1', 'rank': '-', 'ncbi_tax': '353153', 'sci_name': '                Trypanosoma cruzi strain CL Brener'}], max_rank='O', min_rank='S') | raises NameError: name 're' is not defined | fixed | unreviewed |
| smdabdoub__kraken-biom-9 | v0-r1 | 2 | parse_tax_lvl(entry={'pct_reads': '0.00', 'clade_reads': '1', 'taxon_reads': '0', 'rank': 'P', 'ncbi_tax': '3041', 'sci_name': 'Chlorophyta'}) | raises NameError: name 're' is not defined | fixed | unreviewed |
| yt-project__unyt-437 | agent_ok-r1 | 1 | to_astropy(self="unyt_array([1, 2, 3], 'km/m')") | returns <Quantity [1., 2., 3.]> | still_fails | real_bug (developer) |
| yt-project__unyt-437 | gold-r1 | 1 | to_astropy(self="unyt_quantity(5.0, 'km/m')") | returns <Quantity 5.> | - | real_bug (developer) |
