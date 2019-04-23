from app.huey import huey
from app import models, send_email

import datetime

@huey.task()
def send_notification(notification_id):
    print("Start of send_notification")
    notification = models.PushNotification.objects(id=notification_id).first()
    if not notification:
        return
    # Send email
    if notification.send_email:
        send_email.send_email('alongreyber@gmail.com', subject='Hellooo!', body=f"This is a test to see if sending email works. \n{notification.text} \n{notification.link}")
    if notification.send_text:
        print("Sending text not implemented yet")
    if notification.send_push:
        print("Sending push not implemented yet")
    if notification.send_app:
        app_notification = models.AppNotification()
        app_notification.user = notification.user
        app_notification.text = notification.text
        app_notification.link = notification.link
        app_notification.recieve_date = datetime.datetime.now()

        user = notification.user
        user.notifications.append(app_notification)
        user.save()
    notification.sent = True
    notification.save()
    print("End of send_notification")
