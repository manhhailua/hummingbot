import unittest

import hummingbot.connector.exchange.backpack.backpack_constants as CONSTANTS
from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils


class BackpackUtilTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "exchange"
        expected_url = CONSTANTS.REST_URL.format(domain) + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url, domain))

    def test_private_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "exchange"
        expected_url = CONSTANTS.REST_URL.format(domain) + path_url
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url, domain))
