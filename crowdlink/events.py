from . import db
from .lib import distribute_event, catch_error_graceful
from .models import User, CommonMixin

import datetime

class Event(db.EmbeddedDocument, CommonMixin):
    # this represents the key in the subscriber entry that dictates whether it
    # should be publishe
    attr = None
    # template used to render the event
    template = "events/fallback.html"

    def distribute(self):
        """ Copies the subdocument everywhere it needs to go """
        pass

    meta = {'allow_inheritance': True}

class IssueNotif(Event):
    """ Notification of a new issue being created """
    user = db.ReferenceField('User')
    issue = db.GenericReferenceField()  # The object recieving the comment
    created_at = db.DateTimeField(default=datetime.datetime.now)

    template = "events/issue.html"
    standard_join = ['template',
                     {'obj': 'issue',
                      'join_prof': "disp_join"},
                     {'obj': 'user',
                      'join_prof': "disp_join"},
                     'created_at'
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


class CommentNotif(Event):
    """ Notification that a comment has been created """
    user = db.ReferenceField('User')
    obj = db.GenericReferenceField()  # The object recieving the comment
    created_at = db.DateTimeField(default=datetime.datetime.now)
    template = "events/comment_not.html"
    standard_join = ['template']

    def distribute(self):
        if type(self.obj) == "Issue":
            # pass it on to the issues's project if it is from issue
            distribute_event(self.obj.project, self, "comment_notif", self_send=True)

        # we never distribute notifications of the comment to itself, it gets a
        # comment obj instead

        # sent to the user who commented's feed and their subscribers
        distribute_event(self.user, self, "comment_notif", subscriber_send=True, self_send=True)


class Comment(Event):
    """ This is not actually an event. Comments are stored as events to simplify
    display """
    created_at = db.DateTimeField(default=datetime.datetime.now)
    user = db.ReferenceField('User')
    body = db.StringField()
    template = "events/comment.html"

    def distribute(self, issue):
        """ In this instance more of a create. The even obj distributes itself
        and then notifications of its creation. really just to save space on
        the contents of the post body """
        # send to the event queue of the issue
        distribute_event(issue, self, "comment", self_send=True)
        # create the notification, and distribute based on CommentNotif logic
        notif = CommentNotif(user=self.user, obj=self)
        notif.distribute()

    @property
    def md_body(self):
        return markdown2.markdown(self.body)


