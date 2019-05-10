from app import models, forms, oauth, tasks
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint
from flask_login import current_user, login_required

import pendulum
from bson import ObjectId

from mongoengine.errors import NotUniqueError

import datetime

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
        try:
            current_user.modify(**updated_dict)
            flash('Changes Saved', 'success')
            return redirect(url_for('public.user_profile'))
        except NotUniqueError:
            flash('Barcode already in use', 'warning')
    if len(form.errors) > 0:
        flash_errors(form)
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


@public.route('/recurringevent/<id>')
@login_required
def recurring_event_info(id):
    recurring_event = models.RecurringEvent.objects(id=id).first()
    if not recurring_event:
        abort(404)
    # Filter list of assigned_events down to events that are part of this recurring event
    eu_list = []
    for eu in current_user.assigned_events:
        if eu.event in recurring_event.events:
            eu_list.append(eu)
    if len(eu_list) == 0:
        abort(404)
    return render_template('public/recurring_event_info.html', recurring_event=recurring_event, eu_list=eu_list)


@public.route('/eu/<id>/rsvp/<r>')
@login_required
def rsvp_for_event(id, r):
    eu = None
    for my_eu in current_user.assigned_events:
        if my_eu.id == ObjectId(id):
            eu = my_eu
    if not eu:
        abort(404)
    if r in ['y', 'n', 'm']: 
        eu.rsvp = r
        eu.save()
    return redirect(request.referrer)

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

@public.route('/assignment/<id>/complete')
@login_required
def assignment_complete(id):
    # Make sure that the assignment is published and that the user is assigned to it
    au_list = list(filter(lambda au: au.assignment.id == ObjectId(id), current_user.assigned_assignments))
    if len(au_list) == 0:
        abort(404)
    au = au_list[0]
    if not au.completed:
        au.completed = True
        au.save()
    return redirect(url_for('public.assignment_info', id=au.assignment.id))

@public.route('/assignment/<id>')
@login_required
def assignment_info(id):
    # Make sure that the assignment is published and that the user is assigned to it
    au_list = list(filter(lambda au: au.assignment.id == ObjectId(id), current_user.assigned_assignments))
    if len(au_list) == 0:
        abort(404)
    au = au_list[0]
    assignment = au.assignment
    return render_template('public/assignment_info.html', au=au)

@public.route('/task/<id>')
@login_required
def task_redirect(id):
    # Make sure that the task is in the user assigned task list
    tu_list = list(filter(lambda tu: tu.id == ObjectId(id), current_user.assigned_tasks))
    if len(tu_list) == 0:
        abort(404)
    tu = tu_list[0]
    if not tu.seen:
        tu.seen = pendulum.now('UTC')
        tu.save()
    return redirect(tu.link)

@public.route('/tasks')
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

# Utility functions to simplify permission selection form
def init_choices_permission_form(form):
    all_roles = models.Role.objects
    all_users = models.User.objects
    form.permissions.visible_roles.choices = [(str(role.id), role.name) for role in all_roles]
    form.permissions.visible_users.choices = [(str(user.id), user.first_name + " " + user.last_name) for user in all_users]
    form.permissions.editor_roles.choices = [(str(role.id), role.name) for role in all_roles]
    form.permissions.editor_users.choices = [(str(user.id), user.first_name + " " + user.last_name) for user in all_users]

def save_permission_form(form, obj):
    obj.permissions.visible_roles = [ObjectId(r) for r in form.permissions.visible_roles.data]
    obj.permissions.visible_users = [ObjectId(u) for u in form.permissions.visible_users.data]
    obj.permissions.editor_roles = [ObjectId(r) for r in form.permissions.editor_roles.data]
    obj.permissions.editor_users = [ObjectId(u) for u in form.permissions.editor_users.data]

def set_selected_permission_form(form, obj):
    form.permissions.editor_roles.selected = [str(role.id) for role in obj.permissions.editor_roles]
    form.permissions.editor_users.selected = [str(user.id) for user in obj.permissions.editor_users]
    form.permissions.visible_roles.selected = [str(role.id) for role in obj.permissions.visible_roles]
    form.permissions.visible_users.selected = [str(user.id) for user in obj.permissions.visible_users]

