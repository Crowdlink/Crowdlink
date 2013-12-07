from . import db
from .lib import distribute_event, catch_error_graceful
from .models import User, BaseMapper

import datetime

class Event(BaseMapper):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def to_dict(self):
        ret = {str(key) : str(val) for key, val in self.__dict__.items()}
        ret["_cls"] = self.__class__.__name__
        return ret

class IssueNotif(Event):
    template = "events/issue.html"
    standard_join = ['__dont_mongo',
                     'template',
                     'user',
                     'issue'
                     ]

    def distribute(self):
        # send to the project, and people watching the project
        distribute_event(self.issue.project,
                         self,
                         "issue",
                         self_send=True,
                         subscriber_send=True
                    )

        # sent to the user who created the issues's feed and their subscribers
        distribute_event(self.user,
                         self,
                         "issue",
                         subscriber_send=True,
                         self_send=True
                    )
