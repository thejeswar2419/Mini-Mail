import pytest
from unittest.mock import patch, MagicMock


# 🔥 Mock login success
@patch('app.mysql.connector.connect')
def test_login_success(mock_connect, client):

    # Fake DB response
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Simulate user found
    mock_cursor.fetchone.return_value = (1, 'testuser', 'hashed_password')

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = client.post('/login', data={
        'username': 'testuser',
        'password': 'test123'
    })

    # Should redirect after successful login
    assert response.status_code == 302


# 🔥 Mock login failure
@patch('app.mysql.connector.connect')
def test_login_failure(mock_connect, client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # No user found
    mock_cursor.fetchone.return_value = None

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = client.post('/login', data={
        'username': 'wrong',
        'password': 'wrong'
    })

    assert response.status_code == 302


# 🔥 Mock message sending
@patch('app.mysql.connector.connect')
def test_send_message_db(mock_connect, logged_in_client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = logged_in_client.post('/send', data={
        'receiver': 'user2',
        'message': 'Hello!'
    })

    # Ensure DB insert was called
    assert mock_cursor.execute.called
    assert response.status_code == 302


# 🔥 Mock fetch messages
@patch('app.mysql.connector.connect')
def test_fetch_messages(mock_connect, logged_in_client):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Simulate messages
    mock_cursor.fetchall.return_value = [
        ('user1', 'Hello'),
        ('user2', 'Hi')
    ]

    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = logged_in_client.get('/messages')

    assert response.status_code == 200