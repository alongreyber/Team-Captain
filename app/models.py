import datetime
from app import db, login_manager

from flask_login import UserMixin

from bson import ObjectId

class Role(db.Document):
    name = db.StringField()

# Notification that has been queued to send to user
class PushNotification(db.Document):
    user = db.ReferenceField('User')
    text = db.StringField()
    link = db.StringField()
    date = db.DateTimeField()
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
    recieve_date = db.DateTimeField()

class User(db.Document, UserMixin):
    email = db.EmailField(max_length=100)
    personal_email = db.EmailField(max_length=100)
    phone_number = db.StringField(max_length=20)
    bio = db.StringField()
    barcode = db.StringField(max_length=100)
    first_name = db.StringField(max_length=50)
    last_name = db.StringField(max_length=50)
    roles = db.ListField(db.ReferenceField(Role))
    assigned_tasks = db.ListField(db.ReferenceField('TaskUser'))
    notifications = db.EmbeddedDocumentListField(AppNotification)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(id=user_id).first()

class Event(db.Document):
    name = db.StringField()
    # Not filled in if this is a recurring event
    content = db.StringField()
    start = db.DateTimeField()
    end = db.DateTimeField()
    is_draft = db.BooleanField(default=True)
    # Duplicate data, lets us keep track of whether this is a recurring event
    is_recurring = db.BooleanField(default=False)

class RecurringEvent(db.Document):
    name = db.StringField()
    content = db.StringField()
    start = db.DateTimeField()
    end = db.DateTimeField()
    days_of_week = db.ListField(db.IntField())
    is_draft = db.BooleanField(default=True)
    events = db.ListField(db.ReferenceField(Event))

class Task(db.Document):
    subject = db.StringField()
    content = db.StringField()
    due = db.DateTimeField()
    assigned_roles = db.ListField(db.ReferenceField(Role))
    # Only used when task is a draft
    assigned_users = db.ListField(db.ReferenceField(User))
    notify_by_email = db.BooleanField(default=False)
    notify_by_phone = db.BooleanField(default=False)
    additional_notifications = db.IntField()
    is_draft = db.BooleanField(default=True)

class TaskUser(db.Document):
    task = db.ReferenceField(Task)
    completed = db.DateTimeField()
    seen = db.DateTimeField()
