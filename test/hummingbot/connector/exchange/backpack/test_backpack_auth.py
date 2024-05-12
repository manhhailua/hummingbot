import asyncio
import hashlib
import hmac
from copy import copy
from unittest import TestCase
from unittest.mock import MagicMock

from typing_extensions import Awaitable

from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class BackpackAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "testApiKey"
        self._secret = "testSecret"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        params = {
            "price": "0.1",
            "quantity": 1,
            "side": "BUY",
            "symbol": "LTCBTC",
            "timeInForce": "GTC",
            "type": "LIMIT",
        }
        full_params = copy(params)

        auth = BackpackAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.GET, params=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        full_params.update({"timestamp": 1234567890000, "window": 5000})
        encoded_params = "&".join([f"{key}={value}" for key, value in full_params.items()])
        expected_signature = hmac.new(
            self._secret.encode("utf-8"), encoded_params.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        self.assertEqual(now * 1e3, configured_request.headers["X-Timestamp"])
        self.assertEqual(expected_signature, configured_request.headers["X-Signature"])
