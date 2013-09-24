from featurelet import db

import cryptacular.bcrypt
import datetime

class User(db.Document):
    id = db.ObjectIdField()
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    _password = db.StringField(max_length=1023, required=True)
    username = db.StringField(max_length=32, min_length=3, unique=True)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, val):
        self._password = unicode(crypt.encode(val))

    def get_absolute_url(self):
        return url_for('user', username=unicode(self.username).encode('utf-8'))
