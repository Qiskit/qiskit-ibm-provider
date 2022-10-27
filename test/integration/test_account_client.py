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

from qiskit.circuit import ClassicalRegister, QuantumCircuit, QuantumRegister

from qiskit_ibm_provider.api.client_parameters import ClientParameters
from qiskit_ibm_provider.api.clients import AccountClient, AuthClient
from qiskit_ibm_provider.api.exceptions import ApiError, RequestsApiError
from ..contextmanagers import custom_envs, no_envs
from ..decorators import (
    integration_test_setup,
    IntegrationTestDependencies,
)
from ..http_server import SimpleServer, ServerErrorOnceHandler, ClientErrorHandler
from ..ibm_test_case import IBMTestCase


class TestAccountClient(IBMTestCase):
    """Tests for AccountClient."""

    @classmethod
    @integration_test_setup()
    def setUpClass(cls, dependencies: IntegrationTestDependencies) -> None:
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.dependencies = dependencies
        cls.access_token = cls.dependencies.provider._auth_client.current_access_token()

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        quantum_register = QuantumRegister(2)
        classical_register = ClassicalRegister(2)
        self.qc1 = QuantumCircuit(quantum_register, classical_register, name="qc1")
        self.qc2 = QuantumCircuit(quantum_register, classical_register, name="qc2")
        self.qc1.h(quantum_register)
        self.qc2.h(quantum_register[0])
        self.qc2.cx(quantum_register[0], quantum_register[1])
        self.qc1.measure(quantum_register[0], classical_register[0])
        self.qc1.measure(quantum_register[1], classical_register[1])
        self.qc2.measure(quantum_register[0], classical_register[0])
        self.qc2.measure(quantum_register[1], classical_register[1])

        self.fake_server = None

    def tearDown(self) -> None:
        """Test level tear down."""
        super().tearDown()
        if self.fake_server:
            self.fake_server.stop()

    def _get_client(self):
        """Helper for instantiating an AccountClient."""
        return AccountClient(self.dependencies.provider._client_params)

    def test_exception_message(self):
        """Check exception has proper message."""
        client = self._get_client()
        with self.assertRaises(RequestsApiError) as exception_context:
            client.job_status("foo")

        raised_exception = exception_context.exception
        original_error = raised_exception.__cause__.response

        self.assertIn(
            original_error.reason,
            raised_exception.message,
            "Original error message not in raised exception",
        )
        self.assertIn(
            str(original_error.status_code),
            raised_exception.message,
            "Original error code not in raised exception",
        )

    def test_custom_client_app_header(self):
        """Check custom client application header."""
        custom_header = "batman"
        with custom_envs({"QISKIT_IBM_CUSTOM_CLIENT_APP_HEADER": custom_header}):
            client = self._get_client()
            self.assertIn(
                custom_header, client._session.headers["X-Qx-Client-Application"]
            )

        # Make sure the header is re-initialized
        with no_envs(["QISKIT_IBM_CUSTOM_CLIENT_APP_HEADER"]):
            client = self._get_client()
            self.assertNotIn(
                custom_header, client._session.headers["X-Qx-Client-Application"]
            )

    def test_job_submit_retry(self):
        """Test job submit requests get retried."""
        client = self._get_client()

        # Send request to local server.
        valid_data = {
            "id": "fake_id",
            "objectStorageInfo": {"uploadUrl": SimpleServer.URL},
            "job": {"id": "fake_id"},
        }
        self.fake_server = SimpleServer(handler_class=ServerErrorOnceHandler)
        self.fake_server.set_good_response(valid_data)
        self.fake_server.start()
        client.account_api.session.base_url = SimpleServer.URL

        client.job_submit("ibmq_qasm_simulator", {})

    def test_client_error(self):
        """Test client error."""
        client = self._get_client()
        self.fake_server = SimpleServer(handler_class=ClientErrorHandler)
        self.fake_server.start()
        client.account_api.session.base_url = SimpleServer.URL

        sub_tests = [
            {"error": "Bad client input"},
            {},
            {"bad request": "Bad client input"},
            "Bad client input",
        ]

        for err_resp in sub_tests:
            with self.subTest(response=err_resp):
                self.fake_server.set_error_response(err_resp)
                with self.assertRaises(RequestsApiError) as err_cm:
                    client.backend_status("ibmq_qasm_simulator")
                if err_resp:
                    self.assertIn("Bad client input", str(err_cm.exception))


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
