import hashlib
import base64
import json

currency = 'UAH'
PUBLIC_KEY = '**************************'
PRIVAT_KEY = '**************************'


class LiqPayAPI:
    def __init__(self, public_key, private_key):
        self.public_key = public_key
        self.private_key = private_key

    def create_payment_url(self, amount, description, order_id):
        data = {
            "public_key": self.public_key,
            "version": 3,
            "action": "pay",
            "amount": amount,
            "currency": currency,
            "description": description,
            "order_id": order_id,
            "sandbox": 1  # sandbox
        }
        data_encoded = base64.b64encode(json.dumps(data).encode()).decode()
        signature = base64.b64encode(hashlib.sha1((self.private_key + data_encoded + self.private_key).encode()).digest()).decode()

        return f"https://www.liqpay.ua/api/3/checkout?data={data_encoded}&signature={signature}"
