"""Day 1 API tests for helpdesk-agent."""

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
    data = _post({
        "ticket_id": "T-1003",
        "subject": "Attachments will not upload",
        "body": "Uploading a 40 MB video fails every time, what are the limits?",
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
