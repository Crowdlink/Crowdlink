from datetime import datetime

import sqlalchemy

from . import db
from .model_lib import (base )
from .acl import acl


class EmailList(base):

    acl = acl['email_list']

    address = db.Column(db.String, primary_key=True)
    date = db.Column(db.DateTime)

    @classmethod
    def check_taken(cls, value):
        """ Called by the registration form to check if the username is taken
        """
        try:
            EmailList.query.filter_by(address=value).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return {'taken': False}
        else:
            return {'taken': True}

    @classmethod
    def create(cls, address):
        try:
            inst = cls(address=address,
                       date=datetime.now())

            db.session.add(inst)
            db.session.commit()
        except sqlalchemy.exc.IntegrityError:
            db.session.rollback()
            return {'message': 'Email address already registered!',
                    'success': False}
        return {'message': 'Win'}



