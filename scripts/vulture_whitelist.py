# Names vulture reports as unused that are used by something it can't see. Parsed by vulture,
# never imported or run (so ruff skips this file). Review on 2 Oct 2026; add a reason per entry.

_.limit_flags  # proctree: a field of a Windows C structure, read by the OS
model_config  # pydantic reads it (prompts/*.py, tests/test_llm.py)
rationale  # reproducer schema: a field the model must fill in; never used for a verdict
note  # tests/test_llm.py: a schema field of the test model
tb  # workspace: required parameter of the __exit__ protocol
pytest_configure  # tests/conftest.py: a pytest hook
pytest_runtest_setup  # attack_runtime: a pytest hook of the call recorder (loaded with -p)
pytest_runtest_makereport  # attack_runtime: a pytest hook of the call recorder (loaded with -p)
_.connect  # tests/conftest.py: monkeypatched socket method (network block)
_.connect_ex  # tests/conftest.py: monkeypatched socket method (network block)
missing_ok  # tests/test_isolation.py: stand-in keeps the real Path.unlink signature
pytestmark  # tests/test_live.py: read by pytest
visit_Match  # integrity_rules._CutBranch: called by ast.NodeTransformer for each Match node
_.showwarning  # attack_runtime._watching_side: set for the warnings module to call, restored by catch_warnings
_.__v__  # tests/test_diff_runtime.py: a slot named like a dunder, set so the snapshot must read it
_.__cause__  # tests/test_diff_runtime.py: an exception's cause, set so the snapshot must compare it
utcoffset  # tests/test_diff_runtime.py: Zone.utcoffset, called by datetime (the tzinfo protocol)
_.msecs  # attack_runtime._watching_side: a log record's field, fixed so formatters print one time (read by logging)
_.relativeCreated  # attack_runtime._watching_side: a log record's field, read by logging formatters
_.process  # attack_runtime._watching_side: a log record's field, read by logging formatters
_.thread  # attack_runtime._watching_side: a log record's field, read by logging formatters
_model_ids  # config.FileSettings: a pydantic field validator, called by pydantic by name
guarded  # ladder.Facts: read by name in ladder.climb (getattr over its _STEPS)
l4  # ladder.Facts: read by name in ladder.climb (getattr over its _STEPS)
tracefix_version  # receipt.Receipt: a field read only by serialisation (receipt.json)
daemon_threads  # tests/github_fake.py: read by socketserver.ThreadingMixIn
_.server_name  # tests/github_fake.py: read by http.server (set without a name lookup)
_.server_port  # tests/github_fake.py: read by http.server
do_GET  # tests/github_fake.py: called by http.server for each GET
do_POST  # tests/github_fake.py: called by http.server for each POST
do_PATCH  # tests/github_fake.py: called by http.server for each PATCH
do_DELETE  # tests/github_fake.py: called by http.server for each DELETE
log_message  # tests/github_fake.py: overrides http.server's logging (quiet test output)
version  # action.State: a field read only by serialisation (state.json's format number)
_consistent  # bench.data.Task: a pydantic model validator, called by pydantic
_one_per_finding  # bench.report.Labels: a pydantic model validator, called by pydantic
dataset  # bench.data.Source: a field of the pin, written to and checked from benchmarks/sources.json
license  # bench.data.Source: a field of the pin, written to benchmarks/sources.json (CC BY 4.0 attribution)
file_sha256  # bench.agents.Pin: the parquet file's sha256, written to benchmarks/sources.json by scripts/extract_agents.py
unreadable_rows  # bench.agents.Pin: rows without a valid instance id, recorded in benchmarks/sources.json
pip_changes  # bench.prepare.Prepared: set from prepare's facts dict, written to benchmarks/prepared/ (what installing Tracefix changed)
_.numprocesses  # scripts/bench/stubs/tracefix_stub_xdist.py: pytest's option, read by projects' conftests
_.distload  # scripts/bench/stubs/tracefix_stub_xdist.py: pytest's option (xdist's -d), read by projects
_.tx  # scripts/bench/stubs/tracefix_stub_xdist.py: pytest's option (xdist's --tx), read by projects
_.cov_source  # scripts/bench/stubs/tracefix_stub_cov.py: pytest's option (--cov), read by projects
_.no_cov  # scripts/bench/stubs/tracefix_stub_cov.py: pytest's option (--no-cov), read by projects
_.dwFlags  # tests/test_bench_inside.py: subprocess.STARTUPINFO's field, read by Windows' CreateProcess (a hidden console)
isatty  # scripts/landing_run.py: Stamped stands in for sys.stderr, which callers may ask isatty()
handle_starttag  # tests/test_build_site.py: HTMLParser's callback, called by HTMLParser.feed
handle_endtag  # tests/test_build_site.py: HTMLParser's callback, called by HTMLParser.feed
handle_data  # tests/test_build_site.py: HTMLParser's callback, called by HTMLParser.feed
_gives_tracer_ids_back  # tests/conftest.py: an autouse pytest fixture, run by pytest around every test
