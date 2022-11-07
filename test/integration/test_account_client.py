# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for the AccountClient class."""

import re

from qiskit_ibm_provider.api.client_parameters import ClientParameters
from qiskit_ibm_provider.api.clients import AuthClient
from qiskit_ibm_provider.api.exceptions import ApiError
from ..decorators import (
    integration_test_setup,
    IntegrationTestDependencies,
)
from ..ibm_test_case import IBMTestCase


class TestAuthClient(IBMTestCase):
    """Tests for the AuthClient."""

    @classmethod
    @integration_test_setup()
    def setUpClass(cls, dependencies: IntegrationTestDependencies) -> None:
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.dependencies = dependencies

    def test_valid_login(self):
        """Test valid authentication."""
        client = AuthClient(self.dependencies.provider._client_params)
        self.assertTrue(client.access_token)
        self.assertTrue(client.api_token)

    def test_url_404(self):
        """Test login against a 404 URL"""
        url_404 = re.sub(r"/api.*$", "/api/TEST_404", self.dependencies.url)
        with self.assertRaises(ApiError):
            _ = AuthClient(ClientParameters(token=self.dependencies.token, url=url_404))

    def test_invalid_token(self):
        """Test login using invalid token."""
        with self.assertRaises(ApiError):
            _ = AuthClient(
                ClientParameters(token="INVALID_TOKEN", url=self.dependencies.url)
            )

    def test_url_unreachable(self):
        """Test login against an invalid (malformed) URL."""
        with self.assertRaises(ApiError):
            _ = AuthClient(
                ClientParameters(token=self.dependencies.token, url="INVALID_URL")
            )

    def test_api_version(self):
        """Check the version of the QX API."""
        iqx_url = self.dependencies.provider._account.url
        iqx_token = self.dependencies.provider._account.token
        client_params = self.dependencies.provider._client_params
        client_params.url = iqx_url
        client_params.token = iqx_token
        client = AuthClient(client_params)
        version = client.api_version()
        self.assertIsNotNone(version)

    def test_user_urls(self):
        """Check the user urls of the QX API."""
        client = AuthClient(self.dependencies.provider._client_params)
        user_urls = client.user_urls()
        self.assertIsNotNone(user_urls)
        self.assertTrue("http" in user_urls and "ws" in user_urls)

    def test_user_hubs(self):
        """Check the user hubs of the QX API."""
        client = AuthClient(self.dependencies.provider._client_params)
        user_hubs = client.user_hubs()
        self.assertIsNotNone(user_hubs)
        for user_hub in user_hubs:
            with self.subTest(user_hub=user_hub):
                self.assertTrue(
                    "hub" in user_hub and "group" in user_hub and "project" in user_hub
                )
