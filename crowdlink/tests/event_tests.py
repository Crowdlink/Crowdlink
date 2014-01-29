
from flask.ext.login import current_user
from crowdlink.tests import ThinTest
from crowdlink.models import Project
from crowdlink.events import IssueNotif
from pprint import pprint


class EventTests(ThinTest):

    def test_basic_send(self):
        """ cam we send a basic notification? """
        self.new_user(login_ctx=True, login=True)
        project = self.provision_project()
        issue = self.provision_issue(project)
        issue.project.public_events = []
        IssueNotif.generate(issue)
        self.db.session.commit()
        print(issue.title)
        for event in issue.project.public_events:
            pprint(event.to_dict())
        assert issue.project.public_events[-1].iname == issue.title
        assert issue.creator.public_events[-1].iname == issue.title

    def test_dupl_deliv(self):
        user = self.new_user(login_ctx=True)
        project = self.provision_project()
        issue = self.provision_issue(project)
        # subscribe our logged in user to the project and the user who made the
        # post
        issue.project.subscribed = True
        issue.creator.subscribed = True

        # clear the users events for easier testing of duplicate delivery
        current_user.events = None
        current_user.save()
        # distribute
        IssueNotif.generate(issue)
        # the subscriptions above should have double delivered. Ensure double
        # delivery prevention is tracked
        assert len(user.events) == 1
        assert user.events[-1].iname == issue.title
        assert user.public_events[-1].iname == issue.title

    def test_unsubscribe_redeliver(self):
        # clear the users events for easier testing
        user = self.new_user(login_ctx=True)
        project = self.provision_project(user=user)
        self.provision_issue(project)
        assert len(current_user.events) == 0

        # subscribe our logged in user to many issues
        project.subscribed = True

        # the user should now have several events
        assert len(current_user.events) > 0

    def test_subscribe_undeliver(self):
        self.new_user(login_ctx=True, login=True)
        project = self.provision_project()
        project.subscribed = True
        self.provision_issue(project)
        # clear the users events for easier testing
        assert len(current_user.events) > 0

        # subscribe our logged in user to many issues
        project = Project.query.filter_by(name='Crowdlink').first()
        project.subscribed = False

        # the user should now have several events
        for event in current_user.events:
            assert event.origin != project.id
