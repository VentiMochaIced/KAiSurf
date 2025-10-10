import pytest
import os
import sys
from unittest.mock import patch
from datetime import datetime, timedelta
import jwt
import uuid

# --- FIX: Ensure the application module is on the Python path ---
# Adds the directory containing this conftest.py (the project root)
# to the system path so that 'kaisurf_secured_app' can be found.
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# This tells pytest how to import the application correctly
# CRITICAL FIX: Change import name to kaisurf_secured_app
from kaisurf_secured_app import (  # noqa: E402
    app as flask_app,
    db,
    User,
    # F401 FIX: Removed direct import of old constants that caused linter
    # warnings, as they are now accessed via the imported module.
)

# --- Test Constants ---
TEST_SUPABASE_UID = 'auth-uid-12345'
TEST_TRUSTED_KEY = 'super-secret-service-key'
TEST_JWT_SECRET = 'test-jwt-secret'


# --- Standard Flask/Pytest Fixtures ---


@pytest.fixture(scope='session')
def client():
    """
    Session-level client fixture for making HTTP requests.
    Uses the app fixture internally.
    """
    with flask_app.test_client() as client:
        yield client


@pytest.fixture(scope='function')
def app():
    """
    Function-level fixture to set up a clean,
    testable application instance.

    Uses in-memory SQLite database for test isolation.
    CRITICAL FIX: Explicitly set configuration keys on the app instance.
    """

    # Use in-memory SQLite database
    from config import TestingConfig
    flask_app.config.from_object(TestingConfig)

    # CRITICAL CONTEXT FIX: Manually push and pop the context to ensure
    # DB operations (create_all/drop_all) and session removal are safe.
    ctx = flask_app.app_context()
    ctx.push()

    # Setup: drop all tables and recreate them (clean start)
    db.drop_all()
    db.create_all()

    # Yield the app instance to the test function
    yield flask_app

    # Teardown: Clean up
    db.session.remove()
    db.drop_all()
    ctx.pop()  # Pop the context we pushed


@pytest.fixture
def dynamic_user_id():
    """
    Generates a unique auth_uid for each test run to guarantee isolation.
    """
    return {'auth_uid': str(uuid.uuid4())}


@pytest.fixture(scope='function')
def setup_db(app, dynamic_user_id):
    """
    Function-level fixture to create a unique User record in the database.

    Yields:
        str: A unique user auth_uid for test use.
    """
    auth_uid = dynamic_user_id['auth_uid']

    # Create user record
    # The 'app' fixture ensures the context is active.
    user = User(auth_uid=auth_uid)
    db.session.add(user)
    db.session.commit()

    yield auth_uid


@pytest.fixture(scope='session')
def mock_env_vars():
    """
    Mocks environment variables for the lifetime of the test session,
    ensuring a consistent testing environment for app startup.
    """
    with patch.dict(
        os.environ,
        {
            'FLASK_ENV': 'testing',
            'SUPABASE_JWT_SECRET': TEST_JWT_SECRET,
            'TRUSTED_SERVICE_API_KEY': TEST_TRUSTED_KEY
        }
    ):
        yield


@pytest.fixture
def create_test_jwt(setup_db):
    """
    Creates a valid JWT for testing based on the unique user ID
    from setup_db and the known secret.
    """
    auth_uid = setup_db  # Get the unique user ID created for this test

    # Read the secret from the explicit constant (guaranteed to be correct)
    secret = TEST_JWT_SECRET

    # Create a token that expires in 1 hour
    payload = {
        'sub': auth_uid,
        # Use timezone-aware datetime.now(timezone.utc)
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(
        payload,
        secret,
        algorithm='HS256'
    )


# --- Helper Functions for Test Headers ---


@pytest.fixture
def get_auth_headers(create_test_jwt):
    """Returns a dictionary with a valid Authorization header."""
    def _auth_headers():
        return {
            'Authorization': f'Bearer {create_test_jwt}'
        }
    return _auth_headers


@pytest.fixture
def get_trusted_headers():
    """Returns a dictionary with the trusted service API key header."""
    def _trusted_headers():
        # Use the constant from the test configuration
        return {
            'X-Api-Key': TEST_TRUSTED_KEY
        }
    return _trusted_headers


@pytest.fixture
def get_combined_headers(get_auth_headers, get_trusted_headers):
    """Returns a dictionary combining both auth and trusted headers."""
    def _combined_headers():
        auth = get_auth_headers()
        trusted = get_trusted_headers()
        return {**auth, **trusted}
    return _combined_headers


@pytest.fixture
def mock_jwt_decode(dynamic_user_id):
    """
    Mocks the jwt.decode call to return a payload with a dynamic user ID,
    simulating successful token validation.
    """
    payload = {'sub': dynamic_user_id['auth_uid']}
    # Mocking jwt.decode to bypass complex token generation for specific tests
    with patch('jwt.decode', return_value=payload) as mock_decode:
        yield mock_decode