# Update from a form with a task FormField
def save_task_form(task, task_form):
    task.notification_dates = []
    for dt_string in task_form.notification_dates.data.split(","):
        if dt_string:
            dt = pendulum.from_format(dt_string.strip(), "MM/DD/YYYY", tz=current_user.tz).in_tz('UTC')
            task.notification_dates.append(dt)
    task.notify_by_email = task_form.notify_by_email.data
    task.notify_by_phone = task_form.notify_by_phone.data
    task.notify_by_push = task_form.notify_by_push.data
    task.notify_by_app = task_form.notify_by_app.data

def task_send_notifications(task, users):
    task.notification_dates.append(pendulum.now('UTC'))
    for user in users:
        for time in task.notification_dates:
            notification = models.PushNotification()
            notification.user = user
            notification.text = task.text
            notification.date = time
            notification.link = url_for('public.task_redirect', id=task.id)
            notification.send_email = task.notify_by_email
            notification.send_text  = task.notify_by_phone
            notification.send_app   = task.notify_by_app
            notification.send_push  = task.notify_by_push
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
    calendars = models.Calendar.objects
    i = 0
    for c in calendars:
        if c.permissions.check_visible(current_user):
            c.color = calendar_colors[i]
            i += 1
    return dict(calendars=calendars)

@public.route('/calendar/list')
@login_required
def calendar_home():
    events = models.Event.objects
    events_for_fullcalendar = []
    all_recurring_events = models.RecurringEvent.objects
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
        if e.recurrence:
            e_new['url'] = "Not Yet!"
            #e_new['url']    = url_for('public.recurring_event_info', id=recurring_event.id)
        else:
            e_new['url']    = url_for('public.scheduled_event_view', cid=e.calendar.id, id=e.id)
        e_new['allDay'] = False

        e_new['backgroundColor'] = colors_lookup[e.calendar.id]
        e_new['borderColor'] = e_new['backgroundColor']
        events_for_fullcalendar.append(e_new)
    return render_template('public/calendar/home.html',
            events=events,
            events_for_fullcalendar=events_for_fullcalendar,
            sidebar_data=sidebar_data)

@public.route('/calendar/new')
@login_required
def calendar_new():
    calendar = models.Calendar()
    calendar.name = "New Calendar"
    calendar.description = "My New Calendar"
    calendar.owner = current_user.id

    everyone_role = models.Role.objects(name='everyone').first()
    calendar.permissions = models.PermissionSet()
    calendar.permissions.visible_roles = [everyone_role.id]
    calendar.save()
    return redirect(url_for('public.calendar_edit', id=calendar.id))

@public.route('/calendar/<id>/edit', methods=['GET', 'POST'])
@login_required
def calendar_edit(id):
    calendar = models.Calendar.objects(id=id).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user) and not current_user.id == calendar.owner.id:
        abort(404)
    form = forms.CalendarForm(data=calendar.to_mongo().to_dict())
    init_choices_permission_form(form)
    if form.validate_on_submit():
        calendar.name = form.name.data
        calendar.description = form.description.data
        save_permission_form(form, calendar)
        calendar.save()
        flash('Changes Saved', 'success')
    set_selected_permission_form(form, calendar)
    return render_template('public/calendar/calendar_edit.html',
            calendar=calendar,
            sidebar_data=get_calendar_sidebar_data(),
            form=form)

@public.route('/calendar/<id>/view')
@login_required
def calendar_view(id):
    calendar = models.Calendar.objects(id=id).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_visible(current_user) and not current_user.id == calendar.owner.id:
        abort(404)
    return render_template('public/calendar/calendar_view.html', 
            calendar=calendar,
            sidebar_data=get_calendar_sidebar_data())

@public.route('/calendar/<id>/delete')
@login_required
def calendar_delete(id):
    calendar = models.Calendar.objects(id=id)
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user) and not current_user.id == calendar.owner.id:
        abort(404)
    # Delete things!

