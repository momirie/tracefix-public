"""The benchmark's run pool (M10 plan P6, P9): what to run, resuming, the spend guard, timeouts
and the lines it writes. A fake box answers inside.py's commands; everything on the host is the
real code. No Docker, no network, no model."""

from __future__ import annotations

import _thread
import contextlib
import json
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import benchmark
import pytest
from bench import prepare, run
from bench.box import Box, BoxError
from bench.data import DataError, Task, image_for
from bench.prepare import Prepared, Reason
from bench.run import Pool, Results, RunLine, SpendGuard, Unit
from bench_fakes import (
    AGENT_COMMITS,
    AGENT_PATCH,
    COMMITS,
    GONE,
    TIMEOUT,
    FakeBox,
    agent_case,
    answers,
    case,
    ready,
    receipt,
    tried,
)
from hypothesis import given
from hypothesis import strategies as st

from tracefix.ladder import EvidenceLevel
from tracefix.llm import LLMRequest, LLMResponse, Message, RecordingProvider
from tracefix.receipt import ModelProblem, Receipt, StageEntry
from tracefix.record import RunStatus


def line(kind: str = "gold", repeat: int = 1, **changes: object) -> RunLine:
    facts: dict[str, object] = {"instance_id": "tracefix__synthetic-1", "kind": kind,
                                "variant": "gold" if kind == "gold" else "v0", "repeat": repeat,
                                "live": False, "outcome": "receipt"}  # fmt: skip
    return RunLine.model_validate({**facts, **changes})


# --- plan ---------------------------------------------------------------------------------------


def ids(n: int) -> list[str]:
    return [f"tracefix__synthetic-{i}" for i in range(1, n + 1)]


def test_the_plan_runs_ready_tasks_gold_and_partial_first_repeats_first() -> None:
    one, two, three, four = ids(4)
    cases = [case(one, 0), case(two, 1), case(three, 2), case(four, 3)]
    prepared = {
        one: ready(one),
        two: ready(two, kept=None),  # a single-hunk fix: gold only
        three: Prepared(instance_id=three, excluded=Reason.SUITE_TOO_SLOW),
    }  # four: not prepared
    jobs = run.plan(cases, prepared, [], repeats=2)
    assert [j.task.instance_id for j in jobs] == [one, two]
    assert jobs[0].units == (Unit("gold", 1), Unit("partial", 1), Unit("gold", 2),
                             Unit("partial", 2))  # fmt: skip
    assert jobs[1].units == (Unit("gold", 1), Unit("gold", 2))


def test_done_runs_are_skipped_but_harness_errors_are_tried_again() -> None:
    done = [line("gold"), line("partial", outcome="harness_error")]
    [job] = run.plan([case()], {"tracefix__synthetic-1": ready()}, done, repeats=1)
    assert job.units == (Unit("partial", 1),)
    assert run.plan([case()], {"tracefix__synthetic-1": ready()},
                    [*done, line("partial", outcome="timeout")], repeats=1) == []  # fmt: skip


# --- the spend guard ----------------------------------------------------------------------------


def test_spent_counts_every_live_attempt_and_unknown_costs_as_a_reserve() -> None:
    lines = [
        line(live=True, cost_usd=0.4),
        line(live=True, outcome="harness_error"),  # tried again later: still spent
        line(live=True, outcome="receipt", cost_usd=0.6),
        line(live=False, cost_usd=9.0),  # replayed answers cost nothing
    ]
    assert run.spent(lines, reserve=3.0) == pytest.approx(0.4 + 3.0 + 0.6)


def test_the_guard_reserves_for_runs_in_flight_and_never_restarts() -> None:
    guard = SpendGuard(ceiling=10.0, spent=1.0, reserve=3.0)
    assert guard.start() and guard.start() and guard.start()  # 1 + 3 x 3 = 10
    assert not guard.start()  # no room beside the runs in flight: refused, not stopped
    assert not guard.stopped
    guard.finish(0.5)
    assert not guard.start()  # 1.5 + 3 x 3 > 10
    guard.finish(0.5)
    assert guard.start()  # 2 + 3 x 2 <= 10: room again
    guard.finish(2.5)
    guard.finish(3.0)
    assert guard.spent == 7.5 and guard.in_flight == 0
    assert not guard.start() and guard.stopped  # 7.5 + 3 > 10 even alone: stopped for good
    guard.ceiling = 100.0
    assert not guard.start(wait=True) and not guard.room()  # stopped stays stopped


def test_a_run_that_waits_for_room_starts_when_one_in_flight_finishes() -> None:
    guard = SpendGuard(ceiling=7.0, reserve=3.0)
    assert guard.start() and guard.start()  # 3 x 2 <= 7; a third needs 9
    assert guard.room()  # it would fit alone: worth opening a box for
    started: list[bool] = []
    waiter = threading.Thread(target=lambda: started.append(guard.start(wait=True)))
    waiter.start()
    waiter.join(0.2)
    assert waiter.is_alive() and not started  # waiting, not refused
    guard.finish(0.5)  # 0.5 + 3 x 2 <= 7
    waiter.join(5)
    assert started == [True] and guard.in_flight == 2 and not guard.stopped


def test_a_waiting_run_is_refused_when_the_finished_run_used_up_the_room() -> None:
    guard = SpendGuard(ceiling=7.0, reserve=3.0)
    assert guard.start() and guard.start()
    started: list[bool] = []
    waiter = threading.Thread(target=lambda: started.append(guard.start(wait=True)))
    waiter.start()
    guard.finish(3.0)  # 3 + 3 x 2 > 7: waits on for the other run
    waiter.join(0.2)
    assert waiter.is_alive()
    guard.finish(3.0)  # 6 + 3 > 7 even alone
    waiter.join(5)
    assert started == [False] and guard.stopped


def test_an_unknown_cost_counts_as_a_whole_reserve_and_the_reserve_grows() -> None:
    guard = SpendGuard(ceiling=100.0, reserve=3.0)
    guard.start()
    guard.finish(None)
    assert guard.spent == 3.0
    guard.start()
    guard.finish(7.5)
    assert guard.reserve == 7.5 and guard.spent == 10.5


def test_a_live_guard_reserves_at_least_the_dearest_run_and_counts_unknowns_in_full() -> None:
    lines = [line(live=True, cost_usd=0.68), line(live=True, outcome="harness_error"),
             line(live=False, cost_usd=9.0)]  # fmt: skip
    guard = run.live_guard(lines, ceiling=10.0, reserve=0.5)
    assert guard.reserve == 0.68  # a lower --reserve can't go below a run already seen
    assert guard.spent == pytest.approx(0.68 + run.RESERVE_USD)  # the unknown cost: in full
    assert run.live_guard([], ceiling=10.0, reserve=0.5).reserve == 0.5
    assert run.live_guard([], ceiling=10.0).reserve == run.RESERVE_USD


def test_a_reserve_below_what_tracefixs_token_budget_allows_a_run_is_named() -> None:
    worst = run.worst_run_usd()
    # 500k budget tokens and one 16k answer, all at the dearest default model's output price
    assert worst == pytest.approx(516_000 * 20.0 / 1_000_000)
    warning = run.reserve_warning(SpendGuard(ceiling=10.0, reserve=1.2))
    assert warning is not None and "$1.20" in warning and f"${worst:.2f}" in warning
    assert run.reserve_warning(SpendGuard(ceiling=50.0, reserve=worst)) is None


@given(
    st.floats(0.0, 20.0),
    st.lists(st.tuples(st.integers(1, 4), st.floats(0.0, 1.0)), max_size=40),
)
def test_runs_that_cost_no_more_than_their_reserve_never_pass_the_ceiling(
    ceiling: float, waves: list[tuple[int, float]]
) -> None:
    """Waves of up to 4 runs at once; each costs a share of the reserve it started under."""
    guard = SpendGuard(ceiling=ceiling, reserve=3.0)
    for width, share in waves:
        started = [guard.reserve for _ in range(width) if guard.start()]
        for reserve in started:
            guard.finish(reserve * share)
    assert guard.spent <= ceiling + 1e-9


# --- the pool -----------------------------------------------------------------------------------


