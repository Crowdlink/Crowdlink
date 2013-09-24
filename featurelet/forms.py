from yota.nodes import *
import yota
from yota.validators import *
from featurelet.validators import *
from featurelet.models import User

class RegisterForm(yota.Form):
    username = EntryNode(
        css_class="form-control input-sm", validators=UnicodeStringValidator(minval=1))
    password = PasswordNode(
        css_class="form-control input-sm", validators=UnicodeStringValidator(minval=6))
    password_confirm = PasswordNode(title="Confirm", css_class="form-control input-sm")
    _valid_pass = Check(MatchingValidator(message="Password fields must match"), "password", "password_confirm")
    email = EntryNode(css_class="form-control input-sm",
                      validators=EmailValidator())

    submit = SubmitNode(title="Sign Up", css_class="btn-sm btn btn-success")

    def validator(self):

        # Check for unique username
        try:
            user = User.objects.get(username=self.username.data)
        except User.DoesNotExist:
            pass
        else:
            self.username.add_error({'message': 'Username already in use!', "error": True})


class LoginForm(yota.Form):
    username = EntryNode(css_class="form-control input-sm")
    password = PasswordNode(css_class="form-control input-sm")
    submit = SubmitNode(title="Login", css_class="btn-sm btn btn-success")
