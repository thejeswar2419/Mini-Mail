import pytest
from unittest.mock import MagicMock, patch
from app import app, encrypt_mobile, decrypt_mobile


def test_encryption_roundtrip():
    plain = "+919876543210"
    encrypted = encrypt_mobile(plain)
    assert encrypted != plain
    assert encrypted.startswith("gAAAAA")
    decrypted = decrypt_mobile(encrypted)
    assert decrypted == plain


def test_encryption_fallback_plain():
    plain = "9876543210"
    # Unencrypted string should fall back gracefully
    assert decrypt_mobile(plain) == plain
    assert decrypt_mobile(None) is None


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test_secret_key_123"
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = "testuser"
            sess["user_name"] = "Test User"
        yield client


@patch("app.connect_db")
def test_update_username(mock_connect, client):
    mock_con = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_con
    mock_con.cursor.return_value = mock_cur
    
    # Username not taken
    mock_cur.fetchone.return_value = None

    response = client.post("/profile", data={
        "action": "update_username",
        "new_user_id": "newuser123"
    }, follow_redirects=True)
    
    assert response.status_code == 200
    mock_cur.execute.assert_any_call(
        "UPDATE userdetails SET user_ID = %s WHERE user_ID = %s",
        ("newuser123", "testuser")
    )


@patch("app.connect_db")
def test_update_mobile_encrypted(mock_connect, client):
    mock_con = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_con
    mock_con.cursor.return_value = mock_cur

    response = client.post("/profile", data={
        "action": "update_mobile",
        "mobile_no": "+919988776655"
    }, follow_redirects=True)

    assert response.status_code == 200
    all_queries = [call[0][0] for call in mock_cur.execute.call_args_list]
    assert any("UPDATE userdetails SET mobile_no =" in q for q in all_queries)
    
    # Verify encrypted parameter
    mobile_call = [call[0][1] for call in mock_cur.execute.call_args_list if "UPDATE userdetails SET mobile_no =" in call[0][0]][0]
    encrypted_param = mobile_call[0]
    assert encrypted_param.startswith("gAAAAA")
    assert decrypt_mobile(encrypted_param) == "+919988776655"


@patch("app.connect_db")
def test_soft_delete_account_and_recovery(mock_connect, client):
    mock_con = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_con
    mock_con.cursor.return_value = mock_cur

    # Mock get_user_profile for password verification
    with patch("app.get_user_profile") as mock_get_profile:
        from werkzeug.security import generate_password_hash
        mock_get_profile.return_value = {
            "user_ID": "testuser",
            "password_hash": generate_password_hash("password123")
        }

        # Step 1: Delete account
        del_resp = client.post("/delete_account", data={"password": "password123"}, follow_redirects=True)
        assert del_resp.status_code == 200
        all_queries = [call[0][0] for call in mock_cur.execute.call_args_list]
        assert any("UPDATE userdetails SET is_deleted = 1" in q for q in all_queries)

    # Step 2: Account recovery flow
    with client.session_transaction() as sess:
        sess["pending_restore_uid"] = "testuser"

    mock_cur.fetchone.return_value = {"user_ID": "testuser", "name": "Test User", "deleted_at": "2026-08-13 20:00:00"}
    rec_resp = client.post("/recover_account", data={"action": "restore"}, follow_redirects=True)
    assert rec_resp.status_code == 200
    all_queries = [call[0][0] for call in mock_cur.execute.call_args_list]
    assert any("UPDATE userdetails SET is_deleted = 0" in q for q in all_queries)
