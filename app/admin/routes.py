from app import models, forms
from app.admin import context
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint

from flask_login import current_user

import datetime

admin = Blueprint('admin', __name__, template_folder='templates')

@admin.before_request
def require_authorization():
    if not current_user.is_authenticated:
        flash('Please log in to view this page', 'danger')
        return redirect(url_for('login', next=request.endpoint))
    if "admin" not in current_user.roles:
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
    if not user:
        abort(404)
    form = forms.UserForm(request.form, data=user.to_mongo().to_dict())
    role_form = forms.RoleForm()
    if form.validate_on_submit():
        user_updated_dict = form.data
        del user_updated_dict['csrf_token']
        user.modify(**user_updated_dict)
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/user_info.html', user=user, form=form, role_form=role_form)

@admin.route('/u/<id>/role/add', methods=['POST'])
def add_role(id):
    user = models.User.objects(id=id).first()
    if not user:
        abort(404)
    form = forms.RoleForm()
    if form.validate_on_submit():
        role = form.data['role']
        role = role.lower()
        if role in user.roles:
            flash('User already has role', 'warning')
        else:
            user.roles.append(role)
            user.save()
    if len(form.errors) > 0:
        flash_errors(form)
    return redirect(url_for('admin.user_info', id=user.id))

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
    return redirect(url_for('admin.task_info', id=task.id))

@admin.route('/task/<id>', methods=['GET', 'POST'])
def task_info(id):
    task = models.Task.objects(id=id).first()
    form = forms.TaskForm(data=task.to_mongo().to_dict())
    user_select_form = forms.SelectUsersForm()
    if not task:
        abort(404)
    if form.validate_on_submit():
        task_updated_dict = form.data
        del task_updated_dict['csrf_token']
        task.modify(**task_updated_dict)
        flash('Changes Saved', 'success')
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/task_info.html', task=task, form=form, user_select_form=user_select_form)

def flash_errors(form):
    """Flash errors from a form at the top of the page"""
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ), 'warning')
