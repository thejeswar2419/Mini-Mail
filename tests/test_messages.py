def test_send_message(client):
    response = client.post('/send_message', data={
        'receiver': 'testuser2',
        'message': 'Hello!'
    })

    assert response.status_code in [200, 302]

def test_view_messages(client):
    response = client.get('/messages')

    assert response.status_code == 200

def test_dashboard_requires_login(client):
    response = client.get('/dashboard')

    assert response.status_code in [302, 401]