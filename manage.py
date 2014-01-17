from flask.ext.script import Manager
from crowdlink import create_app

app = create_app()
manager = Manager(app)

import os
import sqlalchemy

from crowdlink.mail import TestEmail
from crowdlink import db, root

from flask import current_app


@manager.command
def init_db():
    try:
        db.engine.execute("CREATE EXTENSION hstore")
    except sqlalchemy.exc.ProgrammingError as e:
        if 'already exists' in str(e):
            pass
        else:
            raise Exception("Unable to enable HSTORE extension")
    db.drop_all()
    db.create_all()


@manager.command
def provision():
    from crowdlink.provision import provision
    provision()


@manager.command
def test_email(template=None):
    recipient = current_app.config['email_test_address']
    TestEmail().send_email(recipient)


@manager.command
def runserver():
    current_app.run(debug=True, host='0.0.0.0')


@manager.command
def generate_trans():
    """ Generates testing database fixtures """
    init_db()
    provision()
    username = os.environ.get('WERCKER_POSTGRESQL_USERNAME', 'crowdlink')
    database = os.environ.get('WERCKER_POSTGRESQL_DATABASE', 'crowdlink')
    url = os.environ.get('WERCKER_POSTGRESQL_URL')
    if url:
        host = url.split('@')[1].split(':')[0]
    else:
        host = 'localhost'
    if 'WERCKER_POSTGRESQL_PASSWORD' in os.environ:
        print "Setting pgpass env variable..."
        os.environ['PGPASSWORD'] = os.environ['WERCKER_POSTGRESQL_PASSWORD']
    cmd = ("pg_dump -c -U {username} -h {host} {database} -f "
           "{root}/assets/test_provision.sql"
           .format(username=username,
                   database=database,
                   host=host,
                   root=root))
    print cmd
    print os.environ
    os.system(cmd)


if __name__ == "__main__":
    manager.run()
