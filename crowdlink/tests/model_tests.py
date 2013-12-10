import crowdlink
import json
import datetime

from flask.ext.login import current_user
from crowdlink.tests import BaseTest, login_required, login_required_ctx
from crowdlink.models import Issue, Project, Solution, User, Earmark
from pprint import pprint


class ModelTests(BaseTest):

    def test_relationship_poly(self):
        """ does our polymorphic relationship work as expected? """
        lst = [Issue, Project, User, Solution]
        for obj in lst:
            obj_inst = self.db.session.query(obj).first()
            earmark = Earmark(amount=1000,
                              thing_id=obj_inst.id).safe_save()
            self.db.session.refresh(earmark)
            pprint(earmark.thing.to_dict())
            assert isinstance(earmark.thing, obj)
