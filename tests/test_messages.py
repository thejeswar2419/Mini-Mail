def test_send_message(logged_in_client):
    response = logged_in_client.post('/send', data={
        'receiver': 'testuser2',
        'message': 'Hello!'
    }, follow_redirects=True)

    # If route exists → should not be 404
    assert response.status_code != 404


def test_view_messages_requires_login(client):
    response = client.get('/messages')

    # Not logged in → should redirect
    assert response.status_code == 302


def test_view_messages_logged_in(logged_in_client):
    response = logged_in_client.get('/messages')

    assert response.status_code == 200