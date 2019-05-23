from app import models, forms, oauth, tasks
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint, g
from flask_login import current_user, login_required

import pendulum
from bson import ObjectId

from mongoengine.errors import NotUniqueError

import datetime

team = Blueprint('team', __name__, template_folder='templates')

# Look up the current team
@team.url_value_preprocessor
def get_team(endpoint, values):
    team = models.Team.objects(sub=values.pop('sub')).first()
    if not team:
        abort(404)
    g.team = team

# Check that user belongs to this team
@team.before_request
def check_team():
    if not current_user.team:
        return redirect(url_for('landing_page'))
    if current_user.team.id != g.team.id:
        flash('You are not a member of this team!', 'warning')
        team = current_user.team.fetch()
        return redirect(url_for('team.index', sub=team.sub))

# Inject a function team_url_for that adds the correct subdomain
def team_url_for(*args, **kwargs):
    return url_for(*args, sub=g.team.sub, **kwargs)
@team.context_processor
def inject_url_for():
    return dict(team_url_for=team_url_for)

@team.route('/')
def index():
    return redirect(team_url_for('team.user_profile'))

@team.route('/profile')
@login_required
def user_profile():
    return render_template('team/user_profile.html')

@team.route('/profileedit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = forms.PublicUserForm(data=current_user.to_mongo().to_dict())
    if form.validate_on_submit():
        updated_dict = form.data
        del updated_dict['csrf_token']
        try:
            current_user.modify(**updated_dict)
            flash('Changes Saved', 'success')
            if current_user.first_name and current_user.last_name:
                for task in current_user.assigned_tasks:
                    if task.id == current_user.id:
                        current_user.assigned_tasks.remove(task)
                        current_user.save()
            return redirect(team_url_for('team.user_profile'))
        except NotUniqueError:
            flash('Barcode already in use', 'warning')
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('team/edit_profile.html', form=form)

@team.route('/user/<id>')
@login_required
def user_view(id):
    user = models.User.objects(team=g.team, id=id).first()
    if not user:
        abort(404)
    return render_template('team/user_view.html', user=user)

@team.route('/users')
@login_required
def user_list():
    users = models.User.objects(team=g.team)
    return render_template('team/user_list.html', users=users)

@team.route('/submittimezone', methods=['POST'])
@login_required
def timezone_submit():
    # This isn't stored in db
    if request.json:
        current_user.tz = request.json
    else:
        current_user.tz = 'America/New_York'
    current_user.save()
    return "Success",200

@team.route('/notification/<id>/redirect')
@login_required
def notification_redirect(id):
    notification = current_user.notifications.filter(id=id).first()
    if not notification:
        abort(404)
    # Log info about when notification was seen
    # Might be useful in the future
    return redirect(notification.link)

@team.route('/notification/<id>/dismiss')
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

@team.route('/assignment/<id>/complete')
@login_required
def assignment_complete(id):
    assignment = models.Assignment.objects(team=g.team, id=id).first()
    if not assignment:
        abort(404)
    if not assignment.permissions.check_visible(current_user):
        abort(404)
    if assignment.is_draft:
        abort(404)
    for au_list in assignment.users:
        if au_list.user.id == current_user.id:
            au = au_list
    if not au:
        abort(404)
    if not au.completed:
        au.completed = pendulum.now('UTC')
        au.save()
    for task in current_user.assigned_tasks:
        if task.id == au.id:
            current_user.assigned_tasks.remove(task)
            current_user.save()
    return redirect(team_url_for('team.assignment_view', id=assignment.id))

@team.route('/assignment/<id>/info')
@login_required
def assignment_info(id):
    assignment = models.Assignment.objects(team=g.team, id=id).first()
    if not assignment:
        abort(404)
    if not assignment.permissions.check_editor(current_user):
        abort(404)
    if assignment.is_draft:
        return redirect(team_url_for('team.assignment_edit', id=id))
    return render_template('team/assignment_info.html', assignment=assignment)

def fill_in_task_info(task):
    if type(task) == models.EventUser:
        # Have to find the event
        eu = models.EventUser.objects(user=current_user.id).first()
        event = models.Event.objects(team=g.team, users=eu).first()
        task.text = "RSVP for " + event.name
        task.link = team_url_for('team.event_view', id=event.id)
    elif type(task) == models.AssignmentUser:
        au = models.AssignmentUser.objects(user=current_user.id).first()
        assignment = models.Assignment.objects(team=g.team, users=au).first()
        task.text = assignment.subject
        task.link = team_url_for('team.assignment_view', id=assignment.id)
    elif type(task) == models.User:
        task.text = 'Please fill out your profile'
        task.link = team_url_for('team.edit_profile')
    else:
        raise


@team.route('/task/<id>')
@login_required
def task_redirect(id):
    # Make sure that the task is in the user assigned task list
    task = None
    for task_list in current_user.assigned_tasks:
        if task_list.id == ObjectId(id):
            task = task_list 
    if not task:
        abort(404)
    fill_in_task_info(task)
    return redirect(task.link)

@team.route('/tasks')
def task_list():
    current_user.select_related(max_depth=2)
    tasks = current_user.assigned_tasks
    for task in tasks:
        fill_in_task_info(task)
    return render_template('team/task_list.html',tasks=tasks)

@team.route('/rsvp/<id>')
@login_required
def rsvp_for_meeting(id):
    meeting = models.Meeting.objects(team=g.team, id=id).first()
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

# Utility functions to simplify permission selection form
def init_permission_form(form):
    all_roles = models.Role.objects(team=g.team)
    all_users = models.User.objects(team=g.team)
    form.visible_roles.choices = [(str(role.id), role.name) for role in all_roles]
    form.visible_users.choices = [(str(user.id), user.first_name + " " + user.last_name) for user in all_users]
    form.editor_roles.choices = [(str(role.id), role.name) for role in all_roles]
    form.editor_users.choices = [(str(user.id), user.first_name + " " + user.last_name) for user in all_users]

def save_permission_form(form, obj):
    obj.visible_roles = [ObjectId(r) for r in form.visible_roles.data]
    obj.visible_users = [ObjectId(u) for u in form.visible_users.data]
    obj.editor_roles = [ObjectId(r) for r in form.editor_roles.data]
    obj.editor_users = [ObjectId(u) for u in form.editor_users.data]

def set_selected_permission_form(form, obj):
    form.editor_roles.selected = [str(role.id) for role in obj.editor_roles]
    form.editor_users.selected = [str(user.id) for user in obj.editor_users]
    form.visible_roles.selected = [str(role.id) for role in obj.visible_roles]
    form.visible_users.selected = [str(user.id) for user in obj.visible_users]

def set_selected_notification_form(form, obj):
    form.selected_dates = [dt.in_tz(current_user.tz).isoformat() for dt in obj.notification_dates]

# Update from a form with a task FormField
def save_notification_form(form, obj):
    obj.notification_dates = []
    for dt_string in form.notification_dates.data.split(","):
        if dt_string and dt_string != '[]':
            dt = pendulum.from_format(dt_string.strip(), "MM/DD/YYYY", tz=current_user.tz).in_tz('UTC')
            obj.notification_dates.append(dt)
    obj.notify_by_email = form.notify_by_email.data
    obj.notify_by_phone = form.notify_by_phone.data
    obj.notify_by_push  = form.notify_by_push.data
    obj.notify_by_app   = form.notify_by_app.data

def send_notification(notification_settings, ou):
    notification_settings.notification_dates.append(pendulum.now('UTC'))
    for time in notification_settings.notification_dates:
        notification = models.PushNotification()
        notification.user = ou.user
        notification.text = notification_settings.text
        notification.date = time
        notification.link = team_url_for('team.task_redirect', id=ou.id)
        notification.send_email = notification_settings.notify_by_email
        notification.send_text  = notification_settings.notify_by_phone
        notification.send_app   = notification_settings.notify_by_app
        notification.send_push  = notification_settings.notify_by_push
        notification.save()
        # Schedule assignment for sending unless it's right now
        if notification.date <= pendulum.now('UTC'):
            tasks.send_notification((notification.id))
        else:
            # Notify user at their most recent time zone
            eta = notification.date.in_tz(notification.user.tz)
            tasks.send_notification.schedule((notification.id), eta=eta)


calendar_colors = ['#5484ed', '#dc2127', '#a4bdfc', '#46d6db', '#7ae7bf',  '#fbd75b', '#ffb878', '#51b749', '#ff887c', '#dbadff', '#e1e1e1']

def get_calendar_sidebar_data():
    calendars = models.Calendar.objects(team=g.team)
    i = 0
    for c in calendars:
        if c.permissions.check_visible(current_user):
            c.color = calendar_colors[i]
            i += 1
    return dict(calendars=calendars)

@team.route('/calendar')
@login_required
def calendar_home():
    events = models.Event.objects(team=g.team)
    events_for_fullcalendar = []
    all_recurring_events = models.RecurringEvent.objects(team=g.team)
    # Need to get the colors from this 
    sidebar_data = get_calendar_sidebar_data()
    colors_lookup = { c.id:c.color for c in sidebar_data['calendars'] }
    for e in events:
        if not e.calendar.permissions.check_visible(current_user):
            continue
        e_new = {}
        e_new['title']  = e.name
        e_new['start']  = e.start.isoformat()
        e_new['end']    = e.end.isoformat()
        if e.is_draft:
            continue
        if e.calendar.permissions.check_editor(current_user):
            if e.recurrence:
                e_new['url']    = team_url_for('team.recurring_event_info', cid=e.calendar.id, id=e.recurrence.id)
            else:
                e_new['url']    = team_url_for('team.event_info', cid=e.calendar.id, id=e.id)
        else:
            if e.recurrence:
                e_new['url']    = team_url_for('team.recurring_event_view', cid=e.calendar.id, id=e.recurrence.id)
            else:
                e_new['url']    = team_url_for('team.scheduled_event_view', cid=e.calendar.id, id=e.id)

        e_new['allDay'] = False

        e_new['backgroundColor'] = colors_lookup[e.calendar.id]
        e_new['borderColor'] = e_new['backgroundColor']
        events_for_fullcalendar.append(e_new)
    return render_template('team/calendar/home.html',
            events=events,
            events_for_fullcalendar=events_for_fullcalendar,
            sidebar_data=sidebar_data)

@team.route('/calendar/new')
@login_required
def calendar_new():
    calendar = models.Calendar(team=g.team)
    calendar.name = "New Calendar"
    calendar.description = "My New Calendar"

    everyone_role = models.Role.objects(team=g.team, name='everyone').first()
    calendar.permissions = models.PermissionSet()
    calendar.permissions.visible_roles = [everyone_role.id]
    calendar.permissions.editor_users = [current_user.id]
    calendar.save()
    flash('Calendar created', 'success')
    return redirect(team_url_for('team.calendar_edit', id=calendar.id))

@team.route('/calendar/<id>/edit', methods=['GET', 'POST'])
@login_required
def calendar_edit(id):
    calendar = models.Calendar.objects(team=g.team, id=id).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user):
        abort(404)
    form = forms.CalendarForm(data=calendar.to_mongo().to_dict())
    init_permission_form(form.permissions)
    if form.validate_on_submit():
        calendar.name = form.name.data
        calendar.description = form.description.data
        save_permission_form(form.permissions, calendar.permissions)
        if not calendar.permissions.check_editor(current_user):
            flash('You cannot remove yourself as an editor', 'warning')
        else:
            calendar.save()
            flash('Changes Saved', 'success')
            return redirect(team_url_for('team.calendar_view', id=id))
    set_selected_permission_form(form.permissions, calendar.permissions)
    return render_template('team/calendar/calendar_edit.html',
            calendar=calendar,
            form=form)

