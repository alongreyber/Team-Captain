import os
from flask import Flask, redirect
from flask_mongoengine import MongoEngine
from flask_login import LoginManager

app = Flask(__name__)

app.config['MONGODB_SETTINGS'] = {
    'db': 'admin',
    'host': 'mongo',
    'username': 'root',
    'password': 'password'
}
app.config['SECRET_KEY'] = 'dont-guess-this-please'
app.config['SERVER_NAME'] = os.environ.get('SERVER_NAME')

db = MongoEngine(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.session_protection = "strong"

from app.admin.routes import admin as admin_module
from app.public.routes import public as public_module

# Register admin first so that it takes precendence over our domain search
app.register_blueprint(admin_module, subdomain='admin')
app.register_blueprint(public_module)

from app import routes