def pool(tmp_path: Path, make_box: Callable[[Task], Box], *, live: bool = False,
         guard: SpendGuard | None = None, removed: list[str] | None = None,
         **options: Any) -> Pool:  # fmt: skip
    remove = removed.append if removed is not None else None
    mode = options.pop("mode", "live" if live else "replay")
    return Pool(results=Results(tmp_path / "results"), recordings=tmp_path / "rec",
                work=tmp_path / "work", wheel=tmp_path / "x.whl", mode=mode,
                guard=guard or run.free(), make_box=make_box, remove_image=remove,
                **options)  # fmt: skip


def boxes(tmp_path: Path, answer: object) -> tuple[list[FakeBox], Callable[[Task], Box]]:
    made: list[FakeBox] = []
    lock = threading.Lock()

    def make(task: Task) -> Box:
        with lock:
            b = FakeBox(tmp_path / f"box{len(made)}", answer)  # type: ignore[arg-type]
            made.append(b)
        return b

    return made, make


def jobs(repeats: int = 1) -> list[run.Job]:
    return run.plan([case()], {"tracefix__synthetic-1": ready()}, [], repeats)


def test_gold_and_partial_are_verified_and_the_partial_findings_replayed_on_gold(
    tmp_path: Path,
) -> None:
    made, make = boxes(tmp_path, answers({"tf-gold": receipt("L4", 0.4),
                                          "tf-v0": receipt("COUNTEREXAMPLE", 0.7)}))  # fmt: skip
    removed: list[str] = []
    p = pool(tmp_path, make, removed=removed)
    counts = run.run_all(jobs(), p, workers=2)
    assert counts == {"receipt": 2}
    gold, partial = p.results.lines()
    assert (gold.tag, gold.level, gold.cost_usd, gold.replay) == ("gold-r1", "L4", 0.4, None)
    assert (partial.tag, partial.level) == ("v0-r1", "COUNTEREXAMPLE")
    assert partial.replay is not None
    assert [f.result.value for f in partial.replay.findings] == ["fixed", "still_fails"]
    assert p.results.receipt(partial) == receipt("COUNTEREXAMPLE", 0.7)
    assert partial.receipt == "tracefix__synthetic-1/v0-r1"
    [b] = made
    assert b.commands == ["probe", "commits", "verify", "verify", "replay"]
    assert b.closed and removed == [image_for("tracefix__synthetic-1")]


def test_kept_agent_patches_run_after_gold_and_partial_and_replay_on_gold(
    tmp_path: Path,
) -> None:
    """Slice 2 (plan C3): each kept agent patch is committed from the case's own run, verified
    like the partial fix, and its findings replayed on gold (gate 3's leftover found; an
    agent_ok finding gold passes is the report's "differs from gold")."""
    sent: list[dict[str, object]] = []
    inner = answers({"tf-gold": receipt("L4"), "tf-v0": receipt("COUNTEREXAMPLE"),
                     "tf-agent_wrong": receipt("COUNTEREXAMPLE"),
                     "tf-agent_ok": receipt("COUNTEREXAMPLE")},
                    commits={**COMMITS, **AGENT_COMMITS})  # fmt: skip

    def answer(command: str, request: dict[str, object], b: FakeBox) -> object:
        sent.append(request)
        return inner(command, request, b)

    made, make = boxes(tmp_path, answer)
    prepared = ready(agents=(tried("agent_wrong"), tried("agent_ok")))
    p = pool(tmp_path, make)
    plan = run.plan([agent_case()], {"tracefix__synthetic-1": prepared}, [], repeats=1)
    assert run.run_all(plan, p, workers=1) == {"receipt": 4}
    lines = p.results.lines()
    assert [(x.kind, x.tag) for x in lines] == [
        ("gold", "gold-r1"), ("partial", "v0-r1"), ("agent_wrong", "agent_wrong-r1"),
        ("agent_ok", "agent_ok-r1"),
    ]  # fmt: skip
    assert [x.replay is not None for x in lines] == [False, True, True, True]
    [b] = made
    assert b.commands == ["probe", "commits", "verify", *["verify", "replay"] * 3]  # gold: L4
    commits = next(r for r in sent if "patches" in r)
    patches_sent = commits["patches"]
    assert isinstance(patches_sent, dict)
    assert patches_sent["agent_wrong"] == patches_sent["agent_ok"] == AGENT_PATCH


def test_an_agent_patch_prepare_did_not_keep_is_never_run() -> None:
    prepared = ready(kept=None, agents=(tried("agent_wrong", kept=False), tried("agent_ok")))
    [job] = run.plan([agent_case()], {"tracefix__synthetic-1": prepared}, [], repeats=1)
    assert job.units == (Unit("gold", 1), Unit("agent_ok", 1))
    assert run.variant_for(prepared, "agent_wrong") is None


def test_a_case_whose_agent_run_is_not_the_one_prepare_labelled_runs_nothing(
    tmp_path: Path,
) -> None:
    made, make = boxes(tmp_path, answers({}, commits={**COMMITS, **AGENT_COMMITS}))
    moved = tried("agent_ok").model_copy(update={"source_row": 99})
    prepared = ready(agents=(moved,))
    plan = run.plan([agent_case()], {"tracefix__synthetic-1": prepared}, [], repeats=1)
    assert run.run_all(plan, pool(tmp_path, make), workers=1) == {"setup failed": 3}
    assert made[0].closed


def test_the_api_key_goes_only_to_live_verify_steps(tmp_path: Path) -> None:
    made, make = boxes(tmp_path, answers({"tf-gold": receipt("L4"), "tf-v0": receipt("L4")}))
    run.run_all(jobs(), pool(tmp_path, make, live=True, guard=SpendGuard(10.0)), workers=1)
    [b] = made
    sent = dict(zip(b.commands, b.env_names, strict=True))
    assert sent["verify"] == ("ANTHROPIC_API_KEY",)
    assert all(not env for c, env in zip(b.commands, b.env_names, strict=True) if c != "verify")


def test_a_live_run_replaces_an_earlier_attempts_copy_of_its_recordings(tmp_path: Path) -> None:
    """Slice 2's first live run (22 Oct 2026): the smoke run's copy of recordings-gold-r1 was
    still in the task's scratch folder, so copying the new answers back failed after the model
    was paid, and the run was a harness_error. Our own scratch copy is replaced instead."""
    recorded = answers({"tf-gold": receipt("L4"), "tf-v0": receipt("L1")})

    def answer(command: str, request: dict[str, Any], b: Any) -> object:
        if command == "verify":
            (Path(request["recordings"]) / f"{request['head']}.json").write_text("{}", "utf-8")
        return recorded(command, request, b)

    stale = tmp_path / "work" / "tracefix__synthetic-1" / "run" / "recordings-gold-r1"
    stale.mkdir(parents=True)
    (stale / "old.json").write_text("{}", encoding="utf-8")
    _, make = boxes(tmp_path, answer)
    p = pool(tmp_path, make, live=True, guard=SpendGuard(10.0))
    run.run_all(jobs(), p, workers=1)
    assert [ln.outcome for ln in p.results.lines()] == ["receipt", "receipt"]
    assert sorted(f.name for f in stale.iterdir()) == ["tf-gold.json"]
    kept = tmp_path / "rec" / "tracefix__synthetic-1"
    assert sorted(f.name for f in kept.iterdir()) == ["tf-gold.json", "tf-v0.json"]


def test_a_second_pool_resumes_with_nothing_left_to_do(tmp_path: Path) -> None:
    made, make = boxes(tmp_path, answers({"tf-gold": receipt("L4"), "tf-v0": receipt("L1")}))
    p = pool(tmp_path, make)
    run.run_all(jobs(), p, workers=1)
    again = run.plan([case()], {"tracefix__synthetic-1": ready()}, p.results.lines(), 1)
    assert again == [] and len(made) == 1


def test_a_timeout_is_recorded_and_the_next_run_gets_a_fresh_box(tmp_path: Path) -> None:
    made, make = boxes(tmp_path, answers({"tf-gold": TIMEOUT, "tf-v0": receipt("L2")}))
    p = pool(tmp_path, make)
    run.run_all(jobs(), p, workers=1)
    gold, partial = p.results.lines()
    assert (gold.outcome, gold.exit_code, gold.receipt) == ("timeout", None, None)
    assert partial.outcome == "receipt"
    assert len(made) == 2 and all(b.closed for b in made)


def test_a_receipt_that_is_not_a_receipt_is_recorded_as_unreadable(tmp_path: Path) -> None:
    _, make = boxes(tmp_path, answers({"tf-gold": '{"level": "L4"}', "tf-v0": "not json"}))
    p = pool(tmp_path, make)
    run.run_all(jobs(), p, workers=1)
    assert [ln.outcome for ln in p.results.lines()] == ["unreadable_receipt"] * 2
    assert all(ln.level is None and ln.cost_usd is None for ln in p.results.lines())


