from app import models, forms, oauth
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint
from flask_login import current_user, login_required

import pendulum
from bson import ObjectId

from mongoengine.errors import NotUniqueError

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

@public.route('/events')
@login_required
def event_list():
    events = current_user.assigned_events
    events_for_fullcalendar = []
    all_recurring_events = models.RecurringEvent.objects
    for e in events:
        e_new = {}
        e_new['title']  = e.event.name
        e_new['start']  = e.event.start.isoformat()
        e_new['end']    = e.event.end.isoformat()
        if e.event.is_recurring:
            for recurring_event in all_recurring_events:
                if e.event in recurring_event.events:
                    e_new['url']    = url_for('public.recurring_event_info', id=recurring_event.id)
        else:
            e_new['url']    = url_for('public.scheduled_event_info', id=e.event.id)
        e_new['allDay'] = False

        e_new['backgroundColor'] = "rgb(55, 136, 216)" if e.event.is_recurring else "rgb(216, 55, 76)"
        e_new['borderColor'] = e_new['backgroundColor']
        events_for_fullcalendar.append(e_new)
    return render_template('public/event_list.html', events=events, events_for_fullcalendar=events_for_fullcalendar)

@public.route('/event/<id>')
@login_required
def scheduled_event_info(id):
    # Make sure that the event is published and that the user is assigned to it
    eu_list = list(filter(lambda eu: eu.event.id == ObjectId(id), current_user.assigned_events))
    if len(eu_list) == 0:
        abort(404)
    eu = eu_list[0]
    return render_template('public/event_info.html', eu=eu)

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


def get_sidebar_data():
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
            sidebar_data=get_sidebar_data())

@public.route('/wiki/topic/<id>/view')
def topic_view(id):
    topic = models.Topic.objects(id=id).first()
    if not topic:
        abort(404)
    if not topic.permissions.check_visible(current_user) and not current_user.id == topic.owner.id:
        abort(404)
    return render_template('public/wiki/topic_view.html',
            topic=topic,
            sidebar_data=get_sidebar_data())

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
            sidebar_data=get_sidebar_data())

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
            sidebar_data=get_sidebar_data())

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
            sidebar_data=get_sidebar_data())

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

