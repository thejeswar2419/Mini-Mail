def test_signup_success(client):
    response = client.post('/signup', data={
        'username': 'newuser',
        'password': 'strongpassword'
    }, follow_redirects=True)

    assert response.status_code == 200


def test_signup_missing_fields(client):
    response = client.post('/signup', data={
        'username': '',
        'password': ''
    }, follow_redirects=True)

    assert response.status_code == 200


def test_login_success_redirect(client):
    response = client.post('/login', data={
        'username': 'testuser',
        'password': 'test123'
    })

    # Should redirect to dashboard
    assert response.status_code == 302
    assert '/dashboard' in response.location


def test_login_invalid(client):
    response = client.post('/login', data={
        'username': '',
        'password': ''
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Please fill in both fields' in response.data