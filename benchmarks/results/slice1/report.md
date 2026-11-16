# Tracefix benchmark: slice1

Every number comes from a run, a receipt, a prepare record or the developer's label
(scripts/bench/report.py). Rates show n/N. Headline sections read each task's first
repeat. Set aside: COUNTEREXAMPLEs whose only causes are regressions in test files
the PR's own test patch changed; the gold, partial and separation sections leave
them out.

## Funnel

| | |
|---|---|
| cases | 80 |
| prepared | 80 |
| excluded | base_suite_cannot_run: 39, base_suite_too_slow: 14, hidden_tests_fail_on_gold: 4, image_not_at_base_commit: 1 |
| ready | 22 |
| ready_with_partial | 16 |
| isolation_at_prepare | strict: 22 |
| setup_commit_needed | 5 |
| runs | gold: api_error: 1, receipt: 30, timeout: 1, partial: api_error: 1, receipt: 22, timeout: 1 |
| receipt_status | ok: 52 |
| exit_codes | 0: 54 |
| isolation | strict: 52 |
| stage_errors | none |

## Splits

| | |
|---|---|
| dev | 13 |
| held_out | 7 |

## Set aside

| | |
|---|---|
| gold | 1/20 (5%) |
| partial | 2/14 (14%) |
| tasks | cal-itp__benefits-3198, elementsinteractive__twyn-317 |

## Gold

| | |
|---|---|
| levels | COUNTEREXAMPLE: 4, L0: 1, L1: 9, L2: 5, L3: 0, L4: 0 |
| counterexample | 4/19 (21%) |
| false_alarm | 3/19 (16%) |
| real_bug_in_gold | 1/19 (5%) |
| false_alarm_proposed | 0/19 (0%) |
| unreviewed | 0/19 (0%) |
| at_least_l2 | 5/19 (26%) |
| at_least_l3 | 0/19 (0%) |
| l4 | 0/19 (0%) |

## Partial

| | |
|---|---|
| levels | COUNTEREXAMPLE: 7, L0: 2, L1: 2, L2: 1, L3: 0, L4: 0 |
| detection | 7/12 (58%) |
| not_green_lit | 11/12 (92%) |
| false_pass_l2 | 1/12 (8%) |
| false_pass_l3 | 0/12 (0%) |
| leftover_found | 4/12 (33%) |
| real_bug_by_label | 1/12 (8%) |
| unreviewed | 0/12 (0%) |

## Separation

| | |
|---|---|
| gold_above | 6/12 (50%) |
| same | 5/12 (42%) |
| gold_below | 1/12 (8%) |

## Reproducer

| | |
|---|---|
| statuses | fix_does_not_fix: 1, not_reproduced: 1, reproduced: 18 |
| fail_to_pass | 18/20 (90%) |
| fix_does_not_fix | 1/20 (5%) |

## Guard

### gold

| | |
|---|---|
| statuses | guarded: 6, not_guarded: 12, skipped: 2 |
| guarded | 6/20 (30%) |
| kill_rate | mean 0.563, median 0.6, p90 1.0, max 1.0 (n=18) |
| crash_only_kills | 0/52 (0%) |

### partial

| | |
|---|---|
| statuses | guarded: 2, not_guarded: 6, skipped: 6 |
| guarded | 2/14 (14%) |
| kill_rate | mean 0.603, median 0.584, p90 1.0, max 1.0 (n=8) |
| crash_only_kills | 0/24 (0%) |

## Break my fix

### gold

