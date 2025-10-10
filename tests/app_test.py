import pytest
import os
import sys
from unittest.mock import patch
from datetime import datetime, timedelta, timezone  # ADDED timezone for Fix
import jwt
import uuid

# Temporarily extend sys.path for local module imports (FIX E402)
# The sys.path manipulation must happen before the local imports.
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))  # noqa: E402

# Import the configuration classes (FIX E402)
from config import TestingConfig  # noqa: E402

# CRITICAL FIX: Import from the new application file name (FIX E402)
from kaisurf_secured_app import (  # noqa: E402
    app as flask_app,
    db,
    User,
    KonesBalance,
    KonesLedger,
    Chronolog
)


# --- Test Constants ---
# Use constants from the standard TestingConfig setup to ensure consistency
TEST_TRUSTED_KEY = TestingConfig.TRUSTED_SERVICE_API_KEY
TEST_JWT_SECRET = TestingConfig.SUPABASE_JWT_SECRET
TEST_SUPABASE_UID = 'auth-uid-12345'


# --- Pytest Fixtures ---


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
    Function-level fixture to set up a clean, testable application instance.
    Only handles configuration loading. DB setup/teardown is handled by
    setup_db using explicit app_context() blocks (FIX Context Error).
    """
    # CRITICAL FIX: Load configuration directly from TestingConfig
    flask_app.config.from_object(TestingConfig)

    # E501 Fix: Breaking long configuration lines
    flask_app.config['SUPABASE_JWT_SECRET'] = TEST_JWT_SECRET
    flask_app.config['TRUSTED_SERVICE_API_KEY'] = TEST_TRUSTED_KEY

    # Yield the app instance.
    yield flask_app


@pytest.fixture
def dynamic_user_id():
    """
    Generates a unique auth_uid for each test run to guarantee isolation.
    """
    return {'auth_uid': str(uuid.uuid4())}


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mocks environment variables for consistent test execution."""
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
def setup_db(app, dynamic_user_id):
    """
    Initializes and tears down the in-memory database for each test function.
    Uses explicit context management to fix "Popped wrong app context" errors.
    """
    auth_uid = dynamic_user_id['auth_uid']

    # CRITICAL FIX: All DB setup must occur within the app context.
    with app.app_context():
        # Setup: drop all tables and recreate them (clean start)
        db.drop_all()
        db.create_all()

        # Create the guaranteed User object
        user = User(
            auth_uid=auth_uid
        )
        db.session.add(user)
        db.session.commit()

    # The setup_db fixture yields the auth_uid for other fixtures
    yield auth_uid

    # Teardown: Clean up
    with app.app_context():
        # Clean up by dropping the tables to ensure full isolation
        db.session.remove()
        db.drop_all()


@pytest.fixture
def mock_jwt_decode(dynamic_user_id):
    """Mocks the jwt.decode function for successful token validation."""
    payload = {'sub': dynamic_user_id['auth_uid']}
    # Mocking jwt.decode to bypass complex token generation for specific tests
    with patch('jwt.decode', return_value=payload) as mock_decode:
        yield mock_decode


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
        # FIX DeprecationWarning: Use timezone-aware object
        'exp': datetime.now(timezone.utc) + timedelta(hours=1)
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
    """Returns a dictionary with the trusted X-Api-Key header."""
    def _trusted_headers():
        return {
            'X-Api-Key': TEST_TRUSTED_KEY
        }
    return _trusted_headers


@pytest.fixture
def get_both_headers(get_auth_headers, get_trusted_headers):
    """Returns a dictionary combining both auth and trusted headers."""
    def _both_headers():
        return {
            **get_auth_headers(),
            **get_trusted_headers()
        }
    return _both_headers


# --- Test Helpers ---

def get_db_models(db_session, user_auth_uid):
    """
    Helper to fetch all key model instances using the user_auth_uid.
    """
    # E501 Fix: Breaking the line to avoid E501 violation
    user = db_session.session.get(
        User,
        user_auth_uid,
    )
    # KonesBalance is queried by the foreign key (user_auth_uid)
    kones_balance = db_session.session.query(KonesBalance).filter_by(
        user_auth_uid=user_auth_uid
    ).one_or_none()

    return user, kones_balance


# --- Authentication & Authorization Tests ---

def test_list_posts_no_auth(client):
    """Test access to /content/posts without any auth header."""
    # FIX: Route changed to /posts
    response = client.get('/posts')
    assert response.status_code == 401
    # FIX: Assertion message update (matches new app message)
    expected_message = b'Missing or invalid Authorization header.'
    assert expected_message in response.data


def test_list_posts_invalid_token(client, app, mock_jwt_decode):
    """Test access to /content/posts with an invalid token signature."""
    from jwt.exceptions import InvalidTokenError

    # Simulate a decoding failure (e.g., bad signature, corrupted token)
    with patch('jwt.decode', side_effect=InvalidTokenError(
             'Invalid Signature')):
        response = client.get(
            '/posts',  # FIX: Route changed to /posts
            headers={'Authorization': 'Bearer invalid.token.string'}
        )
    # FIX: Assertion message update (matches new app message)
    assert response.status_code == 401
    # FIX ASSERTION: App returns a simpler "Invalid format." message in JSON.
    assert b'Invalid format.' in response.data


def test_list_posts_success(client, setup_db, get_auth_headers):
    """Test successful access to /content/posts with a valid token."""
    response = client.get(
        '/posts',  # FIX: Route changed to /posts
        headers=get_auth_headers()
    )
    assert response.status_code == 200
    # Checks for content returned by the mock route
    assert b'Wave Riding Tips' in response.data  # FIX:


