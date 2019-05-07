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

class PublicUserForm(FlaskForm):
    first_name = StringField()
    last_name = StringField()
    personal_email = html5.EmailField()
    phone_number = html5.TelField()
    bio = TextAreaField()

class TaskForm(FlaskForm):
    notify_by_email = BooleanField('Notify by Email?')
    notify_by_phone = BooleanField('Notify by Phone?')
    notify_by_push = BooleanField('Notify by Push?')
    notify_by_app = BooleanField('Notify in App?')
    notification_dates = StringField()

class EventForm(FlaskForm):
    start = html5.DateTimeLocalField(format='%Y-%m-%dT%H:%M')
    end = html5.DateTimeLocalField(format='%Y-%m-%dT%H:%M')
    content = TextAreaField('Description (Markdown)')
    name = StringField(validators=[required()])
    assigned_roles = SelectMultipleField('Roles')
    assigned_users = SelectMultipleField('Users')
    enable_rsvp = BooleanField('Enable RSVP')
    rsvp_task = FormField(TaskForm)
    enable_attendance = BooleanField('Enable Attendance Tracking')

class EventUserForm(FlaskForm):
    sign_in = html5.TimeField()
    sign_out = html5.TimeField()

class AssignmentForm(FlaskForm):
    subject = StringField(validators=[required()])
    content = TextAreaField()
    assigned_roles = SelectMultipleField('Roles')
    assigned_users = SelectMultipleField('Users')
    due = html5.DateTimeLocalField(format='%Y-%m-%dT%H:%M', validators=[required()])
    task = FormField(TaskForm)

class FilterForm(FlaskForm):
    filter_by = SelectField('Filter By', coerce=int)
    filter_user = SelectField('User')
    filter_role = SelectField('Role')

class RoleForm(FlaskForm):
    role = StringField(label="Add")

class RecurringEventForm(FlaskForm):
    name = StringField(validators=[required()])
    content = TextAreaField(label="Description (Markdown)")
    start_date = html5.DateField('Start Date', validators=[required()])
    end_date = html5.DateField('End Date', validators=[required()])
    start_time = html5.TimeField('Start Time', validators=[required()])
    end_time = html5.TimeField('End Time', validators=[required()])
    days_of_week = SelectMultipleField('Days of Week', coerce=int)
    assigned_roles = SelectMultipleField('Roles')
    assigned_users = SelectMultipleField('Users')
    enable_rsvp = BooleanField('Enable RSVP')
    rsvp_task = FormField(TaskForm)
    enable_attendance = BooleanField('Enable Attendance Tracking')

class ClockInForm(FlaskForm):
    barcode = StringField(validators=[required()])
