import datetime
from app import db, login_manager

from flask_login import UserMixin

class User(db.Document, UserMixin):
    email = db.EmailField(max_length=100)
    barcode = db.StringField(max_length=100)
    first_name = db.StringField(max_length=50)
    last_name = db.StringField(max_length=50)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(id=user_id).first()

class TimeLog(db.Document):
    user = db.ReferenceField(User)
    time_in = db.DateTimeField()
    time_out = db.DateTimeField()

class RecurringMeeting(db.Document):
    name = db.StringField()
    start_date = db.DateTimeField()
    end_date = db.DateTimeField()
    start_time = db.DateTimeField()
    end_time = db.DateTimeField()
    days_of_week = db.ListField(db.IntField())

class Meeting(db.Document):
    name = db.StringField()
    start_time = db.DateTimeField()
    end_time = db.DateTimeField()
    @property
    def start(self):
        return datetime.datetime.combine( self.date.date(), self.start_time.time() )
    date = db.DateTimeField()
    recurrence = db.ReferenceField(RecurringMeeting)
    rsvp_yes = db.ListField(db.ReferenceField(User))
    rsvp_no = db.ListField(db.ReferenceField(User))
