from app import models, forms, tasks
from app.admin import context
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint

from flask_login import current_user

import datetime, json

import pendulum
from bson import ObjectId

admin = Blueprint('admin', __name__, template_folder='templates')

protected_roles = ['everyone', 'admin']

@admin.before_request
def require_authorization():
    if not current_user.is_authenticated:
        flash('Please log in to view this page', 'danger')
        return redirect(url_for('login', next=request.endpoint))
    for role in current_user.roles:
        if role.name == 'admin':
            return
    flash('You do not have permission to view this page', 'danger')
    return redirect(url_for('public.index'))

@admin.route('/')
def index():
    return redirect(url_for('admin.user_list'))

@admin.route('/users')
def user_list():
    users = models.User.objects
    return render_template('admin/user_list.html', users=users)

@admin.route('/u/<id>', methods=['GET', 'POST'])
def user_info(id):
    user = models.User.objects(id=id).first()
    all_roles = models.Role.objects
    everyone_role = models.Role.objects(name='everyone').first()
    if not user:
        abort(404)
    form = forms.UserForm(request.form, data=user.to_mongo().to_dict())
    form.roles.choices = [(str(role.id), role.name) for role in all_roles if role != everyone_role]
    if form.validate_on_submit():
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.email = form.email.data
        user.barcode = form.barcode.data
        user.roles = [ObjectId(r) for r in form.roles.data]
        user.roles.append(everyone_role)
        user.save()
        flash('Changes Saved', 'success')
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/user_info.html', user=user, form=form,
            selected_roles=[role.name for role in user.roles])

@admin.route('/u/<id>/delete')
def user_delete(id):
    user = models.User.objects(id=id).first()
    for tu in user.assigned_tasks:
        tu.delete()
    user.delete()
    return redirect(url_for('admin.user_list'))

@admin.route('/roles')
def role_list():
    roles = models.Role.objects
    role_form = forms.RoleForm()
    return render_template('admin/role_list.html', roles=roles, role_form=role_form, protected_roles=protected_roles)

@admin.route('/newrole', methods=['POST'])
def role_new():
    form = forms.RoleForm()
    all_roles = models.Role.objects
    if form.validate_on_submit():
        for r in all_roles:
            if r.name == form.data['role'].lower():
                flash('Role already exists', 'warning')
                return redirect(url_for('admin.role_list'))
        new_role = models.Role()
        new_role.name = form.data['role'].lower()
        new_role.save()
        flash('Added Role', 'success')
    if len(form.errors) > 0:
        flash_errors(form)
    return redirect(url_for('admin.role_list'))

@admin.route('/role/<id>/remove')
def role_delete(id):
    role = models.Role.objects(id=id).first()
    if role.name in protected_roles:
        flash('Cannot delete this role', 'danger')
    else:
        for user in models.User.objects:
            user.roles.remove(role)
            user.save()
        role.delete()
        flash('Deleted Role', 'success')
    return redirect(url_for('admin.role_list'))

@admin.route('/attendance', methods=['GET', 'POST'])
def attendance_graphs():
    all_eus = models.EventUser.objects
    all_events = models.Event.objects
    all_users = models.User.objects
    all_roles = models.Role.objects
    form = forms.FilterForm()
    filter_choices = ['None', 'User', 'Role']
    form.filter_by.choices = list(zip(range(len(filter_choices)), filter_choices))
    form.filter_role.choices = [(str(role.id), role.name) for role in all_roles]
    form.filter_user.choices = [(str(user.id), user.first_name + " " + user.last_name) for user in all_users]
    if form.validate_on_submit():
        filter_by = dict(form.filter_by.choices).get(form.filter_by.data)
    else:
        # By default filter by none
        filter_by = 'None'
    # Fill in eu.user
    for eu in all_eus:
        for user in all_users:
            if eu in user.assigned_events:
                eu.user = user
                break
    # Filter data by current user
    data = {}
    for eu in all_eus:
        # We have to do this every time so that we include all the dates
        event_date = eu.event.start.format('MM/DD/YY')
        print(event_date)
        if event_date not in data:
            data[event_date]= 0
        if filter_by == 'User':
            if eu.user.id != ObjectId(form.filter_user.data):
                continue
        if filter_by == 'Role':
            if ObjectId(form.filter_role.data) not in [r.id for r in eu.user.roles]:
                continue
        if not eu.sign_out or not eu.sign_in:
            continue
        minutes = (eu.sign_out - eu.sign_in).total_minutes()
        user_name = eu.user.first_name + " " + eu.user.last_name
        data[event_date] += minutes
    # Get any element in by_user and then get the keys for graph X axis labels
    labels = list(data.keys())
    values = list(data.values())
    if len(form.errors) > 0:
        flash_errors(form)

    # Calculate total hours
    total_hours = 0
    for eu in all_eus:
        if not eu.sign_out or not eu.sign_in:
            continue
        total_hours += (eu.sign_out - eu.sign_in).total_hours()
    # Hours last week
    hours_last_week = 0
    for eu in all_eus:
        if not eu.sign_out or not eu.sign_in:
            continue
        if eu.sign_in < pendulum.now('UTC').subtract(weeks=1):
            continue
        hours_last_week += (eu.sign_out - eu.sign_in).total_hours()
    return render_template('admin/attendance_graphs.html',
            all_events=all_events,
            values=values,
            labels=labels,
            form=form,
            selected_by=form.filter_by.data,
            selected_user=form.filter_user.data,
            selected_role=form.filter_role.data,
            total_hours=total_hours,
            total_events=len(all_events),
            total_users=len(all_users),
            hours_last_week=hours_last_week,
            average_time_at_event=total_hours/len(all_events))

