from unittest.mock import patch, MagicMock


# ---------------- PROFILE ----------------

def test_profile_requires_login(client):
    response = client.get('/profile')
    assert response.status_code == 302


def test_profile_logged_in(logged_in_client):
    response = logged_in_client.get('/profile')
    assert response.status_code == 200


def test_update_display_name(logged_in_client):
    response = logged_in_client.post('/profile', data={
        'action': 'update_name',
        'display_name': 'NewName'
    }, follow_redirects=True)

    assert response.status_code == 200


def test_change_password_invalid(logged_in_client):
    response = logged_in_client.post('/profile', data={
        'action': 'change_password',
        'current_password': 'wrong',
        'new_password': '123456',
        'confirm_new_password': '123456'
    }, follow_redirects=True)

    assert response.status_code == 200


# ---------------- SEND MESSAGE EDGE CASES ----------------

def test_send_empty_receiver(logged_in_client):
    response = logged_in_client.post('/send', data={
        'receiver': '',
        'message': 'Hello'
    }, follow_redirects=True)

    assert response.status_code == 200


def test_send_empty_message(logged_in_client):
    response = logged_in_client.post('/send', data={
        'receiver': 'user2',
        'message': ''
    }, follow_redirects=True)

    assert response.status_code == 200


def test_send_to_self(logged_in_client):
    response = logged_in_client.post('/send', data={
        'receiver': '1',  # same as session user_id
        'message': 'Hello'
    }, follow_redirects=True)

    assert response.status_code == 200


# ---------------- DELETE MESSAGE ----------------

def test_delete_message_invalid(logged_in_client):
    response = logged_in_client.post('/delete_message', data={
        'box_type': 'invalid',
        'msg_id': ''
    }, follow_redirects=True)

    assert response.status_code == 200


@patch('app.m.connect')
def test_delete_message_sent(mock_connect, logged_in_client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Simulate message exists
    mock_cursor.fetchone.return_value = ("date", "receiver", "msg")

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = logged_in_client.post('/delete_message', data={
        'box_type': 'sent',
        'msg_id': '1'
    })

    assert response.status_code == 302


# ---------------- DELETE ACCOUNT ----------------

@patch('app.get_user_profile')
def test_delete_account_wrong_password(mock_profile, logged_in_client):

    mock_profile.return_value = {
        "password_hash": "fakehash"
    }

    response = logged_in_client.post('/delete_account', data={
        'password': 'wrong'
    }, follow_redirects=True)

    assert response.status_code == 200


# ---------------- API ----------------

def test_api_user_not_logged_in(client):
    response = client.get('/api/user/test')
    assert response.status_code == 401


@patch('app.get_user_profile')
def test_api_user_found(mock_profile, logged_in_client):

    mock_profile.return_value = {
        "name": "Test",
        "display_name": "TestUser",
        "avatar": None
    }

    response = logged_in_client.get('/api/user/test')

    assert response.status_code == 200