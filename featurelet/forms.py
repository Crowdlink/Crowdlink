from flask import g

from yota import Check, Form, Listener, Blueprint
import yota.validators as validators
import yota.nodes as nodes
from yota.exceptions import *

from featurelet.models import *


class UnicodeString(object):

    def __init__(self,
                 spmsg=None,
                 minmsg=None,
                 maxmsg=None,
                 minval=3,
                 maxval=28):
        self.minval = minval
        self.maxval = maxval
        self.spmsg = spmsg if spmsg else "Usernames cannot contain spaces"
        self.minmsg = minmsg if minmsg else "Minimum of {0} characters".format(minval)
        self.maxmsg = maxmsg if maxmsg else "No more than {0} characters".format(maxval)

    def __call__(self, username):
        if ' ' in username.data:
            username.add_error({'message': self.spmsg})
        if len(username.data) < self.minval:
            username.add_error({'message': self.minmsg})
        if len(username.data) > self.maxval:
            username.add_error({'message': self.maxmsg})


def replicate_validators(form):
    """ this function runs through the linked model attributes and replicates
    appropriate validators for them, drying up parity between mongoengine and
    yota """

    # look at all the nodes and detect the model they match to
    for node in form._node_list:
        try:
            field = node.model
        except AttributeError:
            continue
        else:
            if field.required:
                form.insert_validator(Check(validators.Required(), node._attr_name))
            ftype = type(field).__name__
            if ftype == "StringField":
                kwarg = {}
                if field.max_length:
                    kwarg['max'] = field.max_length
                if field.min_length:
                    kwarg['min'] = field.min_length
                if kwarg:
                    form.insert_validator(Check(validators.MinMax(**kwarg), node._attr_name))
            elif ftype == "IntField":
                # XXX: If we implement min/max for integer field, this needs filled in
                pass
            elif ftype == "URLField":
                form.insert_validator(Check(validators.URL(), node._attr_name))
            elif ftype == "EmailField":
                form.insert_validator(Check(validators.Email(), node._attr_name))


class ModelForm(Form):
    def __init__(self, *args, **kwargs):
        super(ModelForm, self).__init__(*args, **kwargs)
        replicate_validators(self)

class RegisterForm(ModelForm):
    username = nodes.Entry(model=User.username)
    password = nodes.Password(validators=UnicodeString(minval=5, maxval=32))
    password_confirm = nodes.Password(title="Confirm")
    _valid_pass = Check(validators.Matching(message="Password fields must match"), "password", "password_confirm")
    email = nodes.Entry(validators=validators.Email())

    submit = nodes.Submit(title="Sign Up", css_class="btn btn-info")

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


class PasswordForm(Form):
    title = "Password"

    hidden = {'form': 'password'}
    password = nodes.Password(validators=UnicodeString(minval=5, maxval=32))
    password_confirm = nodes.Password(title="Confirm")
    _valid_pass = Check(validators.Matching(message="Password fields must match"),
                        "password",
                        "password_confirm")
    submit = nodes.Submit(title="Update", css_class="btn-info btn")


class NewProjectForm(ModelForm):
    g_context = {'ajax': True, 'piecewise': True}

    ptitle = nodes.Entry(title='Project Name', model=Project.name)
    url_key = nodes.Entry(title='Url Key', template='url_key', model=Project.url_key)
    description = nodes.Entry(placeholder='(Optional)')
    website = nodes.Entry(placeholder='(Optional)')
    source = nodes.Entry(title="Souce Code Location", validators=validators.Required())
    create = nodes.Submit(title="Create", css_class="btn btn-primary")

    def validator(self):
        # Check for unique project name
        try:
            project = Project.objects.get(maintainer=g.user.id, url_key=self.url_key.data)
        except Project.DoesNotExist:
            pass
        else:
            self.ptitle.add_error({'message': 'You already have a project named that'})


class CommentForm(ModelForm):
    title = "Leave a comment"
    body = nodes.Textarea(rows=12,
                        columns=100,
                        model=Comment.body,
                        css_class="form-control")
    submit = nodes.Submit(title="Add Comment")


class NewImprovementForm(ModelForm):
    g_context = {'ajax': True, 'piecewise': True}
    brief = nodes.Entry(model=Improvement.brief)
    description = nodes.Textarea(rows=15, model=Improvement.description)
    create = nodes.Submit(title="Create", css_class="btn btn-primary")


class LoginForm(Form):
    username = nodes.Entry(css_class="form-control input-sm")
    password = nodes.Password(css_class="form-control input-sm")
    submit = nodes.Submit(title="Login", css_class="btn-sm btn btn-success")


