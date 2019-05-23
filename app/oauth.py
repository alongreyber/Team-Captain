from requests_oauthlib import OAuth2Session
from requests.exceptions import HTTPError

CLIENT_ID = '462287470911-qr61qvn7153as87qklbeuu89ji7ikai3.apps.googleusercontent.com'
CLIENT_SECRET = '2-9hJ899YEAFCNpHcCPDhKIw'
REDIRECT_URI = 'http://manager.com:5000/oauth2callback'  # one of the Redirect URIs from Google APIs console
AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
TOKEN_URI = 'https://accounts.google.com/o/oauth2/token'
USER_INFO = 'https://www.googleapis.com/userinfo/v2/me'
SCOPE = ['profile', 'email']
 
def get_google_auth(state=None, token=None):
    if token:
        return OAuth2Session(CLIENT_ID, token=token)
    if state:
        return OAuth2Session( CLIENT_ID, state=state, redirect_uri=REDIRECT_URI)
    oauth = OAuth2Session( CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPE)
    return oauth