@team.route('/calendar/<id>/view')
@login_required
def calendar_view(id):
    calendar = models.Calendar.objects(team=g.team, id=id).first()
    events = models.Event.objects(team=g.team, calendar=calendar, recurrence=None)
    recurring_events = models.RecurringEvent.objects(team=g.team, calendar=calendar)
    if not calendar:
        abort(404)
    if not calendar.permissions.check_visible(current_user):
        abort(404)
    return render_template('team/calendar/calendar_view.html', 
            calendar=calendar,
            recurring_events=recurring_events,
            events=events)

@team.route('/calendar/<id>/delete')
@login_required
def calendar_delete(id):
    calendar = models.Calendar.objects(team=g.team, id=id)
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user):
        abort(404)
    # Delete things!

@team.route('/event/new')
def scheduled_event_new():
    calendar = None
    if request.args.get('id'):
        calendar = models.Calendar.objects(team=g.team, id=request.args.get('id')).first()
    else:
        all_calendars = models.Calendar.objects(team=g.team)
        for c in all_calendars:
            if c.permissions.check_editor(current_user):
                calendar = c
                break
    if not calendar:
        flash('Please create a calendar first!', 'warning')
        return redirect(team_url_for('team.calendar_home'))
    everyone_role = models.Role.objects(team=g.team, name='everyone').first()

    event = models.Event(team=g.team)
    event.calendar = calendar
    event.name = "New Event"
    event.content = "My New Event"
    event.start = pendulum.now('UTC').add(days=1)
    event.end = event.start.add(hours=2)
    event.rsvp_notifications = models.NotificationSettings()
    event.save()
    return redirect(team_url_for('team.scheduled_event_edit', id=event.id))

