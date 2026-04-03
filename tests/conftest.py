import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'testsecret'

    with app.test_client() as client:
        yield client


# Simulate logged-in user (no DB needed)
@pytest.fixture
def logged_in_client(client):
    with client.session_transaction() as session:
        session['user_id'] = 1
    return client