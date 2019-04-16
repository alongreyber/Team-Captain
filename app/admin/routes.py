from app import models, forms, tasks
from app.admin import context
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint

from flask_login import current_user

import datetime, json

from bson import ObjectId

admin = Blueprint('admin', __name__, template_folder='templates')

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
    if not user:
        abort(404)
    form = forms.UserForm(request.form, data=user.to_mongo().to_dict())
    form.roles.choices = [(str(role.id), role.name) for role in all_roles]
    if form.validate_on_submit():
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.email = form.email.data
        user.barcode = form.barcode.data
        user.roles = [ObjectId(r) for r in form.roles.data]
        user.save()
        flash('Changes Saved', 'success')
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/user_info.html', user=user, form=form,
            selected_roles=[role.name for role in user.roles])

@admin.route('/roles')
def role_list():
    roles = models.Role.objects
    role_form = forms.RoleForm()
    return render_template('admin/role_list.html', roles=roles, role_form=role_form)

@admin.route('/newrole', methods=['POST'])
def role_new():
    form = forms.RoleForm()
    all_roles = models.Role.objects
    if form.validate_on_submit():
        for r in all_roles:
            if r.name == form.data['role'].lower():
                flash(f'Role already exists', 'warning')
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
    role.delete()
    flash('Deleted Role', 'success')
    return redirect(url_for('admin.role_list'))

@admin.route('/u/<id>/role/remove/<role>')
def remove_role(id, role):
    user = models.User.objects(id=id).first()
    if role not in user.roles:
        flash('Role not found!', 'warning')
    else:
        user.roles.remove(role)
        user.save()
        flash('Role Removed', 'success')
    return redirect(url_for('admin.user_info', id=user.id))

@admin.route('/events')
def event_list():
    scheduled_events = models.Event.objects(recurrence=None)
    recurring_events = models.RecurringEvent.objects()
    return render_template('admin/event_list.html',
            scheduled_events=scheduled_events,
            recurring_events=recurring_events)


@admin.route('/m/<id>', methods=["GET","POST"])
def scheduled_event_info(id):
    event = models.Event.objects(id=id, recurrence=None).first()
    if not event or event.start < datetime.datetime.now():
        abort(404)
    form = forms.EventForm(request.form, data=event.to_mongo().to_dict())
    if form.validate_on_submit():
        updated_dict = form.data
        # The dates/times need to be converted to datetime objects
        del updated_dict['csrf_token']
        if updated_dict['end'] <= updated_dict['start']:
            flash('Start of event cannot be before end!', 'warning')
        elif updated_dict['start'] <= datetime.datetime.now():
            flash('Event cannot start in the past', 'warning')
        else:
            flash('Changes Saved', 'success')
            event.modify(**updated_dict)
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/event_info.html', event=event, form=form)

@admin.route('/rm/<id>', methods=["GET","POST"])
def recurring_event_info(id):
    event = models.RecurringEvent.objects(id=id).first()
    if not event:
        abort(404)
    form = forms.RecurringEventForm(request.form, data=event.to_mongo().to_dict())
    all_days_of_week = ['S','M','T','W','H','F','S']
    form.days_of_week.choices = list(zip(range(7), all_days_of_week))
    if form.validate_on_submit():
        updated_dict = form.data
        # The dates/times need to be converted to datetime objects
        updated_dict['start_time'] = datetime.datetime.combine(datetime.datetime.min.date(), updated_dict['start_time'])
        updated_dict['end_time'] = datetime.datetime.combine(datetime.datetime.min.date(), updated_dict['end_time'])
        del updated_dict['csrf_token']
        if updated_dict['end_time'] <= updated_dict['start_time']:
            flash('Start of event cannot be before end!', 'warning')
        elif updated_dict['end_date'] <= updated_dict['start_date']:
            flash('Start of recurring event cannot be before end!', 'warning')
        elif updated_dict['start_date'] < datetime.datetime.now().date():
            flash('Events cannot start in the past!', 'warning')
        elif len(updated_dict['days_of_week']) == 0:
            flash('Event must happen at least one day a week!', 'warning')
        else:
            updated_dict['start_date'] = datetime.datetime.combine(updated_dict['start_date'], datetime.datetime.min.time())
            updated_dict['end_date'] = datetime.datetime.combine(updated_dict['end_date'], datetime.datetime.min.time())
            flash('Changes Saved', 'success')
            event.modify(**updated_dict)
            # Delete the existing events
            models.Event.objects(recurrence=event).delete()
            # Re-add
            d = event.start_date
            while d <= event.end_date:
                d += datetime.timedelta(days=1)
                if d.weekday() in event.days_of_week:
                    new_event = models.Event(name=event.name,
                                                 start=datetime.datetime.combine(d,event.start_time.time()),
                                                 end=datetime.datetime.combine(d,event.end_time.time()),
                                                 recurrence = event)
                    new_event.save()
    if len(form.errors) > 0:
        flash_errors(form)
    print(event.days_of_week)
    return render_template('admin/recurring_event_info.html',
            event=event,
            form=form,
            selected_days_of_week = event.days_of_week)

