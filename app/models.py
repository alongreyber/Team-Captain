import datetime
from app import db, login_manager, tasks

from flask import url_for

from mongoengine.base import BaseField
from mongoengine import signals

from flask_login import UserMixin

from bson import ObjectId
import pendulum

# Custom field for storing datetime objects with the pendulum library
class PendulumField(BaseField):
    # Whether times have to be UTC before saving to DB
    def __init__(self, enforce_utc=True, **kwargs):
        self.enforce_utc = enforce_utc
        super(PendulumField, self).__init__(**kwargs)
    def to_python(self, value):
        if value is None:
            return value
        return pendulum.instance(value, tz='UTC')
    def to_mongo(self, value):
        if value is None:
            return value
        if not isinstance(value, pendulum.DateTime):
            self.error('Not an instance of a pendulum DateTime')
        if self.enforce_utc and not value.is_utc():
            self.error('Date not in UTC!')
        # Automatically converted to string for storage
        return value

class Role(db.Document):
    name = db.StringField()

# Notification that has been queued to send to user
class PushNotification(db.Document):
    user = db.ReferenceField('User')
    text = db.StringField()
    link = db.StringField()
    date = PendulumField()
    sent = db.BooleanField(default=False)
    send_email = db.BooleanField()
    send_text  = db.BooleanField()
    send_push  = db.BooleanField()
    send_app   = db.BooleanField()

# Notification that appears in app
class AppNotification(db.EmbeddedDocument):
    id = db.ObjectIdField(required=True, default=ObjectId,
                    unique=True, primary_key=True)
    text = db.StringField()
    link = db.StringField()
    recieve_date = PendulumField()

class User(db.Document, UserMixin):
    email = db.EmailField(max_length=100)
    personal_email = db.EmailField(max_length=100)
    phone_number = db.StringField(max_length=20)
    # Timemzone
    tz = db.StringField()
    bio = db.StringField()
    barcode = db.StringField(max_length=100, unique=True)
    first_name = db.StringField(max_length=50)
    last_name = db.StringField(max_length=50)
    @property
    def name(self):
        return self.first_name + " " + self.last_name
    roles = db.ListField(db.ReferenceField(Role))
    assigned_tasks = db.ListField(db.ReferenceField('TaskUser'))
    assigned_assignments = db.ListField(db.ReferenceField('AssignmentUser'))
    notifications = db.EmbeddedDocumentListField(AppNotification)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(id=user_id).first()

class PermissionSet(db.EmbeddedDocument):
    editor_users = db.ListField(db.ReferenceField(User))
    editor_roles = db.ListField(db.ReferenceField(Role))
    visible_users = db.ListField(db.ReferenceField(User))
    visible_roles = db.ListField(db.ReferenceField(Role))
    def check_editor(self, user):
        for u in self.editor_users:
            if u.id == user.id:
                return True
        for user_role in user.roles:
            if user_role in self.editor_roles:
                return True
        return False
    def check_visible(self, user):
        for u in self.visible_users:
            if u.id == user.id:
                return True
        for user_role in user.roles:
            if user_role in self.visible_roles:
                return True
        return False

class Task(db.Document):
    notification_dates = db.ListField(PendulumField())
    notify_by_email = db.BooleanField(default=False)
    notify_by_phone = db.BooleanField(default=False)
    notify_by_push  = db.BooleanField(default=False)
    notify_by_app   = db.BooleanField(default=False)
    text = db.StringField()
    due = PendulumField()

# Visible to users
class TaskUser(db.Document):
    task = db.ReferenceField(Task)
    # Link to follow when task is clicked on
    link = db.StringField()

    # Whether the user has seen the task
    seen = PendulumField()
    # Whether the user has completed task. Updated automatically
    completed = PendulumField()
    # Which object to watch for changes
    watch_object = db.GenericLazyReferenceField()
    # Which field on that object to check
    watch_field = db.StringField()

class Calendar(db.Document):
    name = db.StringField()
    description = db.StringField()
    owner = db.ReferenceField(User)
    permissions = db.EmbeddedDocumentField(PermissionSet)

class Event(db.Document):
    name = db.StringField()
    calendar = db.ReferenceField(Calendar)
    content = db.StringField()
    start = PendulumField()
    end = PendulumField()
    is_draft = db.BooleanField(default=True)
    recurrence = db.ReferenceField('RecurringEvent')
    enable_rsvp = db.BooleanField(default=False)
    # This is used to store RSVP and attendance information
    users = db.ListField(db.ReferenceField('EventUser'))
    rsvp_task = db.ReferenceField(Task)
    enable_attendance = db.BooleanField(default=False)

class RecurringEvent(db.Document):
    name = db.StringField()
    calendar = db.ReferenceField(Calendar)
    content = db.StringField()
    # NOTE
    # These are not in UTC. They are naive objects that are turned
    # into real times when the event is published
    start_date = db.DateTimeField()
    start_time = db.DateTimeField()
    end_date = db.DateTimeField()
    end_time = db.DateTimeField()
    days_of_week = db.ListField(db.IntField())
    is_draft = db.BooleanField(default=True)
    # Only used when task is a draft
    enable_rsvp = db.BooleanField(default=False)
    rsvp_task = db.ReferenceField(Task)
    enable_attendance = db.BooleanField(default=False)

class Assignment(db.Document):
    subject = db.StringField()
    permissions = db.EmbeddedDocumentField(PermissionSet)
    content = db.StringField()
    due = PendulumField()
    is_draft = db.BooleanField(default=True)
    task = db.ReferenceField(Task)

class AssignmentUser(db.Document):
    assignment = db.ReferenceField(Assignment)
    completed = db.BooleanField(default=False)

class EventUser(db.Document):
    user = db.ReferenceField('User')
    rsvp = db.StringField()
    sign_in = PendulumField()
    sign_out = PendulumField()

class Topic(db.Document):
    owner = db.ReferenceField(User)
    permissions = db.EmbeddedDocumentField(PermissionSet)
    name = db.StringField()
    description = db.StringField()

class Article(db.Document):
    name = db.StringField()
    content = db.StringField()
    topic = db.ReferenceField(Topic)
    owner = db.ReferenceField(User)

def check_for_automatic_task(sender, document, created):
    tasks.check_automatic_task_completion((document.id))

signals.post_save.connect(check_for_automatic_task)
