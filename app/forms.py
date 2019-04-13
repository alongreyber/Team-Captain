from app import models

from flask_wtf import FlaskForm
from wtforms.fields import html5
from wtforms.fields import *
from wtforms.validators import *

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

MeetingForm = model_form(models.Meeting, field_args = {
    'start' : {'label' : "Start Date/Time"},
    'end' : {'label' : "End Date/Time"},
    'name' : {'label' : "Name"}
})

class RecurringMeetingForm(FlaskForm):
    name = StringField()
    start_date = html5.DateField('Start Date', validators=[required()])
    end_date = html5.DateField('End Date', validators=[required()])
    start_time = html5.TimeField('Start Time', validators=[required()])
    end_time = html5.TimeField('End Time', validators=[required()])
    days_of_week = SelectMultipleField('Days of Week', coerce=int)