@admin.route('/events')
def event_list():
    scheduled_events = models.Event.objects(is_recurring=False)
    recurring_events = models.RecurringEvent.objects()
    return render_template('admin/event_list.html',
            scheduled_events=scheduled_events,
            recurring_events=recurring_events)

@admin.route('/e/<id>/view')
def scheduled_event_view(id):
    event = models.Event.objects(id=id).first()
    if not event:
        abort(404)
    if event.is_draft:
        return redirect(url_for('admin.scheduled_event_edit', id=event.id))
    # Complex query here, but it's okay because this is an admin interface
    all_users = models.User.objects
    all_users.select_related(max_depth=2)
    assigned_users = []
    assigned_users = []
    for user in all_users:
        # Filter AssignmentUser objects to those related to this assignment (should be 1 or 0)
        for eu in user.assigned_events:
            # This is true if the user is assigned to the assignment
            if eu.event.id == event.id:
                # Find associated TaskUser object and attach it
                for tu in user.assigned_tasks:
                    if eu.id == tu.watch_object.id:
                        user.tu = tu
                user.eu = eu
        if user.eu:
            assigned_users.append(user)
    # This is for the back button
    if event.is_recurring:
        all_recurring_events = models.RecurringEvent.objects
        for re in all_recurring_events:
            if event in re.events:
                event.recurring_event = re
    return render_template('admin/scheduled_event_view.html', event=event, assigned_users=assigned_users)

@admin.route('/e/<id>/clockin', methods=['GET', 'POST'])
def event_clockin(id):
    event = models.Event.objects(id=id).first()
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
        flash("Event has already finished!", 'warning')
        return redirect(request.referrer)
    if form.validate_on_submit():
        user = models.User.objects(barcode=form.barcode.data).first()
        if not user:
            flash('Barcode not recognized!', 'danger')
        else:
            # Check that this event is starting soon
            for user_eu in user.assigned_events:
                if user_eu.event == event:
                    eu = user_eu
                    break
            if not eu:
                flash('User is not assigned to this event!', 'danger')
            else:
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
    return render_template('admin/event_clockin.html', event=event, form=form)

