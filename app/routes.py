from app import app, oauth, models, forms, login_manager

from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint, abort
from flask_login import current_user, login_required, login_user, logout_user

from mongoengine.errors import NotUniqueError

import requests
import pendulum
import os, json


# What to do if user tries to access unauthorized route
@login_manager.unauthorized_handler
def unauthorized_callback():
    session['next_url'] = request.path
    return redirect(url_for('login'))

@app.route('/')
def landing_page():
    if current_user.is_authenticated:
        if not current_user.team:
            return redirect(url_for('join_team_pending'))
        team = current_user.team.fetch()
        return redirect(url_for('team.index', sub=team.sub))
    return render_template('landing_page.html')

@app.route('/login')
def login():
    if current_user.is_authenticated:
        team = current_user.team.fetch()
        return redirect(url_for('team.index', sub=team.sub))
    # Save the URL that we go to after logging in
    google = oauth.get_google_auth()
    auth_url, state = google.authorization_url( oauth.AUTH_URI, access_type='offline')
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
    # Redirect user to home page if already logged in.
    if current_user is not None and current_user.is_authenticated:
        team = current_user.team.fetch()
        return redirect(url_for('team.index', sub=team.sub))
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
            email = user_data['email']
            domain = email[email.find('@')+1:]
            user = models.User.objects(email=email).first()
            if not user:
                user = models.User(email=email)
                user.save()
            login_user(user)
            if next_url:
                return redirect(next_url)
            if not user.team:
                flash('Please create or join a team first!', 'warning')
                return redirect(url_for('landing_page'))
            team = user.team.fetch()
            return redirect(url_for('team.index', sub=team.sub))
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
            team.sub = form.sub.data
            saved = False
            try:
                team.save()
                saved = True
            except NotUniqueError:
                flash('Subdomain already in use. Please pick another!', 'warning')
            if saved:
                team.reload()
                load_sample_data(team)
                everyone_role = models.Role.objects(team=team, name='everyone').first()
                admin_role    = models.Role.objects(team=team, name='admin').first()
                mentor_role   = models.Role.objects(team=team, name='mentor').first()
                current_user.team = team
                current_user.approved = pendulum.now()
                current_user.roles = [everyone_role, admin_role, mentor_role]
                current_user.save()
                # Don't know why we have to do this
                this_user = models.User.objects(id=current_user.id).first()
                current_user.assigned_tasks = [this_user]
                current_user.save()
                # Redirect to new workspace
                session['modal_title'] = 'Welcome!'
                session['modal_content'] = '''
                Thanks for joining Team Captain! We've loaded some sample data into your workspace so you can take a look around. Let us know if you have any questions!
                '''
                return redirect(url_for('team.index', sub=team.sub))
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('create_team.html', form=form)

def load_sample_data(team):
    # Sample roles
    path = './sample-data/'
    files = os.listdir(path)
    for f_name in files:
        with open(path + f_name, 'r') as f:
            f_str = f.read()
        collection = json.loads(f_str)
        for doc in collection:
            Model = getattr(models, f_name[:f_name.find('.')])
            obj = Model.from_json(json.dumps(doc))
            obj.team = team
            obj.save()

@app.route('/jointeam', methods=['GET', 'POST'])
@login_required
def join_team():
    form = forms.JoinTeamForm()
    if form.validate_on_submit():
        if current_user.team:
            team = current_user.team.fetch()
            return redirect(url_for('team.index', sub=team.sub))
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
