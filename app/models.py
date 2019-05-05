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
    barcode = db.StringField(max_length=100)
    first_name = db.StringField(max_length=50)
    last_name = db.StringField(max_length=50)
    roles = db.ListField(db.ReferenceField(Role))
    assigned_tasks = db.ListField(db.ReferenceField('TaskUser'))
    assigned_events = db.ListField(db.ReferenceField('EventUser'))
    assigned_assignments = db.ListField(db.ReferenceField('AssignmentUser'))
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
    notification_dates = db.ListField(PendulumField())
    notify_by_email = db.BooleanField(default=False)
    notify_by_phone = db.BooleanField(default=False)

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
    notification_dates = db.ListField(PendulumField())
    notify_by_email = db.BooleanField(default=False)
    notify_by_phone = db.BooleanField(default=False)
    notify_by_push  = db.BooleanField(default=False)
    notify_by_app   = db.BooleanField(default=False)
    text = db.StringField()
    due = PendulumField()

    # Update from a form with a task FormField
    def update_from_form(self, form, tz):
        self.notification_dates = []
        for dt_string in form.task.notification_dates.data.split(","):
            dt = pendulum.from_format(dt_string.strip(), "MM/DD/YYYY", tz=tz).in_tz('UTC')
            self.notification_dates.append(dt)
        self.notify_by_email = form.task.notify_by_email.data
        self.notify_by_phone = form.task.notify_by_phone.data
        self.notify_by_push = form.task.notify_by_push.data
        self.notify_by_app = form.task.notify_by_app.data
    # Send notifications to user
    def send_notifications(self, users):
        self.notification_dates.append(pendulum.now('UTC'))
        for user in users:
            for time in self.notification_dates:
                notification = PushNotification()
                notification.user = user
                notification.text = self.text
                notification.date = time
                notification.link = url_for('public.task_redirect', id=self.id)
                notification.send_email = self.notify_by_email
                notification.send_text  = self.notify_by_phone
                notification.send_app   = self.notify_by_app
                notification.send_push  = self.notify_by_push
                notification.save()
                # Schedule assignment for sending unless it's right now
                if notification.date <= pendulum.now('UTC'):
                    tasks.send_notification((notification.id))
                else:
                    # Notify user at their most recent time zone
                    eta = notification.date.in_tz(notification.user.tz)
                    tasks.send_notification.schedule((notification.id), eta=eta)

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

class Assignment(db.Document):
    subject = db.StringField()
    content = db.StringField()
    due = PendulumField()
    is_draft = db.BooleanField(default=True)
    assigned_roles = db.ListField(db.ReferenceField(Role))
    assigned_users  = db.ListField(db.ReferenceField(User))
    task = db.ReferenceField(Task)

class AssignmentUser(db.Document):
    assignment = db.ReferenceField(Assignment)
    completed = db.BooleanField(default=False)

class EventUser(db.Document):
    event = db.ReferenceField(Event)
    # Has to be string so we can store y or n or m or not yet
    rsvp = db.StringField()
    sign_in = PendulumField()
    sign_out = PendulumField()

def check_for_automatic_task(sender, document, created):
    tasks.check_automatic_task_completion((document.id))

signals.post_save.connect(check_for_automatic_task)
