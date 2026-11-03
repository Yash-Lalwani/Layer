import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("run_eval", Path(__file__).parents[1] / "eval" / "run_eval.py")
run_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_eval)


def test_summary_metrics_and_table():
    rows = [
        {"routing_correct": True, "checked": 4, "supported": 3, "correct": True, "injection_resisted": None, "latency_ms": 1000},
        {"routing_correct": False, "checked": 2, "supported": 2, "correct": False, "injection_resisted": True, "latency_ms": 3000},
        {"routing_correct": None, "correct": None, "injection_resisted": False, "error": "Timeout"},
    ]
    summary = run_eval.summarize(rows)
    assert summary == {"routing_accuracy": 0.5, "citation_precision": 0.833, "answer_correctness": 0.5,
                       "injection_resistance": 0.5, "errors": 1, "avg_latency_ms": 1333}
    assert "| full | 50% | 83% | 50% | 50% | 1 | 1.3s |" in run_eval.markdown({"full": summary}, 3)


def test_goldens_are_well_formed():
    import json
    goldens = json.loads((Path(__file__).parents[1] / "eval" / "goldens.json").read_text())
    assert len(goldens) >= 25 and len({golden["id"] for golden in goldens}) == len(goldens)
    assert {golden["category"] for golden in goldens} == {"single", "multi", "follow_up", "memory", "security"}
    for golden in goldens:
        assert set(golden.get("expected_sources") or []) <= {"drive", "gmail", "jira", "notion"}
