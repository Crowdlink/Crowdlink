from flask import (render_template, send_file, redirect, url_for, session,
                   abort, request, Blueprint)
from flask.ext.login import current_user

from . import root, db
from lever import get_joined

import os


main = Blueprint('main', __name__)


@main.route("/test/<action>/")
def test_403(action=None):
    """ Allows simple testing of the various error display systems """
    if action == 'flash':
        send_message('This is a test of the automated flash alert system!', 'alert-danger')
        return redirect('/')
    if action == 'mflash':
        send_message('This is a test of the automated flash alert system!', 'alert-success')
        send_message('This is another test of the automated flash alert system!', 'alert-info')
        return redirect('/')
    if action == 'lflash':
        send_message('This is a test of the long automated flash alert system!', 'alert-primary', 10000)
        return redirect('/')
    if action == 'sflash':
        send_message('This is a test of the long automated flash alert system!', 'alert-warning', page_stay=3)
        return redirect('/')
    elif action == '403':
        abort(403)
    elif action == '400':
        abort(400)
    elif action == '409':
        abort(409)
    elif action == '500':
        abort(500)
    elif action == '404':
        abort(404)


@main.route("/favicon.ico")
def favicon():
    return send_file(os.path.join(root, 'static/favicon.ico'))


def send_message(message, cls='alert-danger', timeout=5000, page_stay=1):
    if page_stay > 1:
        timeout = None
    dat = {'message': message, 'class': cls, 'timeout': timeout, 'page_stay': page_stay}
    if not '_messages' in session:
        session['_messages'] = [dat]
    else:
        session['_messages'].mainend(dat)


@main.route("/<path:path>", methods=['GET', 'POST'])
@main.route("/", methods=['GET', 'POST'])
def angular_root(path=None):
    logged_in = "true" if current_user.is_authenticated() else "false"
    user = get_joined(current_user) if current_user.is_authenticated() else "undefined"
    # re-encode our flash messages and pass them to angular for display
    messages = session.pop('_messages', None)
    if messages is None:
        messages = []
    return render_template('base.html',
                           logged_in=logged_in,
                           user=user,
                           messages=messages)


@main.route('/activate', methods=['GET'])
def activate_email():
    from .models import Email
    try:
        hash = request.args['hash']
        email_address = request.args['address']
    except KeyError:
        abort(400)
    else:
        try:
            if not Email.activate_email(email_address, hash):
                abort(400)
            try:
                db.session.commit()
            except Exception:
                abort(400)
        except Exception:
            abort(500)

        send_message("Your email address is now verified.", cls='alert-success')
    return redirect(url_for('main.angular_root', _anchor='/'))
