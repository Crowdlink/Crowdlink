from flask.ext.login import current_user
from crowdlink.tests import ThinTest
from crowdlink.models import Project
from crowdlink.events import TaskNotif
from pprint import pprint


class EventTests(ThinTest):

    def test_basic_send(self):
        """ cam we send a basic notification? """
        self.new_user(login_ctx=True, login=True)
        project = self.provision_project()
        task = self.provision_task(project)
        task.project.public_events = []
        TaskNotif.generate(task)
        self.db.session.commit()
        print(task.title)
        for event in task.project.public_events:
            pprint(event.to_dict())
        assert task.project.public_events[-1].iname == task.title
        assert task.creator.public_events[-1].iname == task.title

    def test_dupl_deliv(self):
        user = self.new_user(login_ctx=True)
        project = self.provision_project()
        task = self.provision_task(project)
        # subscribe our logged in user to the project and the user who made the
        # post
        task.project.subscribed = True
        task.creator.subscribed = True

        # clear the users events for easier testing of duplicate delivery
        current_user.events = None
        current_user.save()
        # distribute
        TaskNotif.generate(task)
        # the subscriptions above should have double delivered. Ensure double
        # delivery prevention is tracked
        assert len(user.events) == 1
        assert user.events[-1].iname == task.title
        assert user.public_events[-1].iname == task.title

    def test_unsubscribe_redeliver(self):
        # clear the users events for easier testing
        user = self.new_user(login_ctx=True)
        project = self.provision_project(user=user)
        self.provision_task(project)
        assert len(current_user.events) == 0

        # subscribe our logged in user to many tasks
        project.subscribed = True

        # the user should now have several events
        assert len(current_user.events) > 0

    def test_subscribe_undeliver(self):
        self.new_user(login_ctx=True, login=True)
        project = self.provision_project()
        project.subscribed = True
        self.provision_task(project)
        # clear the users events for easier testing
        assert len(current_user.events) > 0

        # subscribe our logged in user to many tasks
        project = Project.query.filter_by(name='Crowdlink').first()
        project.subscribed = False

        # the user should now have several events
        for event in current_user.events:
            assert event.origin != project.id
