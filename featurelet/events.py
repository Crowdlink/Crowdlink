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

class ImprovementNotif(Event):
    """ Notification of a new improvement being created """
    user = db.ReferenceField('User')
    imp = db.GenericReferenceField()  # The object recieving the comment
    created_at = db.DateTimeField(default=datetime.datetime.now)

    template = "events/improvement.html"

    def distribute(self):
        # send to the project, and people watching the project
        distribute_event(self.imp.project,
                         self,
                         "improvement",
                         self_send=True,
                         subscriber_send=True
                    )

        # sent to the user who created the improvement's feed and their subscribers
        distribute_event(self.user,
                         self,
                         "improvement",
                         subscriber_send=True,
                         self_send=True
                    )


class CommentNotif(Event):
    """ Notification that a comment has been created """
    user = db.ReferenceField('User')
    obj = db.GenericReferenceField()  # The object recieving the comment
    created_at = db.DateTimeField(default=datetime.datetime.now)
    template = "events/comment_not.html"

    def distribute(self):
        if type(self.obj) == "Improvement":
            # pass it on to the improvement's project if it is from improvement
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

    def distribute(self, improvement):
        """ In this instance more of a create. The even obj distributes itself
        and then notifications of its creation. really just to save space on
        the contents of the post body """
        # send to the event queue of the improvement
        distribute_event(improvement, self, "comment", self_send=True)
        # create the notification, and distribute based on CommentNotif logic
        notif = CommentNotif(user=self.user, obj=self)
        notif.distribute()

    @property
    def md_body(self):
        return markdown2.markdown(self.body)


