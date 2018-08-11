from app import models
from flask_mongoengine.wtf import model_form

UserForm = model_form(models.User, field_args = {
    'first_name' : {'label' : "First Name"},
    'last_name' : {'label' : "Last Name"},
    'email' : {'label' : "Email"},
    'barcode' : {'label' : "Barcode"},
})
