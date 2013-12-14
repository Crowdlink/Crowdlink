import stripe
import logging

from crowdlink.tests import BaseTest, login_required
from crowdlink.util import stripe_bank_token, stripe_card_token
from pprint import pprint


class PaymentTests(BaseTest):
    # Transaction api
    # =========================================================================
    @login_required
    def test_run_charge(self):
        # create a new token via the api. this is usually done via the JS side
        stripe.api_key = self.app.config['STRIPE_SECRET_KEY']
        data = {'amount': 1500,
                'token': stripe_card_token()}
        pprint(data)
        # run our transaction test
        res = self.json_post('/api/transaction', data=data)
        pprint(res.json)
        assert res.json['success']
        assert isinstance(res.json['transaction']['id'], int)
        assert res.json['transaction']['id'] > 0

    # Recipeint api
    # =========================================================================
    @login_required
    def test_recipient_create(self):
        """ test recipeint creation """
        stripe.api_key = self.app.config['STRIPE_SECRET_KEY']
        # run our recipient test
        data = {'name': 'John Doe',
                'corporation': False,
                'tax_id': '',
                'token': stripe_bank_token()}
        #logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
        res = self.json_post('/api/recipient', data=data)
        #logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
        pprint(res.json)
        assert res.json['success']
        assert isinstance(res.json['recipient']['id'], int)
        assert res.json['recipient']['id'] > 0

    # Transfer api
    # =========================================================================
    @login_required
    def test_transfer_create(self):
        """ can we make a new transfer? """
        """
        # run our recipient test
        data = {'amount': 1000}
        res = self.json_post('/api/transfer', data=data)
        pprint(res.json)
        assert res.json['success']
        assert isinstance(res.json['recipient']['id'], int)
        assert res.json['recipient']['id'] > 0
        """
