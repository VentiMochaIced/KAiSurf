# FIX: Import timezone alongside datetime for modern, non-deprecated usage
from datetime import datetime, timezone
# CRITICAL FIX: The import now matches the new app file name
from kaisurf_secured_app import db


class User(db.Model):
    # CRITICAL FIX: Removed 'id' as primary key and 'roaming_id' entirely.
    # The external authentication ID ('auth_uid') is now the
    # sole unique identifier.
    auth_uid = db.Column(db.String(128), primary_key=True,
                         unique=True, nullable=False)

    # Relationships
    # Note: user_id ForeignKey must now reference 'user.auth_uid'
    kones_balance = db.relationship(
        'KonesBalance', backref='user', lazy=True, uselist=False
    )
    ledger_entries = db.relationship(
        'KonesLedger', backref='user', lazy=True
    )
    chronolog_entries = db.relationship(
        'Chronolog', backref='user', lazy=True
    )

    def __repr__(self):
        return f'<User {self.auth_uid}>'


class KonesBalance(db.Model):
    # CRITICAL FIX: The Foreign Key now points to the string auth_uid
    id = db.Column(db.Integer, primary_key=True)
    user_auth_uid = db.Column(db.String(128), db.ForeignKey('user.auth_uid'),
                              nullable=False)
    balance = db.Column(db.Integer, nullable=False, default=0)
    # FIX: Use datetime.now(timezone.utc) to resolve DeprecationWarning
    last_updated = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __repr__(self):
        return (f'<KonesBalance User:{self.user_auth_uid} '
                f'Balance:{self.balance}>')


class KonesLedger(db.Model):
    # CRITICAL FIX: The Foreign Key now points to the string auth_uid
    id = db.Column(db.Integer, primary_key=True)
    user_auth_uid = db.Column(db.String(128), db.ForeignKey('user.auth_uid'),
                              nullable=False)
    # Positive for earn, negative for spend
    amount = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(256), nullable=False)
    # FIX: Use datetime.now(timezone.utc) to resolve DeprecationWarning
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __repr__(self):
        return (f'<KonesLedger User:{self.user_auth_uid} '
                f'Amount:{self.amount}>')


class Chronolog(db.Model):
    # CRITICAL FIX: The Foreign Key now points to the string auth_uid
    id = db.Column(db.Integer, primary_key=True)
    user_auth_uid = db.Column(db.String(128), db.ForeignKey('user.auth_uid'),
                              nullable=False)
    event_type = db.Column(db.String(128), nullable=False)
    payload = db.Column(db.JSON, nullable=False)  # Store JSON data
    # FIX: Use datetime.now(timezone.utc) to resolve DeprecationWarning
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __repr__(self):
        return (f'<Chronolog User:{self.user_auth_uid} '
                f'Event:{self.event_type}>')