@admin.route('/newrecurringevent')
def recurring_event_new():
    event = models.RecurringEvent()
    event.start_date = datetime.datetime.now()
    event.end_date = datetime.datetime.now() + datetime.timedelta(days=1) 
    event.start_time = datetime.datetime.combine(datetime.datetime.min.date(), datetime.time(17))
    event.end_time = datetime.datetime.combine(datetime.datetime.min.date(), datetime.time(19))
    event.days_of_week = [1,3,5]
    event.save()
    return redirect(url_for('admin.recurring_event_info', id=event.id))

@admin.route('/newevent')
def event_new():
    event = models.Event()
    event.start = datetime.datetime.now() + datetime.timedelta(days=1)
    event.end = event.start + datetime.timedelta(hours=2)
    event.save()
    return redirect(url_for('admin.scheduled_event_info', id=event.id))

@admin.route('/tasks')
def task_list():
    tasks = models.Task.objects
    return render_template('admin/task_list.html', tasks=tasks)

@admin.route('/newtask')
def task_new():
    task = models.Task()
    task.due = datetime.datetime.now()
    task.save()
    return redirect(url_for('admin.task_edit', id=task.id))


@admin.route('/task/<id>/edit', methods=['GET', 'POST'])
def task_edit(id):
    task = models.Task.objects(id=id).first()
    if not task:
        abort(404)
    if not task.is_draft:
        return redirect(url_for('admin.task_view', id=id))

    # Queries
    task.select_related(max_depth=2)
    all_roles = models.Role.objects
    all_users = models.User.objects

    form = forms.TaskForm(data=task.to_mongo().to_dict())
    form.assigned_roles.choices = [(str(role.id), role.name) for role in all_roles]
    form.assigned_users.choices = [(str(user.id), user.first_name + " " + user.last_name) for user in all_users]
    if form.validate_on_submit():
        task.subject = form.subject.data
        task.content = json.dumps(form.content.data)
        task.due = form.due.data
        task.assigned_roles = [ObjectId(r) for r in form.assigned_roles.data]
        # Need to create a list of TaskUser objects
        tu_list = []
        for r in form.assigned_users.data:
            tu = models.TaskUser()
            tu.user = ObjectId(r)
            tu_list.append(tu)
        task.assigned_users = tu_list
        task.notify_by_email = form.notify_by_email.data
        task.notify_by_phone = form.notify_by_phone.data
        task.additional_notifications = form.additional_notifications.data
        task.save()
        task.reload()
        flash('Changes Saved', 'success')
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/task_edit.html', task=task, form=form,
            selected_roles=[role.name for role in task.assigned_roles],
            selected_users=[tu.user.first_name + " " + tu.user.last_name for tu in task.assigned_users])

@admin.route('/task/<id>/publish')
def task_publish(id):
    task = models.Task.objects(id=id).first()
    task.select_related(max_depth=2)
    if not task:
        abort(404)
    if not task.is_draft:
        redirect(url_for('admin.task_edit', id=id))
    # Parse task into viewing format
    task.is_draft = False
    # Find all users with role
    for role in task.assigned_roles:
        users_with_role = models.User.objects(roles=role)
        for u in users_with_role:
            tu = models.TaskUser()
            tu.user = u
            # have to check if user is already in assigned_users to avoid duplicates
            add = True
            print(f"Existing TU objects: {task.assigned_users}")
            print(f"Trying to add: {u}")
            for existing_tu in task.assigned_users:
                if existing_tu.user == u:
                    add = False
            if add:
                print('Added')
                task.assigned_users.append(tu)
    task.save()
    task.reload()

    times = []
    # Add instant notification
    times.append(datetime.datetime.now())

    # Add notifications on days before due at 5:30PM
    iter_datetime = datetime.datetime.combine(
            task.due.date() - datetime.timedelta(days=1),
            datetime.time(17, 30)) # 5:30
    # By choosing <=, we ensure that at least one notification before due is sent (unless due date is today)
    i = 0
    while iter_datetime > datetime.datetime.now() and i <= task.additional_notifications:
        times.append(iter_datetime)
        iter_datetime = iter_datetime - datetime.timedelta(days=1)
        i += 1

    for tu in task.assigned_users:
        for time in times:
            notification = models.PushNotification()
            notification.user = tu.user
            notification.text = task.subject
            notification.date = time
            notification.link = url_for('public.task_info', id=task.id, _external=True)
            notification.send_email = task.notify_by_email
            notification.send_text  = task.notify_by_phone
            notification.send_app   = True
            notification.send_push  = True
            notification.save()
            # Schedule task for sending unless it's right now
            if notification.date <= datetime.datetime.now():
                tasks.send_notification(notification.id)
            else:
                tasks.send_notification.schedule(notification.id, eta=notification.date)
    return redirect(url_for('admin.task_view',id=id))


@admin.route('/task/<id>/view')
def task_view(id):
    task = models.Task.objects(id=id).first()
    if not task:
        abort(404)
    if task.is_draft:
        return redirect(url_for('admin.task_edit', id=id))
    return render_template('admin/task_view.html', task=task)

def flash_errors(form):
    """Flash errors from a form at the top of the page"""
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ), 'warning')
