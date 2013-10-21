from flask import url_for, session, g

from featurelet import db, github

import cryptacular.bcrypt
import datetime
import mongoengine
import re
import markdown2

crypt = cryptacular.bcrypt.BCRYPTPasswordManager()

class SubscribableMixin(object):
    """ A Mixing providing data model utils for subscribing new users. Maintain
    uniqueness of user by hand through these checks """

    def unsubscribe(self, username):
        i = 0
        for sub in self.subscribers:
            if sub.user.username == username:
                break
            i += 1
        else:
            return False  # Return false if list exhausted
        # I feel uneasy about defaulting to remove i, but hopefully...
        del self.subscribers[i]

    def subscribe(self, sub_obj):
        # ensure that the user key is unique
        for sub in self.subscribers:
            if sub.user == sub_obj.user:
                return False
        self.subscribers.append(sub_obj)

    @property
    def subscribed(self):
        # search the list of subscribers looking for the current user
        for sub in self.subscribers:
            if sub.user.username == g.user.username:
                return True
        return False

class Email(db.EmbeddedDocument):
    address = db.StringField(max_length=1023, required=True, unique=True)
    verified = db.BooleanField(default=False)
    primary = db.BooleanField(default=True)


class Comment(db.EmbeddedDocument):
    body = db.StringField(min_length=10)
    user = db.ReferenceField('User', required=True)
    time = db.DateTimeField()

    @property
    def md_body(self):
        return markdown2.markdown(self.body)


class Improvement(db.Document, SubscribableMixin):
    brief = db.StringField(max_length=512, min_length=3)
    description = db.StringField()
    creator = db.ReferenceField('User')
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    project = db.ReferenceField('Project')
    vote_list = db.ListField(db.ReferenceField('User'))
    votes = db.IntField(default=0)
    events = db.ListField(db.GenericEmbeddedDocumentField())
    url_key = db.StringField(unique=True)
    subscribers = db.ListField(db.EmbeddedDocumentField('ImpSubscriber'))
    meta = {'indexes': [{'fields': ['url_key', 'project'], 'unique': True}]}

    def get_abs_url(self):
        return url_for('main.view_improvement',
                       purl_key=self.project.url_key,
                       user=self.project.maintainer.username,
                       url_key=self.url_key)

    def can_edit_imp(self, user):
        return user == self.creator or self.project.can_edit_imp(user)

    @property
    def md(self):
        return markdown2.markdown(self.description)

    def vote(self, user):
        return Improvement.objects(project=self.project,
                            url_key=self.url_key,
                            vote_list__ne=user.username).\
                    update_one(add_to_set__vote_list=user.username, inc__votes=1)

    def set_url_key(self):
        self.url_key = re.sub('[^0-9a-zA-Z]', '-', self.brief[:100]).lower()

    def add_comment(self, user, body):
        # Send the actual comment to the improvement event queue
        c = Comment(user=user.username, body=body)
        c.distribute(self)


class Project(db.Document, SubscribableMixin):
    id = db.ObjectIdField()
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    maintainer = db.ReferenceField('User')
    name = db.StringField(max_length=64, min_length=3)
    improvement_count = db.IntField(default=1)
    website = db.StringField(max_length=2048)
    source_url = db.StringField(max_length=2048)
    url_key = db.StringField(min_length=3, max_length=64)
    subscribers = db.ListField(db.EmbeddedDocumentField('ProjectSubscriber'))
    events = db.ListField(db.GenericEmbeddedDocumentField())

    meta = {'indexes': [{'fields': ['url_key', 'maintainer'], 'unique': True}]}

    def can_edit_imp(self, user):
        return self.maintainer == user

    def get_abs_url(self):
        return url_for('main.view_project',
                       username=self.maintainer.username,
                       url_key=self.url_key)

    def get_improvements(self):
        return Improvement.objects(project=self)

    def add_improvement(self, imp):
        imp.create_key()
        imp.project = self
        # send a notification to all subscribers that the notification is left
        inotif = ImprovementNotif(user=user.username, obj=imp)
        distribute_event(self, inotif, "comment", subscriber_send=True)
        # Send the actual comment to the improvement event queue
        c = Comment(user=user.username,
                    body=body)
        distribute_event(self, c, "comment", self_send=True)


class ImpSubscriber(db.EmbeddedDocument):
    user = db.ReferenceField('User')
    comment_notif = db.BooleanField(default=True)
    vote = db.BooleanField(default=False)
    status = db.BooleanField(default=True)  # status change event
    donate = db.BooleanField(default=True)


class ProjectSubscriber(db.EmbeddedDocument):
    user = db.ReferenceField('User')
    comment_notif = db.BooleanField(default=True)
    improvement = db.BooleanField(default=False)


class UserSubscriber(db.EmbeddedDocument, SubscribableMixin):
    user = db.ReferenceField('User')
    comment = db.BooleanField(default=True)
    vote = db.BooleanField(default=False)
    improvement = db.BooleanField(default=True)
    project = db.BooleanField(default=True)

class Event(db.EmbeddedDocument):
    # this represents the key in the subscriber entry that dictates whether it
    # should be publishe
    attr = None
    # template used to render the event
    template = ""
    pass

    def distribute(self):
        """ Copies the subdocument everywhere it needs to go """
        pass

    meta = {'allow_inheritance': True}

class ImprovementNotif(Event):
    """ Notification of a new improvement being created """
    user = db.ReferenceField('User')
    obj = db.GenericReferenceField()  # The object recieving the comment
    created_at = db.DateTimeField(default=datetime.datetime.now)


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


class User(db.Document, SubscribableMixin):
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    _password = db.StringField(max_length=128, min_length=5, required=True)
    username = db.StringField(max_length=32, min_length=3, primary_key=True)
    emails = db.ListField(db.EmbeddedDocumentField('Email'))
    github_token = db.StringField()
    subscribers = db.ListField(db.EmbeddedDocumentField(UserSubscriber))
    public_events = db.ListField(db.GenericEmbeddedDocumentField())
    events = db.ListField(db.GenericEmbeddedDocumentField())
    meta = {'indexes': [{'fields': ['github_token'], 'unique': True, 'sparse': True}]}

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, val):
        self._password = unicode(crypt.encode(val))

    def check_password(self, password):
        return crypt.check(self._password, password)

    @property
    def github(self):
        if 'github_user' not in session:
            session['github_user'] = github.get('user').data
        return session['github_user']


    @property
    def primary_email(self):
        for email in self.emails:
            if email.primary:
                return email

    @classmethod
    def create_user(cls, username, password, email_address):
        try:
            email = Email(address=email_address)
            user = cls(emails=[email], username=username)
            user.password = password
            user.save()
        except mongoengine.errors.OperationError:
            return False

        return user

    def get_abs_url(self):
        return url_for('main.user', username=unicode(self.username).encode('utf-8'))

    def get_projects(self):
        return Project.objects(maintainer=self)

    # Authentication callbacks
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.username)

    def __str__(self):
        return self.username

    def __repr__(self):
        return '<User %r>' % (self.username)

from featurelet.lib import distribute_event, catch_error_graceful
