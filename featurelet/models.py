from flask import url_for, session

from featurelet import db, github
from featurelet.events import *

import cryptacular.bcrypt
import datetime
import mongoengine
import re
import markdown2

crypt = cryptacular.bcrypt.BCRYPTPasswordManager()

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


class Improvement(db.Document):
    brief = db.StringField(max_length=512, min_length=3)
    description = db.StringField()
    creator = db.ReferenceField('User')
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    project = db.ReferenceField('Project')
    vote_list = db.ListField(db.ReferenceField('User'))
    votes = db.IntField(default=0)
    events = db.ListField(db.GenericEmbeddedDocumentField())
    url_key = db.StringField(unique=True)
    subscribers = db.ListField(db.ReferenceField('User'))
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
        self.url_key = re.sub('[^0-9a-zA-Z]', '-', self.brief[:100])

    def add_comment(self, user, body):
        comment = Comment(user=user,
                          body=body,
                          time=datetime.datetime.now())
        self.comments.append(comment)
        self.save()
        return comment


class Project(db.Document):
    id = db.ObjectIdField()
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    maintainer = db.ReferenceField('User')
    name = db.StringField(max_length=64, min_length=3)
    improvement_count = db.IntField(default=1)
    website = db.StringField(max_length=2048)
    source_url = db.StringField(max_length=2048)
    url_key = db.StringField(min_length=3, max_length=64)
    meta = {'indexes': [{'fields': ['url_key', 'maintainer'], 'unique': True}]}
    subscribers = db.ListField(db.EmbeddedDocumentField('UserSubscriber'))
    events = db.ListField(db.GenericEmbeddedDocumentField())

    def can_edit_imp(self, user):
        return self.maintainer == user

    def get_abs_url(self):
        return url_for('main.view_project',
                       username=self.maintainer.username,
                       url_key=self.url_key)

    def get_improvements(self):
        return Improvement.objects(project=self)


class UserSubscriber(db.EmbeddedDocument):
    username = db.ReferenceField('User')
    comment = db.BooleanField(default=True)
    vote = db.BooleanField(default=False)
    improvement = db.BooleanField(default=True)
    project = db.BooleanField(default=True)


class CommentNotif(db.EmbeddedDocument):
    username = db.ReferenceField('User')


class User(db.Document):
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    _password = db.StringField(max_length=128, min_length=5, required=True)
    username = db.StringField(max_length=32, min_length=3, primary_key=True)
    emails = db.ListField(db.EmbeddedDocumentField('Email'))
    github_token = db.StringField(unique=True)
    subscribers = db.ListField(db.EmbeddedDocumentField(UserSubscriber))
    public_events = db.ListField(db.GenericEmbeddedDocumentField())

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
        return unicode(self.id)

    def __str__(self):
        return self.username

    def __repr__(self):
        return '<User %r>' % (self.username)
