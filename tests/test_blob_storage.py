import pytest
from unittest.mock import MagicMock, patch
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test_secret"
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = "user1"
            sess["user_name"] = "Test User"
        yield client


@patch("app.connect_db")
def test_serve_avatar_blob(mock_connect, client):
    mock_con = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_con
    mock_con.cursor.return_value = mock_cur

    mock_cur.fetchone.return_value = {
        "avatar_data": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
        "avatar_mime": "image/png"
    }

    response = client.get("/avatar/user1")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data.startswith(b"\x89PNG")


@patch("app.connect_db")
def test_serve_avatar_not_found(mock_connect, client):
    mock_con = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_con
    mock_con.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = None

    response = client.get("/avatar/nonexistent")
    assert response.status_code == 404


@patch("app.connect_db")
def test_download_attachment_blob(mock_connect, client):
    mock_con = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_con
    mock_con.cursor.return_value = mock_cur

    mock_cur.fetchone.return_value = {
        "attachment_name": "report.pdf",
        "attachment_data": b"%PDF-1.4 sample content",
        "attachment_mime": "application/pdf"
    }

    response = client.get("/attachments/10")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert b"%PDF-1.4" in response.data
