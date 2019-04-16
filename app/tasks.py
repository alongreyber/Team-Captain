from app.huey import huey
from app import models, send_email

@huey.task()
def send_notification(notification_id):
    notification = models.PushNotification.objects(id=notification_id).first()
    if not notification:
        return
    if notification.send_email:
        send_email.send_email('alongreyber@gmail.com', subject='Hellooo!', body=f"This is a test to see if sending email works. \n{notification.text} \n{notification.link}")
    # Send email
    # Send other stuff
    notification.sent = True
    notification.save()
