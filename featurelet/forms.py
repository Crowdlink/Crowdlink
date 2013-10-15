from flask import g

from yota.nodes import *
import yota
from yota.validators import *

from featurelet.validators import *
from featurelet.models import User, Project

class RegisterForm(yota.Form):
    username = EntryNode(validators=UnicodeStringValidator(minval=3))
    password = PasswordNode(validators=UnicodeStringValidator(minval=6))
    password_confirm = PasswordNode(title="Confirm")
    _valid_pass = Check(MatchingValidator(message="Password fields must match"), "password", "password_confirm")
    email = EntryNode(validators=EmailValidator())

    submit = SubmitNode(title="Sign Up", css_class="btn btn-info")

    @classmethod
    def get_sm(cls):
        self = cls()
        self.username.css_class = "input-sm"
        self.password.css_class = "input-sm"
        self.password_confirm.css_class = "input-sm"
        self.email.css_class = "input-sm"
        self.submit.css_class = "btn-sm btn btn-primary"
        self.start.action = '/signup'
        return self

    def validator(self):
        # Check for unique username
        try:
            user = User.objects.get(username=self.username.data)
        except User.DoesNotExist:
            pass
        else:
            self.username.add_error({'message': 'Username already in use!'})


class NewProjectForm(yota.Form):
    g_context = {'ajax': True, 'piecewise': True}
    ptitle = EntryNode(title='Project Name', validators=MinMaxValidator(3, 64))
    url_key = EntryNode(title='Url Key', template='url_key', validators=MinMaxValidator(3, 64))
    description = EntryNode(placeholder='(Optional)')
    website = EntryNode(placeholder='(Optional)')
    source = EntryNode(title="Souce Code Location", validators=RequiredValidator())
    create = SubmitNode(title="Create", css_class="btn btn-primary")

    def validator(self):
        # Check for unique project name
        try:
            project = Project.objects.get(maintainer=g.user.id, url_key=self.url_key.data)
        except Project.DoesNotExist:
            pass
        else:
            self.ptitle.add_error({'message': 'You already have a project named that'})


class CommentForm(yota.Form):
    body = TextareaNode(rows=25,
                        columns=100,
                        css_class="form-control",
                        template='epictext',
                        validators=MinLengthValidator(10))
    submit = SubmitNode(title="Add Comment")


class NewImprovementForm(yota.Form):
    g_context = {'ajax': True, 'piecewise': True}
    brief = EntryNode(validators=MinMaxValidator(3, 512))
    description = TextareaNode(rows=15)
    create = SubmitNode(title="Create", css_class="btn btn-primary")

    def validator(self):
        pass

class LoginForm(yota.Form):
    username = EntryNode(css_class="form-control input-sm")
    password = PasswordNode(css_class="form-control input-sm")
    submit = SubmitNode(title="Login", css_class="btn-sm btn btn-success")
