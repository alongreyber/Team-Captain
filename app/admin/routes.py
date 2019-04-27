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
    return render_template('admin/role_list.html', roles=roles, role_form=role_form)

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
    scheduled_events = models.Event.objects(is_recurring=False)
    recurring_events = models.RecurringEvent.objects()
    return render_template('admin/event_list.html',
            scheduled_events=scheduled_events,
            recurring_events=recurring_events)

@admin.route('/m/<id>/view')
def scheduled_event_view(id):
    event = models.Event.objects(id=id, is_recurring=False).first()
    if not event:
        abort(404)
    if event.is_draft:
        redirect(url_for('admin.scheduled_event_edit', id=event.id))
    return render_template('admin/event_view.html', event=event)

@admin.route('/m/<id>/edit', methods=["GET","POST"])
def scheduled_event_edit(id):
    event = models.Event.objects(id=id, is_recurring=False).first()
    if not event:
        abort(404)
    if not event.is_draft:
        return redirect(url_for('admin.scheduled_event_view', id=event.id))
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
    return render_template('admin/event_edit.html', event=event, form=form)

@admin.route('/m/<id>/publish')
def scheduled_event_publish(id):
    event = models.Event.objects(id=id, is_draft=True, is_recurring=False).first()
    if not event:
        abort(404)
    event.is_draft = False
    event.save()
    return redirect(url_for('admin.scheduled_event_view', id=event.id))

@admin.route('/newevent')
def scheduled_event_new():
    event = models.Event()
    event.start = datetime.datetime.now() + datetime.timedelta(days=1)
    event.end = event.start + datetime.timedelta(hours=2)
    event.is_recurring = False
    event.save()
    return redirect(url_for('admin.scheduled_event_edit', id=event.id))

@admin.route('/rm/<id>/view')
def recurring_event_view(id):
    event = models.RecurringEvent.objects(id=id).first()
    raise
    if not event:
        abort(404)
    if event.is_draft:
        return redirect(url_for('admin.recurring_event_edit', id=event.id))
    return render_template('admin/recurring_event_view.html', event=event)

@admin.route('/rm/<id>/subevent/<eid>')
def recurring_event_subevent_view(id, eid):
    recurring_event = models.RecurringEvent.objects(id=id).first()
    if not recurring_event or recurring_event.is_draft:
        abort(404)
    event = models.Event.objects(id=eid).first()
    if not event or not event.is_recurring:
        abort(404)
    return render_template('admin/recurring_event_subevent_view.html', recurring_event=recurring_event, event=event)

@admin.route('/rm/<id>/edit', methods=["GET","POST"])
def recurring_event_edit(id):
    event = models.RecurringEvent.objects(id=id).first()
    if not event:
        abort(404)
    if not event.is_draft:
        return redirect(url_for('admin.recurring_event_view', id=event.id))
    form_data = {'name' : event.name,
            'content': event.content,
            'start_date' : event.start.date(), 'start_time':event.start.time(),
            'end_date':event.end.date(),       'end_time':event.end.time()}
    form = forms.RecurringEventForm(data=form_data)
    all_days_of_week = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
    form.days_of_week.choices = list(zip(range(7), all_days_of_week))
    if form.validate_on_submit():
        if form.end_time.data <= form.start_time.data:
            flash('Start time of event cannot be before end!', 'warning')
        elif form.end_date.data <= form.start_date.data:
            flash('Start date of event cannot be before end!', 'warning')
        elif form.start_date.data < datetime.datetime.now().date():
            flash('Events cannot start in the past!', 'warning')
        elif len(form.days_of_week.data) == 0:
            flash('Event must happen at least one day a week!', 'warning')
        else:
            event.start = datetime.datetime.combine(form.start_date.data, form.start_time.data)
            event.end = datetime.datetime.combine(form.end_date.data, form.end_time.data)
            event.name = form.name.data
            event.content = form.content.data
            event.days_of_week = form.days_of_week.data
            event.save()
            flash('Changes Saved', 'success')
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/recurring_event_edit.html',
            event=event,
            form=form,
            selected_days_of_week = event.days_of_week)

@admin.route('/rm/<id>/publish')
def recurring_event_publish(id):
    event = models.RecurringEvent.objects(id=id, is_draft=True).first()
    if not event:
        abort(404)
    d = event.start.date()
    while d <= event.end.date():
        d += datetime.timedelta(days=1)
        if d.weekday() in event.days_of_week:
            new_event = models.Event(name  = event.name,
                                     start = datetime.datetime.combine(d,event.start.time()),
                                     end   = datetime.datetime.combine(d,event.end.time()))
            new_event.is_recurring = True
            new_event.save()
            event.events.append(new_event)
    event.is_draft = False
    event.save()
    return redirect(url_for('admin.recurring_event_view', id=event.id))