@public.route('/calendar/<id>/newevent')
def scheduled_event_new(id):
    calendar = models.Calendar.objects(id=id).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user) and not current_user.id == calendar.owner.id:
        abort(404)
    everyone_role = models.Role.objects(name='everyone').first()

    event = models.Event()
    event.calendar = calendar
    event.name = "New Event"
    event.content = "My New Event"
    event.start = pendulum.now('UTC').add(days=1)
    event.end = event.start.add(hours=2)
    task = models.Task()
    task.save()
    event.rsvp_task = task
    event.save()
    return redirect(url_for('public.scheduled_event_edit', cid=calendar.id, id=event.id))

@public.route('/calendar/<cid>/event/<id>', methods=["GET","POST"])
def scheduled_event_edit(id, cid):
    calendar = models.Calendar.objects(id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user) and not current_user.id == calendar.owner.id:
        abort(404)
    event = models.Event.objects(id=id, recurrence=None).first()
    if not event:
        abort(404)
    if not event.is_draft:
        return redirect(url_for('admin.scheduled_event_view', id=event.id))
    form_data = event.to_mongo().to_dict()
    # Localize start and end to user's location
    form_data['start'] = form_data['start'].in_tz(current_user.tz)
    form_data['end'] = form_data['end'].in_tz(current_user.tz)
    form = forms.EventForm(request.form, data=form_data)
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
            event.start = start
            event.end = end
            event.content = form.content.data
            event.name = form.name.data
            event.enable_rsvp = form.enable_rsvp.data
            event.enable_attendance = form.enable_attendance.data

            # Update task
            save_task_form(event.rsvp_task, form.rsvp_task)
            event.rsvp_task.text = "RSVP for " + event.name
            event.rsvp_task.due = event.start
            event.rsvp_task.save()

            event.save()
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('public/calendar/scheduled_event_edit.html',
            event=event,
            form=form, 
            selected_dates=[dt.in_tz(current_user.tz).isoformat() for dt in event.rsvp_task.notification_dates],
            calendar=calendar,
            sidebar_data=get_calendar_sidebar_data())

@public.route('/calendar/<cid>/event/<id>/publish')
def scheduled_event_publish(cid, id):
    calendar = models.Calendar.objects(id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user) and not current_user.id == calendar.owner.id:
        abort(404)
    event = models.Event.objects(id=id, recurrence=None).first()
    if not event:
        abort(404)
    if not event.is_draft:
        return redirect(url_for('public.scheduled_event_view', id=event.id))
    # Find all users with role
    # "assigned_users" is a temporary array of user references that is used to create
    # the "users" array
    event.assigned_users = calendar.permissions.visible_users
    for role in calendar.permissions.visible_roles:
        users_with_role = models.User.objects(roles=role)
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
            tu = models.TaskUser()
            tu.task = event.rsvp_task
            tu.watch_object = eu
            tu.link = url_for('public.scheduled_event_view', cid=calendar.id, id=event.id)
            tu.watch_field = "rsvp"
            tu.save()
            user.assigned_tasks.append(tu)

    # Create notifications
    if event.enable_rsvp:
        task_send_notifications(event.rsvp_task, event.assigned_users)
    event.is_draft = False
    event.save()
    return redirect(url_for('public.scheduled_event_view', cid=calendar.id, id=event.id))

@public.route('/calendar/<cid>/event/<id>/view')
def scheduled_event_view(cid, id):
    calendar = models.Calendar.objects(id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_visible(current_user) and not current_user.id == calendar.owner.id:
        abort(404)
    event = models.Event.objects(id=id, recurrence=None).first()
    if not event:
        abort(404)
    if event.is_draft:
        return redirect(url_for('public.scheduled_event_edit', id=event.id))
    return render_template('public/calendar/scheduled_event_view.html',
            event=event,
            calendar=calendar,
            sidebar_data=get_calendar_sidebar_data())

@public.route('/calendar/<cid>/rsvp_edit/<id>', methods=['GET', 'POST'])
def event_user_edit(cid, id):
    calendar = models.Calendar.objects(id=cid).first()
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user) and not current_user.id == calendar.owner.id:
        abort(404)
    eu = models.EventUser.objects(id=id).first()
    event = models.Event.objects(calendar=calendar, users=eu).first()
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
    return render_template('public/calendar/event_user_edit.html',
            eu=eu,
            form=form,
            event=event,
            calendar=calendar,
            sidebar_data=get_calendar_sidebar_data())

