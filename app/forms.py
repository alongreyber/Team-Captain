from app import models

from flask_wtf import FlaskForm
from wtforms.fields import html5
from wtforms.fields import *
from wtforms.validators import *

from flask_mongoengine.wtf import model_form

class UserForm(FlaskForm):
    first_name = StringField()
    last_name = StringField()
    email = html5.EmailField()
    barcode = StringField()
    roles = SelectMultipleField('Roles', coerce=str)

EventForm = model_form(models.Event, field_args = {
    'start' : {'label' : "Start Date/Time"},
    'end' : {'label' : "End Date/Time"},
    'name' : {'label' : "Name"}
})

class TaskForm(FlaskForm):
    subject = StringField()
    content = TextAreaField()
    due = html5.DateTimeLocalField(format='%Y-%m-%dT%H:%M', validators=[required()])
    assigned_roles = SelectMultipleField('Roles')
    assigned_users = SelectMultipleField('Users')

class RoleForm(FlaskForm):
    role = StringField(label="Add")

class RecurringEventForm(FlaskForm):
    name = StringField()
    start_date = html5.DateField('Start Date', validators=[required()])
    end_date = html5.DateField('End Date', validators=[required()])
    start_time = html5.TimeField('Start Time', validators=[required()])
    end_time = html5.TimeField('End Time', validators=[required()])
    days_of_week = SelectMultipleField('Days of Week', coerce=int)
