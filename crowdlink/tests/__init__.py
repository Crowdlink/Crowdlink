import decorator
import crowdlink
import json
import os
import stripe

from pprint import pprint
from flask.ext.testing import TestCase
from flask.ext.login import login_user, logout_user
from crowdlink import root
from crowdlink.models import User


def stripe_card_token_real(number='4242424242424242'):
    token = stripe.Token.create(
        card={
            "number": number,
            "exp_month": 12,
            "exp_year": 2014,
            "cvc": '123'
        },
    )
    # serialize it
    dct_token = dict(token)
    dct_token['card'] = dict(token.card)
    return dct_token


def stripe_bank_token_real(
        routing_number='110000000', account_number='000123456789'):
    # create a new token via the api. this is usually done via the JS side
    token = stripe.Token.create(
        bank_account={
            "country": 'US',
            "routing_number": routing_number,
            "account_number": account_number
        },
    )
    # serialize it
    dct_token = dict(token)
    dct_token['bank_account'] = dict(token.bank_account)
    return dct_token


def stripe_bank_token_mock():
    return {
        "id": "btok_36fWMtZ9rbYXu9",
        "livemode": False,
        "created": 1386826725,
        "used": False,
        "object": "token",
        "type": "bank_account",
        "bank_account": {
            "object": "bank_account",
            "id": "ba_1036fW27yR8C5wlpBuk8GZNb",
            "bank_name": "STRIPE TEST BANK",
            "last4": "6789",
            "country": "US",
            "currency": "usd",
            "validated": False,
            "verified": False,
            "fingerprint": "4da146xwbFRdSqcm"
        }
    }


def stripe_card_token_mock():
    return {
        "id": "tok_1039Vc27yR8C5wlpMxrRRy4p",
        "livemode": False,
        "created": 1387481788,
        "used": False,
        "object": "token",
        "type": "card",
        "card": {
            "id": "card_1039Vc27yR8C5wlpsihVqpZz",
            "object": "card",
            "last4": "4242",
            "type": "Visa",
            "exp_month": 8,
            "exp_year": 2014,
            "fingerprint": "gBSDyxpPKbbCPXqw",
            "customer": None,
            "country": "US",
            "name": None,
            "address_line1": None,
            "address_line2": None,
            "address_city": None,
            "address_state": None,
            "address_zip": None,
            "address_country": None
        }
    }

def login_required(username='crowdlink', password='testing'):
    """ Decorator that logs in the user under a request context as well as a
    testing cleint """
    def login_required(func, self, *args, **kwargs):
        self.user = self.db.session.query(User).filter_by(username=username).one()
        self.login(username, password)['objects'][0]
        login_user(self.user)
        func(self)
        self.logout()
        logout_user()

    return decorator.decorator(login_required)


def login_required_ctx(username='crowdlink', password='testing'):
    """ Decorator for loggin in the user under a request context. Helpful for
    testing """
    def login_required_ctx(f, *args, **kwargs):
        self = args[0]
        self.user = self.db.session.query(User).filter_by(username=username).one()
        login_user(self.user)
        f(self)
        logout_user()

    return decorator.decorator(login_required_ctx)


class BaseTest(TestCase):
    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()

    def json_post(self, url, data):
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json')

    def json_get(self, url, data):
        return self.client.get(
            url,
            query_string=data,
            content_type='application/json')

    def json_put(self, url, data):
        return self.client.put(
            url,
            data=json.dumps(data),
            content_type='application/json')

    def json_patch(self, url, data):
        return self.client.open(
            url,
            method='PATCH',
            data=json.dumps(data),
            content_type='application/json')

    def create_app(self):
        app = crowdlink.create_app()
        app.config['TESTING'] = True
        # Remove flasks stderr handler, replace with stdout so nose can
        # capture properly
        del app.logger.handlers[0]
        try:
            config_vars = json.loads(file(root + '/testing.json').read())
            config_vars = dict(config_vars['public'].items() + config_vars['private'].items())
            for key, val in config_vars.items():
                app.config[key] = val
        except IOError:
            app.logger.warning("Unable to import testing.json, not using "
                               "testing overrides", exc_info=True)
        with app.app_context():
            self.db = crowdlink.db
            os.system("psql -U crowdlink -h localhost crowdlink_testing -f " + root + "/assets/test_provision.sql > /dev/null 2>&1")
            stripe.api_key = app.config['stripe_secret_key']
        return app

    def login(self, username, password):
        data = {
            'identifier': username,
            'password': password,
            '__action': 'login',
            '__cls': True
        }
        ret = self.json_patch('/api/user', data=data).json
        pprint(ret)
        assert ret['success']
        return ret

    def logout(self):
        ret = self.client.get('/api/logout', follow_redirects=True)
        assert ret.json['access_denied']
        return ret.json