@admin.route('/eu/<id>/edit', methods=['GET', 'POST'])
def event_user_edit(id):
    eu = models.EventUser.objects(id=id).first()
    if not eu or not eu.event.enable_attendance:
        abort(404)
    all_users = models.User.objects
    for user in all_users:
        if eu in user.assigned_events:
            eu.user = user
    form_data = eu.to_mongo().to_dict()
    if 'sign_in' in form_data:
        form_data['sign_in'] = form_data['sign_in'].in_tz(current_user.tz)
        form_data['sign_out'] = form_data['sign_out'].in_tz(current_user.tz)
    form = forms.EventUserForm(data=form_data)
    if form.validate_on_submit():
        eu.sign_in = pendulum.instance(datetime.datetime.combine(eu.event.start.date(), form.sign_in.data), tz=current_user.tz).in_tz('UTC')
        eu.sign_out = pendulum.instance(datetime.datetime.combine(eu.event.start.date(), form.sign_out.data), tz=current_user.tz).in_tz('UTC')
        start_range = eu.event.start.subtract(hours=1)
        end_range   = eu.event.end.add(hours=1)
        if eu.sign_in > eu.sign_out:
            flash('Sign in time cannot be after sign out!', 'warning')
        elif eu.sign_in < start_range:
            flash('Sign in cannot be more than an hour before the event starts ' + start_range.in_tz(current_user.tz).format('(hh:mm A)'), 'warning')
        elif eu.sign_out > end_range:
            flash('Sign out cannot be more than an hour after the event ends ' + end_range.in_tz(current_user.tz).format('(hh:mm A)'), 'warning')
        else:
            eu.save()
            flash('Changes Saved', 'success')
    return render_template('admin/event_user_edit.html', eu=eu, form=form)

@admin.route('/e/<id>/delete')
def scheduled_event_delete(id):
    event = models.Event.objects(id=id, is_recurring=False).first()
    if not event:
        abort(404)
    if not event.is_draft:
        # Have to iterate over users and delete references manually
        all_users = models.User.objects
        all_users.select_related(max_depth=2)
        for user in all_users:
            for eu in user.assigned_events:
                if eu.event == event:
                    eu.delete()
                    user.assigned_events.remove(eu)
            if event.enable_rsvp:
                for tu in user.assigned_tasks:
                    if tu.task == event.rsvp_task:
                        tu.delete()
                        user.assigned_tasks.remove(tu)
            user.save()
    if event.enable_rsvp:
        event.rsvp_task.delete()
    event.delete()
    flash('Deleted Event', 'success')
    return redirect(url_for('admin.event_list'))

@admin.route('/m/<id>/edit', methods=["GET","POST"])
def scheduled_event_edit(id):
    event = models.Event.objects(id=id, is_recurring=False).first()
    all_roles = models.Role.objects
    all_users = models.User.objects
    if not event:
        abort(404)
    if not event.is_draft:
        return redirect(url_for('admin.scheduled_event_view', id=event.id))
    form_data = event.to_mongo().to_dict()
    # Localize start and end to user's location
    form_data['start'] = form_data['start'].in_tz(current_user.tz)
    form_data['end'] = form_data['end'].in_tz(current_user.tz)
    form = forms.EventForm(request.form, data=form_data)
    form.assigned_roles.choices = [(str(role.id), role.name) for role in all_roles]
    form.assigned_users.choices = [(str(user.id), user.first_name + " " + user.last_name) for user in all_users]
    if form.validate_on_submit():
        # Convert times to UTC
        start = pendulum.instance(form.start.data, tz=current_user.tz).in_tz('UTC')
        end = pendulum.instance(form.end.data, tz=current_user.tz).in_tz('UTC')
        if start >= end:
            flash('Start of event cannot be after end!', 'warning')
        elif start <= pendulum.now('UTC'):
            flash('Event cannot start in the past', 'warning')
        elif (end - start).hours > 24:
            flash('Events cannot span more than 1 day. Please use a recurring event.', 'warning')
        else:
            flash('Changes Saved', 'success')
            event.assigned_roles = [ObjectId(r) for r in form.assigned_roles.data]
            event.assigned_users = [ObjectId(r) for r in form.assigned_users.data]
            event.start = start
            event.end = end
            event.content = form.content.data
            event.name = form.name.data
            event.enable_rsvp = form.enable_rsvp.data
            event.enable_attendance = form.enable_attendance.data

            # Update task
            event.rsvp_task.update_from_form(form.rsvp_task, current_user.tz)
            event.rsvp_task.text = "RSVP for " + event.name
            event.rsvp_task.due = event.start
            event.rsvp_task.save()

            event.save()
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/scheduled_event_edit.html', event=event, form=form, 
            selected_roles=[role.name for role in event.assigned_roles],
            selected_users=[user.first_name + " " + user.last_name for user in event.assigned_users],

            selected_dates=[dt.in_tz(current_user.tz).isoformat() for dt in event.rsvp_task.notification_dates])

