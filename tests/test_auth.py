def test_signup(client):
    response = client.post('/signup', data={
        'username': 'testuser',
        'password': 'test123'
    }, follow_redirects=True)

    assert response.status_code == 200


def test_login(client):
    response = client.post('/login', data={
        'username': 'testuser',
        'password': 'test123'
    }, follow_redirects=True)

    assert response.status_code == 200


def test_invalid_login(client):
    response = client.post('/login', data={
        'username': 'wrong',
        'password': 'wrong'
    }, follow_redirects=True)

    # After redirect, should still land on login page
    assert response.status_code == 200