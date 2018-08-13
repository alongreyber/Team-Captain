from app import app, oauth, models

from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint
from flask_login import current_user, login_required, login_user

from requests.exceptions import HTTPError

public = Blueprint('public', __name__, template_folder='templates')

@app.route('/')
@login_required
def index():
    return "Authorized!"

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    google = oauth.get_google_auth()
    auth_url, state = google.authorization_url( oauth.AUTH_URI, access_type='offline')
    session['oauth_state'] = state
    return render_template('public/login.html', auth_url=auth_url)

@app.route('/oauth2callback')
def callback():
    # Redirect user to home page if already logged in.
    if current_user is not None and current_user.is_authenticated:
        return redirect(url_for('index'))
    if 'error' in request.args:
        if request.args.get('error') == 'access_denied':
            return 'You denied access.'
        return 'Error encountered.'
    if 'code' not in request.args and 'state' not in request.args:
        return redirect(url_for('app.login'))
    else:
        # Execution reaches here when user has successfully authenticated our app.
        google = oauth.get_google_auth(state=session['oauth_state'])
        try:
            token = google.fetch_token( oauth.TOKEN_URI, client_secret=oauth.CLIENT_SECRET, authorization_response=request.url)
        except HTTPError:
            return 'HTTPError occurred.'
        google = oauth.get_google_auth(token=token)
        resp = google.get(oauth.USER_INFO)
        if resp.status_code == 200:
            user_data = resp.json()
            email = user_data['email']
            user = models.User.objects(email=email).first()
            if user is None:
                user = models.User(email=email)
            user.name = user_data['name']
            #user.tokens = json.dumps(token)
            #user.avatar = user_data['picture']
            user.save()
            login_user(user)
            return redirect(url_for('index'))
        return 'Could not fetch your information.'