@team.route('/event/<id>/edit', methods=["GET","POST"])
def scheduled_event_edit(id):
    event = models.Event.objects(team=g.team, id=id, recurrence=None).first()
    if not event:
        abort(404)
    if not event.calendar.permissions.check_editor(current_user):
        abort(404)
    if not event.is_draft:
        return redirect(team_url_for('team.scheduled_event_view', cid=calendar.id, id=event.id))

    all_calendars = models.Calendar.objects(team=g.team)
    allowed_edit_calendars = []
    for c in all_calendars:
        if c.permissions.check_editor(current_user):
            allowed_edit_calendars.append(c)
    form_data = event.to_mongo().to_dict()
    # Localize start and end to user's location
    form_data['start'] = form_data['start'].in_tz(current_user.tz)
    form_data['end'] = form_data['end'].in_tz(current_user.tz)
    form = forms.EventForm(data=form_data)
    form.calendar.choices = [(str(c.id), c.name) for c in allowed_edit_calendars]
    if form.validate_on_submit():
        # Convert times to UTC
        start = pendulum.instance(form.start.data, tz=current_user.tz).in_tz('UTC')
        end = pendulum.instance(form.end.data, tz=current_user.tz).in_tz('UTC')
        if start >= end:
            flash('Start of event cannot be after end!', 'warning')
        elif end <= pendulum.now('UTC'):
            flash('Event cannot end in the past', 'warning')
        elif (end - start).hours > 24:
            flash('Events cannot span more than 1 day. Please use a recurring event.', 'warning')
        else:
            event.start = start
            event.end = end
            event.content = form.content.data
            event.name = form.name.data
            event.enable_rsvp = form.enable_rsvp.data
            event.enable_attendance = form.enable_attendance.data
            event.calendar = ObjectId(form.calendar.data)

            # Update task
            save_notification_form(form.rsvp_notifications, event.rsvp_notifications)
            event.rsvp_notifications.text = "RSVP for " + event.name
            flash('Changes Saved', 'success')
            event.save()
            event.reload()
    if len(form.errors) > 0:
        flash_errors(form)
    set_selected_notification_form(form.rsvp_notifications, event.rsvp_notifications)
    return render_template('team/calendar/scheduled_event_edit.html',
            event=event,
            form=form)

