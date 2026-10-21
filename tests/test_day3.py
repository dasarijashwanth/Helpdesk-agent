"""Day 3 tests: golden set integrity, recall@5, and threshold calibration."""

import pytest
from fastapi.testclient import TestClient

from app import answer as answer_module
from app.kb import KnowledgeBase
from app.main import app
from evals.calibrate import choose_operating_point, sweep_thresholds
from evals.golden import LABELS, load_golden_set, recall_at_5, run_cases, summarize

client = TestClient(app)


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase.load()


@pytest.fixture(scope="module")
def cases():
    return load_golden_set()


def test_golden_set_has_100_cases(cases):
    assert len(cases) == 100


def test_golden_set_ids_unique(cases):
    ids = [c["id"] for c in cases]
    assert len(set(ids)) == len(ids)


def test_golden_set_labels_and_articles_valid(cases, kb):
    article_ids = {a["id"] for a in kb.articles}
    for case in cases:
        assert case["label"] in LABELS
        assert case["expected_action"] in ("answered", "handoff", "escalate")
        if case["label"] == "covered":
            assert case["expected_article_id"] in article_ids
            assert case["expected_action"] == "answered"
        else:
            assert case["expected_article_id"] is None


def test_golden_set_distribution(cases):
    by_label = {}
    for case in cases:
        by_label[case["label"]] = by_label.get(case["label"], 0) + 1
    assert by_label["covered"] == 60
    assert by_label["kb_gap"] >= 10
    assert by_label["contradiction"] >= 5
    assert by_label["prompt_injection"] >= 5
    routing = (
        by_label["billing_dispute"]
        + by_label["account_action"]
        + by_label["bug_incident"]
    )
    assert routing >= 10


def test_recall_at_5(kb, cases):
    # Measured at 1.0 on Day 3; the floor leaves room for KB edits.
    assert recall_at_5(kb, cases) >= 0.95


def test_shipped_threshold_matches_calibration(kb, cases):
    rows = sweep_thresholds(kb, cases)
    chosen = choose_operating_point(rows)
    assert chosen["threshold"] == answer_module.CONFIDENCE_THRESHOLD
    assert chosen["answered_precision"] >= 0.95


def test_golden_set_action_accuracy_at_shipped_threshold(kb, cases):
    summary = summarize(run_cases(kb, cases))
    # Measured at 0.97 on Day 3.
    assert summary["action_accuracy"] >= 0.95
    assert summary["answered_precision"] >= 0.95


def test_all_injections_escalate(kb, cases):
    injections = [c for c in cases if c["label"] == "prompt_injection"]
    results = run_cases(kb, injections)
    assert all(r["action"] == "escalate" for r in results)


def test_all_routing_cases_hand_off(kb, cases):
    routing_labels = {"billing_dispute", "account_action", "bug_incident"}
    routing = [c for c in cases if c["label"] in routing_labels]
    results = run_cases(kb, routing)
    assert all(r["action"] == "handoff" for r in results)


def test_threshold_override_is_restored(kb, cases):
    before = answer_module.CONFIDENCE_THRESHOLD
    run_cases(kb, cases[:5], threshold=0.5)
    assert answer_module.CONFIDENCE_THRESHOLD == before


def test_marginal_day1_phrasing_hands_off_at_calibrated_threshold():
    # The Day 1 attachments phrasing scores 0.9347 against g4, just under
    # the 0.94 operating point, so the calibrated pipeline hands it to a
    # human instead of answering. This pins the tradeoff on purpose.
    resp = client.post("/tickets/answer", json={
        "ticket_id": "T-D3-1",
        "subject": "Attachments will not upload",
        "body": "Uploading a 40 MB video fails every time, what are the limits?",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "handoff"
    assert data["handoff_reason"] == "low_retrieval_confidence"
