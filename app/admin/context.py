from app import app

@app.template_filter('day_of_week_letter')
def day_of_week_letter(d):
    all_days_of_week = ['S','M','T','W','H','F','S']
    days_of_week_dict = dict(zip(range(7), all_days_of_week))
    return days_of_week_dict[d]