import datetime
from app import db, login_manager

from flask_login import UserMixin

class Notification(db.Document):
    text = db.StringField()
    link = db.StringField()
    seen_date = db.DateTimeField()

class Role(db.Document):
    name = db.StringField()

class User(db.Document, UserMixin):
    email = db.EmailField(max_length=100)
    bio = db.StringField()
    barcode = db.StringField(max_length=100)
    first_name = db.StringField(max_length=50)
    last_name = db.StringField(max_length=50)
    roles = db.ListField(db.ReferenceField(Role))
    notifications = db.ListField(db.ReferenceField(Notification))

@login_manager.user_loader
def load_user(user_id):
    return User.objects(id=user_id).first()

class RecurringEvent(db.Document):
    name = db.StringField()
    start_date = db.DateTimeField()
    end_date = db.DateTimeField()
    start_time = db.DateTimeField()
    end_time = db.DateTimeField()
    days_of_week = db.ListField(db.IntField())

class Event(db.Document):
    name = db.StringField()
    start = db.DateTimeField()
    end = db.DateTimeField()
    recurrence = db.ReferenceField(RecurringEvent)

class TaskUser(db.EmbeddedDocument):
    user = db.ReferenceField(User)
    completed = db.BooleanField(default=False)
    seen = db.BooleanField(default=False)

class Task(db.Document):
    subject = db.StringField()
    content = db.StringField()
    due = db.DateTimeField()
    assigned_users = db.ListField(db.EmbeddedDocumentField(TaskUser))
    assigned_roles = db.ListField(db.ReferenceField(Role))
    notify_by_email = db.BooleanField(default=False)
    notify_by_phone = db.BooleanField(default=False)
    additional_notifications = db.IntField()
    is_draft = db.BooleanField(default=False)