@admin.route('/m/<id>/publish')
def scheduled_event_publish(id):
    event = models.Event.objects(id=id, is_draft=True, is_recurring=False).first()
    if not event:
        abort(404)
    if not event.is_draft:
        redirect(url_for('admin.event_edit', id=id))
    # Save original list of assigned_users so it's possible to duplicate tasks
    original_assigned_users = event.assigned_users
    # Find all users with role
    for role in event.assigned_roles:
        users_with_role = models.User.objects(roles=role)
        for u in users_with_role:
            event.assigned_users.append(u)
    # Make sure list of users is unique
    event.assigned_users = list(set(event.assigned_users))
    # Create EventUser objects and assignments to user
    # Also create TaskUser objects 
    for user in event.assigned_users:
        eu = models.EventUser()
        eu.event = event
        eu.save()
        user.assigned_events.append(eu)

        if event.enable_rsvp:
            tu = models.TaskUser()
            tu.task = event.rsvp_task
            tu.watch_object = eu
            tu.link = url_for('public.event_info', id=event.id)
            tu.watch_field = "rsvp"
            tu.save()
            user.assigned_tasks.append(tu)

        user.save()

    # Create notifications
    if event.enable_rsvp:
        event.rsvp_task.send_notifications(event.assigned_users)
    event.assigned_users = original_assigned_users
    event.is_draft = False
    event.save()

    # Create task to RSVP
    return redirect(url_for('admin.scheduled_event_view', id=event.id))

@admin.route('/m/<id>/send_reminder')
def scheduled_event_send_reminder(id):
    event = models.Event.objects(id=id).first()
    if not event or event.is_draft:
        abort(404)
    all_users = models.User.objects
    for user in all_users:
        send_reminder = False
        for eu in user.assigned_events:
            if eu.event == event and not eu.rsvp:
                send_reminder = True
        if send_reminder:
            notification = models.PushNotification()
            notification.user = user
            notification.text = "RSVP Reminder : " + event.name
            notification.link = url_for('public.event_info', id=event.id, _external=True)
            notification.send_email = False
            notification.send_text  = False
            notification.send_app   = True
            notification.send_push  = False
            notification.save()
            tasks.send_notification((notification.id))
    flash('Sent notification to users', 'success')
    return redirect(url_for('admin.scheduled_event_view', id=event.id))

@admin.route('/newevent')
def scheduled_event_new():
    everyone_role = models.Role.objects(name='everyone').first()

    event = models.Event()
    event.start = pendulum.now('UTC').add(days=1)
    event.end = event.start.add(hours=2)
    task = models.Task()
    task.save()
    event.rsvp_task = task
    event.is_recurring = False
    event.assigned_roles = [everyone_role]
    event.save()
    return redirect(url_for('admin.scheduled_event_edit', id=event.id))

@admin.route('/rm/<id>/view')
def recurring_event_view(id):
    event = models.RecurringEvent.objects(id=id).first()
    if not event:
        abort(404)
    if event.is_draft:
        return redirect(url_for('admin.recurring_event_edit', id=event.id))
    return render_template('admin/recurring_event_view.html', event=event)

@admin.route('/rm/<id>/edit', methods=["GET","POST"])
def recurring_event_edit(id):
    event = models.RecurringEvent.objects(id=id).first()
    all_roles = models.Role.objects
    all_users = models.User.objects
    if not event:
        abort(404)
    if not event.is_draft:
        return redirect(url_for('admin.recurring_event_view', id=event.id))
    form_data = event.to_mongo().to_dict()
    form = forms.RecurringEventForm(data=form_data)
    all_days_of_week = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
    form.days_of_week.choices = list(zip(range(7), all_days_of_week))
    form.assigned_roles.choices = [(str(role.id), role.name) for role in all_roles]
    form.assigned_users.choices = [(str(user.id), user.first_name + " " + user.last_name) for user in all_users]
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
            event.assigned_roles = [ObjectId(r) for r in form.assigned_roles.data]
            event.assigned_users = [ObjectId(r) for r in form.assigned_users.data]
            event.name = form.name.data
            event.content = form.content.data
            event.days_of_week = form.days_of_week.data
            event.enable_rsvp = form.enable_rsvp.data
            event.enable_attendance = form.enable_attendance.data

            # Update task
            event.rsvp_task.update_from_form(form.rsvp_task, current_user.tz)
            event.rsvp_task.text = "RSVP for " + event.name
            event.rsvp_task.save()

            event.save()
            flash('Changes Saved', 'success')
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/recurring_event_edit.html',
            event=event,
            form=form,
            selected_days_of_week = event.days_of_week,
            selected_roles=[role.name for role in event.assigned_roles],
            selected_users=[user.first_name + " " + user.last_name for user in event.assigned_users],
            selected_dates=[dt.in_tz(current_user.tz).isoformat() for dt in event.rsvp_task.notification_dates])

