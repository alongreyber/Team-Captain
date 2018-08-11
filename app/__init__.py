import os
from flask import Flask, redirect
from flask_mongoengine import MongoEngine

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

from app import routes
