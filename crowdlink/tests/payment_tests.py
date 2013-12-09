import stripe

from crowdlink.tests import BaseTest, login_required
from pprint import pprint


class PaymentTests(BaseTest):
    @login_required
    def test_run_charge(self):
        # create a new token via the api. this is usually done via the JS side
        stripe.api_key = self.app.config['STRIPE_SECRET_KEY']
        token = stripe.Token.create(
            card={
                "number": '4242424242424242',
                "exp_month": 12,
                "exp_year": 2014,
                "cvc": '123'
            },
        )
        # serialize it
        dct_token = dict(token)
        dct_token['card'] = dict(token.card)
        data = {'amount': 1500,
                'token': dct_token}
        pprint(data)
        # run our transaction test
        res = self.json_post('/api/transaction', data=data)
        pprint(res.json)
        assert res.json['success']