def with_problem(built: Receipt, kind: str) -> Receipt:
    problem = ModelProblem(stage="reproduce", role="reproducer", model="m", kind=kind,
                           status=None, words="w", detail="d")  # fmt: skip
    return built.model_copy(update={"llm": built.llm.model_copy(update={"problems": [problem]})})


def test_a_run_the_api_failed_is_kept_out_of_the_numbers_and_tried_again(
    tmp_path: Path,
) -> None:
    made, make = boxes(tmp_path, answers({
        "tf-gold": with_problem(receipt("L1", 0.1), "network"),
        "tf-v0": with_problem(receipt("COUNTEREXAMPLE", 0.2), "rate_limit"),
    }))  # fmt: skip
    p = pool(tmp_path, make)
    assert run.run_all(jobs(), p, workers=1) == {"api_error": 2}
    gold, partial = p.results.lines()
    assert (gold.outcome, gold.level, gold.cost_usd) == ("api_error", "L1", 0.1)
    assert (
        gold.detail == "api: reproduce: network" and gold.receipt == "tracefix__synthetic-1/gold-r1"
    )
    assert partial.replay is None and made[0].commands.count("replay") == 0
    assert p.results.receipt(gold) is None and p.results.receipt(partial) is None
    [job] = run.plan([case()], {"tracefix__synthetic-1": ready()}, p.results.lines(), 1)
    assert job.units == (Unit("gold", 1), Unit("partial", 1))


def test_a_replay_without_recorded_answers_is_kept_out_of_the_numbers_and_tried_again(
    tmp_path: Path,
) -> None:
    made, make = boxes(tmp_path, answers({
        "tf-gold": with_problem(receipt("L1", 0.0), "missing_recording"),
        "tf-v0": with_problem(receipt("COUNTEREXAMPLE", 0.0), "missing_recording"),
    }))  # fmt: skip
    p = pool(tmp_path, make)
    assert run.run_all(jobs(), p, workers=1) == {"no_recording": 2}
    gold, partial = p.results.lines()
    assert (gold.outcome, gold.live, gold.detail) == (
        "no_recording", False, "replay: reproduce: no recorded answer"
    )  # fmt: skip
    assert partial.replay is None and made[0].commands.count("replay") == 0
    assert p.results.receipt(gold) is None and p.results.receipt(partial) is None
    [job] = run.plan([case()], {"tracefix__synthetic-1": ready()}, p.results.lines(), 1)
    assert job.units == (Unit("gold", 1), Unit("partial", 1))


@pytest.mark.parametrize("kind", ["budget", "invalid_output", "refusal", "rejected", "other"])
def test_a_model_problem_of_tracefix_s_own_still_counts(tmp_path: Path, kind: str) -> None:
    _, make = boxes(tmp_path, answers({"tf-gold": with_problem(receipt("L1"), kind),
                                       "tf-v0": receipt("L1")}))  # fmt: skip
    p = pool(tmp_path, make)
    assert run.run_all(jobs(), p, workers=1) == {"receipt": 2}
    assert p.results.receipt(p.results.lines()[0]) is not None


def test_a_box_whose_commits_differ_from_prepares_runs_nothing(tmp_path: Path) -> None:
    other = {"base": "a" * 40, "gold": "e" * 40, "v0": "c" * 40}
    made, make = boxes(tmp_path, answers({}, commits=other))
    removed: list[str] = []
    p = pool(tmp_path, make, removed=removed)
    assert run.run_all(jobs(), p, workers=1) == {"setup failed": 2}
    assert p.results.lines() == [] and made[0].closed and removed == []


def test_a_box_that_cannot_start_is_a_setup_failure(tmp_path: Path) -> None:
    def make(task: Task) -> Box:
        raise BoxError("docker run failed (exit 125)")

    p = pool(tmp_path, make)
    assert run.run_all(jobs(), p, workers=1) == {"setup failed": 2}


def test_the_guard_stops_live_runs_before_the_ceiling(tmp_path: Path) -> None:
    made, make = boxes(tmp_path, answers({"tf-gold": receipt("L4", 2.0),
                                          "tf-v0": receipt("L4", 2.0)}))  # fmt: skip
    guard = SpendGuard(ceiling=4.5, reserve=3.0)  # after one $2 run, 2 + 3 > 4.5
    p = pool(tmp_path, make, live=True, guard=guard)
    counts = run.run_all(jobs(), p, workers=1)
    assert counts == {"receipt": 1, "not started (spend ceiling)": 1}
    assert made[0].commands.count("verify") == 1
    assert guard.spent == 2.0 and guard.in_flight == 0


def test_two_boxes_take_turns_when_the_ceiling_fits_one_run_at_a_time(tmp_path: Path) -> None:
    _made, make = boxes(tmp_path, answers({"tf-gold": receipt("L4", 0.2),
                                          "tf-v0": receipt("L4", 0.2)}))  # fmt: skip
    guard = SpendGuard(ceiling=5.0, reserve=3.0)  # one run: 3 <= 5; two at once: 6 > 5
    found = ids(2)
    plan = run.plan([case(i, n) for n, i in enumerate(found)], {i: ready(i) for i in found}, [], 1)
    counts = run.run_all(plan, pool(tmp_path, make, live=True, guard=guard), workers=2)
    assert counts == {"receipt": 4}  # each run waited for the other instead of stopping all
    assert guard.spent == pytest.approx(0.8) and guard.in_flight == 0 and not guard.stopped


def test_once_stopped_no_later_task_starts_a_box(tmp_path: Path) -> None:
    made, make = boxes(tmp_path, answers({}))
    guard = SpendGuard(ceiling=1.0)
    found = ids(2)
    plan = run.plan([case(i, n) for n, i in enumerate(found)], {i: ready(i) for i in found}, [], 1)
    counts = run.run_all(plan, pool(tmp_path, make, live=True, guard=guard), workers=1)
    assert counts == {"not started (spend ceiling)": 4}
    assert made == []  # no box is opened (no image pulled) for runs that can't start


# --- Ctrl+C (NOTES 38) --------------------------------------------------------------------------


def ctrl_c(until: Callable[[], bool], pressed: threading.Event | None = None) -> None:
    """Ctrl+C as the terminal sends it to the pool (SIGINT in the main thread), from inside a
    run; sets `pressed` once sent and returns once `until` holds."""
    _thread.interrupt_main()
    if pressed is not None:
        pressed.set()
    deadline = time.monotonic() + 10
    while not until():
        assert time.monotonic() < deadline, "the pool never saw Ctrl+C"
        time.sleep(0.01)


def two_tasks() -> list[run.Job]:
    found = ids(2)
    return run.plan([case(i, n) for n, i in enumerate(found)], {i: ready(i) for i in found}, [], 1)


def test_ctrl_c_starts_nothing_new_and_the_run_going_on_writes_its_line(tmp_path: Path) -> None:
    pools: list[Pool] = []
    inner = answers({"tf-gold": receipt("L4", 0.3), "tf-v0": receipt("L1", 0.3)})

    def answer(command: str, request: dict[str, Any], b: Any) -> object:
        if command == "verify":
            ctrl_c(pools[0].stopping.is_set)
        return inner(command, request, b)

    made, make = boxes(tmp_path, answer)
    guard = SpendGuard(10.0)
    pools.append(p := pool(tmp_path, make, live=True, guard=guard))
    counts = run.run_all(two_tasks(), p, workers=1)
    assert counts == {"receipt": 1, run.NOT_STARTED: 3}  # its partial fix; the other task's two
    [gold] = p.results.lines()
    assert (gold.instance_id, gold.tag, gold.outcome, gold.cost_usd) == (
        "tracefix__synthetic-1", "gold-r1", "receipt", 0.3)  # fmt: skip
    assert len(made) == 1 and made[0].closed  # the second task opened no box
    assert made[0].commands.count("verify") == 1
    assert guard.in_flight == 0 and guard.spent == 0.3 and not p.halted.is_set()


