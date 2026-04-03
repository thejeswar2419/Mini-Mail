from unittest.mock import patch, MagicMock
from app import allowed_file, validate_user_id


# ---------------- HELPERS ----------------

def test_allowed_file():
    assert allowed_file("image.png")
    assert not allowed_file("file.txt")


def test_validate_user_id():
    assert validate_user_id("user1")
    assert not validate_user_id("bad/user")
    assert not validate_user_id("bad`user")


# ---------------- DASHBOARD ----------------

@patch('app.m.connect')
def test_dashboard_data(mock_connect, logged_in_client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_cursor.fetchone.side_effect = [(5,), (3,)]
    mock_cursor.fetchall.return_value = []

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = logged_in_client.get('/dashboard')

    assert response.status_code == 200


# ---------------- PROFILE FULL ----------------

@patch('app.connect_server')
def test_update_name_success(mock_connect, logged_in_client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = logged_in_client.post('/profile', data={
        'action': 'update_name',
        'display_name': 'Updated'
    })

    assert response.status_code == 302


@patch('app.get_user_profile')
def test_change_password_success(mock_profile, logged_in_client):

    mock_profile.return_value = {
        "password_hash": "pbkdf2:sha256:fake"
    }

    with patch('app.check_password_hash', return_value=True):
        with patch('app.connect_server') as mock_connect:

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            response = logged_in_client.post('/profile', data={
                'action': 'change_password',
                'current_password': 'old',
                'new_password': '123456',
                'confirm_new_password': '123456'
            })

            assert response.status_code == 302


# ---------------- SEND MESSAGE FULL ----------------

@patch('app.connect_server')
@patch('app.m.connect')
def test_send_message_full(mock_m_connect, mock_connect, logged_in_client):

    # receiver exists
    mock_conn1 = MagicMock()
    mock_cursor1 = MagicMock()
    mock_cursor1.fetchone.return_value = ('user2',)
    mock_conn1.cursor.return_value = mock_cursor1

    mock_connect.return_value = mock_conn1

    # DB insert mocks
    mock_conn2 = MagicMock()
    mock_cursor2 = MagicMock()
    mock_conn2.cursor.return_value = mock_cursor2

    mock_m_connect.return_value = mock_conn2

    response = logged_in_client.post('/send', data={
        'receiver': 'user2',
        'message': 'Hello'
    })

    assert response.status_code == 302


# ---------------- DELETE ACCOUNT SUCCESS ----------------

@patch('app.get_user_profile')
@patch('app.connect_server')
def test_delete_account_success(mock_connect, mock_profile, logged_in_client):

    mock_profile.return_value = {
        "password_hash": "fake"
    }

    with patch('app.check_password_hash', return_value=True):

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        response = logged_in_client.post('/delete_account', data={
            'password': 'correct'
        })

        assert response.status_code == 302


# ---------------- DELETE MESSAGE RECEIVED ----------------

@patch('app.m.connect')
def test_delete_received(mock_connect, logged_in_client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = logged_in_client.post('/delete_message', data={
        'box_type': 'received',
        'msg_id': '1'
    })

    assert response.status_code == 302


# ---------------- API EDGE ----------------

@patch('app.get_user_profile')
def test_api_not_found(mock_profile, logged_in_client):

    mock_profile.return_value = None

    response = logged_in_client.get('/api/user/unknown')

    assert response.status_code == 404