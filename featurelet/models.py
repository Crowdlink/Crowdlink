from flask import url_for

from featurelet import db
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


class Milestone(db.Document):
    pass


class Improvement(db.Document):
    brief = db.StringField(max_length=512, min_length=3)
    description = db.StringField()
    creator = db.ReferenceField('User')
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    project = db.ReferenceField('Project')
    vote_list = db.ListField(db.ReferenceField('User'))
    votes = db.IntField(default=0)
    url_key = db.StringField(unique=True)
    meta = {'indexes': [{'fields': ['url_key', 'project'], 'unique': True}]}

    def get_abs_url(self):
        return url_for('main.view_improvement',
                       purl_key=self.project.url_key,
                       user=self.project.maintainer.username,
                       url_key=self.url_key)

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


class Project(db.Document):
    id = db.ObjectIdField()
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    maintainer = db.ReferenceField('User')
    name = db.StringField(max_length=64, min_length=3)
    improvement_count = db.IntField(default=1)
    website = db.StringField(max_length=2048)
    source_url = db.StringField(max_length=2048)
    subscribers = db.ListField(db.GenericReferenceField())
    url_key = db.StringField(min_length=3, max_length=64)
    meta = {'indexes': [{'fields': ['url_key', 'maintainer'], 'unique': True}]}

    def get_abs_url(self):
        return url_for('main.view_project',
                       username=self.maintainer.username,
                       url_key=self.url_key)

    def get_improvements(self):
        return Improvement.objects(project=self)

class Subscriber(db.Document):
    username = db.ReferenceField('User')
    subscribee = db.GenericReferenceField()


class User(db.Document):
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    _password = db.StringField(max_length=1023, required=True)
    username = db.StringField(max_length=32, min_length=3, primary_key=True)
    emails = db.ListField(db.EmbeddedDocumentField('Email'))

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, val):
        self._password = unicode(crypt.encode(val))

    def check_password(self, password):
        return crypt.check(self._password, password)

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
