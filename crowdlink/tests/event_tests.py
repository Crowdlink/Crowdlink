import crowdlink
import json
import datetime

from flask.ext.login import current_user
from crowdlink.tests import BaseTest, login_required, login_required_ctx
from crowdlink.models import Issue, Project, Solution, User
from crowdlink.events import IssueNotif
from pprint import pprint


class EventTests(BaseTest):

    @login_required_ctx
    def test_basic_send(self):
        """ cam we send a basic notification? """
        issue = self.db.session.query(Issue).first()
        # subscribe our logged in user to the project and the user who made the
        # post
        issue.project.subscribe()
        issue.creator.subscribe()

        inotif = IssueNotif.generate(issue)
        # reload all the recipeints
        self.db.session.refresh(issue)
        self.db.session.refresh(issue.project)
        self.db.session.refresh(issue.creator)
        self.db.session.refresh(self.user)
        assert issue.project.events[-1].iname == issue.title
        assert issue.creator.public_events[-1].iname == issue.title
        assert self.user.events[-1].iname == issue.title
