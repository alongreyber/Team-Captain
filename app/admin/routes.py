from app import models, forms
from app.admin import context
from flask import render_template, request, redirect, flash, session, abort, url_for, Blueprint

import datetime

admin = Blueprint('admin', __name__, template_folder='templates')

@admin.route('/')
def index():
    return redirect(url_for('admin.user_list'))

@admin.route('/users')
def user_list():
    users = models.User.objects
    return render_template('admin/user_list.html', users=users)

@admin.route('/u/<id>', methods=['GET', 'POST'])
def user_info(id):
    user = models.User.objects(id=id).first()
    if not user:
        abort(404)
    form = forms.UserForm(request.form, data=user.to_mongo().to_dict())
    if form.validate_on_submit():
        user_updated_dict = form.data
        del user_updated_dict['csrf_token']
        user.modify(**user_updated_dict)
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/user_info.html', user=user, form=form)

@admin.route('/u/<id>/delete')
def user_delete(id):
    return "Deleted user"

@admin.route('/timelogs')
def timelog_list():
    timelogs = models.TimeLog.objects
    return render_template('admin/timelog_list.html', timelogs=timelogs)

@admin.route('/t/<id>', methods=['GET', 'POST'])
def timelog_info(id):
    timelog = models.TimeLog.objects(id=id).first()
    if not timelog:
        abort(404)
    form = forms.TimeLogForm(request.form, data=timelog.to_mongo().to_dict())
    if form.validate_on_submit():
        updated_dict = form.data
        del updated_dict['csrf_token']
        timelog.modify(**updated_dict)
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/timelog_info.html', timelog=timelog, form=form)

@admin.route('/clockin')
def clock_in():
    if request.args.get('barcode'):
        user = models.User.objects(barcode=request.args.get('barcode')).first()
        if not user:
            flash('Invalid Barcode', 'danger')
            return render_template('admin/clock_in.html')
        # Look for a time log with a sign in but not a sign out
        timelog = models.TimeLog.objects(user=user.id, time_out=None).first()
        if not timelog:
            timelog = models.TimeLog(user=user.id, time_in=datetime.datetime.now()).save()
            flash('Signed in', 'success')
        else:
            timelog.time_out = datetime.datetime.now()
            flash('Signed out', 'success')
    return render_template('admin/clock_in.html')

@admin.route('/sign_everyone_out')
def sign_everyone_out():
    timelogs = models.TimeLog.objects(time_out=None)
    for t in timelogs:
        t.time_out = datetime.datetime.now()
        t.save()
    flash('Signed Out ' + str(len(timelogs)) + ' users', 'success')
    return redirect(url_for('admin.timelog_list'))

@admin.route('/meetings')
def meeting_list():
    scheduled_meetings = models.Meeting.objects(recurrence=None)
    recurring_meetings = models.RecurringMeeting.objects()
    return render_template('admin/meeting_list.html',
            scheduled_meetings=scheduled_meetings,
            recurring_meetings=recurring_meetings)

@admin.route('/m/<id>', methods=["GET","POST"])
def scheduled_meeting_info(id):
    meeting = models.Meeting.objects(id=id, recurrence=None).first()
    if not meeting or meeting.start < datetime.datetime.now():
        abort(404)
    form = forms.MeetingForm(request.form, data=meeting.to_mongo().to_dict())
    if form.validate_on_submit():
        updated_dict = form.data
        # The dates/times need to be converted to datetime objects
        del updated_dict['csrf_token']
        if updated_dict['end'] <= updated_dict['start']:
            flash('Start of meeting cannot be before end!', 'warning')
        elif updated_dict['start'] <= datetime.datetime.now():
            flash('Meeting cannot start in the past', 'warning')
        else:
            flash('Changes Saved', 'success')
            meeting.modify(**updated_dict)
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/meeting_info.html', meeting=meeting, form=form)

@admin.route('/rm/<id>', methods=["GET","POST"])
def recurring_meeting_info(id):
    meeting = models.RecurringMeeting.objects(id=id).first()
    if not meeting:
        abort(404)
    form = forms.RecurringMeetingForm(request.form, data=meeting.to_mongo().to_dict())
    all_days_of_week = ['S','M','T','W','H','F','S']
    form.days_of_week.choices = list(zip(range(7), all_days_of_week))
    if form.validate_on_submit():
        updated_dict = form.data
        # The dates/times need to be converted to datetime objects
        updated_dict['start_time'] = datetime.datetime.combine(datetime.datetime.min.date(), updated_dict['start_time'])
        updated_dict['end_time'] = datetime.datetime.combine(datetime.datetime.min.date(), updated_dict['end_time'])
        del updated_dict['csrf_token']
        if updated_dict['end_time'] <= updated_dict['start_time']:
            flash('Start of meeting cannot be before end!', 'warning')
        elif updated_dict['end_date'] <= updated_dict['start_date']:
            flash('Start of recurring meeting cannot be before end!', 'warning')
        elif updated_dict['start_date'] < datetime.datetime.now().date():
            flash('Meetings cannot start in the past!', 'warning')
        elif len(updated_dict['days_of_week']) == 0:
            flash('Meeting must happen at least one day a week!', 'warning')
        else:
            updated_dict['start_date'] = datetime.datetime.combine(updated_dict['start_date'], datetime.datetime.min.time())
            updated_dict['end_date'] = datetime.datetime.combine(updated_dict['end_date'], datetime.datetime.min.time())
            flash('Changes Saved', 'success')
            meeting.modify(**updated_dict)
            # Delete the existing meetings
            models.Meeting.objects(recurrence=meeting).delete()
            # Re-add
            d = meeting.start_date
            while d <= meeting.end_date:
                d += datetime.timedelta(days=1)
                if d.weekday() in meeting.days_of_week:
                    new_meeting = models.Meeting(name=meeting.name,
                                                 start=datetime.datetime.combine(d,meeting.start_time.time()),
                                                 end=datetime.datetime.combine(d,meeting.end_time.time()),
                                                 recurrence = meeting)
                    new_meeting.save()
    if len(form.errors) > 0:
        flash_errors(form)
    print(meeting.days_of_week)
    return render_template('admin/recurring_meeting_info.html',
            meeting=meeting,
            form=form,
            selected_days_of_week = meeting.days_of_week)

@admin.route('/newrecurringmeeting')
def recurring_meeting_new():
    meeting = models.RecurringMeeting()
    meeting.start_date = datetime.datetime.now()
    meeting.end_date = datetime.datetime.now() + datetime.timedelta(days=1) 
    meeting.start_time = datetime.datetime.combine(datetime.datetime.min.date(), datetime.time(17))
    meeting.end_time = datetime.datetime.combine(datetime.datetime.min.date(), datetime.time(19))
    meeting.days_of_week = [1,3,5]
    meeting.save()
    return redirect(url_for('admin.recurring_meeting_info', id=meeting.id))

@admin.route('/newmeeting')
def meeting_new():
    meeting = models.Meeting()
    meeting.start = datetime.datetime.now() + datetime.timedelta(days=1)
    meeting.end = meeting.start + datetime.timedelta(hours=2)
    meeting.save()
    return redirect(url_for('admin.scheduled_meeting_info', id=meeting.id))


def flash_errors(form):
    """Flash errors from a form at the top of the page"""
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ), 'warning')