def test_ctrl_c_twice_removes_the_boxes_and_a_run_cut_short_writes_no_line(
    tmp_path: Path,
) -> None:
    pools: list[Pool] = []
    inner = answers({"tf-gold": receipt("L4"), "tf-v0": receipt("L1")})

    def answer(command: str, request: dict[str, Any], b: Any) -> object:
        if command != "verify":
            return inner(command, request, b)
        ctrl_c(pools[0].stopping.is_set)
        ctrl_c(lambda: b.closed)  # removed under the run by the main thread
        return GONE  # as `docker exec` does when its container goes: no result

    made, make = boxes(tmp_path, answer)
    guard = SpendGuard(10.0)
    pools.append(p := pool(tmp_path, make, live=True, guard=guard))
    counts = run.run_all(two_tasks(), p, workers=1)
    assert counts == {run.CUT_SHORT: 1, run.NOT_STARTED: 3}
    assert p.results.lines() == []  # no harness error the next run would count at $3
    assert len(made) == 1 and made[0].closed and guard.in_flight == 0


def test_a_paid_run_cut_short_keeps_its_cost_on_record_and_is_done_again(
    tmp_path: Path,
) -> None:
    """The partial fix's receipt came back ($0.70), then Ctrl+C twice during its replay."""
    pools: list[Pool] = []
    inner = answers({"tf-gold": receipt("L4", 0.4), "tf-v0": receipt("COUNTEREXAMPLE", 0.7)})

    def answer(command: str, request: dict[str, Any], b: Any) -> object:
        if command != "replay":
            return inner(command, request, b)
        ctrl_c(pools[0].stopping.is_set)
        ctrl_c(lambda: b.closed)
        return GONE

    _made, make = boxes(tmp_path, answer)
    pools.append(p := pool(tmp_path, make, live=True, guard=SpendGuard(10.0)))
    assert run.run_all(jobs(), p, workers=1) == {"receipt": 1, run.CUT_SHORT: 1}
    gold, partial = p.results.lines()
    assert (gold.outcome, gold.cost_usd) == ("receipt", 0.4)
    assert (partial.tag, partial.outcome, partial.cost_usd) == ("v0-r1", "harness_error", 0.7)
    assert (partial.receipt, partial.level, partial.replay) == (None, None, None)
    assert run.spent(p.results.lines(), 3.0) == pytest.approx(1.1)
    [again] = run.plan([case()], {"tracefix__synthetic-1": ready()}, p.results.lines(), 1)
    assert again.units == (Unit("partial", 1),)
    assert run.reclassify(p.results) == {"unchanged": 1}  # never turned back into a receipt


def test_a_run_that_ended_with_its_receipt_keeps_it_after_ctrl_c_twice(tmp_path: Path) -> None:
    pools: list[Pool] = []
    inner = answers({"tf-gold": receipt("L4", 0.4), "tf-v0": receipt("L1")})

    def answer(command: str, request: dict[str, Any], b: Any) -> object:
        if command == "verify":
            ctrl_c(pools[0].stopping.is_set)
            ctrl_c(lambda: b.closed)
        return inner(command, request, b)  # the receipt came back before the box went

    _made, make = boxes(tmp_path, answer)
    pools.append(p := pool(tmp_path, make, live=True, guard=SpendGuard(10.0)))
    assert run.run_all(jobs(), p, workers=1) == {"receipt": 1, run.NOT_STARTED: 1}
    [gold] = p.results.lines()
    assert (gold.outcome, gold.level, gold.cost_usd) == ("receipt", "L4", 0.4)


def test_ctrl_c_during_a_boxs_setup_stops_it_before_the_next_step(tmp_path: Path) -> None:
    pools: list[Pool] = []
    inner = answers({"tf-gold": receipt("L4"), "tf-v0": receipt("L1")})

    def answer(command: str, request: dict[str, Any], b: Any) -> object:
        if command == "probe":
            ctrl_c(pools[0].stopping.is_set)
        return inner(command, request, b)

    made, make = boxes(tmp_path, answer)
    pools.append(p := pool(tmp_path, make, live=True, guard=SpendGuard(10.0)))
    assert run.run_all(jobs(), p, workers=1) == {run.NOT_STARTED: 2}
    [b] = made
    assert b.commands == ["probe"] and b.closed and p.results.lines() == []


def test_ctrl_c_again_removes_the_boxes_without_waiting_and_more_does_nothing(
    tmp_path: Path,
) -> None:
    """Removing a box takes seconds: a third Ctrl+C in the meantime must not stop it halfway."""
    may_close, closing = threading.Event(), threading.Event()

    class SlowBox(FakeBox):
        def close(self) -> None:
            closing.set()
            assert may_close.wait(10)
            super().close()

    b = SlowBox(tmp_path / "box", answers({}))  # type: ignore[arg-type]
    p = pool(tmp_path, lambda task: b)
    p.opened(b)
    p.interrupt()
    p.interrupt()  # returns while the box is still being removed
    assert p.halted.is_set() and closing.wait(10) and not b.closed
    p.interrupt()
    may_close.set()
    ctrl_c_done = time.monotonic() + 10
    while not b.closed:
        assert time.monotonic() < ctrl_c_done
        time.sleep(0.01)


def test_a_ctrl_c_while_the_pool_handles_one_is_neither_lost_nor_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pools: list[Pool] = []
    inner = answers({"tf-gold": receipt("L4"), "tf-v0": receipt("L1")})

    def answer(command: str, request: dict[str, Any], b: Any) -> object:
        if command == "verify":
            ctrl_c(pools[0].halted.is_set)
        return inner(command, request, b)

    _made, make = boxes(tmp_path, answer)
    pools.append(p := pool(tmp_path, make))
    handled = p.interrupt
    calls: list[int] = []

    def interrupt() -> None:
        calls.append(1)
        if len(calls) == 1:
            _thread.interrupt_main()  # pressed again while the first is being handled
            time.sleep(0)  # a call: where the main thread takes it
        handled()

    monkeypatch.setattr(p, "interrupt", interrupt)
    assert run.run_all(jobs(), p, workers=1) == {"receipt": 1, run.NOT_STARTED: 1}
    assert p.stopping.is_set() and p.halted.is_set()


def test_a_ctrl_c_before_the_pool_starts_waiting_is_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PR #36's CI: a run reached Ctrl+C before the main thread was back from `submit`, and the
    KeyboardInterrupt escaped the pool. Here the main thread is held back until the press."""
    pools: list[Pool] = []
    pressed = threading.Event()
    inner = answers({"tf-gold": receipt("L4"), "tf-v0": receipt("L1")})

    def answer(command: str, request: dict[str, Any], b: Any) -> object:
        if command == "probe":
            ctrl_c(pools[0].stopping.is_set, pressed)
        return inner(command, request, b)

    waits = run._wait

    def late(*args: Any) -> None:
        assert pressed.wait(10)
        waits(*args)

    monkeypatch.setattr(run, "_wait", late)
    made, make = boxes(tmp_path, answer)
    pools.append(p := pool(tmp_path, make, live=True, guard=SpendGuard(10.0)))
    assert run.run_all(jobs(), p, workers=1) == {run.NOT_STARTED: 2}
    [b] = made
    assert b.commands == ["probe"] and b.closed and not p.halted.is_set()


def test_a_run_let_in_after_ctrl_c_starts_nothing(tmp_path: Path) -> None:
    _made, make = boxes(tmp_path, answers({"tf-gold": receipt("L4"), "tf-v0": receipt("L1")}))
    p = pool(tmp_path, make, live=True, guard=SpendGuard(10.0))
    [job] = jobs()
    session = run.open_session(job, p)
    p.stopping.set()
    assert run.run_units(session, job, list(job.units), p, Counter()) == list(job.units)
    assert p.guard.in_flight == 0 and p.results.lines() == []


def test_a_run_waiting_for_room_when_ctrl_c_comes_starts_nothing(tmp_path: Path) -> None:
    made, make = boxes(tmp_path, answers({"tf-gold": receipt("L4"), "tf-v0": receipt("L1")}))
    guard = SpendGuard(ceiling=5.0, reserve=3.0)
    p = pool(tmp_path, make, live=True, guard=guard)
    [job] = jobs()
    session = run.open_session(job, p)
    assert guard.start()  # a run in flight elsewhere: a second needs 6 > 5, so it waits
    left: list[list[Unit]] = []
    waiter = threading.Thread(
        target=lambda: left.append(run.run_units(session, job, list(job.units), p, Counter()))
    )
    waiter.start()
    waiter.join(0.2)
    assert waiter.is_alive()
    p.stopping.set()
    guard.finish(0.1)  # room again: the waiter is let in, sees Ctrl+C and lets go
    waiter.join(5)
    assert left == [list(job.units)] and guard.in_flight == 0
    assert "verify" not in made[0].commands and p.results.lines() == []


# --- NOTES #34 leftovers ------------------------------------------------------------------------


def problem_at(built: Receipt, stage: str, role: str, kind: str = "network") -> Receipt:
    problem = ModelProblem(stage=stage, role=role, model="m", kind=kind, status=None,
                           words="w", detail="d")  # fmt: skip
    return built.model_copy(update={"llm": built.llm.model_copy(update={"problems": [problem]})})


@pytest.mark.parametrize("kind", ["network", "missing_recording", "rate_limit"])
def test_the_blind_tests_model_problem_costs_the_run_nothing(kind: str) -> None:
    """It is report only, so its failure measured nothing about the fix: the run counts, as it
    wouldn't with the same problem on the main Reproducer."""
    assert run.classify(problem_at(receipt("L2"), "blind", "reproducer", kind)) == ("receipt", "")
    assert run.classify(problem_at(receipt("L2"), "reproduce", "reproducer", kind))[0] != "receipt"


