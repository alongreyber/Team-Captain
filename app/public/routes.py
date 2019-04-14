from app import models, forms, oauth
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint
from flask_login import current_user, login_required

import datetime

public = Blueprint('public', __name__, template_folder='templates')

@public.route('/home')
def index():
    return redirect(url_for('public.user_profile'))

@public.route('/profile')
@login_required
def user_profile():
    return render_template('public/user_profile.html', user=current_user)

@public.route('/meetings')
@login_required
def meetings_page():
    meetings = models.Meeting.objects()
    one_week_from_now = datetime.datetime.now() + datetime.timedelta(days=7)
    return render_template('public/meetings.html', user=current_user, meetings=meetings, one_week_from_now=one_week_from_now)

@public.route('/task/<id>')
@login_required
def task_info(id):
    task = models.Task.objects(id=id).first()
    if not task:
        abort(404)
    if current_user not in task.assigned_to:
        abort(404)
    return render_template('public/task_info.html', task=task)

@public.route('/rsvp/<id>')
@login_required
def rsvp_for_meeting(id):
    meeting = models.Meeting.objects(id=id).first()
    if not meeting or \
        'r' not in request.args \
        or request.args.get('r') not in ['y', 'n', 'm']:
        return redirect(request.referrer)
    if current_user in meeting.rsvp_yes:
        meeting.modify(pull__rsvp_yes=current_user.to_dbref())
    if current_user in meeting.rsvp_no:
        meeting.modify(pull__rsvp_no=current_user.to_dbref())
    if request.args.get('r') == 'y':
        meeting.modify(push__rsvp_yes=current_user.to_dbref())
    if request.args.get('r') == 'n':
        meeting.modify(push__rsvp_no=current_user.to_dbref())
    return redirect(request.referrer)
