import hashlib
import hmac
from collections import OrderedDict
from typing import Any, Dict, Tuple
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BackpackAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        """
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self._get_auth_headers(request))
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated.
        """
        return request

    def _get_auth_headers(self, request: RESTRequest) -> Dict[str, Any]:
        """
        Generates authentication headers for Backpack REST API

        :return: a dictionary with headers
        """
        signature, timestamp = self._sign_payload(request)

        return {
            "X-Timestamp": timestamp,
            "X-Window": request.headers.get("X-Window", 5000),
            "X-API-Key": self.api_key,
            "X-Signature": signature,
        }

    def _sign_payload(self, request: RESTRequest) -> Tuple[str, int]:
        """
        To generate a signature perform the following: https://docs.backpack.exchange/#section/Authentication/Signing-requests

        :return: a tuple with the signature and the timestamp
        """
        instruction = self._get_instruction(request)
        params = self._get_sorted_params(request)
        timestamp = int(self.time_provider.time() * 1e3)
        window = request.headers.get("X-Window", 5000)

        message = f"timestamp={timestamp}&window={window}"
        if params:
            message = f"{urlencode(params)}&{message}"
        if instruction:
            message = f"instruction={instruction}&{message}"

        # This message should be signed using the private key of the ED25519 keypair
        # that corresponds to the public key in the X-API-Key header. The signature
        # should then be base64 encoded and submitted in the X-Signature header.
        signature = hmac.new(self.secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

        return signature, timestamp

    def _get_instruction(self, request: RESTRequest) -> str:
        """
        Extracts the instruction by the request path

        :return: the instruction in str
        """
        instruction_mapping = {
            (RESTMethod.GET, "/api/v1/capital"): "balanceQuery",
            (RESTMethod.GET, "/wapi/v1/capital/deposit/address"): "depositAddressQuery",
            (RESTMethod.GET, "/wapi/v1/capital/deposits"): "depositQueryAll",
            (RESTMethod.GET, "/wapi/v1/history/fills"): "fillHistoryQueryAll",
            (RESTMethod.DELETE, "/api/v1/order"): "orderCancel",
            (RESTMethod.DELETE, "/api/v1/orders"): "orderCancelAll",
            (RESTMethod.POST, "/api/v1/order"): "orderExecute",
            (RESTMethod.GET, "/wapi/v1/history/orders"): "orderHistoryQueryAll",
            (RESTMethod.GET, "/api/v1/order"): "orderQuery",
            (RESTMethod.GET, "/api/v1/orders"): "orderQueryAll",
            (RESTMethod.POST, "/wapi/v1/capital/withdrawals"): "withdraw",
            (RESTMethod.GET, "/wapi/v1/capital/withdrawals"): "orderTest",
        }

        request_key = (request.method, request.path)
        return instruction_mapping.get(request_key, "")

    def _get_sorted_params(self, request: RESTRequest) -> Dict[str, Any]:
        """
        Sorts the request parameters in alphabetical order

        :return: a dictionary with the sorted parameters
        """
        params = request.params or {}
        body = request.body or {}
        params.update(body)
        sorted_params = OrderedDict(sorted(params.items(), key=lambda x: x[0]))
        return dict(sorted_params)
