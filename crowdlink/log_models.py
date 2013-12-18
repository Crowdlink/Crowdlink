from . import db
from .models import base, JSONEncodedDict, HSTOREStringify
from .fin_models import Earmark, Charge, Mark, Transfer, Recipient

from datetime import datetime
from flask.ext.login import current_user


class Log(object):
    @classmethod
    def create(cls, user=current_user, **kwargs):
        cls = cls(**kwargs)
        cls.actor = user.get()
        return cls


def make_log(model):
    name = model.__tablename__.title()

    return type(name + "Log", (Log, base), {
        '__tablename__': name.lower() + "_log",
        'id': db.Column(db.Integer, primary_key=True),
        'action': db.Column(db.String, nullable=False),
        'data': db.Column(HSTOREStringify),
        'blob': db.Column(JSONEncodedDict),
        'actor': db.relationship('User'),
        'actor_id': db.Column(db.Integer,
                              db.ForeignKey('user.id'),
                              nullable=False),
        'created_at': db.Column(db.DateTime,
                                default=datetime.utcnow,
                                nullable=False),
        'item': db.relationship(name),
        'item_id': db.Column(db.Integer,
                             db.ForeignKey(name.lower() + '.id'),
                             nullable=False),
    })


EarmarkLog = make_log(Earmark)
ChargeLog = make_log(Charge)
MarkLog = make_log(Mark)
TransferLog = make_log(Transfer)
RecipientLog = make_log(Recipient)
