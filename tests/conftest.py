import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'testsecret'

    with app.test_client() as client:
        yield client


# Helper: login by session (bypass DB)
@pytest.fixture
def logged_in_client(client):
    with client.session_transaction() as session:
        session['user'] = 'testuser'
    return client