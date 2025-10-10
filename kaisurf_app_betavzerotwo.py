# -*- coding: utf-8 -*-
"""KAiSurf Multi-Platform Test App

KAiSurf Multi-Platform Test App - RL v1.0 Checkpoint - SECURITY FIX COMMITTED

This update integrates mandatory security requirements for online testing:
1. JWT validation using PyJWT and SUPABASE_JWT_SECRET.
2. Trusted API Key validation for server-to-server endpoints (e.g., /kones/earn).
3. Updated User model to securely map Supabase auth_uid to the internal record.
4. **NEW:** Implements CRUD for KinetikontentPost and RU for UserProfile.
"""

import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

# Load environment variables (mandatory for local testing/deployment)
load_dotenv()

# --- Configuration & Initialization ---
app = Flask(__name__)
# Get DB URL safely, ensuring it exists for app context creation
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print("WARNING: DATABASE_URL not set. Using SQLite in memory for structure modeling.")
    db_url = 'sqlite:///:memory:' 

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_for_test')

db = SQLAlchemy(app)

# --- Database Models (Content Sharing Apparatus Models Added) ---

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    auth_uid = db.Column(db.String(36), unique=True, nullable=False)
    roaming_id = db.Column(db.String(50), unique=True, nullable=False)

    # Relationship to other models
    profile = db.relationship('UserProfile', backref='user', uselist=False, lazy=True)
    posts = db.relationship('KinetikontentPost', backref='author', lazy=True)
    
    def __repr__(self):
        return f"<User {self.roaming_id}>"

class UserProfile(db.Model):
    __tablename__ = 'userprofile'
    # Primary key is the user_id, ensuring 1:1 relationship
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    bio = db.Column(db.Text, default="A kinetic soul on the surf.")
    avatar_url = db.Column(db.String(255))
    kones_total_earned = db.Column(db.Integer, default=0)
    last_login = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'bio': self.bio,
            'avatar_url': self.avatar_url,
            'kones_total_earned': self.kones_total_earned,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class KinetikontentPost(db.Model):
    __tablename__ = 'kinetikontentpost'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    media_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=db.func.now())
    is_active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'content': self.content,
            'media_url': self.media_url,
            'created_at': self.created_at.isoformat(),
            'author_roaming_id': self.author.roaming_id # Access via relationship
        }

# --- Ledger & Chronolog Models (from previous version, included for completeness) ---

class Chronolog(db.Model):
    __tablename__ = 'chronolog'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    event_type = db.Column(db.String(50), nullable=False)
    payload = db.Column(db.JSON)

class KonesLedger(db.Model):
    __tablename__ = 'konesledger'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    transaction_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255))

class KonesBalance(db.Model):
    __tablename__ = 'konesbalance'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    balance = db.Column(db.Integer, default=0)


# --- Helper Functions ---

def add_chrono_log_entry(user_id, event_type, payload):
    log_entry = Chronolog(user_id=user_id, event_type=event_type, payload=payload)
    db.session.add(log_entry)

# --- SECURITY DECORATORS AND AUTHENTICATION LOGIC ---

def get_user_from_auth_header():
    """Validates the JWT from the Authorization header and returns the internal User object."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, jsonify({"error": "Unauthorized: Missing or malformed Authorization header."}), 401

    token = auth_header.split(' ')[1]
    supabase_jwt_secret = os.environ.get('SUPABASE_JWT_SECRET')

    if not supabase_jwt_secret:
        print("CRITICAL: SUPABASE_JWT_SECRET is not configured.")
        return None, jsonify({"error": "Server configuration error."}), 500

    try:
        payload = jwt.decode(
            token,
            supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_signature": True, "verify_exp": True}
        )
        auth_uid = payload.get('sub') # 'sub' is the Supabase user ID

        user = User.query.filter_by(auth_uid=auth_uid).first()
        if not user:
            return None, jsonify({"error": "User token validated, but internal user record not found. Please sync."}), 404
        
        # Store user in Flask global request context for easy access in views
        g.current_user = user 
        return user, None

    except ExpiredSignatureError:
        return None, jsonify({"error": "Authentication failed: Token has expired."}), 401
    except InvalidTokenError as e:
        return None, jsonify({"error": f"Authentication failed: Invalid token ({e})."}), 401
    except Exception as e:
        return None, jsonify({"error": f"Authentication processing failed: {e}"}), 401

def login_required(f):
    """Decorator to enforce user authentication via JWT."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user, error = get_user_from_auth_header()
        if error:
            return error
        return f(*args, **kwargs)
    return decorated_function