@admin.route('/rm/<id>/publish')
def recurring_event_publish(id):
    event = models.RecurringEvent.objects(id=id, is_draft=True).first()
    if not event:
        abort(404)
    if not event.is_draft:
        redirect(url_for('admin.recurring_event_edit', id=id))

    # Save original list of assigned_users so it's possible to duplicate tasks
    original_assigned_users = event.assigned_users
    # Find all users with role
    for role in event.assigned_roles:
        users_with_role = models.User.objects(roles=role)
        for u in users_with_role:
            event.assigned_users.append(u)
    # Make sure list of users is unique
    event.assigned_users = list(set(event.assigned_users))

    start_date = pendulum.instance(event.start_date, tz=current_user.tz)
    end_date = pendulum.instance(event.end_date, tz=current_user.tz)
    period = end_date - start_date
    # Create individual instances of Event class (subevents)
    # Each one contains duplicated data of the recurring event
    # which allows for quicker access to that data from the public site
    for dt in period.range('days'):
        if dt.day_of_week in event.days_of_week:
            start = dt.at(event.start_time.hour, event.start_time.minute)
            start = start.in_tz('UTC')
            end = dt.at(event.end_time.hour, event.end_time.minute)
            end = end.in_tz('UTC')
            new_event = models.Event(name  = event.name,
                                     start = start,
                                     end   = end)
            new_event.is_recurring = True
            new_event.content = event.content
            new_event.name = event.name
            new_event.assigned_users = event.assigned_users
            new_event.enable_rsvp = event.enable_rsvp
            new_event.enable_attendance = event.enable_attendance
            new_event.is_draft = False
            new_event.save()
            event.events.append(new_event)

            # Create a separate task for each subevent
            if event.enable_rsvp:
                new_task = models.Task()
                new_task.text = event.rsvp_task.text + " on " + start.format('MM/DD/YYYY')
                new_task.notify_by_email = event.rsvp_task.notify_by_email
                new_task.notify_by_phone = event.rsvp_task.notify_by_phone
                new_task.notify_by_app = event.rsvp_task.notify_by_app
                new_task.notify_by_push = event.rsvp_task.notify_by_push
                new_task.due = new_event.start
                # Only notify on dates before this subevent
                new_task.notification_dates = event.rsvp_task.notification_dates
                new_task.save()

            # Create EventUser objects and assign to users
            for user in new_event.assigned_users:
                eu = models.EventUser()
                eu.event = new_event
                eu.save()
                user.assigned_events.append(eu)
                if event.enable_rsvp:
                    tu = models.TaskUser()
                    tu.task = new_task
                    tu.watch_object = eu
                    tu.link = url_for('public.recurring_event_info', id=event.id)
                    tu.watch_field = "rsvp"
                    tu.save()
                    user.assigned_tasks.append(tu)
                user.save()
            # Create notifications
            if event.enable_rsvp:
                new_task.send_notifications(new_event.assigned_users)
    event.is_draft = False
    event.save()
    return redirect(url_for('admin.recurring_event_view', id=event.id))

@admin.route('/rm/<id>/delete')
def recurring_event_delete(id):
    event = models.RecurringEvent.objects(id=id).first()
    all_users = models.User.objects
    if not event:
        abort(404)
    if not event.is_draft:
        # Delete associated recurring events
        for e in event.events:
            # Have to iterate over users and delete references manually
            for user in all_users:
                for eu in user.assigned_events:
                    if eu.event == e:
                        eu.delete()
                        user.assigned_events.remove(eu)
                if event.enable_rsvp:
                    for tu in user.assigned_tasks:
                        if tu.task == e.rsvp_task:
                            tu.delete()
                            user.assigned_tasks.remove(tu)
                user.save()
            if e.enable_rsvp:
                e.rsvp_task.delete()
            e.delete()
    if event.enable_rsvp:
        event.rsvp_task.delete()
    event.delete()
    flash('Deleted Event', 'success')
    return redirect(url_for('admin.event_list'))


