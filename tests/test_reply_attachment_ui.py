import pytest
from unittest.mock import MagicMock, patch
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = "testuser"
            sess["user_name"] = "Test User"
        yield client


def test_send_prefill(client):
    response = client.get("/send?to=sanju1&subject=Re:%20Greetings")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'value="sanju1"' in html
    assert 'value="Re: Greetings"' in html


@patch("app.connect_db")
def test_messages_gmail_attachment_and_reply(mock_connect, client):
    mock_con = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_con
    mock_con.cursor.return_value = mock_cur

    # Mock inbox with message + attachment
    mock_cur.fetchall.side_effect = [
        [
            {
                "id": 10,
                "sent_at": "2026-08-13 20:00:00",
                "sender_id": "sanju1",
                "subject": "Project Spec",
                "message_text": "Here is the PDF spec document.",
                "attachment": "10_doc.pdf",
                "attachment_name": "spec_v1.pdf",
                "attachment_mime": "application/pdf",
                "is_read": 0
            }
        ],
        [] # Sent messages
    ]

    response = client.get("/messages")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Check Reply link generated
    assert 'to=sanju1' in html
    assert 'subject=Re%3A+Project+Spec' in html or 'subject=Re:+Project+Spec' in html or 'Re:' in html
    # Check Gmail attachment card rendered
    assert 'gmail-attachment-card' in html
    assert 'spec_v1.pdf' in html
    assert 'PDF' in html
