from app import models, forms, tasks
from app.admin import context
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint, send_file

from flask_login import current_user

import datetime, json, io, csv

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

@admin.route('/user/<id>', methods=['GET', 'POST'])
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

@admin.route('/user/<id>/delete')
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

@admin.route('/attendance/csv')
def attendance_download_csv():
    all_eus = models.EventUser.objects
    all_users = models.User.objects
    # Fill in eu.user
    for eu in all_eus:
        for user in all_users:
            if eu in user.assigned_events:
                eu.user = user
                break
    proxy = io.StringIO()
    writer = csv.writer(proxy)
    header = ['Event Name','Event Date', 'Sign In', 'Sign Out', 'User Name', 'User Email']
    writer.writerow(header)
    # Write to CSV
    for eu in all_eus:
        if eu.sign_in:
            start_time = eu.sign_in.in_tz(current_user.tz).format('HH:mm')
        else:
            start_time = ""
        if eu.sign_out:
            end_time = eu.sign_out.in_tz(current_user.tz).format('HH:mm')
        else:
            end_time = ""
        row = [eu.event.name,
                eu.event.start.in_tz(current_user.tz).format('MM/DD/YYYY'),
                start_time,
                end_time,
                eu.user.first_name + " " + eu.user.last_name,
                eu.user.email]
        writer.writerow(row)

    # Creating the byteIO object from the StringIO Object
    mem = io.BytesIO()
    mem.write(proxy.getvalue().encode('utf-8'))
    mem.seek(0)
    proxy.close()

    response = send_file(
        mem,
        as_attachment=True,
        attachment_filename='attendance-data.csv',
        mimetype='text/csv')
    response.headers["Cache-Control"] = "no-cache"
    return response

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

@admin.route('/wiki')
def article_list():
    articles = models.Article.objects
    topics = models.Topic.objects
    return render_template('admin/article_list.html', articles=articles, topics=topics)

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
    models.Calendar.drop_collection()
    models.Topic.drop_collection()
    models.Article.drop_collection()

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
