import argparse
import datetime
import time
import os
import mongoengine
import logging

from featurelet.models import User, Project, Improvement

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
rootLogger = logging.getLogger()

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)
rootLogger.setLevel(logging.INFO)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Provisions the featurelet project on featurelet')
    args = parser.parse_args()

    usr = User.create_user("featurelet", "testing", "support@featurelet.com")
    usr.active = True
    usr.save()

    # Create the project for featurelet
    proj = Project(
        maintainer=usr.id,
        name='Featurelet',
        website="http://featurelet.com",
        url_key='featurelet',
        description="A platform for user feedback")
    proj.save()

    imps = [('Graphing of Improvement popularity', 'Generate simple d3 graphs that show how many votes an Improvement has recieved since its creation. Current thought was a on day to day basis.'),
            ('Change log for Improvements', 'Like gists on Github, show a historical revision log for an Improvements descriptions'),
            ('Hot sorting metric for Improvements', 'Periodically re-calculate a "hot" value for various improvements based on how quickly they\'ve recieved votes over time. Similar to reddit, or other websites trending function'),
            ('Allow revoking of Github synchronization via Featurelet', 'Currently, desynchronizing can only be done via Github.'),
            ('Approval option for Improvements', 'Similar function to a lot of mailing lists, Improvements would be by default hidden until approved by a project maintainer. Perhaps a user could be put on an approved list as well, allowing their suggestions to be auto-approved.'),
            ('Promote with donations', 'Instead of dontaing to the project, donate to a charity, yet earmark this donation towards a project or Improvement to show your support'),
            ('Google Analytics Hooks', 'Allow project maintainers to specify a Google Analytics Key and select from a range of events that they would like logged into their GA account'),
        ]
    for title, desc in imps:
        imp = Improvement(
            creator=usr.id,
            brief=title,
            description=desc)
        proj.add_improvement(imp, usr)
