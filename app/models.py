import datetime
from app import db, login_manager

from flask_login import UserMixin

class BaseModel(db.Document):
    meta = {'allow_inheritance': True}

class User(BaseModel, UserMixin):
    email = db.EmailField(max_length=100)
    barcode = db.StringField(max_length=100)
    first_name = db.StringField(max_length=50)
    last_name = db.StringField(max_length=50)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(id=user_id).first()

class TimeLog(BaseModel):
    user = db.ReferenceField(User)
    time_in = db.DateTimeField()
    time_out = db.DateTimeField()

class RecurringMeeting(BaseModel):
    name = db.StringField()
    start_date = db.DateTimeField()
    end_date = db.DateTimeField()
    start_time = db.DateTimeField()
    end_time = db.DateTimeField()
    days_of_week = db.ListField(db.StringField())

class Meeting(BaseModel):
    name = db.StringField()
    start_time = db.DateTimeField()
    end_time = db.DateTimeField()
    date = db.DateTimeField()
    recurrence = db.ReferenceField(RecurringMeeting)

