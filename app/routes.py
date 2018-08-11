from app import app, models, forms
from flask import render_template, request, redirect, flash, session

from flask_mongoengine.wtf import model_form

@app.route('/')
def user_list():
    users = models.User.objects
    return render_template('user_list.html', users=users)

@app.route('/u/<id>', methods=['GET', 'POST'])
def user_info(id):
    user = models.User.objects(id=id).first()
    form = forms.UserForm(request.form, data=user.to_mongo().to_dict())
    if form.validate_on_submit():
        user_updated_dict = form.data
        del user_updated_dict['csrf_token']
        user.update(**user_updated_dict)
    if len(form.errors) > 0:
        flash_errors(form)
    return render_template('user_info.html', user=user, form=form)

def flash_errors(form):
    """Flash errors from a form at the top of the page"""
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ), 'warning')
