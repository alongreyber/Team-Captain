import datetime
from app import db, login_manager

from mongoengine.base import BaseField

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
    barcode = db.StringField(max_length=100)
    first_name = db.StringField(max_length=50)
    last_name = db.StringField(max_length=50)
    roles = db.ListField(db.ReferenceField(Role))
    assigned_tasks = db.ListField(db.ReferenceField('TaskUser'))
    assigned_events = db.ListField(db.ReferenceField('EventUser'))
    notifications = db.EmbeddedDocumentListField(AppNotification)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(id=user_id).first()

class Event(db.Document):
    name = db.StringField()
    # Not filled in if this is a recurring event
    content = db.StringField()
    start = PendulumField()
    end = PendulumField()
    is_draft = db.BooleanField(default=True)
    # Duplicate data, lets us keep track of whether this is a recurring event
    is_recurring = db.BooleanField(default=False)
    assigned_roles = db.ListField(db.ReferenceField(Role))
    assigned_users = db.ListField(db.ReferenceField(User))
    enable_rsvp = db.BooleanField(default=False)
    enable_attendance = db.BooleanField(default=False)

class RecurringEvent(db.Document):
    name = db.StringField()
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
    events = db.ListField(db.ReferenceField(Event))
    # Only used when task is a draft
    assigned_roles = db.ListField(db.ReferenceField(Role))
    assigned_users = db.ListField(db.ReferenceField(User))

class Task(db.Document):
    subject = db.StringField()
    content = db.StringField()
    due = PendulumField()
    assigned_roles = db.ListField(db.ReferenceField(Role))
    # Only used when task is a draft
    assigned_users = db.ListField(db.ReferenceField(User))
    notify_by_email = db.BooleanField(default=False)
    notify_by_phone = db.BooleanField(default=False)
    additional_notifications = db.IntField()
    is_draft = db.BooleanField(default=True)

class TaskUser(db.Document):
    task = db.ReferenceField(Task)
    completed = PendulumField()
    seen = PendulumField()

class EventUser(db.Document):
    event = db.ReferenceField(Event)
    rsvp = db.BooleanField()
