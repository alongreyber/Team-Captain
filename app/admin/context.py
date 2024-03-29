from app import app
import datetime
import hashlib

@app.template_filter('day_of_week_letter')
def day_of_week_letter(d):
    all_days_of_week = ['S','M','T','W','H','F','S']
    days_of_week_dict = dict(zip(range(7), all_days_of_week))
    return days_of_week_dict[d]

@app.context_processor
def inject_time():
    return dict(now=datetime.datetime.now())

@app.template_filter('md5')
def md5(s):
    return hashlib.md5(s)
