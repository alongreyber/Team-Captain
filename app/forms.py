from app import models

from flask_wtf import FlaskForm
from wtforms.fields import html5
from wtforms.fields import *

from flask_mongoengine.wtf import model_form

UserForm = model_form(models.User, field_args = {
    'first_name' : {'label' : "First Name"},
    'last_name' : {'label' : "Last Name"},
    'email' : {'label' : "Email"},
    'barcode' : {'label' : "Barcode"},
})

TimeLogForm = model_form(models.TimeLog, field_args = {
    'user' : {'label' : "User", 'label_attr' : 'email'},
    'time_in' : {'label' : "Time In"},
    'time_out' : {'label' : "Time Out"},
})

#MeetingForm = model_form(models.Meeting, field_args = {
#    'start_time' : {'label' : "Start Time"},
#    'end_time' : {'label' : "End Time"},
#    'date' : {'label' : "Date"},
#})

class MeetingForm(FlaskForm):
    name = StringField()
    start_time = html5.TimeField('Start Time')
    end_time = html5.TimeField('End Time')
    date = html5.DateField('Date')