| | |
|---|---|
| statuses | found: 3, inconclusive: 4, none_found: 7, skipped: 6 |
| skip_reasons | no target could be attacked: its objects' code can't run here: ArrayVNMetadata is not the module's own name or plain data: 1, the attack ran no input: 3, the fix changes no function Break My Fix can call: 1, the fix changes no function Break My Fix can call (ArrayVNMetadata.to_buffer_dict._json_convert: a nested function: it can't be imported, not attacked yet): 1, the fix changes no function Break My Fix can call (Bot.__repr__: a special method (such as __init__ or __eq__): not called yet): 1, the fix changes no function Break My Fix can call (ClientTransport.__aenter__: a special method (such as __init__ or __eq__): not called yet; ClientTransport.__: 1, the fix changes no function Break My Fix can call (FigureEight.__init__: a special method (such as __init__ or __eq__): not called yet): 1, the fix changes no function Break My Fix can call (unyt_array.__array_ufunc__: a special method (such as __init__ or __eq__): not called yet): 1 |
| targets | 31 |
| inputs_per_target | 103.7 |
| pre_existing | 0 |
| first_l4_blocker | none |

### partial

| | |
|---|---|
| statuses | found: 4, inconclusive: 4, none_found: 3, skipped: 3 |
| skip_reasons | no target could be attacked: its objects' code can't run here: ArrayVNMetadata is not the module's own name or plain data: 1, the attack on rx._lazy_resolve did not finish: 1, the attack ran no input: 2, the fix changes no function Break My Fix can call: 2, the fix changes no function Break My Fix can call (FigureEight.__init__: a special method (such as __init__ or __eq__): not called yet): 1 |
| targets | 26 |
| inputs_per_target | 100.9 |
| pre_existing | 0 |
| first_l4_blocker | none |

## Behaviour diff

### gold

| | |
|---|---|
| statuses | compared: 1, inconclusive: 7, partial: 5, skipped: 7 |
| l3_gate_open | 0/20 (0%) |
| first_l3_blocker | <name>: module-level code that computes a value changed (line N); what uses it is not compared: 1, <name>: not compared (a special method (such as __init__ or __eq__): not called yet): 2, <name>: the comparison did not finish: 1, no changed function was compared: 1 |

### partial

| | |
|---|---|
| statuses | compared: 1, inconclusive: 5, partial: 5, skipped: 3 |
| l3_gate_open | 0/14 (0%) |
| first_l3_blocker | <name>: not compared (a special method (such as __init__ or __eq__): not called yet): 1 |

## Report only

### gold

| | |
|---|---|
| fix_line_coverage | repro: 125/204 (61%) |
| regressions | found: 2, none_found: 18 |

### partial

| | |
|---|---|
| fix_line_coverage | repro: 61/122 (50%) |
| regressions | found: 2, inconclusive: 1, none_found: 11 |

## Cost and time

| | |
|---|---|
| usd_per_run | mean 0.236, median 0.197, p90 0.539, max 0.675 (n=34) |
| usd_unknown | 0 |
| usd_spent_live | 18.56 |
| usd_spent_known | 12.56 |
| live_attempts_cost_unknown | 2 |
| calls | mean 5.676, median 6.0, p90 8.0, max 9.0 (n=34) |
| tokens | mean 48064.765, median 40471.0, p90 89825.0, max 132846.0 (n=34) |
| seconds_per_run | mean 886.231, median 389.554, p90 2293.671, max 4139.641 (n=34) |
| seconds_per_stage | behaviour_diff: mean 103.873, median 8.085, p90 85.77, max 1597.44 (n=34), break_my_fix: mean 52.644, median 38.07, p90 125.9, max 170.83 (n=34), environment: mean 40.969, median 17.05, p90 108.38, max 122.95 (n=34), fix_line_coverage: mean 4.168, median 4.195, p90 9.25, max 11.46 (n=34), guard: mean 512.585, median 164.56, p90 1727.9, max 3336.77 (n=34), import_check: mean 8.172, median 6.46, p90 17.75, max 20.48 (n=34), integrity: mean 0.045, median 0.02, p90 0.12, max 0.37 (n=34), regressions: mean 110.449, median 19.3, p90 361.95, max 514.28 (n=34), reproduce: mean 48.481, median 36.13, p90 86.16, max 174.89 (n=34) |

## Stability

| | |
|---|---|
| groups | 18 |
| level_flips | 6/18 (33%) |
| counterexample_flips | 2/18 (11%) |
| guard_flips | 4/18 (22%) |
| finding_flips | 4/18 (22%) |

## Findings

| task | run | # | call | outcome | replay on gold | label |
|---|---|---|---|---|---|---|
| MAIF__arta-50 | gold-r1 | - | (the run's level, not a finding) | the fix does not fix the bug: the reproduction test fails the same way before and after it | - | false_alarm (developer) |
| cal-itp__benefits-3198 | gold-r1 | - | (the run's level, not a finding) | regression: tests/pytest/core/admin/test_transit.py::TestTransitAgencyAdmin.test_get_exclude[staff-expected0] passed before the fix and fails after it (and 1 more) | - | false_alarm (developer) |
| elementsinteractive__twyn-317 | gold-r1 | - | (the run's level, not a finding) | regression: tests/main/test_main.py::TestCheckDependencies.test_check_dependencies_npm_v3 passed before the fix and fails after it (and 12 more) | - | false_alarm (developer) |
| elementsinteractive__twyn-317 | gold-r1 | 1 | normalize_packages(packages=set()) | returns None | - | false_alarm (developer) |
| elementsinteractive__twyn-317 | gold-r2 | - | (the run's level, not a finding) | regression: tests/main/test_main.py::TestCheckDependencies.test_check_dependencies_npm_v3 passed before the fix and fails after it (and 12 more) | - | false_alarm (developer) |
| elementsinteractive__twyn-317 | v0-r2 | 1 | normalize_packages(packages={''}) | returns None | still_fails | false_alarm (developer) |
| itsdnns__docsight-437 | v1-r1 | 1 | _aggregate_period(snapshots=[{'timestamp': '2024-01-01T00:00:00Z', 'summary': {'ds_power_avg': 1.0, 'ds_snr_avg': 40.0, 'us_power_avg': 45.0, 'ds_correctable_errors': None, 'ds_uncorrectable_errors': None, 'health': 'good'}}]) | raises UnboundLocalError: cannot access local variable 'corr_errors_supported' where it is not associated with a value | fixed | unreviewed |
| joke2k__django-environ-592 | gold-r1 | 1 | db_url(self='Env()', var='DJANGO_ENVIRON_SURELY_UNSET_VAR', default='sqlite://:memory:', extra_options={'timeout': 20}) | returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'} | - | real_bug (developer) |
| joke2k__django-environ-592 | gold-r1 | 2 | db_url(self='Env()', var='DJANGO_ENVIRON_TEST_UNSET_DB_URL_XYZ', default='sqlite://:memory:', engine=None, options_cast=None, extra_options={'timeout': 20}) | returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'} | - | real_bug (developer) |
| joke2k__django-environ-592 | gold-r1 | 3 | db_url_config(url='sqlite://:memory:', extra_options={'timeout': 20}) | returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'} | - | real_bug (developer) |
| joke2k__django-environ-592 | gold-r1 | 4 | db_url_config(url='sqlite://:memory:', engine=None, options_cast=None, extra_options={'timeout': 20}) | returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'} | - | real_bug (developer) |
| joke2k__django-environ-592 | v1-r1 | 1 | db_url(self='Env()', var='ENVIRON_TEST_UNSET_VAR_XYZ', default='postgres://user:pass@localhost:5432/db', extra_options={'pool': True}) | returns {'NAME': 'db', 'USER': 'user', 'PASSWORD': 'pass', 'HOST': 'localhost', 'PORT': 5432, 'ENGINE': 'django.db.backends.postgresql'} | fixed | unreviewed |
| joke2k__django-environ-592 | v1-r1 | 2 | db_url(self='Env()', var='DJANGO_ENVIRON_UNSET_TEST_VAR_XYZ', default='postgres://user:pass@localhost:5432/db', extra_options={'pool': {'min_size': 2, 'max_size': 4, 'timeout': 10}}) | returns {'NAME': 'db', 'USER': 'user', 'PASSWORD': 'pass', 'HOST': 'localhost', 'PORT': 5432, 'ENGINE': 'django.db.backends.postgresql'} | fixed | unreviewed |
| joke2k__django-environ-592 | v1-r1 | 3 | db_url(self='Env()', var='DJANGO_ENVIRON_UNSET_TEST_VAR_XYZ', default='postgres://user:pass@localhost:5432/db', engine=None, options_cast=None, extra_options={'pool': {'min_size': 2, 'max_size': 4, 'timeout': 10}}) | returns {'NAME': 'db', 'USER': 'user', 'PASSWORD': 'pass', 'HOST': 'localhost', 'PORT': 5432, 'ENGINE': 'django.db.backends.postgresql'} | fixed | unreviewed |
| joke2k__django-environ-592 | v1-r1 | 4 | db_url_config(url='sqlite://:memory:', extra_options={'timeout': 20}) | returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'} | still_fails | real_bug (developer) |
| omni-us__jsonargparse-770 | v3-r1 | 1 | set_parsing_settings(stubs_resolver_allow_py_files=True) | returns None | fixed | unreviewed |
| omni-us__jsonargparse-770 | v3-r2 | 1 | set_parsing_settings(validate_defaults=None, parse_optionals_as_positionals=None, stubs_resolver_allow_py_files=True) | returns None | fixed | unreviewed |
| zarr-developers__virtualizarr-979 | gold-r1 | 1 | manifest_from_kerchunk_chunk_dict(kerchunk_chunk_dict={}) | raises ValueError: need a chunk grid shape if no chunks given | - | false_alarm (developer) |
| zarr-developers__virtualizarr-979 | v0-r1 | 1 | manifest_from_kerchunk_chunk_dict(kerchunk_chunk_dict={'0': 'base64:'}, fs_root=None, shape=None) | raises NameError: name 'base64' is not defined | fixed | unreviewed |
