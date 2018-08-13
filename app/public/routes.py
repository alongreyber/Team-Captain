from app import models, forms, oauth
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint
from flask_login import current_user, login_required

import datetime

public = Blueprint('public', __name__, template_folder='templates')

@public.route('/')
@login_required
def index():
    return "Authorized!"