def check_ownership(model_instance, user_id):
    """Helper function to verify if the given user owns the model instance."""
    return model_instance.user_id == user_id


def trusted_service_required(f):
    """Decorator to require a valid API key for server-to-server communication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-Api-Key')
        trusted_key = os.environ.get('TRUSTED_SERVICE_API_KEY')

        if not trusted_key:
            print("CRITICAL: TRUSTED_SERVICE_API_KEY is not configured.")
            return jsonify({"error": "Server configuration error."}), 500

        if not api_key or api_key != trusted_key:
            print(f"SECURITY ALERT: Forbidden access attempt with key: {api_key}")
            return jsonify({"error": "Forbidden: Invalid or missing API Key for trusted service."}), 403

        return f(*args, **kwargs)
    return decorated

# --- Content Sharing Endpoints (CRUD KinetikontentPost) ---

# R - Read (List): Get all active posts
@app.route('/content/posts', methods=['GET'])
@login_required
def list_posts():
    # Only list active posts
    posts = KinetikontentPost.query.filter_by(is_active=True).order_by(KinetikontentPost.created_at.desc()).limit(100).all()
    
    return jsonify({
        "message": f"Welcome, {g.current_user.roaming_id}. Content listing successful.",
        "user_id": g.current_user.id,
        "posts": [post.to_dict() for post in posts]
    }), 200

# C - Create: Create a new content post
@app.route('/content/post', methods=['POST'])
@login_required
def create_post():
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    media_url = data.get('media_url')

    if not title or not content:
        return jsonify({"error": "Title and content are required fields."}), 400

    new_post = KinetikontentPost(
        user_id=g.current_user.id,
        title=title,
        content=content,
        media_url=media_url
    )
    db.session.add(new_post)
    add_chrono_log_entry(g.current_user.id, 'POST_CREATED', {'post_id': new_post.id, 'title': title})
    db.session.commit()

    return jsonify({"message": "Post created successfully.", "post": new_post.to_dict()}), 201

# R - Read (Single): Get a specific post
@app.route('/content/post/<int:post_id>', methods=['GET'])
# Note: Public access, RLS handles visibility/security in the database
def get_post(post_id):
    post = KinetikontentPost.query.get(post_id)
    if not post or not post.is_active:
        return jsonify({"error": "Post not found."}), 404
    
    return jsonify({"post": post.to_dict()}), 200

# U - Update: Modify an existing post (Ownership required)
@app.route('/content/post/<int:post_id>', methods=['PUT'])
@login_required
def update_post(post_id):
    post = KinetikontentPost.query.get(post_id)
    if not post or not post.is_active:
        return jsonify({"error": "Post not found."}), 404

    # Ownership Check: Only the original creator can update
    if not check_ownership(post, g.current_user.id):
        return jsonify({"error": "Forbidden: You do not own this post."}), 403

    data = request.get_json()
    post.title = data.get('title', post.title)
    post.content = data.get('content', post.content)
    post.media_url = data.get('media_url', post.media_url)
    
    add_chrono_log_entry(g.current_user.id, 'POST_UPDATED', {'post_id': post.id})
    db.session.commit()
    return jsonify({"message": "Post updated successfully.", "post": post.to_dict()}), 200

# D - Delete: Soft-delete a post (Ownership required)
@app.route('/content/post/<int:post_id>', methods=['DELETE'])
@login_required
def delete_post(post_id):
    post = KinetikontentPost.query.get(post_id)
    if not post or not post.is_active:
        return jsonify({"error": "Post not found."}), 404
    
    # Ownership Check: Only the original creator can delete
    if not check_ownership(post, g.current_user.id):
        return jsonify({"error": "Forbidden: You do not own this post."}), 403

    # Perform soft-delete (setting is_active=False)
    post.is_active = False

    add_chrono_log_entry(g.current_user.id, 'POST_DELETED', {'post_id': post.id})
    db.session.commit()
    return jsonify({"message": "Post soft-deleted successfully."}), 200


# --- User Profile Endpoints (RU UserProfile) ---

# R - Read: Get a user's profile
@app.route('/user/profile/<int:user_id>', methods=['GET'])
# Note: Public read access is assumed, with RLS protecting the update endpoint
def get_user_profile(user_id):
    profile = UserProfile.query.get(user_id)
    if not profile:
        return jsonify({"error": "User profile not found."}), 404
    
    return jsonify({"profile": profile.to_dict()}), 200

# U - Update: Update the current user's own profile
@app.route('/user/profile', methods=['PUT'])
@login_required
def update_own_profile():
    # Because @login_required ran, g.current_user is available
    user_id = g.current_user.id
    profile = UserProfile.query.get(user_id)
    
    if not profile:
        # If profile doesn't exist yet, create a default one (or handle initial sync)
        profile = UserProfile(user_id=user_id)
        db.session.add(profile)

    data = request.get_json()
    profile.bio = data.get('bio', profile.bio)
    profile.avatar_url = data.get('avatar_url', profile.avatar_url)
    
    add_chrono_log_entry(user_id, 'PROFILE_UPDATED', {'fields': list(data.keys())})
    db.session.commit()
    return jsonify({"message": "Profile updated successfully.", "profile": profile.to_dict()}), 200


# --- Kones Earning & Webhook Endpoints (from previous version, included for completeness) ---

@app.route('/kones/earn', methods=['POST'])
@login_required
@trusted_service_required
def earned_kones():
    # User identity is in g.current_user from @login_required
    user = g.current_user
    data = request.get_json()
    amount = data.get('amount')
    description = data.get('description', 'Content reward')

    if not isinstance(amount, int) or amount <= 0:
        return jsonify({"error": "A positive integer amount is required."}), 400

    # Add to ledger
    ledger_entry = KonesLedger(user_id=user.id, transaction_type='EARN_CONTENT', amount=amount, description=description)
    db.session.add(ledger_entry)

    # Update balance (needs creation if not exists)
    balance = KonesBalance.query.get(user.id)
    if not balance:
        balance = KonesBalance(user_id=user.id, balance=0)
        db.session.add(balance)

    balance.balance += amount
    
    # Update total earned in user profile
    profile = UserProfile.query.get(user.id)
    if profile:
        profile.kones_total_earned += amount
    
    add_chrono_log_entry(user.id, 'KONES_EARNED', {'amount': amount, 'reason': description})
    db.session.commit()

    return jsonify({"message": f"{amount} Kones awarded.", "new_balance": balance.balance}), 200

@app.route('/webhook/sync', methods=['POST'])
@login_required
@trusted_service_required
def webhook_sync():
    # User identity is in g.current_user from @login_required
    user = g.current_user
    data = request.get_json()
    if not data or 'event_type' not in data or 'payload' not in data:
        return jsonify({"error": "Request must include 'event_type' and 'payload'."}), 400

    add_chrono_log_entry(user.id, f"WEBHOOK_{data['event_type'].upper()}", data['payload'])
    db.session.commit()
    return jsonify({"status": "Webhook event processed."}), 200

# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context():
        # WARNING: This is for local development only. 
        # For deployment, a migration tool (Alembic/Flask-Migrate) must be used.
        # This function creates all required tables (User, UserProfile, KinetikontentPost, Ledger, Chronolog, Balance)
        print("Creating ALL required tables (DEV ONLY - REMOVE FOR PROD DEPLOYMENT)...")
        # db.create_all() # Uncomment for initial local testing
    print("--- KAiSurf Test App (RL v1.0, Content Sharing Complete) ---")
    # app.run(debug=True)
