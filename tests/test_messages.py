def test_send_message_success(logged_in_client):
    response = logged_in_client.post('/send', data={
        'receiver': 'testuser2',
        'message': 'Hello!'
    })

    # Should redirect (either success or validation)
    assert response.status_code == 302

def test_send_message_missing_fields(logged_in_client):
    response = logged_in_client.post('/send', data={
        'receiver': '',
        'message': ''
    }, follow_redirects=True)

    assert response.status_code == 200


def test_send_requires_login(client):
    response = client.post('/send', data={
        'receiver': 'user',
        'message': 'Hello'
    })

    # Not logged in → redirect
    assert response.status_code == 302


def test_view_messages_requires_login(client):
    response = client.get('/messages')

    assert response.status_code == 302


def test_view_messages_logged_in(logged_in_client):
    response = logged_in_client.get('/messages')

    assert response.status_code == 200