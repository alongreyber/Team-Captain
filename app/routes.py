from app import app, oauth, models, forms

from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint
from flask_login import current_user, login_required, login_user, logout_user

import requests
import pendulum

# These routes are for non-authenticated users

@app.route('/')
def landing_page():
    if current_user.is_authenticated:
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
    session['creating_team'] = request.args.get('creating_team')
    return redirect(auth_url)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing_page'))

@app.route('/oauth2callback')
def callback():
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
                if 'creating_team' in session:
                    user.creating_team = True
                user.save()
                user.reload()

            login_user(user)
            if user.team and user.approved:
                team = user.team.fetch()
                return redirect(url_for('team.index', sub=team.sub))
            if user.creating_team:
                return redirect(url_for('create_team'))
            else:
                # User is joining a team
                if user.team:
                    return redirect(url_for('join_team_pending'))
                else:
                    return redirect(url_for('join_team'))
        return 'Could not fetch your information.'

@app.route('/createteam', methods=['GET', 'POST'])
@login_required
def create_team():
    form = forms.CreateTeamForm()
    if form.validate_on_submit():
        team = models.Team.objects(number=form.number.data).first()
        if team:
            flash('Team already exists!', 'warning')
        else:
            url = 'https://frc-events.firstinspires.org/services/avatar/team'
            params = {'teamNumber': form.number.data,
                      'accessCode': form.code.data,
                      'terms'     : 'on'}
            r = requests.post(url, data=params)
            verified = str(form.number.data) in r.text
            if verified:
                flash('Verification Successful', 'success')
                team = models.Team(number=form.number.data)
                team.save()
                team.reload()
                user.team = team
                user.approved = pendulum.now()
                user.save()
                # Redirect to new workspace
                return redirect(url_for('team.index'), sub=team.sub)
            else:
                flash('Verification Unsuccessful. Please try again', 'danger')
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('create_team.html', form=form)

@app.route('/jointeam_pending')
@login_required
def join_team_pending():
    return render_template('join_team_pending.html')

@app.route('/jointeam', methods=['GET', 'POST'])
@login_required
def join_team():
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
