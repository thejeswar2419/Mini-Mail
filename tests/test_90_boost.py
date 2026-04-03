from unittest.mock import patch, MagicMock
import io


# ---------------- SIGNUP EDGE ----------------

def test_signup_invalid_userid(client):
    response = client.post('/signup', data={
        'name': 'Test',
        'user_id': 'bad/user',
        'password': '123456',
        'confirm_password': '123456'
    }, follow_redirects=True)

    assert response.status_code == 200


def test_signup_short_password(client):
    response = client.post('/signup', data={
        'name': 'Test',
        'user_id': 'user1',
        'password': '123',
        'confirm_password': '123'
    }, follow_redirects=True)

    assert response.status_code == 200


# ---------------- LOGIN EDGE ----------------

@patch('app.connect_server')
def test_login_no_user(mock_connect, client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = client.post('/login', data={
        'user_id': 'unknown',
        'password': '123'
    })

    assert response.status_code == 302


# ---------------- PROFILE DB ERROR ----------------

@patch('app.connect_server', side_effect=Exception("fail"))
def test_profile_db_error(mock_connect, logged_in_client):

    response = logged_in_client.post('/profile', data={
        'action': 'update_name',
        'display_name': 'Test'
    }, follow_redirects=True)

    assert response.status_code == 200


# ---------------- AVATAR EMPTY ----------------

def test_avatar_no_file(logged_in_client):
    response = logged_in_client.post('/profile', data={
        'action': 'upload_avatar'
    }, follow_redirects=True)

    assert response.status_code == 200


# ---------------- SEND ATTACHMENT ----------------

@patch('app.connect_server')
@patch('app.m.connect')
def test_send_with_attachment(mock_m, mock_connect, logged_in_client):

    # receiver exists
    mock_conn1 = MagicMock()
    mock_cursor1 = MagicMock()
    mock_cursor1.fetchone.return_value = ('user2',)
    mock_conn1.cursor.return_value = mock_cursor1
    mock_connect.return_value = mock_conn1

    mock_conn2 = MagicMock()
    mock_cursor2 = MagicMock()
    mock_conn2.cursor.return_value = mock_cursor2
    mock_m.return_value = mock_conn2

    data = {
        'receiver': 'user2',
        'message': '',
        'attachment': (io.BytesIO(b"file"), 'file.png')
    }

    response = logged_in_client.post('/send', data=data, content_type='multipart/form-data')

    assert response.status_code == 302


# ---------------- SEND SAVE FAILURE ----------------

@patch('app.connect_server')
@patch('app.m.connect', side_effect=Exception("fail"))
def test_send_save_fail(mock_m, mock_connect, logged_in_client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ('user2',)

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = logged_in_client.post('/send', data={
        'receiver': 'user2',
        'message': 'Hello'
    }, follow_redirects=True)

    assert response.status_code == 200


# ---------------- DELETE MESSAGE DEEP ----------------

@patch('app.m.connect')
def test_delete_sent_with_row(mock_connect, logged_in_client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_cursor.fetchone.return_value = ("date", "receiver", "msg")

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = logged_in_client.post('/delete_message', data={
        'box_type': 'sent',
        'msg_id': '1'
    })

    assert response.status_code == 302


# ---------------- DELETE ACCOUNT DB FAIL ----------------

@patch('app.get_user_profile')
@patch('app.connect_server', side_effect=Exception("fail"))
def test_delete_account_db_fail(mock_connect, mock_profile, logged_in_client):

    mock_profile.return_value = {"password_hash": "x"}

    with patch('app.check_password_hash', return_value=True):
        response = logged_in_client.post('/delete_account', data={
            'password': 'x'
        }, follow_redirects=True)

        assert response.status_code == 200


# ---------------- API ERROR EDGE ----------------

@patch('app.get_user_profile', side_effect=Exception("fail"))
def test_api_exception(mock_profile, logged_in_client):

    response = logged_in_client.get('/api/user/test')

    assert response.status_code in [200, 500]