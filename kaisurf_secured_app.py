import os
import jwt
# FIX: Import timezone for modern, non-deprecated usage of datetime
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

# Ensure environment variables are loaded
from dotenv import load_dotenv
load_dotenv()

# --- Configuration Import ---
# E402 Fix: We import config, so we need to put the import after app=Flask()
from config import DevelopmentConfig, ProductionConfig  # noqa: E402

# --- Application Initialization ---

app = Flask(__name__)

# Determine configuration class based on FLASK_ENV environment variable
# Default to DevelopmentConfig if FLASK_ENV is not set or recognized
config_name = os.getenv('FLASK_ENV', 'development')
if config_name == 'production':
    app.config.from_object(ProductionConfig)
elif config_name == 'testing':
    # NOTE: The testing configuration is often set directly in conftest.py
    # to ensure the most rigid control, but defining it here is good practice.
    from config import TestingConfig
    app.config.from_object(TestingConfig)
else:
    # Default is 'development'
    app.config.from_object(DevelopmentConfig)


db = SQLAlchemy(app)

# Environment variables for security are now read from app.config
# This is a cleaner way to access them across the application
SUPABASE_JWT_SECRET = app.config.get('SUPABASE_JWT_SECRET')
TRUSTED_SERVICE_API_KEY = app.config.get('TRUSTED_SERVICE_API_KEY')


# --- Import Models (This prevents circular imports) ---

# E402 Fix: Import must come after 'db = SQLAlchemy(app)'
from models import User, KonesLedger, KonesBalance, Chronolog  # noqa: E402


# --- Decorators ---

def get_user_from_auth_header(f):
    """Decorator to extract and validate JWT from the Authorization header."""

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                # FIX: Consistent message to align with test failures
                'message': 'Missing or invalid Authorization header.'
            }), 401

        jwt_token = auth_header.split(' ')[1]

        # Use the secret from app.config
        jwt_secret = app.config.get('SUPABASE_JWT_SECRET')

        if not jwt_secret:
            print("ERROR: SUPABASE_JWT_SECRET is not configured.")
            return jsonify({'message': 'Server misconfiguration.'}), 500

        try:
            # Validate and decode the token
            payload = jwt.decode(
                jwt_token,
                jwt_secret,
                algorithms=["HS256"]
            )
            auth_uid = payload.get('sub')

            if not auth_uid:
                return jsonify({'message': 'Invalid JWT payload.'}), 401

            # FIX: Resolve LegacyAPIWarning by rp User.query.get(auth_uid)
            # with the modern SQLAlchemy 2.0+ session.get method.
            current_user = db.session.get(User, auth_uid)

            if not current_user:
                return jsonify({'message': 'User not found in database.'}), 404

        except ExpiredSignatureError:
            return jsonify({'message': 'JWT has expired.'}), 401
        except InvalidTokenError:
            # FIX: Use general message to cover all InvalidTokenError cases
            return jsonify({'message': 'Invalid format.'}), 401
        except Exception as e:
            # Catch all other JWT errors (e.g., malformed header)
            print(f"JWT Decoding Error: {e}")
            return jsonify({'message': 'Invalid JWT format.'}), 401

        return f(current_user=current_user, *args, **kwargs)

    return decorated


def trusted_service_required(f):
    """Decorator to protect endpoints with a secret X-Api-Key."""

    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-Api-Key')

        # Use the trusted key from app.config
        trusted_key = app.config.get('TRUSTED_SERVICE_API_KEY')

        if api_key != trusted_key:
            return jsonify({
                # FIX: Consistent message to align with test failures
                'message': 'Invalid API Key for trusted service.'
            }), 403

        return f(*args, **kwargs)

    return decorated


# --- Routes ---

@app.route('/posts', methods=['GET'])
@get_user_from_auth_header
def list_posts(current_user):
    """
    Dummy route demonstrating authentication.
    Requires a valid JWT.
    """
    # In a real app, you would fetch posts based on current_user's preferences
    return jsonify({
        'user': current_user.auth_uid,
        'message': 'Access granted. Listing personalized content.',
        'posts': [
            {'title': 'Wave Riding Tips'},
            {'title': 'Newest Surfboards'}
        ]
    }), 200


@app.route('/earn/kones', methods=['POST'])
@trusted_service_required
@get_user_from_auth_header
def earn_kones(current_user):
    """
    Trusted route for service-to-service communication to add Kones currency.
    Requires X-Api-Key AND a valid JWT.
    """
    data = request.get_json()
    if not data or 'amount' not in data or 'description' not in data:
        return jsonify({
            'message': 'Missing required fields: amount and description.'
        }), 400

    try:
        amount = int(data['amount'])
    except ValueError:
        return jsonify({'message': 'Amount must be an integer.'}), 400

    description = data['description']

    if amount <= 0:
        # FIX: The test expects the more concise "Amount must be positive."
        return jsonify({'message': 'Amount must be positive.'}), 400

    # 1. Update/Create KonesBalance
    # Uses filter_by/first() for querying, which is acceptable in this context
    balance_record = KonesBalance.query.filter_by(
        user_auth_uid=current_user.auth_uid
    ).first()

    if not balance_record:
        balance_record = KonesBalance(
            user_auth_uid=current_user.auth_uid,
            balance=0
        )
        db.session.add(balance_record)

    balance_record.balance += amount
    # FIX: Resolve DeprecationWarning: datetime.utcnow() is deprecated
    balance_record.last_updated = datetime.now(timezone.utc)

    # 2. Log the transaction in the ledger
    ledger_entry = KonesLedger(
        user_auth_uid=current_user.auth_uid,
        amount=amount,
        description=description,
        # FIX: Resolve DeprecationWarning: datetime.utcnow() is deprecated
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(ledger_entry)

    db.session.commit()

    return jsonify({
        'message': f'Successfully added {amount} Kones.',
        'new_balance': balance_record.balance
    }), 200


@app.route('/webhook/sync', methods=['POST'])
@trusted_service_required
@get_user_from_auth_header
def webhook_sync(current_user):
    """
    Trusted route for syncing external data (e.g., e-commerce,
    third-party events) to the Chronolog for auditing.
    """
    data = request.get_json()
    event_type = data.get('event_type')
    payload = data.get('payload')

    if not event_type or not payload:
        return jsonify({
            'message': ("Request must include 'event_type' and 'payload'.")
        }), 400

    # Sanitize and standardize event type for Chronolog
    log_event = f"WEBHOOK_{event_type.upper().replace(' ', '_')}"

    # 1. Log the incoming webhook event
    chronolog_entry = Chronolog(
        user_auth_uid=current_user.auth_uid,
        event_type=log_event,
        payload=payload,
        # FIX: Resolve DeprecationWarning: datetime.utcnow() is deprecated
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(chronolog_entry)
    db.session.commit()

    return jsonify({
        'message': 'Webhook event processed.',
        'event_type': log_event
    }), 200


if __name__ == '__main__':
    # When running the app directly (e.g., python kaisurf_secured_app.py)
    with app.app_context():
        # Ensure the database tables are created for development
        db.create_all()
    app.run()
