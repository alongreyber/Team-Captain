from app import app, models
from flask import render_template

from flask_mongoengine.wtf import model_form

@app.route('/')
def list_users():
    users = models.User.objects
    return render_template('user_list.html', users=users)
