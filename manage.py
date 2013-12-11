from flask.ext.script import Manager
from crowdlink import create_app

app = create_app()
manager = Manager(app)

import logging
from crowdlink.lib import send_email
from crowdlink import db
from crowdlink.models import User


@manager.option('-u', '--userid', dest='userid')
@manager.option('-n', '--username', dest='username')
def send_confirm(userid=None, username=None):
    if userid:
        recipient = User.objects.get(id=userid).primary_email
    else:
        recipient = User.objects.get(username=username).primary_email
    send_email(recipient, 'test')


@manager.command
def init_db():
    db.drop_all()
    db.create_all()


@manager.command
def provision():
    from crowdlink.util import provision
    provision()


@manager.command
def test_email():
    recipient = app.config['EMAIL_TEST_ADDR']
    send_email(recipient, 'test')


@manager.command
def runserver():
    app.run(debug=True, host='0.0.0.0')


if __name__ == "__main__":
    manager.run()
