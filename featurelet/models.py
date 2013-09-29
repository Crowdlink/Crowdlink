from featurelet import db
from featurelet.events import *

import cryptacular.bcrypt
import datetime
import mongoengine

crypt = cryptacular.bcrypt.BCRYPTPasswordManager()

class Email(db.EmbeddedDocument):
    address = db.StringField(max_length=1023, required=True, unique=True)
    verified = db.BooleanField(default=False)
    primary = db.BooleanField(default=True)


class Project(db.Document):
    id = db.ObjectIdField()
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    maintainer = db.ReferenceField('User')
    name = db.StringField(max_length=64, min_length=3)
    website = db.StringField(max_length=2048, min_length=3)
    source_url = db.StringField(max_length=2048, min_length=3)
    subscribers = db.ListField(db.GenericReferenceField())


class Subscriber(db.Document):
    username = db.ReferenceField('User')
    subscribee = db.GenericReferenceField()


class User(db.Document):
    id = db.ObjectIdField()
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    _password = db.StringField(max_length=1023, required=True)
    username = db.StringField(max_length=32, min_length=3, unique=True)
    emails = db.ListField(db.EmbeddedDocumentField('Email'))

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, val):
        print val
        self._password = unicode(crypt.encode(val))
        print self._password

    def check_password(self, password):
        print self._password
        print unicode(crypt.encode(password))
        return self._password == unicode(crypt.encode(password))

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

    def get_absolute_url(self):
        return url_for('user', username=unicode(self.username).encode('utf-8'))

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)

    def __repr__(self):
        return '<User %r>' % (self.nickname)