# --- Trusted Service Tests (API Key) ---

def test_earn_kones_no_api_key(client, get_auth_headers):
    """Test Kones earn route without the trusted API key."""
    # FIX: Route changed to /earn/kones
    response = client.post('/earn/kones', headers=get_auth_headers(), json={})
    assert response.status_code == 403
    # FIX ASSERTION: App returns the simplified message in JSON.
    expected_message = b'Invalid API Key for trusted service.'
    assert expected_message in response.data


def test_earn_kones_invalid_trusted_key(client, get_auth_headers):
    """Test Kones earn route with an incorrect trusted API key."""
    # Using a helper to ensure no W293 violation on nearby blank lines
    wrong_headers = get_auth_headers()
    wrong_headers['X-Api-Key'] = 'wrong-key'
    response = client.post(
        '/earn/kones',  # FIX: Route changed to /earn/kones
        headers=wrong_headers,
        json={}
    )
    assert response.status_code == 403
    # FIX ASSERTION: App returns the simplified message in JSON.
    expected_message = b'Invalid API Key for trusted service.'
    assert expected_message in response.data


def test_earn_kones_missing_auth_token(client, get_trusted_headers):
    """Test Kones earn route with a valid API key but missing JWT."""
    # The trusted key check passes (200) but the JWT check fails (401).
    response = client.post(
        '/earn/kones',  # FIX: Route changed to /earn/kones
        headers=get_trusted_headers(),
        json={'amount': 100, 'description': 'test'}
    )
    assert response.status_code == 401
    # FIX E501 (potential): Ensuring line length is respected
    expected_message = b'Missing or invalid Authorization header.'
    assert expected_message in response.data


# --- Kones Earning Logic Tests ---

def test_earn_kones_success_new_balance(
        client, setup_db, get_both_headers
):
    """Test successful Kones earn when the user has no existing balance."""
    # Retrieve the unique user ID from the fixture setup
    user_auth_uid = setup_db

    response = client.post(
        '/earn/kones',  # FIX: Route changed to /earn/kones
        headers=get_both_headers(),
        json={'amount': 50, 'description': 'First login bonus'}
    )
    assert response.status_code == 200
    assert b'Successfully added 50 Kones' in response.data
    assert b'50' in response.data  # Checks new_balance

    # Verify DB state
    user, balance = get_db_models(db, user_auth_uid)
    ledger_entry = db.session.query(KonesLedger).first()
    assert balance.balance == 50
    assert ledger_entry.amount == 50
    assert ledger_entry.description == 'First login bonus'


def test_earn_kones_success_existing_balance(
        client, setup_db, get_both_headers
):
    """Test successful Kones earn when the user has an existing balance."""
    # Retrieve the unique user ID from the fixture setup
    user_auth_uid = setup_db

    # Create initial balance record using the correct foreign key
    with flask_app.app_context():
        initial_balance = KonesBalance(
            user_auth_uid=user_auth_uid, balance=100
            )
        db.session.add(initial_balance)
        db.session.commit()

    response = client.post(
        '/earn/kones',  # FIX: Route changed to /earn/kones
        headers=get_both_headers(),
        json={'amount': 25, 'description': 'Daily reward'}
    )
    assert response.status_code == 200
    assert b'Successfully added 25 Kones' in response.data
    assert b'125' in response.data  # Checks new_balance (100 + 25)

    # Verify DB state
    # Need context here to query the DB
    with flask_app.app_context():
        _, balance = get_db_models(db, user_auth_uid)
        assert balance.balance == 125
        assert db.session.query(KonesLedger).count() == 1


def test_earn_kones_invalid_amount(
        client, setup_db, get_both_headers
):
    """Test Kones earn route with invalid (non-positive) amount."""
    response = client.post(
        '/earn/kones',  # FIX: Route changed to /earn/kones
        headers=get_both_headers(),
        json={'amount': 0, 'description': 'test'}  # Added description
    )
    assert response.status_code == 400
    # FIX: Assertion message update (matches app message)
    expected_message = b'Amount must be positive.'
    assert expected_message in response.data


# --- Webhook Sync Logic Tests ---

def test_webhook_sync_missing_payload(
        client, setup_db, get_both_headers
):
    """Test webhook sync route when missing event_type or payload."""
    response = client.post(
        '/webhook/sync',
        headers=get_both_headers(),
        json={'event_type': 'purchase'}  # Missing payload
    )
    assert response.status_code == 400
    # FIX E501: Breaking long line
    expected_message = b"Request must include 'event_type' and 'payload'."
    assert expected_message in response.data


def test_webhook_sync_success(
        client, setup_db, get_both_headers
):
    """Test successful webhook sync and Chronolog logging."""
    # Retrieve the unique user ID from the fixture setup
    user_auth_uid = setup_db
    test_payload = {'order_id': 'AX123', 'value': 49.99}

    response = client.post(
        '/webhook/sync',
        headers=get_both_headers(),
        json={'event_type': 'purchase_complete', 'payload': test_payload}
    )
    assert response.status_code == 200
    expected_message = b'Webhook event processed'
    assert expected_message in response.data
    assert b'WEBHOOK_PURCHASE_COMPLETE' in response.data

    # Verify Chronolog state
    # Need context here to query the DB
    with flask_app.app_context():
        chronolog_entry = db.session.query(Chronolog).filter_by(
            user_auth_uid=user_auth_uid
        ).first()
        assert chronolog_entry.event_type == 'WEBHOOK_PURCHASE_COMPLETE'
        assert chronolog_entry.payload == test_payload
        assert chronolog_entry.user_auth_uid == user_auth_uid