@admin.route('/newrecurringevent')
def recurring_event_new():
    everyone_role = models.Role.objects(name='everyone').first()
    event = models.RecurringEvent()

    event.assigned_roles = [everyone_role]
    event.start_date = pendulum.today().naive()
    event.end_date = pendulum.today().add(weeks=1).naive()
    event.start_time = pendulum.naive(2010,1,1, 17, 0)
    event.end_time = pendulum.naive(2010,1,1, 19, 0)
    event.days_of_week = [1,3,5]
    task = models.Task()
    task.save()
    event.rsvp_task = task
    event.save()
    return redirect(url_for('admin.recurring_event_edit', id=event.id))

@admin.route('/assignments')
def assignment_list():
    assignments = models.Assignment.objects
    all_users = models.User.objects
    all_users.select_related(max_depth=2)
    for assignment in assignments:
        assignment.number_assigned = 0
        assignment.number_seen = 0
        assignment.number_completed = 0
        for user in all_users:
            # Filter AssignmentUser objects to those related to this assignment (should be 1 or 0)
            for au in user.assigned_assignments:
                # This is true if the user is assigned to the assignment
                if au.assignment.id == assignment.id:
                    assignment.number_assigned += 1
                    # Find associated TaskUser object
                    for tu in user.assigned_tasks:
                        if au.id == tu.watch_object.id:
                            if tu.seen:
                                assignment.number_seen += 1
                            if tu.completed:
                                assignment.number_completed += 1
    return render_template('admin/assignment_list.html', assignments=assignments)

@admin.route('/newassignment')
def assignment_new():
    everyone_role = models.Role.objects(name='everyone').first()
    assignment = models.Assignment()
    task = models.Task()
    task.save()
    assignment.subject = "New Assignment"
    assignment.task = task
    assignment.due = pendulum.now('UTC').add(days=7)
    assignment.task.notification_dates.append(pendulum.today(tz=current_user.tz).at(17,0).in_tz('UTC'))
    assignment.assigned_roles = [everyone_role]
    assignment.save()
    assignment.task.save()
    return redirect(url_for('admin.assignment_edit', id=assignment.id))


@admin.route('/assignment/<id>/edit', methods=['GET', 'POST'])
def assignment_edit(id):
    assignment = models.Assignment.objects(id=id).first()
    if not assignment:
        abort(404)
    if not assignment.is_draft:
        return redirect(url_for('admin.assignment_view', id=id))

    # Queries
    assignment.select_related(max_depth=2)
    all_roles = models.Role.objects
    all_users = models.User.objects

    form_data = assignment.to_mongo().to_dict()
    form_data['due'] = form_data['due'].in_tz(current_user.tz)
    form = forms.AssignmentForm(data=form_data)
    form.assigned_roles.choices = [(str(role.id), role.name) for role in all_roles]
    form.assigned_users.choices = [(str(user.id), user.first_name + " " + user.last_name) for user in all_users]
    if form.validate_on_submit():
        assignment.subject = form.subject.data
        assignment.content = form.content.data
        assignment.due = pendulum.instance(form.due.data, tz=current_user.tz).in_tz('UTC')
        if assignment.due < pendulum.now('UTC'):
            flash('Task cannot be due in the past', 'warning')
        else:
            assignment.assigned_roles = [ObjectId(r) for r in form.assigned_roles.data]
            assignment.assigned_users = [ObjectId(r) for r in form.assigned_users.data]
            # Update task
            assignment.task.update_from_form(form.task, current_user.tz)
            assignment.task.text = assignment.subject
            assignment.task.due = assignment.due
            assignment.task.save()
            assignment.save()
            assignment.reload()
            flash('Changes Saved', 'success')
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/assignment_edit.html', assignment=assignment, form=form,
            selected_roles=[role.name for role in assignment.assigned_roles],
            selected_users=[user.first_name + " " + user.last_name for user in assignment.assigned_users],
            selected_dates=[dt.in_tz(current_user.tz).isoformat() for dt in assignment.task.notification_dates])

