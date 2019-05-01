from app import models, forms, oauth
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint
from flask_login import current_user, login_required

import pendulum
from bson import ObjectId


public = Blueprint('public', __name__, template_folder='templates')

@public.route('/home')
def index():
    return redirect(url_for('public.user_profile'))

@public.route('/profile')
@login_required
def user_profile():
    return render_template('public/user_profile.html')

@public.route('/profileedit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = forms.PublicUserForm(data=current_user.to_mongo().to_dict())
    if form.validate_on_submit():
        updated_dict = form.data
        del updated_dict['csrf_token']
        current_user.modify(**updated_dict)
        flash('Changes Saved', 'success')
        return redirect(url_for('public.user_profile'))
    return render_template('public/edit_profile.html', form=form)

@public.route('/submittimezone', methods=['POST'])
@login_required
def timezone_submit():
    # This isn't stored in db
    if request.json:
        current_user.tz = request.json
    else:
        current_user.tz = 'America/New_York'
    current_user.save()
    return "Success",200

@public.route('/meetings')
@login_required
def meetings_page():
    meetings = models.Meeting.objects()
    one_week_from_now = pendulum.now('UTC') + datetime.timedelta(days=7)
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

@public.route('/task/<id>/complete')
@login_required
def task_complete(id):
    # Make sure that the task is published and that the user is assigned to it
    tu_list = list(filter(lambda tu: tu.task.id == ObjectId(id), current_user.assigned_tasks))
    if len(tu_list) == 0:
        abort(404)
    tu = tu_list[0]
    if not tu.completed:
        tu.completed = pendulum.now('UTC')
        tu.save()
    return redirect(url_for('public.task_info', id=tu.task.id))

@public.route('/task/<id>')
@login_required
def task_info(id):
    # Make sure that the task is published and that the user is assigned to it
    tu_list = list(filter(lambda tu: tu.task.id == ObjectId(id), current_user.assigned_tasks))
    if len(tu_list) == 0:
        abort(404)
    tu = tu_list[0]
    if not tu.seen:
        tu.seen = pendulum.now('UTC')
        tu.save()
    task = tu.task
    return render_template('public/task_info.html', tu=tu)

@public.route('/tasks')
@login_required
def task_list():
    current_user.select_related(max_depth=2)
    tus = current_user.assigned_tasks
    return render_template('public/task_list.html',tus=tus)

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
