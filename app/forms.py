from app import models

from flask_wtf import FlaskForm
from wtforms.fields import html5
from wtforms.fields import *
from wtforms.validators import *

from flask_wtf.file import FileField, FileRequired, FileAllowed
from flask_uploads import UploadSet, IMAGES

images = UploadSet('images', IMAGES)

class PermissionSetForm(FlaskForm):
    editor_roles = SelectMultipleField('Roles')
    editor_users = SelectMultipleField('Users')
    visible_roles = SelectMultipleField('Roles')
    visible_users = SelectMultipleField('Users')

class TeamForm(FlaskForm):
    name = StringField()
    sub = StringField('Workspace URL')
    number = IntegerField()
    email_subdomain = StringField('Email Subdomain (optional)')

class UserForm(FlaskForm):
    first_name = StringField()
    last_name = StringField()
    email = html5.EmailField()
    barcode = StringField()
    roles = SelectMultipleField('Roles', coerce=str)

class TeamUpdateForm(FlaskForm):
    content = TextAreaField(validators=[required()])
    images = FileField(validators=[FileAllowed('Images only!')])
    post = SubmitField()
    edit = SubmitField()

class PublicUserForm(FlaskForm):
    first_name = StringField()
    last_name = StringField()
    personal_email = html5.EmailField()
    phone_number = html5.TelField()
    bio = TextAreaField()
    barcode = StringField()

class NotificationForm(FlaskForm):
    notify_by_email = BooleanField('Notify by Email?')
    notify_by_phone = BooleanField('Notify by Phone?')
    notify_by_push = BooleanField('Notify by Push?')
    notify_by_app = BooleanField('Notify in App?')
    notification_dates = StringField()

class EventForm(FlaskForm):
    calendar = SelectField('Calendar')
    start = html5.DateTimeLocalField(format='%Y-%m-%dT%H:%M')
    end = html5.DateTimeLocalField(format='%Y-%m-%dT%H:%M')
    content = TextAreaField('Description (Markdown)')
    name = StringField(validators=[required()])
    enable_rsvp = BooleanField('Enable RSVP')
    rsvp_notifications = FormField(NotificationForm)
    enable_attendance = BooleanField('Enable Attendance Tracking')

class EventUserForm(FlaskForm):
    sign_in = html5.TimeField()
    sign_out = html5.TimeField()

class AssignmentForm(FlaskForm):
    subject = StringField(validators=[required()])
    content = TextAreaField()
    due = html5.DateTimeLocalField(format='%Y-%m-%dT%H:%M', validators=[required()])
    permissions = FormField(PermissionSetForm)
    notifications = FormField(NotificationForm)

class FilterForm(FlaskForm):
    filter_by = SelectField('Filter', coerce=int)
    filter_user = SelectField('User')
    filter_role = SelectField('Role')

class RoleForm(FlaskForm):
    role = StringField(label="Add")

class RecurringEventForm(FlaskForm):
    calendar = SelectField('Calendar')
    name = StringField(validators=[required()])
    content = TextAreaField(label="Description (Markdown)")
    start_date = html5.DateField('Start Date', validators=[required()])
    end_date = html5.DateField('End Date', validators=[required()])
    start_time = html5.TimeField('Start Time', validators=[required()])
    end_time = html5.TimeField('End Time', validators=[required()])
    days_of_week = SelectMultipleField('Days of Week', coerce=int)
    enable_rsvp = BooleanField('Enable RSVP')
    rsvp_notifications = FormField(NotificationForm)
    enable_attendance = BooleanField('Enable Attendance Tracking')

class ClockInForm(FlaskForm):
    barcode = StringField(validators=[required()])

class TopicForm(FlaskForm):
    name = StringField(validators=[required()])
    description = TextAreaField(validators=[required()])
    permissions = FormField(PermissionSetForm)

class CalendarForm(FlaskForm):
    name = StringField(validators=[required()])
    description = TextAreaField(validators=[required()])
    permissions = FormField(PermissionSetForm)

class ArticleForm(FlaskForm):
    topic = SelectField('Topic')
    name = StringField(validators=[required()])
    content = TextAreaField()

class CreateTeamForm(FlaskForm):
    name = StringField('Team Name', validators=[required()])
    sub = StringField('Workspace URL', validators=[required()])
    number = IntegerField(validators=[required()])

class JoinTeamForm(FlaskForm):
    number = IntegerField(validators=[required()])
