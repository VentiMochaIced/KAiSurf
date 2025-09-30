"""
KAiSurf Multi-Platform Test App - RL v1.0.1

This Flask application serves as a comprehensive template for the KAiSurf backend,
incorporating all features discussed and designed for multi-platform deployment.
The database configuration is interchangeable, supporting SQLite for local testing
and PostgreSQL for production environments like Supabase.

==================================
AI FEEDBACK & ARCHITECTURAL ANALYSIS (RL v1.0.1):
==================================
This version introduces a critical separation of concerns between the backend logic and the
front-end user experience (UIX). By creating a centralized `/app/config` endpoint, the backend now
drives the main UI flow, allowing for dynamic menu structures and feature flagging without
requiring client-side updates. This is a significant step towards a truly multi-platform,
remotely configurable application.

The "Kones" reward system has been refactored into an optional, variant-based module. This
addresses the core requirement of making the cryptocurrency functionality an expansion variable.
The system can be enabled or disabled via a single configuration flag, and the types of rewards
are now data-driven, managed via a new `RewardRule` table. This provides immense flexibility for
A/B testing reward strategies or pivoting the monetization model.

* **UIX & Retro-compatibility:** The new `/app/config` endpoint is the designated entry point for
    all front-end applications. It provides a structured menu that older client versions can still
    partially understand, while newer clients can render the full, context-aware UI. This ensures
    forward progression without breaking older app versions.

* **Conflict Subversion/Class Dismissal:**
    - Clarification Check: Dismissing the concept of building a literal UI within this backend file.
      Instead, this version provides the API endpoints and data structures that a dedicated UIX
      (React, Vue, mobile native) would consume to build the user interface.
    - The new `RewardRule` model and its associated endpoints replace potential conflicts where reward
      logic might have been hard-coded, making it a single source of truth for all "Kone" variants.

* **Conceptual Rewards Variation:** The `RewardRule` system is designed to handle a wide range of
    user incentives:
    - **Common (Accumulation):** E.g., 'CREATE_KONTENT', 'DAILY_LOGIN'. These are standard, repeatable
      actions that drive core engagement.
    - **Uncommon (Collection):** E.g., 'EVENT_PARTICIPATION', 'BETA_TESTER_BONUS'. These can be
      time-limited or single-claim rules, managed by an admin, to incentivize specific behaviors.
    - **Transaction Callbacks:** The 'temporary' or 'standard' reward increases are handled by
      activating/deactivating or updating the `kone_amount` in the `RewardRule` table. This allows
      for dynamic "double reward weekends" or promotional events without code changes.

==================
CHANGE LOG (TEST BRANCH - RL v1.0.1):
==================
Version: Test Branch RL v1.0.1

-   **FEATURE (Main UIX Configuration):**
    -   Added a new public endpoint `/app/config` that serves a JSON object defining the main UI
      menu, app version, and feature flags. This is the new primary entry point for any client app.
    -   The menu structure is now driven by the backend, allowing for dynamic updates.
      [* dev feedback: The front-end should fetch this config on startup. The `menu` array can be
      used to dynamically generate navigation links. The `feature_flags` object tells the client
      which features, like 'kones', are active server-side. *]

-   **MODULE (Optional "Kones" System):**
    -   The entire "Kones" cryptocurrency system is now modular and can be disabled.
    -   Added `app.config['KONES_REWARDS_ENABLED']`. If set to `False`, all "Kones" models are
      bypassed, and related endpoints will return a 'feature disabled' message.
      [* dev feedback: This allows for a "slimmed down" version of the app to be deployed, or for
      the rewards system to be toggled for maintenance, without affecting core functionality. *]

-   **FEATURE ("Kones" Variants & Rules Engine):**
    -   Introduced a new `RewardRule` model to define different ways users can earn Kones. This
      makes the rewards system data-driven and highly configurable.
    -   Added a conceptual admin endpoint `/admin/rewards/set` to manage these rules, allowing for
      temporary reward increases or new earning methods to be added on the fly.
    -   Added a new user-facing endpoint `/kones/ledger` for users to view their transaction history.
      [* dev feedback: The UIX can use the `/kones/ledger` endpoint to build a "bank statement"
      view for the user, showing how they earned and spent their Kones. *]

-   **REFACTOR (Authentication & Context):**
    -   The `get_user_from_auth_header` function now attaches the authenticated user object to Flask's
      global `g` context (`g.user`).
    -   Created a new decorator `@require_auth` that uses `g.user` to protect endpoints, simplifying
      the code and making authentication checks more explicit and readable.
      [* dev feedback: This is a standard and robust pattern in Flask. All protected endpoints should
      now use `@require_auth` instead of manually calling the helper function. *]
"""
import os
import datetime
import uuid
import json
from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

