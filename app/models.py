import datetime, re
from app import db, login_manager, tasks, storage

from flask import url_for

from mongoengine.base import BaseField
from mongoengine import signals

from flask_login import UserMixin

from bson import ObjectId
import pendulum

# Custom field for storing datetime objects with the pendulum library
class PendulumField(BaseField):
    # Whether times have to be UTC before saving to DB
    def __init__(self, **kwargs):
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
        return value

# Object that gets stored in Google Cloud Storage
class CloudStorageObject(db.Document):
    meta = { 'allow_inheritance' : True }
    extension = db.StringField()

    @classmethod
    def post_save(cls, sender, document, **kwargs):
        storage.upload_file_obj('team_captain', document.file, str(document.id) + "." + document.extension)

    @classmethod
    def post_delete(cls, sender, document, **kwargs):
        storage.delete_obj(str(document.id) + "." + document.extension)

    @property
    def public_url(self):
        return f"https://storage.googleapis.com/team_captain/{self.id}.{self.extension}"

class Image(CloudStorageObject):
    width = db.IntField()
    height = db.IntField()

# This should really be on CloudStorageObject but signals aren't triggered for superclasses
signals.post_save.connect(Image.post_save, sender=Image)
signals.post_delete.connect(Image.post_save, sender=Image)

class Team(db.Document):
    name = db.StringField()
    number = db.IntField(unique=True)
    owner = db.LazyReferenceField('User')
    description = db.StringField()
    cover_photo = db.ReferenceField(Image)
    profile_photo = db.ReferenceField(Image)
    website = db.StringField()
    social_facebook  = db.StringField()
    social_instagram = db.StringField()
    social_github    = db.StringField()
    social_twitter   = db.StringField()
    social_youtube   = db.StringField()

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
# Need to create an ID field because this is an embedded document
class AppNotification(db.EmbeddedDocument):
    id = db.ObjectIdField(required=True, default=ObjectId,
                    unique=True, primary_key=True)
    text = db.StringField()
    link = db.StringField()
    recieve_date = PendulumField()

class User(db.Document, UserMixin):
    # Used during sign up process
    team_number = db.IntField()
    # Used after sign up
    team = db.ReferenceField(Team)
    admin = db.BooleanField(default=False)

    email = db.EmailField(max_length=100)
    personal_email = db.EmailField(max_length=100)
    phone_number = db.StringField(max_length=20)
    # Timemzone
    tz = db.StringField()
    bio = db.StringField()
    barcode = db.StringField(max_length=100)
    first_name = db.StringField(max_length=50)
    last_name = db.StringField(max_length=50)
    @property
    def name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        if self.first_name:
            return f"{self.first_name}"
        else:
            return ""
    assigned_tasks = db.ListField(db.GenericReferenceField())
    notifications = db.EmbeddedDocumentListField(AppNotification)
    def is_admin(self):
        for r in self.roles:
            if r.name == 'admin':
                return True
        return False

@login_manager.user_loader
def load_user(user_id):
    return User.objects(id=user_id).first()

class PermissionSet(db.EmbeddedDocument):
    editor_users = db.ListField(db.ReferenceField(User))
    visible_users = db.ListField(db.ReferenceField(User))
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

class NotificationSettings(db.EmbeddedDocument):
    notification_dates = db.ListField(PendulumField())
    notify_by_email = db.BooleanField(default=False)
    notify_by_phone = db.BooleanField(default=False)
    notify_by_push  = db.BooleanField(default=False)
    notify_by_app   = db.BooleanField(default=False)
    text = db.StringField()

class TeamUpdate(db.Document):
    owner = db.ReferenceField(User)
    post_time = PendulumField()
    content = db.StringField()
    images = db.ListField(db.ReferenceField(Image))
    video = db.StringField()
    is_draft = db.BooleanField(default=False)
    users_starred = db.ListField(db.LazyReferenceField(User))

# Calendar models

class Calendar(db.Document):
    name = db.StringField()
    description = db.StringField()
    permissions = db.EmbeddedDocumentField(PermissionSet)

class Event(db.Document):
    name = db.StringField()
    description = db.StringField()
    photo = db.ReferenceField(Image)
    date = PendulumField()
    is_draft = db.BooleanField(default=True)
    enable_rsvp = db.BooleanField(default=False)
    # This is used to store RSVP and attendance information
    users = db.ListField(db.ReferenceField('EventUser'))
    rsvp_notifications = db.EmbeddedDocumentField(NotificationSettings)
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
    rsvp_notifications = db.EmbeddedDocumentField(NotificationSettings)
    enable_attendance = db.BooleanField(default=False)

class EventUser(db.Document):
    user = db.ReferenceField('User')
    rsvp = db.StringField()
    sign_in = PendulumField()
    sign_out = PendulumField()
    seen = PendulumField()
    completed = PendulumField()

# Assignment models

class Assignment(db.Document):
    permissions = db.EmbeddedDocumentField(PermissionSet)
    users = db.ListField(db.ReferenceField('AssignmentUser'))
    subject = db.StringField()
    content = db.StringField()
    due = PendulumField()
    is_draft = db.BooleanField(default=True)
    notifications = db.EmbeddedDocumentField(NotificationSettings)

class AssignmentUser(db.Document):
    user = db.ReferenceField('User')
    seen = PendulumField()
    completed = PendulumField()

# Wiki models

class Topic(db.Document):
    permissions = db.EmbeddedDocumentField(PermissionSet)
    name = db.StringField()
    description = db.StringField()

class Article(db.Document):
    name = db.StringField()
    content = db.StringField()
    topic = db.ReferenceField(Topic)
