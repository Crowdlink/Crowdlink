import crowdlink
import json

from crowdlink.tests import BaseTest, login_required, login_required_ctx
from crowdlink.models import Issue, Project, Solution, User
from crowdlink.fin_models import Charge, Earmark

from pprint import pprint
from flask.ext.login import current_user


class ModelAPITests(BaseTest):
    @login_required_ctx(username='scrappy')
    def test_earmarking(self):
        """ create some earmarks with our charged money. """
        first_issue = self.db.session.query(Issue).first()
        prev_amount = self.user.available_balance
        amnt = self.user.available_balance*0.10
        mark = Earmark.create(first_issue.id, amnt)

        self.db.session.refresh(self.user)
        assert self.user.available_balance == prev_amount - amnt
        assert mark.id > 0
        assert mark.user_id > 0
