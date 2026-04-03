from unittest.mock import patch, MagicMock
import io


# ---------------- SIGNUP FULL ----------------

@patch('app.connect_server')
def test_signup_success(mock_connect, client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_cursor.fetchone.return_value = None  # user not exists
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = client.post('/signup', data={
        'name': 'Test',
        'phone': '123',
        'user_id': 'user1',
        'password': '123456',
        'confirm_password': '123456'
    })

    assert response.status_code == 302


def test_signup_password_mismatch(client):
    response = client.post('/signup', data={
        'name': 'Test',
        'user_id': 'user1',
        'password': '123456',
        'confirm_password': 'wrong'
    }, follow_redirects=True)

    assert response.status_code == 200


# ---------------- LOGIN SUCCESS + DB ERROR ----------------

@patch('app.connect_server')
@patch('app.check_password_hash', return_value=True)
def test_login_success(mock_hash, mock_connect, client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_cursor.fetchone.return_value = ('TestUser', 'hash')
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = client.post('/login', data={
        'user_id': 'user1',
        'password': '123456'
    })

    assert response.status_code == 302


@patch('app.connect_server', side_effect=Exception("DB error"))
def test_login_db_error(mock_connect, client):

    response = client.post('/login', data={
        'user_id': 'user1',
        'password': '123456'
    }, follow_redirects=True)

    assert response.status_code == 200


# ---------------- DASHBOARD EDGE ----------------

@patch('app.m.connect')
def test_dashboard_with_data(mock_connect, logged_in_client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_cursor.fetchone.side_effect = [(10,), (5,)]
    mock_cursor.fetchall.return_value = [
        ('date', 'user', 'message')
    ]

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = logged_in_client.get('/dashboard')

    assert response.status_code == 200


# ---------------- PROFILE ALL BRANCHES ----------------

def test_profile_empty_name(logged_in_client):
    response = logged_in_client.post('/profile', data={
        'action': 'update_name',
        'display_name': ''
    }, follow_redirects=True)

    assert response.status_code == 200


def test_profile_password_mismatch(logged_in_client):
    response = logged_in_client.post('/profile', data={
        'action': 'change_password',
        'current_password': 'x',
        'new_password': '123456',
        'confirm_new_password': 'wrong'
    }, follow_redirects=True)

    assert response.status_code == 200


# ---------------- SEND MESSAGE ALL BRANCHES ----------------

def test_send_long_message(logged_in_client):
    response = logged_in_client.post('/send', data={
        'receiver': 'user2',
        'message': 'a' * 3000
    }, follow_redirects=True)

    assert response.status_code == 200


@patch('app.connect_server')
def test_send_db_error(mock_connect, logged_in_client):

    mock_connect.side_effect = Exception("fail")

    response = logged_in_client.post('/send', data={
        'receiver': 'user2',
        'message': 'Hello'
    }, follow_redirects=True)

    assert response.status_code == 200


# ---------------- DELETE MESSAGE FULL ----------------

@patch('app.m.connect')
def test_delete_sent_no_row(mock_connect, logged_in_client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_cursor.fetchone.return_value = None

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = logged_in_client.post('/delete_message', data={
        'box_type': 'sent',
        'msg_id': '1'
    })

    assert response.status_code == 302


# ---------------- DELETE ACCOUNT ERROR ----------------

@patch('app.get_user_profile')
def test_delete_account_no_profile(mock_profile, logged_in_client):

    mock_profile.return_value = None

    response = logged_in_client.post('/delete_account', data={
        'password': 'x'
    }, follow_redirects=True)

    assert response.status_code == 200


@patch('app.connect_server', side_effect=Exception("fail"))
@patch('app.get_user_profile')
def test_delete_account_exception(mock_profile, mock_connect, logged_in_client):

    mock_profile.return_value = {"password_hash": "x"}

    with patch('app.check_password_hash', return_value=True):
        response = logged_in_client.post('/delete_account', data={
            'password': 'x'
        }, follow_redirects=True)

        assert response.status_code == 200


# ---------------- API EDGE ----------------

@patch('app.get_user_profile')
def test_api_partial_data(mock_profile, logged_in_client):

    mock_profile.return_value = {
        "name": "Test",
        "display_name": None,
        "avatar": None
    }

    response = logged_in_client.get('/api/user/test')

    assert response.status_code == 200