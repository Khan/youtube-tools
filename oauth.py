import gdata.gauth

import secrets

token = gdata.gauth.OAuth2Token(
    client_id=secrets.oauth_client_id,
    client_secret=secrets.oauth_client_secret,
    scope='https://gdata.youtube.com',
    user_agent='')

print token.generate_authorize_url()
code = raw_input("Enter the resulting code: ")
token.get_access_token(code)
print "Access token: %s" % token.access_token
