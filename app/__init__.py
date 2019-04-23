import os, configparser, datetime
from flask import Flask, redirect
from flask_mongoengine import MongoEngine
from flask_login import LoginManager
from flask_gravatar import Gravatar

mongo_settings = configparser.ConfigParser()
mongo_settings.read('mongo-credentials.ini')

app = Flask(__name__)

app.config['MONGODB_SETTINGS'] = {
#    'db' : 'test',
    'host': mongo_settings['development']['hostname'],
}
app.config['SECRET_KEY'] = 'dont-guess-this-please'
app.config['SERVER_NAME'] = os.environ.get('SERVER_NAME')

db = MongoEngine(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.session_protection = "strong"
login_manager.login_message = None

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

from app.admin.routes import admin as admin_module
from app.public.routes import public as public_module
from app.huey import huey

# Add current datetime to jinja template
@app.context_processor
def inject_datetime():
    return dict(now=datetime.datetime.now())

# Register admin first so that it takes precendence over our domain search
app.register_blueprint(admin_module, url_prefix='/admin')
app.register_blueprint(public_module)

from app import routes
