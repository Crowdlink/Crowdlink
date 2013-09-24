from yota.nodes import *
import yota
from yota.validators import *
from featurelet.validators import *

class RegisterForm(yota.Form):
    username = EntryNode(css_class="form-control input-sm", validators=UnicodeStringValidator())
    password = PasswordNode(css_class="form-control input-sm", validators=UnicodeStringValidator()
    password_confirm = PasswordNode(title="Confirm", css_class="form-control input-sm")
    _valid_pass = Check(MatchingValidator(message="Password fields must match"), "password", "password_confirm")
    email = EntryNode(css_class="form-control input-sm",
                      validators=EmailValidator())

    submit = SubmitNode(title="Sign Up", css_class="btn-sm btn btn-success")
