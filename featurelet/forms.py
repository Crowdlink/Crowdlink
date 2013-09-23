from yota.nodes import *
import yota
from yota.validators import *

class RegisterForm(yota.Form):

    username = EntryNode(css_class="form-control input-sm")
    password = PasswordNode(css_class="form-control input-sm")
    password_confirm = PasswordNode(title="Confirm", css_class="form-control input-sm")
    email = EntryNode(css_class="form-control input-sm")

    submit = SubmitNode(title="Register", css_class="btn-sm btn btn-success")
