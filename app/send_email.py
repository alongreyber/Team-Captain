from flask import render_template
import smtplib
# Import the email modules
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import os

from jinja2 import Environment, FileSystemLoader, select_autoescape
env = Environment(
    loader=FileSystemLoader(os.getcwd() + '/app/admin/templates/admin/'),
    autoescape=select_autoescape(['html', 'xml'])
)

def send_email(to, cc=None, bcc=None, subject=None, body=None):
    ''' sends email with an HTML body '''
    
    # convert TO into list if string
    if type(to) is not list:
        to = to.split()
    
    to_list = to + [cc] + [bcc]
    to_list = [t for t in to_list if t] # remove null emails

    sender = 'teamcaptain@bullcitybotics.co'
    passwd = 'the3Qguy'

    msg = MIMEMultipart('alternative')
    msg['From']    = sender
    msg['Subject'] = subject
    msg['To']      = ','.join(to)
    msg['Cc']      = cc
    msg['Bcc']     = bcc
    msg.attach(MIMEText(body, 'html'))
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.login(sender, passwd)
    try:
        print('Sending email')
        server.sendmail(sender, to_list, msg.as_string())
    except Exception as e:
        print('Error sending email')
        print(e)
    finally:
        server.quit()

def send_startups_email(startups):
    """Given a list of startups send an email notifying that they have been updated
    
    This uses a Jinja template to render"""
    template = env.get_template('startups_email.html')
    html = template.render(startups=startups, len=len)
    to_list = ['alon@colopy.com']
    cc = None
    bcc = None
    subject = str(len(startups)) + " startups updated"
    send_email(to_list, cc, bcc, subject, html)

