from app import models, forms
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

@admin.route('/timelogs')
def timelog_list():
    timelogs = models.TimeLog.objects
    return render_template('admin/timelog_list.html', timelogs=timelogs)

@admin.route('/u/<id>', methods=['GET', 'POST'])
def user_info(id):
    user = models.User.objects(id=id).first()
    if not user:
        abort(404)
    form = forms.UserForm(request.form, data=user.to_mongo().to_dict())
    if form.validate_on_submit():
        user_updated_dict = form.data
        del user_updated_dict['csrf_token']
        user.update(**user_updated_dict)
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('admin/user_info.html', user=user, form=form)

@admin.route('/t/<id>', methods=['GET', 'POST'])
def timelog_info(id):
    timelog = models.TimeLog.objects(id=id).first()
    if not timelog:
        abort(404)
    form = forms.TimeLogForm(request.form, data=timelog.to_mongo().to_dict())
    if form.validate_on_submit():
        updated_dict = form.data
        del updated_dict['csrf_token']
        timelog.update(**updated_dict)
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

def flash_errors(form):
    """Flash errors from a form at the top of the page"""
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ), 'warning')