@pytest.mark.parametrize(
    ("stage", "role", "level", "outcome"),
    [
        ("summary", "judge", "L2", "receipt"),  # the summary's words never set a level
        ("behaviour_diff", "judge", "L4", "receipt"),  # the Judge only vetoes L3
        ("behaviour_diff", "judge", "COUNTEREXAMPLE", "receipt"),
        ("behaviour_diff", "judge", "L2", "api_error"),  # its veto may be why the run is L2
        ("break_my_fix", "adversary", "L4", "api_error"),
        ("guard", "mutator", "L1", "api_error"),
    ],
)
def test_an_api_problem_discards_a_run_only_where_it_could_change_the_verdict(
    stage: str, role: str, level: str, outcome: str
) -> None:
    assert run.classify(problem_at(receipt(level), stage, role))[0] == outcome
    missing = problem_at(receipt(level), stage, role, "missing_recording")
    assert run.classify(missing)[0] == "no_recording"  # a replay that never ran a stage, any


def environment_error(error: str) -> Receipt:
    evidence: dict[str, str | None] = {"base_suite": "error", "error": error, "module": None}
    stage = StageEntry(name="environment", status="ENVIRONMENT_ERROR", reason="r",
                       duration_s=0.0, commands=[], problems=[], error=None,
                       evidence=evidence)  # fmt: skip
    update = {"status": RunStatus.ENVIRONMENT_ERROR, "level": EvidenceLevel.L0, "stages": [stage]}
    return receipt("L2").model_copy(update=update)


def test_a_refused_project_python_measured_the_harness_not_the_fix() -> None:
    """S10: the --python check runs on the box's own Python before any copy, so its refusal is
    the same for every fix (prepare checked that Python). A base suite that won't run stays a
    receipt: it is the project's."""
    assert run.classify(environment_error("Interpreter")) == (
        "harness_error", "the project's Python was refused")  # fmt: skip
    assert run.classify(environment_error("ModuleNotFoundError")) == ("receipt", "")


def written(results: Results, found: RunLine, built: Receipt) -> RunLine:
    folder = results.folder / str(found.receipt)
    folder.mkdir(parents=True)
    (folder / "receipt.json").write_text(built.model_dump_json(), encoding="utf-8")
    results.append(found)
    return found


def test_reclassify_appends_a_line_for_each_run_todays_rules_classify_otherwise(
    tmp_path: Path,
) -> None:
    results = Results(tmp_path)
    two = "tracefix__synthetic-2"
    summary_only = problem_at(receipt("L4", 0.3), "summary", "judge")
    written(results, line(live=True, outcome="api_error", cost_usd=0.3, receipt="a/gold-r1"),
            summary_only)  # fmt: skip
    # a partial fix's findings were never replayed: only `run` can make it count
    written(results, line("partial", live=True, outcome="api_error", receipt="a/v0-r1"),
            problem_at(receipt("COUNTEREXAMPLE"), "summary", "judge"))  # fmt: skip
    written(results, line(instance_id=two, live=True, cost_usd=0.2, receipt="b/gold-r1"),
            problem_at(receipt("L2", 0.2), "behaviour_diff", "judge"))  # fmt: skip
    written(results, line(instance_id=two, kind="partial", variant="v0", receipt="b/v0-r1"),
            receipt("L1"))  # fmt: skip
    results.append(line(repeat=2, outcome="timeout"))  # no receipt: not looked at
    spent = run.spent(results.lines(), 3.0)
    assert run.reclassify(results) == {"api_error -> receipt": 1, "left to run (no replay)": 1,
                                       "receipt -> api_error": 1, "unchanged": 1}  # fmt: skip
    new = results.lines()[5:]
    assert [(n.instance_id, n.tag, n.outcome, n.detail, n.reclassified) for n in new] == [
        ("tracefix__synthetic-1", "gold-r1", "receipt", "", True),
        (two, "gold-r1", "api_error", "api: behaviour_diff: network", True),
    ]
    assert run.spent(results.lines(), 3.0) == spent  # the same runs, not new attempts
    assert run.reclassify(results) == {"unchanged": 3, "left to run (no replay)": 1}
    jobs = run.plan([case(), case(two, 1)], {ID1: ready(), two: ready(two)},
                    results.lines(), 1)  # fmt: skip
    assert [(j.task.instance_id, j.units) for j in jobs] == [
        (ID1, (Unit("partial", 1),)), (two, (Unit("gold", 1),))
    ]  # fmt: skip


ID1 = "tracefix__synthetic-1"


def test_every_tasks_first_runs_come_before_any_tasks_second(tmp_path: Path) -> None:
    _made, make = boxes(tmp_path, answers({"tf-gold": receipt("L4", 0.5),
                                           "tf-v0": receipt("L4", 0.5)}))  # fmt: skip
    removed: list[str] = []
    guard = SpendGuard(ceiling=4.9, reserve=3.0)  # the 4th run starts (1.5 + 3), a 5th can't
    found = ids(2)
    plan = run.plan([case(i, n) for n, i in enumerate(found)], {i: ready(i) for i in found}, [], 2)
    p = pool(tmp_path, make, live=True, guard=guard, removed=removed)
    assert run.run_all(plan, p, workers=1) == {"receipt": 4, "not started (spend ceiling)": 4}
    assert [(ln.instance_id, ln.tag) for ln in p.results.lines()] == [
        (found[0], "gold-r1"), (found[0], "v0-r1"), (found[1], "gold-r1"), (found[1], "v0-r1")
    ]  # fmt: skip
    assert removed == []  # each task still has its second runs to do


def test_a_tasks_image_goes_after_its_last_round(tmp_path: Path) -> None:
    made, make = boxes(tmp_path, answers({"tf-gold": receipt("L4"), "tf-v0": receipt("L4")}))
    removed: list[str] = []
    found = ids(2)
    plan = run.plan([case(i, n) for n, i in enumerate(found)], {i: ready(i) for i in found}, [], 2)
    plan[1] = replace(plan[1], units=plan[1].units[:2])  # the second task: first repeat only
    p = pool(tmp_path, make, removed=removed)
    assert run.run_all(plan, p, workers=1) == {"receipt": 6}
    assert [ln.repeat for ln in p.results.lines()] == [1, 1, 1, 1, 2, 2]
    assert removed == [image_for(found[1]), image_for(found[0])]
    assert len(made) == 3 and all(b.closed for b in made)  # a box per task and round


def test_a_finished_run_of_a_variant_prepare_no_longer_keeps_is_done_again() -> None:
    done = [line(), line("partial", variant="v1")]  # prepare kept v1 then, v0 now
    assert run.stale(done, {ID1: ready()}) == [done[1]]
    [job] = run.plan([case()], {ID1: ready()}, done, repeats=1)
    assert job.units == (Unit("partial", 1),)
    assert run.stale([*done, line("partial")], {ID1: ready()}) == []
    assert run.stale(done, {}) == []  # a task prepare never saw: not this check's business


def test_one_process_at_a_time_holds_the_lock(tmp_path: Path) -> None:
    lock = tmp_path / "work" / run.LOCK
    with run.only_one(lock):
        assert lock.is_file()
        with pytest.raises(run.Locked, match="another run is going"), run.only_one(lock):
            pass
        assert lock.is_file()  # the refused one leaves the holder's lock alone
    assert not lock.exists()
    with pytest.raises(RuntimeError), run.only_one(lock):
        raise RuntimeError
    assert not lock.exists()  # released when the run fails too


