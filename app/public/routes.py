from app import models, forms, tasks
from app.admin import context
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint, send_file, g
from flask_login import current_user, login_required

public = Blueprint('public', __name__, template_folder='templates')

@public.route('/home')
@login_required
def home():
    return render_template('public/home.html')
