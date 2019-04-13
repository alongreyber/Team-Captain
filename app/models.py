import datetime
from app import db, login_manager

from flask_login import UserMixin

class User(db.Document, UserMixin):
    email = db.EmailField(max_length=100)
    bio = db.StringField()
    barcode = db.StringField(max_length=100)
    first_name = db.StringField(max_length=50)
    last_name = db.StringField(max_length=50)
    roles = db.ListField(db.StringField(max_length=50))

@login_manager.user_loader
def load_user(user_id):
    return User.objects(id=user_id).first()

'''
class TimeLog(db.Document):
    user = db.ReferenceField(User)
    time_in = db.DateTimeField()
    time_out = db.DateTimeField()
'''

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
    recurrence = db.ReferenceField(RecurringMeeting)