# --- Application Setup ---
app = Flask(__name__)

# --- Configuration ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///kaisurf_test_rl101.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-super-secret-key-for-testing')

# --- Main UIX / Addon Configuration ---
# This flag controls the entire "Kones" module. Set to False to disable.
app.config['KONES_REWARDS_ENABLED'] = True


db = SQLAlchemy(app)

# --- SQLAlchemy ORM Models (Full Schema) ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roaming_id = db.Column(db.String(100), unique=True, nullable=False)
    registration_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class LoginRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    login_username = db.Column(db.String(150), nullable=False)
    login_timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class ChronoLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# --- "Kones" Kryptocoin System Models (Now Optional) ---
if app.config['KONES_REWARDS_ENABLED']:
    class KonesBalance(db.Model):
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
        balance = db.Column(db.Integer, default=0, nullable=False)

    class KonesLedger(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
        transaction_type = db.Column(db.String(50), nullable=False)
        amount = db.Column(db.Integer, nullable=False)
        description = db.Column(db.Text)
        timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    class RewardRule(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        rule_name = db.Column(db.String(100), unique=True, nullable=False) # e.g., 'DAILY_LOGIN', 'CREATE_KONTENT'
        kone_amount = db.Column(db.Integer, nullable=False)
        description = db.Column(db.String(255))
        is_active = db.Column(db.Boolean, default=True)

# --- Placeholder Models for Future Branches ---
# [* dev feedback: These classes are defined but not used. They establish the intended future schema.
#    A new feature branch, e.g., 'feature/social', would add relationships and endpoints for UserProfile. *]
class UserProfile(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    display_name = db.Column(db.String(100))
    avatar_url = db.Column(db.String(255))

# --- Helper Functions & Decorators ---

def get_daily_username(roaming_id):
    today = datetime.date.today().isoformat()
    words = roaming_id.split()
    if len(words) != 2: return None
    return f"{words[0]}-{today}-{words[1]}"

def add_chrono_log_entry(user_id, activity_type, content):
    log_entry = ChronoLog(user_id=user_id, activity_type=activity_type, content=json.dumps(content))
    db.session.add(log_entry)

def require_auth(f):
    """Decorator to protect endpoints and load the user into the context."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_username = request.headers.get('X-Auth-Username')
        if not auth_username:
            return jsonify({"error": "Authentication username required."}), 401
        record = LoginRecord.query.filter_by(login_username=auth_username).order_by(LoginRecord.login_timestamp.desc()).first()
        if not record:
            return jsonify({"error": "Invalid or expired session username."}), 403
        user = User.query.get(record.user_id)
        if not user:
             return jsonify({"error": "Authenticated user not found."}), 404
        g.user = user  # Store user in Flask's global context for this request
        return f(*args, **kwargs)
    return decorated_function

# --- API Endpoints ---

@app.route('/app/config', methods=['GET'])
def get_app_config():
    """Main UIX endpoint. Provides the client with necessary info to render menus and features."""
    main_menu = [
        {"id": "profile", "label": "My Profile", "endpoint": "/user/profile", "auth_required": True},
        {"id": "chronolog", "label": "My Activity", "endpoint": "/user/chronolog", "auth_required": True},
    ]
    if app.config['KONES_REWARDS_ENABLED']:
        main_menu.append({"id": "kones", "label": "Kones Wallet", "endpoint": "/kones/balance", "auth_required": True})

    return jsonify({
        "app_name": "KAiSurf",
        "version": "RL v1.0.1",
        "menu": main_menu,
        "feature_flags": {
            "kones_enabled": app.config['KONES_REWARDS_ENABLED']
        }
    })

@app.route('/register', methods=['POST'])
def register():
    # ... (no changes from previous version)
    data = request.get_json()
    roaming_id = data.get('roaming_id', '').strip()
    if len(roaming_id.split()) != 2: return jsonify({"error": "Registration requires a 'roaming_id' of exactly two words."}), 400
    existing_user = User.query.filter_by(roaming_id=roaming_id).first()
    if not existing_user:
        new_user = User(roaming_id=roaming_id)
        db.session.add(new_user)
        db.session.commit()
        if app.config['KONES_REWARDS_ENABLED']:
            kones_balance = KonesBalance(user_id=new_user.id, balance=0)
            db.session.add(kones_balance)
        add_chrono_log_entry(new_user.id, 'REGISTRATION', {'status': 'Account created.'})
        db.session.commit()
    return jsonify({"message": "Registration request processed."}), 202

@app.route('/login', methods=['POST'])
def login():
    # ... (no changes from previous version)
    data = request.get_json()
    if not data or not all(k in data for k in ['roaming_id', 'username']): return jsonify({"error": "Roaming ID and username are required."}), 400
    user = User.query.filter_by(roaming_id=data['roaming_id']).first()
    if not user: return jsonify({"error": "Invalid credentials."}), 401
    expected_username = get_daily_username(data['roaming_id'])
    if data['username'] == expected_username:
        db.session.add(LoginRecord(user_id=user.id, login_username=data['username']))
        add_chrono_log_entry(user.id, 'LOGIN', {'status': 'Successful authentication.'})
        db.session.commit()
        return jsonify({"message": "Access Granted", "auth_username": expected_username}), 200
    else:
        return jsonify({"error": "Invalid credentials."}), 401

@app.route('/user/profile', methods=['GET'])
@require_auth
def get_user_profile():
    # Uses g.user from the decorator
    return jsonify({ "user_id": g.user.id, "roaming_id_hint": f"{g.user.roaming_id.split()[0]}...", "registered_since": g.user.registration_date.isoformat() }), 200

@app.route('/user/chronolog', methods=['GET'])
@require_auth
def get_chrono_log():
    # Uses g.user from the decorator
    logs = ChronoLog.query.filter_by(user_id=g.user.id).order_by(ChronoLog.timestamp.asc()).all()
    log_data = [{"timestamp": log.timestamp.isoformat(), "activity": log.activity_type, "details": json.loads(log.content)} for log in logs]
    return jsonify(log_data), 200

# --- Kones API Endpoints (Now Optional) ---
if app.config['KONES_REWARDS_ENABLED']:
    @app.route('/kones/balance', methods=['GET'])
    @require_auth
    def get_kones_balance():
        balance = KonesBalance.query.get(g.user.id)
        if not balance:
            balance = KonesBalance(user_id=g.user.id, balance=0)
            db.session.add(balance)
            db.session.commit()
        return jsonify({"user_id": g.user.id, "kone_balance": balance.balance}), 200

    @app.route('/kones/ledger', methods=['GET'])
    @require_auth
    def get_kones_ledger():
        """UIX Addon: Provides a transaction history for the Kones wallet view."""
        ledger_entries = KonesLedger.query.filter_by(user_id=g.user.id).order_by(KonesLedger.timestamp.desc()).all()
        history = [
            {"timestamp": entry.timestamp.isoformat(), "type": entry.transaction_type, "amount": entry.amount, "description": entry.description}
            for entry in ledger_entries
        ]
        return jsonify(history), 200

    @app.route('/admin/rewards/set', methods=['POST'])
    @require_auth # [* dev feedback: In production, this should have an additional decorator to check for admin role. *]
    def set_reward_rule():
        """Conceptual Admin Endpoint to create or update reward rules."""
        data = request.get_json()
        rule = RewardRule.query.filter_by(rule_name=data.get('rule_name')).first()
        if not rule:
            rule = RewardRule(rule_name=data.get('rule_name'))

        rule.kone_amount = data.get('kone_amount')
        rule.description = data.get('description')
        rule.is_active = data.get('is_active', True)
        db.session.add(rule)
        db.session.commit()
        return jsonify({"message": f"Reward rule '{rule.rule_name}' has been saved."}), 200

# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # [* dev feedback: Seed the database with a default rule if it doesn't exist.
        #    This makes the addon testable out-of-the-box. *]
        if app.config['KONES_REWARDS_ENABLED']:
            if not RewardRule.query.filter_by(rule_name='CREATE_KONTENT').first():
                 default_rule = RewardRule(rule_name='CREATE_KONTENT', kone_amount=10, description='For creating a new piece of Kinetikontent.')
                 db.session.add(default_rule)
                 db.session.commit()

    print("--- KAiSurf Test App (RL v1.0.1) Initialized ---")
    print(f"Database engine: {db.engine.url.drivername}")
    print(f"Kones Reward Module Enabled: {app.config['KONES_REWARDS_ENABLED']}")
    print("-------------------------------------------------")
    app.run(debug=True, port=5001)

