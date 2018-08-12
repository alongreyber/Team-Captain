from app import models
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
