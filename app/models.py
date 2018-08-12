import datetime
from app import db

class BaseModel(db.Document):
    meta = {'allow_inheritance': True}

class User(BaseModel):
    email = db.EmailField(max_length=100)
    barcode = db.StringField(max_length=100)
    first_name = db.StringField(max_length=50)
    last_name = db.StringField(max_length=50)

class TimeLog(BaseModel):
    user = db.ReferenceField(User)
    time_in = db.DateTimeField()
    time_out = db.DateTimeField()

# Sample data
if not User.objects(email='alongreyber@gmail.com'):
    u1 = User(email='alongreyber@gmail.com', first_name='Alon', last_name='Greyber').save()
    User(email='amgreybe@ncsu.edu', first_name='Ricky', last_name='Bobby').save()
    TimeLog(user=u1, time_in=datetime.datetime.now(),
                     time_out=datetime.datetime.now() + datetime.timedelta(hours=5)).save()