from crowdlink.tests import BaseTest, login_required_ctx
from crowdlink.models import Issue, Project, Solution, User, Email
from crowdlink.fin_models import Earmark
from pprint import pprint


class ModelTests(BaseTest):
    @login_required_ctx()
    def test_relationship_poly(self):
        """ does our polymorphic relationship work as expected? """
        lst = [Issue, Project, User, Solution]
        for obj in lst:
            obj_inst = self.db.session.query(obj).first()
            mark = Earmark.create(obj_inst, 1000)
            self.db.session.refresh(mark)
            pprint(mark.thing.to_dict())
            assert isinstance(mark.thing, obj)

    @login_required_ctx()
    def test_activate_email(self):
        addr = "this.test.unique@testingdsflkjgsdfg.com"
        email = Email(user=self.user,
                      address=addr,
                      primary=False).save()

        Email.activate_email(addr)
        self.db.session.commit()
        self.db.session.refresh(email)
        print email.to_dict()
        assert email.verified is True
