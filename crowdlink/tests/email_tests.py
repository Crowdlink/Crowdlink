from crowdlink.tests import BaseTest, login_required, login_required_ctx
from crowdlink.mail import TestEmail
from pprint import pprint


class EmailTests(BaseTest):
    @login_required_ctx()
    def test_email_send(self):
        assert TestEmail().send(self.app.config['email_test_address'])
