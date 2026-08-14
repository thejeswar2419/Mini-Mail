import pytest
from unittest.mock import MagicMock, patch
from app import app, generate_ai_smart_replies


@patch("os.getenv")
def test_generate_ai_smart_replies_fallback(mock_getenv):
    mock_getenv.return_value = ""
    # Test meeting context
    replies = generate_ai_smart_replies("Meeting tomorrow?", "Can we schedule a call?")
    assert len(replies) == 4
    tones = [r["tone"] for r in replies]
    assert "Formal" in tones
    assert "Direct" in tones
    assert "Casual" in tones
    assert "Detailed" in tones

    # Test positive / accept intent fallback
    pos_replies = generate_ai_smart_replies("Job Offer", "We are pleased to offer you the position.", intent="positive")
    assert len(pos_replies) == 4
    assert any("accept" in r["text"].lower() or "pleased" in r["text"].lower() or "agree" in r["text"].lower() for r in pos_replies)

    # Test negative / decline intent fallback
    neg_replies = generate_ai_smart_replies("Invitation to event", "Would you like to join?", intent="negative")
    assert len(neg_replies) == 4
    assert any("decline" in r["text"].lower() or "unable" in r["text"].lower() or "regret" in r["text"].lower() for r in neg_replies)




@patch("requests.post")
@patch("os.getenv")
def test_generate_ai_smart_replies_openrouter(mock_getenv, mock_post):
    def env_side_effect(key, default=""):
        if key == "OPENROUTER_API_KEY":
            return "sk-or-v1-test-key-12345"
        if key == "OPENROUTER_MODEL":
            return "google/gemini-2.5-flash"
        return default

    mock_getenv.side_effect = env_side_effect

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": """[
                        {"tone": "Formal", "label": "Formal reply", "text": "Thank you for your email."},
                        {"tone": "Direct", "label": "Direct reply", "text": "Received, thanks."},
                        {"tone": "Casual", "label": "Casual reply", "text": "Hey, thanks!"},
                        {"tone": "Detailed", "label": "Detailed reply", "text": "Thank you for reaching out with details."}
                    ]"""
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    replies = generate_ai_smart_replies("Project Update", "Here is the latest report.")
    assert len(replies) == 4
    assert replies[0]["tone"] == "Formal"
    assert replies[1]["tone"] == "Direct"
    mock_post.assert_called()


@patch("requests.post")
@patch("os.getenv")
def test_generate_ai_smart_replies_openrouter_error_fallback(mock_getenv, mock_post):
    def env_side_effect(key, default=""):
        if key == "OPENROUTER_API_KEY":
            return "sk-or-v1-test-key-12345"
        return default

    mock_getenv.side_effect = env_side_effect
    mock_post.side_effect = Exception("OpenRouter connection timeout")

    # Should fall back to rule engine smoothly without crashing
    replies = generate_ai_smart_replies("Meeting schedule", "Let's meet tomorrow")
    assert len(replies) == 4
    assert any(r["tone"] == "Formal" for r in replies)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = "testuser"
            sess["user_name"] = "Test User"
        yield client


@patch("app.connect_db")
def test_ai_smart_reply_api(mock_connect, client):
    mock_con = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_con
    mock_con.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = {
        "subject": "Project Status Update",
        "message_text": "Could you provide a status report on the project?"
    }

    response = client.get("/api/ai/smart_reply?msg_id=10")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["replies"]) == 4


def test_send_prefill_body(client):
    response = client.get("/send?to=sanju1&subject=Re:%20Status&reply_body=Thank%20you%20for%20reaching%20out.")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'value="sanju1"' in html
    assert 'value="Re: Status"' in html
    assert 'Thank you for reaching out.' in html