@admin.route('/assignment/<id>/publish')
def assignment_publish(id):
    assignment = models.Assignment.objects(id=id).first()
    assignment.select_related(max_depth=2)
    if not assignment:
        abort(404)
    if not assignment.is_draft:
        redirect(url_for('admin.assignment_edit', id=id))
    # Parse assignment into viewing format
    assignment.is_draft = False
    # Save original list of assigned_users so it's possible to duplicate assignments
    original_assigned_users = assignment.assigned_users
    # Find all users with role
    for role in assignment.assigned_roles:
        users_with_role = models.User.objects(roles=role)
        for u in users_with_role:
            assignment.assigned_users.append(u)
    # Make sure list of users is unique
    assignment.assigned_users = list(set(assignment.assigned_users))
    # Create TaskUser objects and assignments to user
    for user in assignment.assigned_users:
        au = models.AssignmentUser()
        au.assignment = assignment
        au.save()

        tu = models.TaskUser()
        tu.task = assignment.task
        tu.link = url_for('public.assignment_info', id=assignment.id)
        tu.watch_object = au
        tu.watch_field = 'completed'
        tu.save()

        user.assigned_assignments.append(au)
        user.assigned_tasks.append(tu)
        user.save()

    # Create notifications
    assignment.save()
    assignment.task.send_notifications(assignment.assigned_users)
    return redirect(url_for('admin.assignment_view',id=id))


@admin.route('/assignment/<id>/view')
def assignment_view(id):
    assignment = models.Assignment.objects(id=id).first()
    if not assignment:
        abort(404)
    if assignment.is_draft:
        return redirect(url_for('admin.assignment_edit', id=id))
    # Complex query here, but it's okay because this is an admin interface
    # First filter users to make sure they're assigned to the assignment
    all_users = models.User.objects
    all_users.select_related(max_depth=2)
    assigned_users = []
    for user in all_users:
        # Filter AssignmentUser objects to those related to this assignment (should be 1 or 0)
        for au in user.assigned_assignments:
            # This is true if the user is assigned to the assignment
            if au.assignment.id == assignment.id:
                # Find associated TaskUser object and attach it
                for tu in user.assigned_tasks:
                    if au.id == tu.watch_object.id:
                        user.tu = tu
                user.au = au
        if user.au:
            assigned_users.append(user)
    return render_template('admin/assignment_view.html', assignment=assignment, assigned_users=assigned_users)

@admin.route('/assignment/<id>/duplicate')
def assignment_duplicate(id):
    assignment = models.Assignment.objects(id=id).first()
    if not assignment:
        abort(404)
    new_assignment         = models.Assignment()
    new_assignment.subject = assignment.subject + " Copy"
    new_assignment.content = assignment.content
    new_assignment.assigned_roles = assignment.assigned_roles
    new_assignment.assigned_users = assignment.assigned_users
    new_assignment.due     = pendulum.tomorrow('UTC')
    new_assignment.task    = assignment.task
    # Clear notification dates in case they are outside the range
    new_assignment.task.notification_dates = []
    new_assignment.save()
    return redirect(url_for('admin.assignment_edit', id=new_assignment.id))


@admin.route('/assignment/<id>/delete')
def assignment_delete(id):
    assignment = models.Assignment.objects(id=id).first()
    if not assignment:
        abort(404)
    if not assignment.is_draft:
        # Since assignments have no record of who is assigned we have to delete au's manually
        # Same with tus
        all_users = models.User.objects
        all_users.select_related(max_depth=2)
        for user in all_users:
            for au in user.assigned_assignments:
                if au.assignment == assignment:
                    au.delete()
                    user.assigned_assignments.remove(au)
            for tu in user.assigned_tasks:
                if tu.task == assignment.task:
                    tu.delete()
                    user.assigned_tasks.remove(tu)
            user.save()
    assignment.delete()
    assignment.task.delete()
    return redirect(url_for('admin.assignment_list'))

@admin.route('/debug')
def debug_tools():
    return render_template('admin/debug_tools.html')

@admin.route('/debug/clear_db')
def clear_db():
    models.PushNotification.drop_collection()
    models.Event.drop_collection()
    models.EventUser.drop_collection()
    models.RecurringEvent.drop_collection()
    models.Task.drop_collection()
    models.TaskUser.drop_collection()
    models.Assignment.drop_collection()
    models.AssignmentUser.drop_collection()

    for user in models.User.objects:
        user.assigned_tasks = []
        user.assigned_events = []
        user.assigned_assignments = []
        user.notifications = []
        user.save()

    flash('Cleared DB', 'success')
    return redirect(url_for('admin.debug_tools'))

def flash_errors(form):
    """Flash errors from a form at the top of the page"""
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ), 'warning')
