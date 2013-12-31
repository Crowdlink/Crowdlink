import crowdlink
import json
import datetime

from flask.ext.login import current_user
from crowdlink.tests import BaseTest, login_required, login_required_ctx
from crowdlink.models import Issue, Project, Solution, User
from crowdlink.events import IssueNotif
from pprint import pprint


class EventTests(BaseTest):

    @login_required_ctx()
    def test_basic_send(self):
        """ cam we send a basic notification? """
        issue = self.db.session.query(Issue).first()
        issue.project.public_events = []
        inotif = IssueNotif.generate(issue)
        self.db.session.commit()
        # reload all the recipeints
        self.db.session.refresh(issue)
        self.db.session.refresh(issue.project)
        self.db.session.refresh(issue.creator)
        print issue.title
        for event in issue.project.public_events:
            pprint(event.to_dict())
        assert issue.project.public_events[-1].iname == issue.title
        assert issue.creator.public_events[-1].iname == issue.title

    @login_required_ctx()
    def test_dupl_deliv(self):
        issue = self.db.session.query(Issue).first()
        # subscribe our logged in user to the project and the user who made the
        # post
        issue.project.subscribed = True
        issue.creator.subscribed = True

        # clear the users events for easier testing of duplicate delivery
        current_user.events = None
        current_user.save()
        # distribute
        inotif = IssueNotif.generate(issue)
        # the subscriptions above should have double delivered. Ensure double
        # delivery prevention is tracked
        assert len(self.user.events) == 1
        assert self.user.events[-1].iname == issue.title
        assert self.user.public_events[-1].iname == issue.title

    @login_required_ctx()
    def test_unsubscribe_redeliver(self):
        # clear the users events for easier testing
        project = self.db.session.query(Project).first()
        project.subscribed = False
        current_user.events = None
        current_user.save()
        assert len(current_user.events) == 0

        # subscribe our logged in user to many issues
        project.subscribed = True

        # the user should now have several events
        assert len(current_user.events) > 1

    @login_required_ctx()
    def test_subscribe_undeliver(self):
        # clear the users events for easier testing
        assert len(current_user.events) > 0

        # subscribe our logged in user to many issues
        project = Project.query.filter_by(name='Crowdlink').first()
        project.subscribed = False

        # the user should now have several events
        assert len(current_user.events) == 0
