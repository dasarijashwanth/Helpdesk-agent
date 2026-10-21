"""Day 1 API tests for helpdesk-agent."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post(body: dict) -> dict:
    resp = client.post("/tickets/answer", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["kb_articles"] == 30


def test_billing_question_answered():
    data = _post({
        "ticket_id": "T-1001",
        "subject": "How do I update my credit card?",
        "body": "My card expired and I need to replace the payment method on file.",
    })
    assert data["ticket_id"] == "T-1001"
    assert data["action"] == "answered"
    assert data["answer"]
    assert data["confidence"] > 0.35
    assert data["citations"]
    assert data["citations"][0]["article_id"] == "b2"


def test_account_question_answered():
    data = _post({
        "ticket_id": "T-1002",
        "subject": "Forgot password help",
        "body": "I cannot sign in, the reset link never arrived in my inbox.",
    })
    assert data["action"] == "answered"
    assert data["citations"][0]["article_id"] == "a1"


def test_bug_question_answered():
    # Rewritten on Day 3: the original phrasing ("40 MB video") scores
    # 0.9347, just under the calibrated 0.94 operating point, so it now
    # hands off. This clearer documented phrasing covers the same intent.
    # The original phrasing's handoff is pinned in tests/test_day3.py.
    data = _post({
        "ticket_id": "T-1003",
        "subject": "Attachment size limit and file types",
        "body": "What is the attachment size limit per file and which file types are allowed, like PDF, PNG, or CSV?",
    })
    assert data["action"] == "answered"
    assert data["citations"][0]["article_id"] == "g4"


def test_howto_question_answered():
    data = _post({
        "ticket_id": "T-1004",
        "subject": "Connect Slack",
        "body": "How do I connect the Slack integration to get ticket alerts?",
    })
    assert data["action"] == "answered"
    assert data["citations"][0]["article_id"] == "h5"


def test_gibberish_topic_hands_off():
    data = _post({
        "ticket_id": "T-1005",
        "subject": "Xyzzy plugh frobnicate",
        "body": "Wibble wobble blorp zqxj kvnth mwarg xyzzy.",
    })
    assert data["action"] == "handoff"
    assert data["handoff_reason"] == "low_retrieval_confidence"
    assert data["answer"] == ""
    assert data["citations"] == []


def test_empty_body_rejected():
    resp = client.post("/tickets/answer", json={
        "ticket_id": "T-1006",
        "subject": "Empty body",
        "body": "",
    })
    assert resp.status_code == 422


def test_missing_subject_rejected():
    resp = client.post("/tickets/answer", json={
        "ticket_id": "T-1007",
        "body": "No subject here.",
    })
    assert resp.status_code == 422


def test_response_shape():
    data = _post({
        "ticket_id": "T-1008",
        "subject": "Refund policy",
        "body": "Can I get a refund on my monthly plan?",
    })
    for key in ("ticket_id", "answer", "citations", "confidence", "action", "handoff_reason"):
        assert key in data
    assert 0.0 <= data["confidence"] <= 1.0
    assert data["action"] in ("answered", "handoff")


def test_answer_cites_article_title():
    data = _post({
        "ticket_id": "T-1009",
        "subject": "Enable 2FA",
        "body": "How do I turn on two-factor authentication for my account?",
    })
    assert "Enable two-factor authentication" in data["answer"]
    assert data["action"] == "answered"


@pytest.mark.parametrize("field", ["ticket_id", "subject", "body"])
def test_whitespace_only_field_rejected(field: str):
    payload = {
        "ticket_id": "T-1010",
        "subject": "Password reset",
        "body": "I need help resetting my password.",
    }
    payload[field] = "   "

    resp = client.post("/tickets/answer", json=payload)

    assert resp.status_code == 422


def test_ticket_fields_are_stripped():
    resp = client.post("/tickets/answer", json={
        "ticket_id": "  T-1011  ",
        "subject": "  Password reset  ",
        "body": "  How do I reset my password?  ",
    })

    assert resp.status_code == 200
    assert resp.json()["ticket_id"] == "T-1011"
