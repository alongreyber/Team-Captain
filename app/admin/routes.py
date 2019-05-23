from app import models, forms, tasks
from app.admin import context
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint, send_file, g

from flask_login import current_user

import datetime, json, io, csv

import pendulum
from bson import ObjectId

admin = Blueprint('admin', __name__, template_folder='templates')

# Roles that can't be deleted
protected_roles = ['everyone', 'admin']

# Look up the current team
@admin.url_value_preprocessor
def get_team(endpoint, values):
    team = models.Team.objects(sub=values.pop('sub')).first()
    if not team:
        abort(404)
    g.team = team

# Inject a function team_url_for that adds the correct subdomain
def team_url_for(*args, **kwargs):
    return url_for(*args, sub=g.team.sub, **kwargs)
@admin.context_processor
def inject_url_for():
    return dict(team_url_for=team_url_for)

@admin.before_request
def require_authorization():
    if not current_user.is_authenticated:
        flash('Please log in to view this page', 'danger')
        return redirect(team_url_for('login', next=request.endpoint))
    for role in current_user.roles:
        if role.name == 'admin':
            return
    flash('You do not have permission to view this page', 'danger')
    return redirect(team_url_for('team.index'))

@admin.route('/')
def index():
    return redirect(team_url_for('admin.user_list'))

@admin.route('/settings', methods=['GET', 'POST'])
def team_settings():
    form = forms.TeamForm(data=g.team.to_mongo().to_dict())
    if form.validate_on_submit():
        old_subdomain = g.team.sub
        g.team.name = form.name.data
        g.team.sub = form.sub.data
        g.team.number = form.number.data
        g.team.email_subdomain = form.email_subdomain.data
        g.team.save()
        flash('Changes Saved', 'success')
        g.team.reload()
        if g.team.sub != old_subdomain:
            return redirect(team_url_for('admin.team_settings'))
    return render_template('admin/team_settings.html',
            form=form)

@admin.route('/users')
def user_list():
    users = models.User.objects(team=g.team)
    role_colors = ['#5484ed', '#dc2127', '#a4bdfc', '#46d6db', '#7ae7bf',  '#fbd75b', '#ffb878', '#51b749', '#ff887c', '#dbadff', '#e1e1e1']
    seen_roles = []
    for user in users:
        for role in user.roles:
            if role not in seen_roles:
                seen_roles.append(role)
                role.color = role_colors[len(seen_roles)]
            else:
                for r in seen_roles:
                    if r.id == role.id:
                        role.color = r.color
    unconfirmed_users = models.User.objects(team=None, team_number=g.team.number)
    return render_template('admin/user_list.html',
            users=users,
            unconfirmed_users=unconfirmed_users)

@admin.route('/user/<id>/approve')
def user_approve(id):
    user = models.User.objects(id=id).first()
    if not user:
        abort(404)
    if user.team:
        abort(404)
    user.team = g.team
    everyone_role = models.Role.objects(team=g.team, name='everyone').first()
    user.roles = [everyone_role]
    user.team_number = None
    user.save()
    # Make users complete their profile
    user.assigned_tasks = [user]
    user.save()
    flash('User Approved', 'success')
    return redirect(team_url_for('admin.user_list'))

@admin.route('/user/<id>/deny')
def user_deny(id):
    user = models.User.objects(id=id).first()
    if not user:
        abort(404)
    if user.team:
        abort(404)
    user.team_number = None
    user.save()
    flash('User Denied', 'success')
    return redirect(team_url_for('admin.user_list'))

@admin.route('/user/<id>', methods=['GET', 'POST'])
def user_info(id):
    user = models.User.objects(team=g.team, id=id).first()
    all_roles = models.Role.objects(team=g.team)
    everyone_role = models.Role.objects(team=g.team, name='everyone').first()
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
    user = models.User.objects(team=g.team, id=id).first()
    for tu in user.assigned_tasks:
        tu.delete()
    user.delete()
    return redirect(team_url_for('admin.user_list'))

@admin.route('/roles')
def role_list():
    roles = models.Role.objects(team=g.team)
    role_form = forms.RoleForm()
    return render_template('admin/role_list.html', roles=roles, role_form=role_form, protected_roles=protected_roles)

@admin.route('/newrole', methods=['POST'])
def role_new():
    form = forms.RoleForm()
    all_roles = models.Role.objects(team=g.team)
    if form.validate_on_submit():
        for r in all_roles:
            if r.name == form.data['role'].lower():
                flash('Role already exists', 'warning')
                return redirect(team_url_for('admin.role_list'))
        new_role = models.Role(team=g.team)
        new_role.name = form.data['role'].lower()
        new_role.save()
        flash('Added Role', 'success')
    if len(form.errors) > 0:
        flash_errors(form)
    return redirect(team_url_for('admin.role_list'))

@admin.route('/role/<id>/remove')
def role_delete(id):
    role = models.Role.objects(team=g.team, id=id).first()
    if role.name in protected_roles:
        flash('Cannot delete this role', 'danger')
    else:
        for user in models.User.objects(team=g.team):
            user.roles.remove(role)
            user.save()
        role.delete()
        flash('Deleted Role', 'success')
    return redirect(team_url_for('admin.role_list'))

@admin.route('/attendance', methods=['GET', 'POST'])
def attendance_graphs():
    all_eus = models.EventUser.objects(team=g.team)
    all_events = models.Event.objects(team=g.team)
    all_users = models.User.objects(team=g.team)
    all_roles = models.Role.objects(team=g.team)
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
    # Filter data by current user
    data = {}
    # Fill in eu.event
    for eu in all_eus:
        eu.event = models.Event.objects(team=g.team, users=eu.id).first()
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
    all_eus = models.EventUser.objects(team=g.team)
    all_users = models.User.objects(team=g.team)
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


@admin.route('/wiki')
def article_list():
    articles = models.Article.objects(team=g.team)
    topics = models.Topic.objects(team=g.team)
    return render_template('admin/article_list.html', articles=articles, topics=topics)

@admin.route('/debug')
def debug_tools():
    return render_template('admin/debug_tools.html')


@admin.route('/debug/clear_db')
def clear_db():
    models.Team.drop_collection()
    models.Role.drop_collection()
    models.PushNotification.drop_collection()
    models.User.drop_collection()
    models.Calendar.drop_collection()
    models.Event.drop_collection()
    models.RecurringEvent.drop_collection()
    models.EventUser.drop_collection()
    models.Assignment.drop_collection()
    models.AssignmentUser.drop_collection()
    models.Topic.drop_collection()
    models.Article.drop_collection()

    flash('Cleared DB', 'success')
    return redirect(team_url_for('admin.debug_tools'))

@admin.route('/debug/save_db')
def save_db():
    collections = [
        models.Team,
        models.Role,
        models.PushNotification,
        models.User,
        models.Calendar,
        models.Event,
        models.RecurringEvent,
        models.EventUser,
        models.Assignment,
        models.AssignmentUser,
        models.Topic,
        models.Article]
    for c in collections:
        c_str = c.objects.to_json()
        with open("export/" + c.__name__ + ".json", 'w') as outfile:
            outfile.write(c_str)
    flash('Saved DB', 'success')
    return redirect(team_url_for('admin.debug_tools'))


def flash_errors(form):
    """Flash errors from a form at the top of the page"""
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ), 'warning')