@admin.route('/newrecurringevent')
def recurring_event_new():
    event = models.RecurringEvent()
    event.start = datetime.datetime.combine(
            datetime.date.today(),
            datetime.time(17, 0)
            )
    event.end = datetime.datetime.combine(
            datetime.date.today() + datetime.timedelta(days=7),
            datetime.time(19, 0)
            )
    event.days_of_week = [1,3,5]
    event.save()
    return redirect(url_for('admin.recurring_event_edit', id=event.id))

@admin.route('/tasks')
def task_list():
    tasks = models.Task.objects
    all_users = models.User.objects
    all_users.select_related(max_depth=2)

    # Complex query, but that's ok because we're in admin interface
    for task in tasks:
        task.number_completed = 0
        task.number_seen = 0
        task.number_assigned = 0
        for user in all_users:
            # Filter TaskUser objects to those related to this task (should be 1 or 0)
            for tu in user.assigned_tasks:
                if tu.task == task:
                    task.number_assigned += 1
                    if tu.completed:
                        task.number_completed += 1
                    if tu.seen:
                        task.number_seen += 1
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
        task.content = form.content.data
        task.due = form.due.data
        task.assigned_roles = [ObjectId(r) for r in form.assigned_roles.data]
        task.assigned_users = [ObjectId(r) for r in form.assigned_users.data]
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
            selected_users=[user.first_name + " " + user.last_name for user in task.assigned_users])

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
    # Save original list of assigned_users so it's possible to duplicate tasks
    task.original_assigned_users = task.assigned_users
    # Find all users with role
    for role in task.assigned_roles:
        users_with_role = models.User.objects(roles=role)
        for u in users_with_role:
            task.assigned_users.append(u)
    # Make sure list of users is unique
    task.assigned_users = list(set(task.assigned_users))
    # Create TaskUser objects and assignments to user
    for user in task.assigned_users:
        tu = models.TaskUser()
        tu.task = task
        tu.save()
        user.assigned_tasks.append(tu)
        user.save()
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

    for user in task.assigned_users:
        for time in times:
            notification = models.PushNotification()
            notification.user = user
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
                tasks.send_notification((notification.id))
            else:
                tasks.send_notification.schedule((notification.id), eta=notification.date)
    task.assigned_users = task.original_assigned_users
    task.save()
    return redirect(url_for('admin.task_view',id=id))


@admin.route('/task/<id>/view')
def task_view(id):
    # Complex query here, but it's okay because this is an admin interface
    task = models.Task.objects(id=id).first()
    if not task:
        abort(404)
    # First filter users to make sure they're assigned to the task
    all_users = models.User.objects
    all_users.select_related(max_depth=2)
    assigned_users = []
    for user in all_users:
        # Filter TaskUser objects to those related to this task (should be 1 or 0)
        assigned_tasks = []
        for tu in user.assigned_tasks:
            if tu.task == task:
                assigned_tasks.append(tu)
        user.assigned_tasks = assigned_tasks
        if len(user.assigned_tasks) > 0:
            assigned_users.append(user)
    if not task:
        abort(404)
    if task.is_draft:
        return redirect(url_for('admin.task_edit', id=id))
    return render_template('admin/task_view.html', task=task, assigned_users=assigned_users)

@admin.route('/task/<id>/duplicate')
def task_duplicate(id):
    task = models.Task.objects(id=id).first()
    if not task:
        abort(404)
    new_task         = models.Task()
    new_task.subject = task.subject + " Copy"
    new_task.content = task.content
    new_task.due     = datetime.datetime.now()
    new_task.assigned_users = task.assigned_users
    new_task.assigned_roles = task.assigned_roles
    new_task.notify_by_phone = task.notify_by_phone
    new_task.notify_by_email = task.notify_by_email
    new_task.additional_notifications = task.additional_notifications
    new_task.save()
    return redirect(url_for('admin.task_edit', id=new_task.id))


@admin.route('/task/<id>/delete')
def task_delete(id):
    task = models.Task.objects(id=id).first()
    if not task:
        abort(404)
    if not task.is_draft:
        # Since tasks have no record of who is assigned we have to delete tu's manually
        all_users = models.User.objects
        all_users.select_related(max_depth=2)
        for user in all_users:
            for tu in user.assigned_tasks:
                if tu.task == task:
                    tu.delete()
                    user.assigned_tasks.remove(tu)
            user.save()
    task.delete()
    return redirect(url_for('admin.task_list'))

def flash_errors(form):
    """Flash errors from a form at the top of the page"""
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ), 'warning')
