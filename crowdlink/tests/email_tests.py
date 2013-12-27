import stripe

from crowdlink.tests import BaseTest, login_required, login_required_ctx
from crowdlink.lib import send_email
from pprint import pprint


class EmailTests(BaseTest):
    @login_required_ctx()
    def test_email_send(self):
        assert send_email(self.app.config['email_test_addr'], 'test')
