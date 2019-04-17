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

@public.route('/notification/<id>/redirect')
@login_required
def notification_redirect(id):
    notification = current_user.notifications.filter(id=id).first()
    if not notification:
        abort(404)
    # Log info about when notification was seen
    # Might be useful in the future
    return redirect(notification.link)

@public.route('/notification/<id>/dismiss')
def notification_dismiss(id):
    notification = current_user.notifications.filter(id=id).first()
    if not notification:
        abort(404)
    current_user.notifications.remove(notification)
    current_user.save()
    session['open-notifications'] = True
    # Log info about when notification was dismisised
    # Might be useful in the future
    return redirect(request.referrer)

@public.route('/task/<id>')
@login_required
def task_info(id):
    task = models.Task.objects(id=id).first()
    task.select_related(max_depth=2)
    if not task:
        abort(404)
    for tu in task.assigned_users:
        if current_user == tu.user:
            return render_template('public/task_info.html', task=task)
    abort(404)

@public.route('/tasks')
@login_required
def task_list():
    tasks = models.Task.objects(assigned_users__user=current_user.id)
    return render_template('public/task_list.html',tasks=tasks)

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