@team.route('/calendar/<cid>/event/<id>/publish')
def scheduled_event_publish(cid, id):
    calendar = models.Calendar.objects(team=g.team, id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user):
        abort(404)
    event = models.Event.objects(team=g.team, id=id, recurrence=None).first()
    if not event:
        abort(404)
    if not event.is_draft:
        return redirect(team_url_for('team.scheduled_event_view', cid=calendar.id, id=event.id))
    # Find all users with role
    # "assigned_users" is a temporary array of user references that is used to create
    # the "users" array
    event.assigned_users = calendar.permissions.visible_users
    for role in calendar.permissions.visible_roles:
        users_with_role = models.User.objects(team=g.team, roles=role)
        for u in users_with_role:
            event.assigned_users.append(u)
    # Make sure list of users is unique
    event.assigned_users = list(set(event.assigned_users))
    # Create EventUser objects and assignments to user
    # Also create TaskUser objects 
    for user in event.assigned_users:
        eu = models.EventUser()
        eu.user = user
        eu.save()
        event.users.append(eu)
        if event.enable_rsvp:
            user.assigned_tasks.append(eu)
            user.save()
            send_notification(event.rsvp_notifications, eu)

    event.is_draft = False
    event.save()
    flash('Event Published', 'success')
    return redirect(team_url_for('team.event_info', cid=calendar.id, id=event.id))

@team.route('/calendar/<cid>/event/<id>/info')
def event_info(cid, id):
    calendar = models.Calendar.objects(team=g.team, id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user):
        abort(404)
    event = models.Event.objects(team=g.team, id=id).first()
    if not event:
        abort(404)
    if event.is_draft:
        if event.recurrence:
            return redirect(team_url_for('team.recurring_event_edit', cid=calendar.id, id=event.recurrence.id))
        else:
            return redirect(team_url_for('team.scheduled_event_edit', cid=calendar.id, id=event.id))
    return render_template('team/calendar/event_info.html',
            event=event,
            calendar=calendar)

