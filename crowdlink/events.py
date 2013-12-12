from . import db
from .models import BaseMapper, EventJSON, User

from sqlalchemy.orm import joinedload
from flask import current_app

import sqlalchemy
import flask_sqlalchemy
import datetime
import copy
import json


class Event(BaseMapper):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def to_dict(self):
        ret = self.jsonize(self.__dict__.keys(), raw=True)
        ret["_cls"] = self.__class__.__name__
        return ret

    def originates(self, id):
        """ utility function for seeing if the event originated from an id """
        return hasattr(self, 'origin') and self.origin == id

    def sendable(self, user):
        """ returns whether or not the user is subscribed to this type of event
        """
        return True

    def send_event(self, *args):
        """ A method that handles event disitribution """
        # keep a list of places that have been delivered to to prevent
        # duplicate messages
        delivered = []
        for arg in args:
            # if it's a bas query then it's a subscribers attribute
            if isinstance(arg, flask_sqlalchemy.BaseQuery):
                # assume its a list of subscribers
                for subscription in arg.options(joinedload('subscriber')):
                    # mark this path as delivered
                    deliv_tupl = ('events', subscription.subscriber.id)
                    if deliv_tupl not in delivered:
                        delivered.append(deliv_tupl)
                        self.origin = subscription.subscribee_id
                        new = subscription.subscriber.events + [self]
                        subscription.subscriber.events = new
                        #current_app.logger.debug(
                        #    "Sending event to subscribed user {} for notif "
                        #    "{}".format(subscription.subscriber.username,
                        #                self.__class__.__name__))
            # otherwise it's an events attribute
            elif isinstance(arg, tuple):
                obj, event_attr = arg
                # mark this path as delivered
                deliv_tupl = (event_attr, obj.id)
                if deliv_tupl not in delivered:
                    delivered.append(deliv_tupl)
                    # if it's going to a users public feed, record it so it can be
                    # removed later (hiding public things...)
                    if isinstance(obj, User):
                        self.origin = obj.id
                    new = getattr(arg[0], arg[1]) + [self]
                    setattr(arg[0], arg[1], new)
                    #current_app.logger.debug(
                    #    "Sending event to object {} event queue for notif "
                    #    "{}".format(arg[0].__class__.__name__,
                    #                self.__class__.__name__))

            else:
                current_app.logger.warn(
                    "Unkown object type given to send_event {}".format(
                        type(arg)))

        db.session.commit()


class IssueNotif(Event):
    template = "events/issue.html"
    standard_join = [
        '__dont_mongo',
        'time',
        'template',
        'uname',
        'user_p',
        'pname',
        'proj_p',
        'iname',
        'issue_p'
    ]

    @classmethod
    def generate(cls, issue):
        user = issue.creator
        project = issue.project
        notif = cls(
            time=datetime.datetime.now(),
            uname=user.username,
            user_p=user.get_dur_url,
            pname=project.name,
            proj_p=project.get_dur_url,
            iname=issue.title,
            issue_p=issue.get_dur_url)

        notif.send_event((user, 'public_events'),
                         (project, 'public_events'),
                         project.subscribers,
                         user.subscribers)
