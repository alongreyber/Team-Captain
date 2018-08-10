from flask import Flask, redirect
from flask_mongoengine import MongoEngine

app = Flask(__name__)

app.config['MONGODB_SETTINGS'] = {
    'db': 'admin',
    'host': 'mongo',
    'username': 'root',
    'password': 'password'
}

db = MongoEngine(app)

from app import routes
