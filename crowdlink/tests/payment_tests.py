from crowdlink.tests import (BaseTest, login_required, stripe_bank_token_real,
                             stripe_card_token_real)
from pprint import pprint


class PaymentTests(BaseTest):
    # Charge api
    # =========================================================================
    @login_required()
    def test_run_charge(self):
        # create a new token via the api. this is usually done via the JS side
        data = {'amount': 1500,
                'token': stripe_card_token_real()}
        pprint(data)
        # run our charge test
        res = self.json_post('/api/charge', data=data)
        pprint(res.json)
        assert res.json['success']
        assert isinstance(res.json['objects'][0]['id'], int)
        assert res.json['objects'][0]['id'] > 0

    # Recipeint api
    # =========================================================================
    @login_required()
    def test_recipient_create(self):
        """ test recipeint creation """
        # run our recipient test
        data = {'name': 'John Doe',
                'corporation': False,
                'token': stripe_bank_token_real()}
        res = self.json_post('/api/recipient', data=data)
        pprint(res.json)
        assert res.json['success']
        assert isinstance(res.json['objects'][0]['id'], int)
        assert res.json['objects'][0]['id'] > 0

    # Transfer api
    # =========================================================================
    @login_required()
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