# This is like view but for editors. Shows more information like results of RSVP, etc
@team.route('/calendar/<cid>/event/<id>/view')
def scheduled_event_view(cid, id):
    calendar = models.Calendar.objects(team=g.team, id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_visible(current_user):
        abort(404)
    event = models.Event.objects(team=g.team, id=id, recurrence=None).first()
    for eu_list in event.users:
        if eu_list.user.id == current_user.id:
            eu = eu_list
    if not event:
        abort(404)
    if event.is_draft:
        return redirect(team_url_for('team.scheduled_event_edit', cid=calendar.id, id=event.id))
    return render_template('team/calendar/event_view.html',
            event=event,
            eu=eu,
            calendar=calendar)

@team.route('/calendar/<cid>/event/<id>/<r>')
@login_required
def event_rsvp(cid, id, r):
    calendar = models.Calendar.objects(team=g.team, id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_visible(current_user):
        abort(404)
    event = models.Event.objects(team=g.team, id=id).first()
    if not event:
        abort(404)
    for eu_list in event.users:
        if eu_list.user.id == current_user.id:
            eu = eu_list
    if not eu:
        abort(404)
    if r in ['y', 'n', 'm']: 
        eu.rsvp = r
        eu.save()
    return redirect(request.referrer)

@team.route('/calendar/<cid>/event/<id>/clockin', methods=['GET', 'POST'])
def event_clockin(cid, id):
    calendar = models.Calendar.objects(team=g.team, id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user):
        abort(404)
    event = models.Event.objects(team=g.team, id=id).first()
    form = forms.ClockInForm()
    if not event or event.is_draft:
        abort(404)
    # Sign in and sign out start 1 hour before and after the event
    start_range = event.start.subtract(hours=1)
    end_range   = event.end.add(hours=1)
    if pendulum.now('UTC') < start_range:
        flash("Event hasn't started yet!", 'warning')
        return redirect(request.referrer)
    if pendulum.now('UTC') > end_range:
        flash("Event has already finished! Please modify attendance manually", 'warning')
        return redirect(request.referrer)
    if form.validate_on_submit():
        user = models.User.objects(team=g.team, barcode=form.barcode.data).first()
        if not user:
            flash('Barcode not recognized!', 'danger')
        else:
            for eu_list in event.users:
                if user.id == eu_list.user.id:
                    eu = eu_list
            if not eu:
                flash('User not added to this event!', 'danger')
            else:
                # Check that this event is starting soon
                # If user already signed in and out
                # we'll edit the sign out time
                if eu.sign_in and eu.sign_out:
                    eu.sign_out = pendulum.now('UTC')
                    eu.save()
                    flash('Sign out time updated for ' + user.first_name + " " + user.last_name, 'success')
                elif eu.sign_in:
                    eu.sign_out = pendulum.now('UTC')
                    eu.save()
                    flash('Signed out ' + user.first_name + " " + user.last_name, 'success')
                else:
                    eu.sign_in = pendulum.now('UTC')
                    eu.save()
                    flash('Signed in ' + user.first_name + " " + user.last_name, 'success')
    return render_template('team/calendar/event_clockin.html',
            event=event,
            form=form)


@team.route('/calendar/<cid>/rsvp_edit/<id>', methods=['GET', 'POST'])
def event_user_edit(cid, id):
    calendar = models.Calendar.objects(team=g.team, id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user):
        abort(404)
    eu = models.EventUser.objects(team=g.team, id=id).first()
    event = models.Event.objects(team=g.team, calendar=calendar, users=eu).first()
    if not event:
        abort(404)
    form_data = eu.to_mongo().to_dict()
    if 'sign_in' in form_data:
        form_data['sign_in'] = form_data['sign_in'].in_tz(current_user.tz)
        form_data['sign_out'] = form_data['sign_out'].in_tz(current_user.tz)
    form = forms.EventUserForm(data=form_data)
    if form.validate_on_submit():
        eu.sign_in = pendulum.instance(datetime.datetime.combine(event.start.date(), form.sign_in.data), tz=current_user.tz).in_tz('UTC')
        eu.sign_out = pendulum.instance(datetime.datetime.combine(event.start.date(), form.sign_out.data), tz=current_user.tz).in_tz('UTC')
        start_range = event.start.subtract(hours=1)
        end_range   = event.end.add(hours=1)
        if eu.sign_in > eu.sign_out:
            flash('Sign in time cannot be after sign out!', 'warning')
        elif eu.sign_in < start_range:
            flash('Sign in cannot be more than an hour before the event starts ' + start_range.in_tz(current_user.tz).format('(hh:mm A)'), 'warning')
        elif eu.sign_out > end_range:
            flash('Sign out cannot be more than an hour after the event ends ' + end_range.in_tz(current_user.tz).format('(hh:mm A)'), 'warning')
        else:
            eu.save()
            flash('Changes Saved', 'success')
            return redirect(team_url_for('team.event_info', id=event.id, cid=calendar.id))
    return render_template('team/calendar/event_user_edit.html',
            eu=eu,
            form=form,
            event=event,
            calendar=calendar)

@team.route('/calendar/<cid>/event/<id>/delete')
def scheduled_event_delete(cid, id):
    calendar = models.Calendar.objects(team=g.team, id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user):
        abort(404)
    event = models.Event.objects(team=g.team, id=id, recurrence=None, calendar=calendar).first()
    if not event:
        abort(404)
    if not event.is_draft:
        # Have to iterate over users and delete references manually
        for eu in event.users:
            eu.user.assigned_tasks.remove(eu)
            eu.user.save()
            eu.delete()
    event.delete()
    flash('Deleted Event', 'success')
    return redirect(team_url_for('team.event_list'))

@team.route('/event-recurring/new')
@login_required
def recurring_event_new():
    calendar = None
    if request.args.get('id'):
        calendar = models.Calendar.objects(team=g.team, id=request.args.get('id')).first()
    else:
        all_calendars = models.Calendar.objects(team=g.team)
        for c in all_calendars:
            if c.permissions.check_editor(current_user):
                calendar = c
                break
    if not calendar:
        flash('Please create a calendar first!', 'warning')
        return redirect(team_url_for('team.calendar_home'))
    everyone_role = models.Role.objects(team=g.team, name='everyone').first()
    event = models.RecurringEvent(team=g.team)
    event.name = "New Event"
    event.content = "My New Recurring Event"
    event.calendar = calendar
    event.start_date = pendulum.today().naive()
    event.end_date = pendulum.today().add(weeks=1).naive()
    event.start_time = pendulum.naive(2010,1,1, 17, 0)
    event.end_time = pendulum.naive(2010,1,1, 19, 0)
    event.days_of_week = [1,3,5]
    event.rsvp_notifications = models.NotificationSettings()
    event.save()
    flash('Created Recurring Event', 'success')
    return redirect(team_url_for('team.recurring_event_edit', id=event.id))

@team.route('/event-recurring/<id>/edit', methods=["GET","POST"])
def recurring_event_edit(id):
    event = models.RecurringEvent.objects(team=g.team, id=id).first()
    if not event:
        abort(404)
    if not event.is_draft:
        return redirect(team_url_for('team.recurring_event_view', cid=calendar.id,  id=event.id))
    if not event.calendar.permissions.check_editor(current_user):
        abort(404)
    all_calendars = models.Calendar.objects(team=g.team)
    allowed_edit_calendars = []
    for c in all_calendars:
        if c.permissions.check_editor(current_user):
            allowed_edit_calendars.append(c)
    form_data = event.to_mongo().to_dict()
    form = forms.RecurringEventForm(data=form_data)
    all_days_of_week = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
    form.days_of_week.choices = list(zip(range(7), all_days_of_week))
    form.calendar.choices = [(str(c.id), c.name) for c in allowed_edit_calendars]
    if form.validate_on_submit():
        if form.end_time.data <= form.start_time.data:
            flash('Start time of event cannot be before end!', 'warning')
        elif form.end_date.data <= form.start_date.data:
            flash('Start date of event cannot be before end!', 'warning')
        elif len(form.days_of_week.data) == 0:
            flash('Event must happen at least one day a week!', 'warning')
        else:
            event.start_date = datetime.datetime.combine(form.start_date.data, datetime.datetime.min.time())
            event.end_date   = datetime.datetime.combine(form.end_date.data, datetime.datetime.min.time())
            event.start_time = datetime.datetime.combine(datetime.datetime.min.date(), form.start_time.data)
            event.end_time   = datetime.datetime.combine(datetime.datetime.min.date(), form.end_time.data)
            event.name = form.name.data
            event.content = form.content.data
            event.days_of_week = form.days_of_week.data
            event.enable_rsvp = form.enable_rsvp.data
            event.enable_attendance = form.enable_attendance.data
            event.calendar = ObjectId(form.calendar.data)

            save_notification_form(form.rsvp_notifications, event.rsvp_notifications)
            event.rsvp_notifications.text = "RSVP for " + event.name

            event.save()
            event.reload()
            flash('Changes Saved', 'success')
    if len(form.errors) > 0:
        flash_errors(form)
    set_selected_notification_form(form.rsvp_notifications, event.rsvp_notifications)
    return render_template('team/calendar/recurring_event_edit.html',
            event=event,
            form=form,
            selected_days_of_week = event.days_of_week)

@team.route('/calendar/<cid>/event-recurring/<id>/publish')
def recurring_event_publish(cid, id):
    calendar = models.Calendar.objects(team=g.team, id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user):
        abort(404)
    event = models.RecurringEvent.objects(team=g.team, id=id).first()
    if not event:
        abort(404)
    if not event.is_draft:
        return redirect(team_url_for('team.recurring_event_view', cid=calendar.id, id=event.id))
    # Save original list of assigned_users so it's possible to duplicate tasks
    event.assigned_users = calendar.permissions.visible_users
    # Find all users with role
    for role in calendar.permissions.visible_roles:
        users_with_role = models.User.objects(team=g.team, roles=role)
        for u in users_with_role:
            event.assigned_users.append(u)
    # Make sure list of users is unique
    event.assigned_users = list(set(event.assigned_users))
    start_date = pendulum.instance(event.start_date, tz=current_user.tz)
    end_date = pendulum.instance(event.end_date, tz=current_user.tz)
    period = end_date - start_date
    # Create individual instances of Event class (subevents)
    # Each one contains duplicated data of the recurring event
    # which allows for quicker access to that data from the team site
    for dt in period.range('days'):
        if dt.day_of_week in event.days_of_week:
            start = dt.at(event.start_time.hour, event.start_time.minute)
            start = start.in_tz('UTC')
            end = dt.at(event.end_time.hour, event.end_time.minute)
            end = end.in_tz('UTC')
            new_event = models.Event(team=g.team,
                                     name  = event.name,
                                     start = start,
                                     end   = end,
                                     recurrence = event,
                                     content = event.content,
                                     calendar = calendar,
                                     is_draft = False,
                                     enable_rsvp = event.enable_rsvp,
                                     enable_attendance = event.enable_attendance,
                                     rsvp_notifications=event.rsvp_notifications)

            for user in event.assigned_users:
                eu = models.EventUser(team=g.team)
                eu.user = user
                eu.save()
                new_event.users.append(eu)
                if event.enable_rsvp:
                    user.assigned_tasks.append(eu)
                    user.save()
                    send_notification(new_event.rsvp_notifications, eu)

            new_event.save()
    event.is_draft = False
    event.save()
    return redirect(team_url_for('team.recurring_event_info', cid=calendar.id, id=event.id))

@team.route('/calendar/<cid>/event-recurring/<id>/view')
def recurring_event_view(cid, id):
    calendar = models.Calendar.objects(team=g.team, id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_visible(current_user):
        abort(404)
    event = models.RecurringEvent.objects(team=g.team, id=id).first()
    if not event:
        abort(404)
    if event.is_draft:
        return redirect(team_url_for('team.recurring_event_edit', cid=calendar.id, id=event.id))
    subevents = models.Event.objects(team=g.team, recurrence=event)
    for subevent in subevents:
        for eu_list in subevent.users:
            if eu_list.user.id == current_user.id:
                subevent.eu = eu_list
    return render_template('team/calendar/recurring_event_view.html',
            calendar=calendar,
            event=event,
            subevents=subevents)

@team.route('/calendar/<cid>/event-recurring/<id>/info')
def recurring_event_info(cid, id):
    calendar = models.Calendar.objects(team=g.team, id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user):
        abort(404)
    event = models.RecurringEvent.objects(team=g.team, id=id).first()
    if not event:
        abort(404)
    if event.is_draft:
        return redirect(team_url_for('team.recurring_event_edit', cid=calendar.id, id=event.id))
    subevents = models.Event.objects(team=g.team, recurrence=event)
    return render_template('team/calendar/recurring_event_info.html',
            calendar=calendar,
            event=event,
            subevents=subevents)





@team.route('/calendar/<cid>/event-recurring/<id>/delete')
def recurring_event_delete(cid, id):
    calendar = models.Calendar.objects(team=g.team, id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user):
        abort(404)
    recurring_event = models.RecurringEvent.objects(team=g.team, calendar=cid, id=id).first()
    if not recurring_event:
        abort(404)
    if not recurring_event.is_draft:
        events = models.Event.objects(team=g.team, recurrence=recurring_event)
        # Delete associated events
        for event in events:
            for eu in event.users:
                eu.user.assigned_tasks.remove(eu)
                eu.user.save()
                eu.delete()
            event.delete()
    recurring_event.delete()
    flash('Deleted Event', 'success')
    return redirect(team_url_for('team.calendar_home'))


def get_wiki_sidebar_data():
    articles = models.Article.objects(team=g.team)
    topics = models.Topic.objects(team=g.team)
    return dict(articles=articles, topics=topics)

@team.route('/wiki')
def wiki_home():
    articles = models.Article.objects(team=g.team)
    topics = models.Topic.objects(team=g.team)
    return render_template('team/wiki/home.html',
            articles=articles,
            topics=topics,
            sidebar_data=get_wiki_sidebar_data())

@team.route('/wiki/topic/<id>/view')
def topic_view(id):
    topic = models.Topic.objects(team=g.team, id=id).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_visible(current_user):
        abort(404)
    return render_template('team/wiki/topic_view.html',
            topic=topic,
            sidebar_data=get_wiki_sidebar_data())

@team.route('/wiki/topic/new')
def topic_new():
    topic = models.Topic(team=g.team)
    topic.name = "New Topic"
    topic.description = "My New Topic"

    everyone_role = models.Role.objects(team=g.team, name='everyone').first()
    topic.permissions = models.PermissionSet()
    topic.permissions.visible_roles = [everyone_role.id]
    topic.permissions.editor_users = [current_user.id]

    flash('Created Topic', 'success')
    topic.save()
    return redirect(team_url_for('team.topic_edit', id=topic.id))

@team.route('/wiki/topic/<id>/edit', methods=['GET','POST'])
def topic_edit(id):
    topic = models.Topic.objects(team=g.team, id=id).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_editor(current_user):
        abort(404)
    form = forms.TopicForm(data=topic.to_mongo().to_dict())
    init_permission_form(form.permissions)
    if form.validate_on_submit():
        topic.name = form.name.data
        topic.description = form.description.data
        save_permission_form(form.permissions, topic.permissions)
        if not topic.permissions.check_editor(current_user):
            flash('You cannot remove yourself as an editor', 'warning')
        else:
            topic.save()
            flash('Changes Saved', 'success')
    set_selected_permission_form(form.permissions, topic.permissions)
    return render_template('team/wiki/topic_edit.html',
            topic=topic,
            form=form,
            sidebar_data=get_wiki_sidebar_data())

@team.route('/wiki/topic/<id>/delete')
def topic_delete(id):
    topic = models.Topic.objects(team=g.team, id=id).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_editor(current_user):
        abort(404)
    articles = models.Article.objects(team=g.team, topic=topic)
    if len(articles) != 0:
        flash('Topic ' + topic.name + ' has articles associated with it. Please remove these before deleting', 'warning')
        return redirect(team_url_for('team.topic_edit', id=topic.id))
    topic.delete()
    flash('Topic Deleted', 'success')
    return redirect(team_url_for('team.wiki_home'))


@team.route('/wiki/article/new')
def article_new():
    topic = None
    if request.args.get('id'):
        topic = models.Topic.objects(team=g.team, id=request.args.get('id')).first()
    else:
        all_topics = models.Topic.objects(team=g.team)
        for t in all_topics:
            if t.permissions.check_editor(current_user):
                topic = t
                break
    if not topic:
        flash('Please create a topic first!', 'warning')
        return redirect(team_url_for('team.wiki_home'))
    article = models.Article(team=g.team)
    article.name = "New Article"
    article.content = "My New Article"
    article.topic = topic
    article.save()
    return redirect(team_url_for('team.article_edit', id=article.id, tid=topic.id))

@team.route('/wiki/topic/<tid>/article/<id>/edit', methods=['GET','POST'])
def article_edit(tid, id):
    article = models.Article.objects(team=g.team, id=id).first()
    if not article:
        abort(404)
    if not article.topic.permissions.check_editor(current_user):
        abort(404)
    form = forms.ArticleForm(data=article.to_mongo().to_dict())
    all_topics = models.Topic.objects(team=g.team)
    allowed_edit_topics = []
    for t in all_topics:
        if t.permissions.check_editor(current_user):
            allowed_edit_topics.append(t)
    form.topic.choices = [(str(t.id), t.name) for t in allowed_edit_topics]
    if form.validate_on_submit():
        article.name = form.name.data
        article.topic = ObjectId(form.topic.data)
        article.content = form.content.data
        article.save()
        flash('Changes Saved', 'success')
        article.reload()
    return render_template('team/wiki/article_edit.html',
            article=article,
            form=form,
            sidebar_data=get_wiki_sidebar_data())

@team.route('/wiki/topic/<tid>/article/<id>/view')
def article_view(tid, id):
    topic = models.Topic.objects(team=g.team, id=tid).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_visible(current_user) and not topic.permissions.check_editor(current_user):
        abort(404)
    article = models.Article.objects(team=g.team, id=id).first()
    if not article:
        abort(404)
    return render_template('team/wiki/article_view.html',
            article=article,
            sidebar_data=get_wiki_sidebar_data())

@team.route('/wiki/topic/<tid>/article/<id>/delete')
def article_delete(tid, id):
    topic = models.Topic.objects(team=g.team, id=tid).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_editor(current_user):
        abort(404)
    article = models.Article.objects(team=g.team, id=id).first()
    if not article:
        abort(404)
    article.delete()
    flash('Article Deleted', 'success')
    return redirect(team_url_for('team.topic_view', id=tid))

@team.route('/assignments')
def assignment_list():
    assignments = models.Assignment.objects(team=g.team)
    for a in assignments:
        a.number_assigned = len(a.users)
        a.number_seen = 0
        a.number_completed = 0
        for au in a.users:
            if au.seen:
                a.number_seen += 1
            if au.completed:
                a.number_completed += 1
            if au.user.id == current_user.id:
                a.au = au
    return render_template('team/assignment_list.html', assignments=assignments)

@team.route('/assignment/new')
def assignment_new():
    everyone_role = models.Role.objects(team=g.team, name='everyone').first()
    assignment = models.Assignment(team=g.team)
    assignment.subject = "New Assignment"
    assignment.permissions = models.PermissionSet()
    # Visible users corresponds to assigned users
    assignment.permissions.editor_users = [current_user.id]
    assignment.permissions.visible_roles = [everyone_role]

    assignment.notifications = models.NotificationSettings()
    assignment.notifications.notification_dates.append(pendulum.today(tz=current_user.tz).at(17,0).in_tz('UTC'))
    assignment.due = pendulum.now('UTC').add(days=7)
    assignment.save()
    return redirect(team_url_for('team.assignment_edit', id=assignment.id))


@team.route('/assignment/<id>/edit', methods=['GET', 'POST'])
def assignment_edit(id):
    assignment = models.Assignment.objects(team=g.team, id=id).first()
    if not assignment:
        abort(404)
    if not assignment.is_draft:
        return redirect(team_url_for('team.assignment_view', id=id))

    # Queries
    assignment.select_related(max_depth=2)
    all_roles = models.Role.objects(team=g.team)
    all_users = models.User.objects(team=g.team)

    form_data = assignment.to_mongo().to_dict()
    form_data['due'] = form_data['due'].in_tz(current_user.tz)
    form = forms.AssignmentForm(data=form_data)
    init_permission_form(form.permissions)
    if form.validate_on_submit():
        assignment.subject = form.subject.data
        assignment.content = form.content.data
        assignment.due = pendulum.instance(form.due.data, tz=current_user.tz).in_tz('UTC')
        save_permission_form(form.permissions, assignment.permissions)
        save_notification_form(form.notifications, assignment.notifications)
        assignment.notifications.text = assignment.subject
        if assignment.due < pendulum.now('UTC'):
            flash('Task cannot be due in the past', 'warning')
        else:
            # Update task
            assignment.save()
            assignment.reload()
            flash('Changes Saved', 'success')
    if len(form.errors) > 0:
        flash_errors(form)
    set_selected_permission_form(form.permissions, assignment.permissions)
    set_selected_notification_form(form.notifications, assignment.notifications)
    return render_template('team/assignment_edit.html',
            assignment=assignment,
            form=form)

@team.route('/assignment/<id>/publish')
def assignment_publish(id):
    assignment = models.Assignment.objects(team=g.team, id=id).first()
    if not assignment:
        abort(404)
    if not assignment.is_draft:
        redirect(team_url_for('team.assignment_edit', id=id))
    # Find all users with role
    # "assigned_users" is a temporary array of user references that is used to create
    # the "users" array
    assignment.assigned_users = assignment.permissions.visible_users
    for role in assignment.permissions.visible_roles:
        users_with_role = models.User.objects(team=g.team, roles=role)
        for u in users_with_role:
            assignment.assigned_users.append(u)
    # Create TaskUser objects and assignments to user
    for user in assignment.assigned_users:
        au = models.AssignmentUser()
        au.user = user
        au.save()
        assignment.users.append(au)
        user.assigned_tasks.append(au)
        user.save()
        send_notification(assignment.notifications, au)

    # Create notifications
    assignment.is_draft = False
    assignment.save()
    return redirect(team_url_for('team.assignment_info',id=id))


@team.route('/assignment/<id>/view')
def assignment_view(id):
    assignment = models.Assignment.objects(team=g.team, id=id).first()
    if not assignment:
        abort(404)
    if not assignment.permissions.check_visible(current_user):
        abort(404)
    if assignment.is_draft:
        return redirect(team_url_for('team.assignment_edit', id=id))
    for au_list in assignment.users:
        if au_list.user.id == current_user.id:
            au = au_list
    if au:
        au.seen = pendulum.now('UTC')
        au.save()
    return render_template('team/assignment_view.html', assignment=assignment, au=au)

@team.route('/assignment/<id>/duplicate')
def assignment_duplicate(id):
    assignment = models.Assignment.objects(team=g.team, id=id).first()
    if not assignment:
        abort(404)
    new_assignment         = models.Assignment(team=g.team)
    new_assignment.subject = assignment.subject + " Copy"
    new_assignment.content = assignment.content
    new_assignment.assigned_roles = assignment.assigned_roles
    new_assignment.assigned_users = assignment.assigned_users
    new_assignment.due     = pendulum.tomorrow('UTC')
    new_assignment.save()
    return redirect(team_url_for('team.assignment_edit', id=new_assignment.id))


@team.route('/assignment/<id>/delete')
def assignment_delete(id):
    assignment = models.Assignment.objects(team=g.team, id=id).first()
    if not assignment:
        abort(404)
    if not assignment.permissions.check_editor(current_user):
        abort(404)
    if not assignment.is_draft:
        for au in assignment.users:
            if au in au.user.assigned_tasks:
                au.user.assigned_tasks.remove(au)
                au.user.save()
            au.delete()
    assignment.delete()
    return redirect(team_url_for('team.assignment_list'))
