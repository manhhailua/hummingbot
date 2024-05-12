import base64
from collections import OrderedDict
from typing import Any, Dict, Tuple
from urllib.parse import urlencode, urlparse

from cryptography.hazmat.primitives.asymmetric import ed25519

import hummingbot.connector.exchange.backpack.backpack_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BackpackAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = ed25519.Ed25519PrivateKey.from_private_bytes(base64.b64decode(secret_key))
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
        signature, timestamp, window = self._sign_payload(request)

        return {
            "X-Timestamp": str(timestamp),
            "X-Window": str(window),
            "X-API-Key": self.api_key,
            "X-Signature": signature,
        }

    def _sign_payload(self, request: RESTRequest) -> Tuple[str, int, int]:
        """
        To generate a signature perform the following: https://docs.backpack.exchange/#section/Authentication/Signing-requests

        :return: a tuple with the signature and the timestamp
        """
        instruction = self._get_instruction(request)
        params = self._get_sorted_params(request)
        timestamp = int(self.time_provider.time() * 1e3)
        window = request.headers.get("X-Window", 5000) if type(request.headers) is dict else 5000

        message = f"timestamp={timestamp}&window={window}"
        if params:
            message = f"{urlencode(params)}&{message}"
        if instruction:
            message = f"instruction={instruction}&{message}"

        signature = base64.b64encode(self.secret_key.sign(message.encode())).decode()

        return signature, timestamp, window

    def _get_instruction(self, request: RESTRequest) -> str:
        """
        Extracts the instruction by the request path

        :return: the instruction in str
        """
        instruction_mapping = {
            (RESTMethod.GET, f"{CONSTANTS.API_PREFIX_V1}/capital"): "balanceQuery",
            (RESTMethod.GET, f"{CONSTANTS.W_API_PREFIX_V1}/capital/deposit/address"): "depositAddressQuery",
            (RESTMethod.GET, f"{CONSTANTS.W_API_PREFIX_V1}/capital/deposits"): "depositQueryAll",
            (RESTMethod.GET, f"{CONSTANTS.W_API_PREFIX_V1}/history/fills"): "fillHistoryQueryAll",
            (RESTMethod.DELETE, f"{CONSTANTS.API_PREFIX_V1}/order"): "orderCancel",
            (RESTMethod.DELETE, f"{CONSTANTS.API_PREFIX_V1}/orders"): "orderCancelAll",
            (RESTMethod.POST, f"{CONSTANTS.API_PREFIX_V1}/order"): "orderExecute",
            (RESTMethod.GET, f"{CONSTANTS.W_API_PREFIX_V1}/history/orders"): "orderHistoryQueryAll",
            (RESTMethod.GET, f"{CONSTANTS.API_PREFIX_V1}/order"): "orderQuery",
            (RESTMethod.GET, f"{CONSTANTS.API_PREFIX_V1}/orders"): "orderQueryAll",
            (RESTMethod.POST, f"{CONSTANTS.W_API_PREFIX_V1}/capital/withdrawals"): "withdraw",
            (RESTMethod.GET, f"{CONSTANTS.W_API_PREFIX_V1}/capital/withdrawals"): "orderTest",
        }

        request_key = (request.method, urlparse(request.url).path)
        return instruction_mapping.get(request_key, "")

    def _get_sorted_params(self, request: RESTRequest) -> Dict[str, Any]:
        """
        Sorts the request parameters in alphabetical order

        :return: a dictionary with the sorted parameters
        """
        params = request.params or {}
        body = request.data or {}
        params.update(body)
        sorted_params = OrderedDict(sorted(params.items(), key=lambda x: x[0]))
        return dict(sorted_params)
