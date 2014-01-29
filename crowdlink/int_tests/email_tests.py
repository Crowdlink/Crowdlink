from crowdlink.tests import ThinTest
from crowdlink.mail import TestEmail


class EmailTests(ThinTest):
    def test_email_send(self):
        self.new_user(login=True)
        assert TestEmail().send(self.app.config['email_test_address'],
                                force_send=False)
