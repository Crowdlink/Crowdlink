# Monkey patch the login managers error function
# =========================================================================
from flask.ext.login import LoginManager, user_unauthorized
from flask import current_app, jsonify
def unauthorized(self):
    '''
    This is a slightly patched version of the default flask-login
    de-auth function. Instead of a 302 redirect we pass some json back
    for angular to catch
    '''
    user_unauthorized.send(current_app._get_current_object())

    if self.unauthorized_callback:
        return self.unauthorized_callback()

    ret = jsonify(access_denied=True)
    ret.status_code = 403
    return ret
LoginManager.unauthorized = unauthorized

# Monkey patch flasks request to inject a helper function
# =========================================================================
from flask import Request
@property
def dict_args(self):
    return {one: two for one, two in self.args.iteritems()}

@property
def json_dict(self):
    js = self.json
    if js is None:
        return {}
    return js
Request.dict_args = dict_args
Request.json_dict = json_dict
