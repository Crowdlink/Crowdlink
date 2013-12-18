from crowdlink.tests import BaseTest, login_required_ctx
from crowdlink.models import Issue, Project, Solution, User
from crowdlink.fin_models import Earmark
from pprint import pprint


class ModelTests(BaseTest):
    @login_required_ctx
    def test_relationship_poly(self):
        """ does our polymorphic relationship work as expected? """
        lst = [Issue, Project, User, Solution]
        for obj in lst:
            obj_inst = self.db.session.query(obj).first()
            mark = Earmark.create(obj_inst, 1000)
            self.db.session.refresh(mark)
            pprint(mark.thing.to_dict())
            assert isinstance(mark.thing, obj)
