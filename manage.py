from flask.ext.script import Manager
from crowdlink import app

manager = Manager(app)

import logging
from crowdlink.lib import send_email
from crowdlink import db
from crowdlink.models import User, Project, Issue

# setup logging to go to stdout
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
rootLogger = logging.getLogger()

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)
rootLogger.setLevel(logging.INFO)

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
    usr = User.create_user("crowdlink", "testing", "support@crowdlink.com")

    # Create the project for crowdlink
    proj = Project(
        maintainer=usr,
        name='crowdlink',
        website="http://crowdlink.com",
        url_key='crowdlink',
        desc="A platform for user feedback").init()
    proj.safe_save()

    issues = [('Graphing of Improvement popularity', 'Generate simple d3 graphs that show how many votes an Improvement has recieved since its creation. Current thought was a on day to day basis.'),
            ('Change log for Improvements', 'Like gists on Github, show a historical revision log for an Improvements descriptions'),
            ('Hot sorting metric for Improvements', 'Periodically re-calculate a "hot" value for various improvements based on how quickly they\'ve recieved votes over time. Similar to reddit, or other websites trending function'),
            ('Allow revoking of Github synchronization via crowdlink', 'Currently, desynchronizing can only be done via Github.'),
            ('Approval option for Improvements', 'Similar function to a lot of mailing lists, Improvements would be by default hidden until approved by a project maintainer. Perhaps a user could be put on an approved list as well, allowing their suggestions to be auto-approved.'),
            ('Promote with donations', 'Instead of dontaing to the project, donate to a charity, yet earmark this donation towards a project or Improvement to show your support'),
            ('Google Analytics Hooks', 'Allow project maintainers to specify a Google Analytics Key and select from a range of events that they would like logged into their GA account'),
        ]
    for title, desc in issues:
        issue = Issue(
            creator=usr,
            title=title,
            desc=desc)
        proj.add_issue(issue, usr)

@manager.command
def test_email():
    recipient = app.config['EMAIL_TEST_ADDR']
    send_email(recipient, 'test')


@manager.command
def runserver():
    app.run(debug=True, host='0.0.0.0')

if __name__ == "__main__":
    manager.run()
