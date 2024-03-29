from app import app, oauth, models, forms, login_manager

from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint, abort
from flask_login import current_user, login_required, login_user, logout_user

from mongoengine.errors import NotUniqueError

import requests
import pendulum
import os, json

from bson import ObjectId

# What to do if user tries to access unauthorized route
@login_manager.unauthorized_handler
def unauthorized_callback():
    session['next_url'] = request.path
    return redirect(url_for('login'))

@app.route('/')
def landing_page():
    return render_template('landing_page.html')

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('public.feed'))
    # Save the URL that we go to after logging in
    google = oauth.get_google_auth()
    auth_url, state = google.authorization_url(oauth.AUTH_URI,
                                               access_type='offline',
                                               prompt='consent')
    session['oauth_state'] = state
    return redirect(auth_url)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing_page'))

@app.route('/oauth2callback')
def callback():
    next_url = session.pop('next_url', None)
    if 'error' in request.args:
        if request.args.get('error') == 'access_denied':
            return 'You denied access.'
        return 'Error encountered.'
    if 'code' not in request.args and 'state' not in request.args:
        return redirect(url_for('login'))
    else:
        # Execution reaches here when user has successfully authenticated our app.
        google = oauth.get_google_auth(state=session['oauth_state'])
        try:
            token = google.fetch_token( oauth.TOKEN_URI, client_secret=oauth.CLIENT_SECRET, authorization_response=request.url)
        except requests.exceptions.HTTPError:
            return 'HTTPError occurred.'
        google = oauth.get_google_auth(token=token)
        resp = google.get(oauth.USER_INFO)
        if resp.status_code == 200:
            user_data = resp.json()
            print(user_data)
            email = user_data['email']
            domain = email[email.find('@')+1:]
            user = models.User.objects(email=email).first()
            if not user:
                user = models.User()
                user.email = user_data['email']
                user.first_name = user_data['given_name']
                user.last_name = user_data['family_name']
                user.save()
            login_user(user)
            if next_url:
                return redirect(next_url)
            return redirect(url_for('public.feed'))
        return 'Could not fetch your information.'

def verify_team(number, code):
    url = 'https://frc-events.firstinspires.org/services/avatar/team'
    params = {'teamNumber': number,
              'accessCode': code,
              'terms'     : 'on'}
    r = requests.post(url, data=params)
    verified = str(form.number.data) in r.text
    return verified

@app.route('/createteam', methods=['GET', 'POST'])
@login_required
def create_team():
    if current_user.team:
        flash('You are already a member of a team! To change or leave your team please go to the user settings page', 'warning')
        return redirect(request.referrer)
    form = forms.CreateTeamForm()
    if form.validate_on_submit():
        team = models.Team.objects(number=form.number.data).first()
        if team:
            flash('Team already exists!', 'warning')
        else:
            team = models.Team(number=form.number.data)
            team.owner = current_user.id
            team.number = form.number.data
            team.name = form.name.data
            saved = False
            try:
                team.save()
                saved = True
            except NotUniqueError:
                flash('Subdomain already in use. Please pick another!', 'warning')
            if saved:
                team.reload()
                current_user.team = team
                current_user.save()
                # Redirect to new workspace
                session['modal_title'] = 'Welcome!'
                session['modal_content'] = '''
                Thanks for joining Team Captain!
                '''
                return redirect(url_for('admin.index'))
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('create_team.html', form=form)

def load_sample_data(team):
    path = './sample-data/'
    files = os.listdir(path)
    # We need to replace all ObjectIds with new ones
    oid_mappings = {}
    for f_name in files:
        if not f_name.endswith('.json'):
            continue
        with open(path + f_name, 'r') as f:
            f_str = f.read()
        def generate_new_oid(v):
            # Only one key-val
            if len(v) == 1:
                if '$oid' in v:
                    oid = v['$oid']
                    if oid not in oid_mappings:
                        oid_mappings[oid] = str(ObjectId())
                    v['$oid'] = oid_mappings[oid]
            return v
        collection = json.loads(f_str, object_hook=generate_new_oid)
        for doc in collection:
            Model = getattr(models, f_name[:f_name.find('.')])
            obj = Model.from_json(json.dumps(doc))
            obj.team = team
            obj.save(force_insert=True)

@app.route('/jointeam', methods=['GET', 'POST'])
@login_required
def join_team():
    if current_user.team:
        flash('You are already a member of a team! To change or leave your team please go to the user settings page', 'warning')
        return redirect(request.referrer)
    form = forms.JoinTeamForm()
    if form.validate_on_submit():
        team = models.Team.objects(number=form.number.data).first()
        if not team:
            flash('This team does not have a Team Captain account yet. Ask your mentors to sign up!', 'warning')
        else:
            current_user.team_number = team.number
            current_user.save()
            return redirect(url_for('join_team_pending'))
    return render_template('join_team.html', form=form)

def flash_errors(form):
    """Flash errors from a form at the top of the page"""
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ), 'warning')

@app.route('/jointeam_pending')
def join_team_pending():
    if current_user.team:
        team = current_user.team.fetch()
        return redirect(url_for('team.index', sub=team.sub))
    return render_template('join_team_pending.html')