@public.route('/calendar/<cid>/event/<id>/delete')
def scheduled_event_delete(id):
    calendar = models.Calendar.objects(id=cid)
    if not calendar:
        abort(404)
    if not calendar.permissions.check_editor(current_user) and not current_user.id == calendar.owner.id:
        abort(404)
    event = models.Event.objects(id=id, is_recurring=False, calendar=calendar).first()
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

def get_wiki_sidebar_data():
    articles = models.Article.objects
    topics = models.Topic.objects
    return dict(articles=articles, topics=topics)

@public.route('/wiki')
def wiki_home():
    articles = models.Article.objects
    topics = models.Topic.objects
    return render_template('public/wiki/home.html',
            articles=articles,
            topics=topics,
            sidebar_data=get_wiki_sidebar_data())

@public.route('/wiki/topic/<id>/view')
def topic_view(id):
    topic = models.Topic.objects(id=id).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_visible(current_user) and not current_user.id == topic.owner.id:
        abort(404)
    return render_template('public/wiki/topic_view.html',
            topic=topic,
            sidebar_data=get_wiki_sidebar_data())

@public.route('/wiki/newtopic')
def topic_new():
    topic = models.Topic()
    topic.name = "New Topic"
    topic.owner = current_user.id
    topic.description = "My New Topic"

    everyone_role = models.Role.objects(name='everyone').first()
    topic.permissions = models.PermissionSet()
    topic.permissions.visible_roles = [everyone_role.id]

    topic.save()
    return redirect(url_for('public.topic_edit', id=topic.id))

@public.route('/wiki/topic/<id>/edit', methods=['GET','POST'])
def topic_edit(id):
    topic = models.Topic.objects(id=id).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_editor(current_user) and not current_user.id == topic.owner.id:
        abort(404)
    form = forms.TopicForm(data=topic.to_mongo().to_dict())
    init_choices_permission_form(form)
    if form.validate_on_submit():
        topic.name = form.name.data
        topic.description = form.description.data
        save_permission_form(form, topic)
        topic.save()
        flash('Changes Saved', 'success')
    set_selected_permission_form(form, topic)
    return render_template('public/wiki/topic_edit.html',
            topic=topic,
            form=form,
            sidebar_data=get_wiki_sidebar_data())

@public.route('/wiki/topic/<id>/newarticle')
def new_article(id):
    topic = models.Topic.objects(id=id).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_editor(current_user) and not current_user.id == topic.owner.id:
        abort(404)
    article = models.Article()
    article.name = "New Article"
    article.content = "My New Article"
    article.owner = current_user.id
    article.topic = topic
    article.save()
    return redirect(url_for('public.article_edit', id=article.id, tid=topic.id))

@public.route('/wiki/topic/<tid>/article/<id>/edit', methods=['GET','POST'])
def article_edit(tid, id):
    topic = models.Topic.objects(id=tid).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_editor(current_user) and not current_user.id == topic.owner.id:
        abort(404)
    article = models.Article.objects(id=id).first()
    if not article:
        abort(404)
    form = forms.ArticleForm(data=article.to_mongo().to_dict())
    if form.validate_on_submit():
        article.name = form.name.data
        article.content = form.content.data
        article.save()
        flash('Changes Saved', 'success')
    return render_template('public/wiki/article_edit.html',
            article=article,
            form=form,
            sidebar_data=get_wiki_sidebar_data())

@public.route('/wiki/topic/<tid>/article/<id>/view')
def article_view(tid, id):
    topic = models.Topic.objects(id=tid).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_visible(current_user) and not current_user.id == topic.owner.id:
        abort(404)
    article = models.Article.objects(id=id).first()
    if not article:
        abort(404)
    return render_template('public/wiki/article_view.html',
            article=article,
            sidebar_data=get_wiki_sidebar_data())

@public.route('/wiki/topic/<tid>/article/<id>/delete')
def article_delete(id):
    topic = models.Topic.objects(id=tid).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_editor(current_user) and not current_user.id == topic.owner.id:
        abort(404)
    article = models.Article.objects(id=id).first()
    if not article:
        abort(404)
    article.delete()
    flash('Article Deleted', 'success')
    return redirect(url_for('public.topic_view'))

