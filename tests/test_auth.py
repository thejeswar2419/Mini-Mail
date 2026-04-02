def test_signup(client):
    response = client.post('/signup', data={
        'username': 'testuser',
        'password': 'test123'
    })

    assert response.status_code in [200, 302]

def test_login(client):
    response = client.post('/login', data={
        'username': 'testuser',
        'password': 'test123'
    })

    assert response.status_code in [200, 302]

def test_invalid_login(client):
    response = client.post('/login', data={
        'username': 'wrong',
        'password': 'wrong'
    })

    assert b'Invalid' in response.data or response.status_code == 200

