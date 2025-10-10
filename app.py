# app.py
# The primary entry point for the Flask application.

import os
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Load environment variables from .env file (must be installed: pip install python-dotenv)
load_dotenv()

# Initialize SQLAlchemy outside of the app factory pattern for ease of use 
# with separate model files and the initialization script (db.create_all()).
db = SQLAlchemy()

def create_app():
    """Initializes and configures the Flask application."""
    app = Flask(__name__)
    
    # 1. Load Configuration
    # Reads DATABASE_URL from the environment (or .env file)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Reads necessary security keys from the environment (or .env file)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_dev_secret')
    
    # Initialize the database with the app
    db.init_app(app)

    # NOTE: Routes will be imported and registered here once they are created in the 'routes/' folder.
    # Example: from .routes.content import content_bp
    #          app.register_blueprint(content_bp)

    return app

if __name__ == '__main__':
    # This block is used for local development serving.
    app = create_app()
    app.run(debug=True)