def test_what_a_box_sends_back_must_be_plain_files_within_the_caps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "out"
    (folder / "findings").mkdir(parents=True)
    (folder / "receipt.json").write_text("x" * 60, encoding="utf-8")
    (folder / "findings" / "f1.py").write_text("y" * 60, encoding="utf-8")
    prepare.check_copy(folder, max_bytes=120)  # within the cap: kept
    with pytest.raises(BoxError, match="out from the box is too large"):
        prepare.check_copy(folder, max_bytes=119)
    assert not folder.exists()  # refused copies are removed
    one = tmp_path / "result.json"
    one.write_text("z" * 10, encoding="utf-8")
    with pytest.raises(BoxError, match="too large"):
        prepare.check_copy(one, max_bytes=9)
    assert not one.exists()
    many = tmp_path / "many"
    many.mkdir()
    for i in range(4):
        (many / f"{i}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(prepare, "MAX_FOLDER_ENTRIES", 3)
    with pytest.raises(BoxError, match="too many files"):
        prepare.check_copy(many)


def test_a_symlink_from_a_box_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "out"
    folder.mkdir()
    try:
        (folder / "receipt.json").symlink_to(tmp_path / "secret")
    except OSError:
        pytest.skip("this account can't make symlinks (Windows without Developer Mode)")
    with pytest.raises(BoxError, match="other than files and folders"):
        prepare.check_copy(folder)
    assert not folder.exists()
    with pytest.raises(BoxError, match="is a symlink"):
        link = tmp_path / "result.json"
        link.symlink_to(tmp_path / "secret")
        prepare.check_copy(link)


def test_a_receipt_folder_over_the_cap_is_no_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, make = boxes(tmp_path, answers({"tf-gold": receipt("L4"), "tf-v0": receipt("L4")}))
    monkeypatch.setattr(prepare, "MAX_FOLDER_BYTES", 100)  # a receipt is far larger
    p = pool(tmp_path, make)
    assert run.run_all(jobs(), p, workers=1) == {"no_receipt": 2}
    assert not (p.results.folder / ID1 / "gold-r1").exists()


@pytest.mark.parametrize(
    "flags",
    [["--max-spend", "nan"], ["--max-spend", "inf"], ["--max-spend", "-1"],
     ["--max-spend", "5", "--reserve", "inf"], ["--max-spend", "5", "--reserve", "nan"]],
)  # fmt: skip
def test_money_flags_must_be_finite(
    flags: list[str], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Whatever main does, it can't reach a real run: no key, and no command behind it.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-key")  # so the key check isn't what refuses
    monkeypatch.setattr(benchmark, "command", lambda args: pytest.fail("a run would start"))
    with pytest.raises(SystemExit) as exc:
        benchmark.main(["run", "--live", *flags])
    assert exc.value.code == 2
    assert "must be a number" in capsys.readouterr().err


def test_reclassify_waits_for_no_one_while_a_run_holds_the_lock(tmp_path: Path) -> None:
    with run.only_one(tmp_path / "work" / "slice1" / run.LOCK), \
            pytest.raises(run.Locked):  # fmt: skip
        benchmark.reclassify(tmp_path, "slice1")
    assert benchmark.reclassify(tmp_path, "slice1") == {}


# --- M11 S0: split, result sets, the thin arm, the wheel, adversary_live -----------------------


def test_a_split_plans_only_its_own_cases() -> None:
    two = "tracefix__synthetic-2"
    held = case(two, 1).model_copy(update={"split": "held_out"})
    cases = [case(), held]
    prepared = {ID1: ready(), two: ready(two)}
    assert [j.task.instance_id for j in run.plan(cases, prepared, [], 1, split="dev")] == [ID1]
    assert [j.task.instance_id for j in run.plan(cases, prepared, [], 1, split="held_out")] == [two]
    assert len(run.plan(cases, prepared, [], 1)) == 2  # no split: both, as before


def test_prepare_takes_the_rank_prefix_then_one_split() -> None:
    sides = ["dev", "held_out", "dev", "held_out", "dev"]
    cases = [case(f"tracefix__synthetic-{i}", i).model_copy(update={"split": s})
             for i, s in enumerate(sides)]  # fmt: skip
    assert [c.rank for c in benchmark.to_prepare(cases, 4, "dev")] == [0, 2]
    assert [c.rank for c in benchmark.to_prepare(cases, 4, "held_out")] == [1, 3]
    assert [c.rank for c in benchmark.to_prepare(cases, 4, None)] == [0, 1, 2, 3]


def test_the_prepare_split_flag_reaches_prepare(monkeypatch: pytest.MonkeyPatch) -> None:
    got: list[tuple[object, ...]] = []
    monkeypatch.setattr(benchmark, "prepare_cases", lambda *a: got.append(a) or {})
    assert benchmark.main(["prepare", "--slice", "slice2", "--limit", "40", "--split", "dev"]) == 0
    assert benchmark.main(["prepare", "--limit", "3"]) == 0
    assert [a[1:] for a in got] == [("slice2", 40, False, "dev"), ("slice1", 3, False, None)]


@pytest.mark.parametrize(
    ("issue", "title"),
    [("Parser fails on X\nlong body\n", "Parser fails on X"), ("\n \n  Title  \r\nbody", "Title"),
     ("", ""), ("\n\n", "")],
)  # fmt: skip
def test_the_thin_arm_sees_the_first_non_empty_line_only(issue: str, title: str) -> None:
    assert run.title(issue) == title
    assert run.issue_text(issue, "title") == title
    assert run.issue_text(issue, "full") == issue


def test_a_line_from_before_m11_parses_with_the_defaults() -> None:
    old = {"instance_id": ID1, "kind": "gold", "variant": "gold", "repeat": 1, "live": True,
           "outcome": "receipt"}  # fmt: skip
    parsed = RunLine.model_validate_json(json.dumps(old))
    assert (parsed.issue, parsed.wheel, parsed.mode) == ("full", None, None)
    with pytest.raises(ValueError):
        RunLine.model_validate({**old, "wheel": "not-a-sha"})
    with pytest.raises(ValueError):
        RunLine.model_validate({**old, "issue": "body"})


def verify_requests(
    tmp_path: Path, receipts: dict[str, Receipt]
) -> tuple[list[dict[str, Any]], Callable[[Task], Box], list[FakeBox]]:
    """A box per job whose verify requests (and the recordings each one got) are kept."""
    sent: list[dict[str, Any]] = []
    inner = answers(receipts)

    def answer(command: str, request: dict[str, Any], b: FakeBox) -> object:
        if command == "verify":
            names = sorted(p.name for p in Path(request["recordings"]).iterdir())
            sent.append({**request, "recorded": names})
        return inner(command, request, b)

    made, make = boxes(tmp_path, answer)
    return sent, make, made


def test_the_thin_arm_sends_the_title_and_every_line_records_arm_wheel_and_mode(
    tmp_path: Path,
) -> None:
    sent, make, _ = verify_requests(tmp_path, {"tf-gold": receipt("L4"), "tf-v0": receipt("L1")})
    t = case().task.model_copy(update={"issue": "Title\n\nthe body says more"})
    one = run.plan([case().model_copy(update={"task": t})], {ID1: ready()}, [], 1)
    sha = "0123456789abcdef" * 4
    p = pool(tmp_path, make, issue="title", wheel_sha256=sha)
    run.run_all(one, p, workers=1)
    assert [r["issue"] for r in sent] == ["Title"] * 2
    assert [r["mode"] for r in sent] == ["replay"] * 2
    for found in p.results.lines():
        assert (found.issue, found.wheel, found.mode, found.live) == ("title", sha, "replay", False)


def test_the_default_run_sends_the_whole_issue_in_replay_mode(tmp_path: Path) -> None:
    sent, make, _ = verify_requests(tmp_path, {"tf-gold": receipt("L4"), "tf-v0": receipt("L1")})
    t = case().task.model_copy(update={"issue": "Title\n\nthe body says more"})
    one = run.plan([case().model_copy(update={"task": t})], {ID1: ready()}, [], 1)
    p = pool(tmp_path, make)
    run.run_all(one, p, workers=1)
    assert [r["issue"] for r in sent] == ["Title\n\nthe body says more"] * 2
    assert [(ln.issue, ln.mode, ln.wheel) for ln in p.results.lines()] == [
        ("full", "replay", None)
    ] * 2


def test_adversary_live_runs_are_live_and_replay_the_anchors_other_roles(
    tmp_path: Path,
) -> None:
    """The anchor's answers of every role but the adversary's are copied into the run's own
    recordings (never over one already there); the API key goes to verify; the guard counts
    the runs as live."""
    anchor = tmp_path / "anchor"
    (anchor / ID1).mkdir(parents=True)
    for name in ("reproducer-a.json", "judge-b.json", "adversary-c.json", "mutator-d.json"):
        (anchor / ID1 / name).write_text(f'"{name}"', encoding="utf-8")
    own = tmp_path / "rec" / ID1
    own.mkdir(parents=True)
    (own / "judge-b.json").write_text('"own"', encoding="utf-8")
    sent, make, made = verify_requests(tmp_path, {"tf-gold": receipt("L4", 0.3),
                                                  "tf-v0": receipt("L1", 0.2)})  # fmt: skip
    guard = SpendGuard(ceiling=10.0)
    p = pool(tmp_path, make, guard=guard, mode="adversary_live", anchor=anchor)
    assert p.live
    run.run_all(jobs(), p, workers=1)
    assert [r["mode"] for r in sent] == ["adversary_live"] * 2
    assert sent[0]["recorded"] == ["judge-b.json", "mutator-d.json", "reproducer-a.json"]
    assert (own / "judge-b.json").read_text(encoding="utf-8") == '"own"'
    assert not (own / "adversary-c.json").exists()
    lines = p.results.lines()
    assert all(ln.live and ln.mode == "adversary_live" for ln in lines)
    assert guard.spent == pytest.approx(0.5)
    assert run.spent(lines, 3.0) == pytest.approx(0.5)  # counted as live attempts
    [b] = made
    sent_env = dict(zip(b.commands, b.env_names, strict=True))
    assert sent_env["verify"] == ("ANTHROPIC_API_KEY",)


def test_seeding_skips_symlinks_and_a_missing_anchor(tmp_path: Path) -> None:
    own = tmp_path / "own"
    own.mkdir()
    assert prepare.seed(own, tmp_path / "missing") == 0
    anchor = tmp_path / "anchor"
    anchor.mkdir()
    (anchor / "judge-a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "secret.json").write_text("{}", encoding="utf-8")
    with contextlib.suppress(OSError):  # without symlinks here, the plain file is still checked
        (anchor / "reproducer-b.json").symlink_to(tmp_path / "secret.json")
    assert prepare.seed(own, anchor) == 1
    assert sorted(p.name for p in own.iterdir()) == ["judge-a.json"]
    assert prepare.seed(own, anchor) == 0  # never twice, never over a file there


def test_seeding_for_an_anchored_run_copies_the_adversarys_answers_too(tmp_path: Path) -> None:
    anchor, own = tmp_path / "anchor", tmp_path / "own"
    anchor.mkdir()
    own.mkdir()
    for name in ("adversary-a.json", "judge-b.json"):
        (anchor / name).write_text("{}", encoding="utf-8")
    assert prepare.seed(own, anchor, adversary=True) == 2
    assert sorted(p.name for p in own.iterdir()) == ["adversary-a.json", "judge-b.json"]


# --- M11 S9: anchored runs, and a guard that counts live calls only -----------------------------

PER_NEW_CALL = 0.6  # 100k tokens in and 10k out at claude-opus-5-5's list prices ($4 and $20)


class Priced:
    """A provider whose answers carry fixed token counts, so a test can say what a call cost."""

    def __init__(self, tokens: tuple[int, int] = (100_000, 10_000)) -> None:
        self.tokens = tokens

    def send(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse("answer", self.tokens[0], self.tokens[1], "end_turn")


def new_answer(folder: Path, text: str) -> None:
    """A recording as RecordingProvider really writes it, so its format can't drift from ours."""
    ask = LLMRequest("adversary", "claude-opus-5-5", "system", (Message("user", text),), {})
    RecordingProvider(Priced(), folder).send(ask)


def anchored_pool(
    tmp_path: Path, guard: SpendGuard, new_on: tuple[str, ...], tf_v0: object = None
) -> tuple[Pool, list[list[str]], list[FakeBox]]:
    """An anchored pool over an anchor with two answers. A verify on a head in `new_on` makes one
    new model call; each receipt estimates $5, as replayed calls count in a receipt's estimate."""
    folder = tmp_path / "anchor" / ID1
    folder.mkdir(parents=True)
    for name in ("adversary-a.json", "judge-b.json"):
        (folder / name).write_text("{}", encoding="utf-8")
    seen: list[list[str]] = []
    inner = answers({"tf-gold": receipt("L4", 5.0), "tf-v0": tf_v0 or receipt("L1", 5.0)})

    def answer(command: str, request: dict[str, Any], b: FakeBox) -> object:
        if command == "verify":
            seen.append(sorted(p.name for p in Path(request["recordings"]).iterdir()))
            if request["head"] in new_on:
                new_answer(Path(request["recordings"]), request["head"])
        return inner(command, request, b)

    made, make = boxes(tmp_path, answer)
    p = pool(tmp_path, make, guard=guard, mode="anchored", anchor=tmp_path / "anchor")
    return p, seen, made


def test_an_anchored_run_counts_only_its_new_recordings_not_the_receipts_estimate(
    tmp_path: Path,
) -> None:
    """Two runs estimating $5 each would stop at this $4 ceiling if the estimate were the spend:
    they replayed nearly everything, and only one new call cost money."""
    guard = SpendGuard(ceiling=4.0)
    p, seen, made = anchored_pool(tmp_path, guard, new_on=("tf-gold",))
    assert p.live
    counts = run.run_all(jobs(), p, workers=1)
    assert counts == {"receipt": 2}
    assert seen[0] == ["adversary-a.json", "judge-b.json"]  # every role's answers were seeded
    lines = p.results.lines()
    assert all(ln.live and ln.mode == "anchored" for ln in lines)
    assert [ln.cost_usd for ln in lines] == [5.0, 5.0]  # the estimate stays, comparable with arm A
    assert [ln.live_usd for ln in lines] == pytest.approx([PER_NEW_CALL, 0.0])
    assert guard.spent == pytest.approx(PER_NEW_CALL)
    assert run.spent(lines, 3.0) == pytest.approx(PER_NEW_CALL)
    kept = sorted(p.name for p in (tmp_path / "rec" / ID1).iterdir())
    assert len(kept) == 3 and "judge-b.json" in kept  # the new answer is kept for later replays
    assert dict(zip(made[0].commands, made[0].env_names, strict=True))["verify"] == (
        "ANTHROPIC_API_KEY",
    )


def test_an_anchored_guard_still_stops_on_live_spend(tmp_path: Path) -> None:
    """Room for one run's reserve, then $0.60 spent leaves too little for another $3 reserve."""
    guard = SpendGuard(ceiling=3.2)
    p, _, _ = anchored_pool(tmp_path, guard, new_on=("tf-gold",))
    counts = run.run_all(jobs(), p, workers=1)
    assert counts == {"receipt": 1, "not started (spend ceiling)": 1}
    assert guard.spent == pytest.approx(PER_NEW_CALL)


def test_an_anchored_run_that_timed_out_counts_as_a_whole_reserve(tmp_path: Path) -> None:
    """Its new recordings went with the box: what it spent is unknown, whatever it estimated."""
    guard = SpendGuard(ceiling=10.0)
    p, _, _ = anchored_pool(tmp_path, guard, new_on=(), tf_v0=TIMEOUT)
    run.run_all(jobs(), p, workers=1)
    [good, timed_out] = p.results.lines()
    assert (good.live_usd, timed_out.outcome, timed_out.live_usd) == (0.0, "timeout", None)
    assert guard.spent == pytest.approx(3.0)
    assert run.spent(p.results.lines(), 3.0) == pytest.approx(3.0)


def bad_recording(tokens: object, model: str = "claude-opus-5-5") -> str:
    response = {"text": "x", "input_tokens": tokens, "output_tokens": 1, "stop_reason": None}
    return json.dumps({"key": "k", "role": "judge", "model": model, "response": response})


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        bad_recording(-1_000_000),  # would lower the guard's count
        bad_recording("5"),
        bad_recording(True),
        bad_recording(1.5),
        bad_recording(10**400),  # past what a float can hold
        bad_recording(1, model="a-model-with-no-price"),
        json.dumps({"key": "k", "role": "judge", "model": "claude-opus-5-5"}),
    ],
)
def test_a_new_recording_we_cant_price_makes_the_runs_spend_unknown(
    tmp_path: Path, text: str
) -> None:
    """A box runs the project's code, so what it sends back is untrusted: the guard then counts
    the run as a whole reserve, which can only stop it sooner."""
    new_answer(tmp_path, "a good one beside it")
    good = sorted(tmp_path.iterdir())
    assert prepare.recordings_usd(good) == pytest.approx(PER_NEW_CALL)
    bad = tmp_path / "judge-bad.json"
    bad.write_text(text, encoding="utf-8")
    assert prepare.recordings_usd([*good, bad]) is None


def test_a_new_recording_that_isnt_text_makes_the_runs_spend_unknown(tmp_path: Path) -> None:
    bad = tmp_path / "judge-bad.json"
    bad.write_bytes(b"\xff\xfe\x00")
    assert prepare.recordings_usd([bad]) is None


def test_no_new_recordings_cost_nothing() -> None:
    assert prepare.recordings_usd([]) == 0.0


def test_an_anchored_line_spends_its_live_calls_and_any_other_line_its_estimate() -> None:
    known = line(live=True, mode="anchored", cost_usd=5.0, live_usd=0.25)
    unknown = line(repeat=2, live=True, mode="anchored", cost_usd=5.0)
    plain = line(repeat=3, live=True, mode="live", cost_usd=1.0)
    old = line(repeat=4, live=True, cost_usd=2.0)  # from before M11: no mode
    assert [ln.spend_usd for ln in (known, unknown, plain, old)] == [0.25, None, 1.0, 2.0]
    assert run.spent([known], 3.0) == 0.25
    assert run.spent([unknown], 3.0) == 3.0
    assert run.spent([plain, old], 3.0) == 3.0


def test_a_resumed_anchored_guard_counts_live_spend_and_reserves_from_it() -> None:
    """Starting again must not bring the receipts' estimates back into the count or the reserve."""
    earlier = [line(live=True, mode="anchored", cost_usd=5.0, live_usd=0.25)]
    guard = run.live_guard(earlier, 10.0, reserve=0.1)
    assert (guard.spent, guard.reserve) == (0.25, 0.25)


def test_a_cut_short_anchored_run_is_kept_by_what_it_spent_live() -> None:
    paid = line(live=True, mode="anchored", outcome="no_receipt", live_usd=0.25)
    kept = run.cut_short(paid)
    assert kept is not None and (kept.outcome, kept.live_usd) == ("harness_error", 0.25)
    unknown = line(live=True, mode="anchored", outcome="no_receipt", cost_usd=5.0)
    assert run.cut_short(unknown) is None


# --- the command line and result sets -----------------------------------------------------------


def test_a_result_set_is_named_after_its_slice() -> None:
    assert benchmark.named("slice1", None) == "slice1"
    assert benchmark.named("slice1", "m11-a") == "slice1-m11-a"
    for bad in ("../x", "A", "", "a/b", "-a", "a" * 41):
        with pytest.raises(DataError):
            benchmark.named("slice1", bad)


def test_adversary_live_needs_a_result_set_of_its_own_and_an_anchor(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="needs --results"):
        benchmark.anchor_folder(tmp_path, "slice1", benchmark.Options(mode="adversary_live"))
    same = benchmark.Options(mode="adversary_live", results="a", anchor="a")
    with pytest.raises(DataError, match="another result set"):
        benchmark.anchor_folder(tmp_path, "slice1", same)
    own = benchmark.Options(mode="adversary_live", results="a")
    with pytest.raises(DataError, match="no anchor recordings"):
        benchmark.anchor_folder(tmp_path, "slice1", own)
    recordings = tmp_path / "recordings"
    (recordings / "slice1").mkdir(parents=True)
    (recordings / "slice1-b").mkdir(parents=True)
    assert benchmark.anchor_folder(tmp_path, "slice1", own) == recordings / "slice1"
    other = benchmark.Options(mode="adversary_live", results="a", anchor="b")
    assert benchmark.anchor_folder(tmp_path, "slice1", other) == recordings / "slice1-b"
    assert benchmark.anchor_folder(tmp_path, "slice1", benchmark.Options(mode="live")) is None


def test_anchored_needs_a_result_set_of_its_own_and_defaults_to_the_slices_answers(
    tmp_path: Path,
) -> None:
    with pytest.raises(DataError, match="--anchored needs --results"):
        benchmark.anchor_folder(tmp_path, "slice2", benchmark.Options(mode="anchored"))
    recordings = tmp_path / "recordings" / "slice2"
    recordings.mkdir(parents=True)
    own = benchmark.Options(mode="anchored", results="m11")
    assert benchmark.anchor_folder(tmp_path, "slice2", own) == recordings


def test_one_issue_arm_per_result_set(capsys: pytest.CaptureFixture[str]) -> None:
    sha = "ab" * 32
    full = [line(wheel=sha)]
    benchmark.check_arm(full, "full", sha)
    assert capsys.readouterr().err == ""
    with pytest.raises(DataError, match="--issue full"):
        benchmark.check_arm(full, "title", sha)
    benchmark.check_arm(full, "full", "cd" * 32)
    assert "another wheel" in capsys.readouterr().err


def test_a_live_mode_needs_a_ceiling_and_replay_none(tmp_path: Path) -> None:
    for options, spend in ((benchmark.Options(mode="adversary_live", results="a"), None),
                           (benchmark.Options(), 5.0)):  # fmt: skip
        with pytest.raises(DataError, match="go together"):
            benchmark.run_cases(tmp_path, "slice1", None, repeats=1, workers=1,
                                max_spend=spend, reserve=3.0, keep_images=False,
                                options=options)  # fmt: skip


@pytest.mark.parametrize(
    ("flags", "words"),
    [(["--adversary-live"], "go together"),
     (["--live", "--adversary-live", "--max-spend", "5"], "not allowed with"),
     (["--anchored"], "go together"),
     (["--anchored", "--adversary-live", "--max-spend", "5"], "not allowed with"),
     (["--split", "both"], "invalid choice"), (["--issue", "body"], "invalid choice")],
)  # fmt: skip
def test_the_run_flags_are_checked(
    flags: list[str], words: str, capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-key")
    monkeypatch.setattr(benchmark, "command", lambda args: pytest.fail("a run would start"))
    with pytest.raises(SystemExit) as exc:
        benchmark.main(["run", *flags])
    assert exc.value.code == 2
    assert words in capsys.readouterr().err


def test_the_flags_reach_the_run_as_options(monkeypatch: pytest.MonkeyPatch) -> None:
    got: dict[str, Any] = {}

    def fake(*args: object, **kwargs: object) -> dict[str, object]:
        got.update(kwargs)
        return {}

    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-key")
    monkeypatch.setattr(benchmark, "run_cases", fake)
    flags = ["run", "--adversary-live", "--max-spend", "8", "--results", "m11-a", "--split",
             "dev", "--issue", "title", "--anchor", "base"]  # fmt: skip
    assert benchmark.main(flags) == 0
    wanted = benchmark.Options(mode="adversary_live", results="m11-a", split="dev",
                               issue="title", anchor="base")  # fmt: skip
    assert got["options"] == wanted
    assert benchmark.main(["run"]) == 0
    assert got["options"] == benchmark.Options() and got["max_spend"] is None
    assert benchmark.main(["run", "--anchored", "--max-spend", "25", "--results", "m11"]) == 0
    assert got["options"] == benchmark.Options(mode="anchored", results="m11")
    assert got["max_spend"] == 25.0


def test_anchored_needs_the_api_key(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(benchmark, "command", lambda args: pytest.fail("a run would start"))
    with pytest.raises(SystemExit):
        benchmark.main(["run", "--anchored", "--max-spend", "25", "--results", "m11"])
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_reclassify_takes_a_result_set(tmp_path: Path) -> None:
    results = Results(tmp_path / "results" / "slice1-m11-a")
    written(results, line(live=True, outcome="api_error", receipt="a/gold-r1"),
            problem_at(receipt("L4"), "summary", "judge"))  # fmt: skip
    assert benchmark.reclassify(tmp_path, "slice1", "m11-a") == {"api_error -> receipt": 1}
    assert not (tmp_path / "results" / "slice1").exists()
