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

"""Tests for the IBMProvider class."""

# import os
from datetime import datetime
from unittest import skip, mock

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.compiler import transpile
from qiskit.providers.exceptions import QiskitBackendNotFoundError
from qiskit.providers.models.backendproperties import BackendProperties
from qiskit.test import providers, slow_test

from qiskit_ibm_provider import hub_group_project
from qiskit_ibm_provider.api.clients import AccountClient
from qiskit_ibm_provider.api.exceptions import RequestsApiError

# from qiskit_ibm_provider.apiconstants import QISKIT_IBM_API_URL

# from qiskit_ibm_provider.credentials.hub_group_project_id import HubGroupProjectID
# from ..contextmanagers import custom_qiskitrc, no_envs, CREDENTIAL_ENV_VARS
# from qiskit_ibm_provider.exceptions import (
#     IBMProviderError,
# )
from qiskit_ibm_provider.ibm_backend import IBMBackend
from qiskit_ibm_provider.ibm_backend_service import IBMBackendService
from qiskit_ibm_provider.ibm_provider import IBMProvider
from ..decorators import (
    IntegrationTestDependencies,
    integration_test_setup,
    integration_test_setup_with_backend,
)
from ..ibm_test_case import IBMTestCase

# from ..utils import get_hgp

API_URL = "https://api.quantum-computing.ibm.com/api"
AUTH_URL = "https://auth.quantum-computing.ibm.com/api"


class TestIBMProviderEnableAccount(IBMTestCase):
    """Tests for IBMProvider."""

    # Enable Account Tests

    @classmethod
    @integration_test_setup()
    def setUpClass(cls, dependencies: IntegrationTestDependencies) -> None:
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.dependencies = dependencies

    def test_provider_init_token(self):
        """Test initializing IBMProvider with only API token."""
        # pylint: disable=unused-argument
        provider = IBMProvider(token=self.dependencies.token)
        self.assertIsInstance(provider, IBMProvider)
        self.assertEqual(provider._client_params.token, self.dependencies.token)

    def test_pass_unreachable_proxy(self):
        """Test using an unreachable proxy while enabling an account."""
        proxies = {
            "urls": {
                "http": "http://user:password@127.0.0.1:5678",
                "https": "https://user:password@127.0.0.1:5678",
            }
        }
        with self.assertRaises(RequestsApiError) as context_manager:
            IBMProvider(self.dependencies.token, self.dependencies.url, proxies=proxies)
        self.assertIn("ProxyError", str(context_manager.exception))

    # TODO: check why test fails
    @skip("assertLogs is not working even though warning is logged")
    def test_discover_backend_failed(self):
        """Test discovering backends failed."""
        with mock.patch.object(
            AccountClient,
            "list_backends",
            return_value=[{"backend_name": "bad_backend"}],
        ):
            with self.assertLogs(
                hub_group_project.logger, level="WARNING"
            ) as context_manager:
                IBMProvider(self.dependencies.token, self.dependencies.url)
        self.assertIn("bad_backend", str(context_manager.output))


# @skipIf(os.name == "nt", "Test not supported in Windows")
# class TestIBMProviderAccounts(IBMTestCase):
#     """Tests for account handling."""

#     @classmethod
#     def setUpClass(cls):
#         """Initial class setup."""
#         super().setUpClass()
#         cls.token = "API_TOKEN"

#     def test_provider_init_saved_account(self, qe_token, qe_url):
#         """Test initializing IBMProvider with credentials from qiskitrc file."""
#         if qe_url != QISKIT_IBM_API_URL:
#             # save expects an auth production URL.
#             self.skipTest("Test requires production auth URL")

#         with custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
#             IBMProvider.save_account(qe_token, url=qe_url)
#             provider = IBMProvider()

#         self.assertIsInstance(provider, IBMProvider)
#         self.assertEqual(provider.backend._default_hgp.credentials.token, qe_token)
#         self.assertEqual(provider.backend._default_hgp.credentials.auth_url, qe_url)

#     def test_load_account_saved_provider(self, qe_token, qe_url):
#         """Test loading an account that contains a saved hub/group/project."""
#         if qe_url != QISKIT_IBM_API_URL:
#             # .save_account() expects an auth production URL.
#             self.skipTest("Test requires production auth URL")

#         # Get a non default hub/group/project.
#         non_default_hgp = get_hgp(qe_token, qe_url, default=False)

#         with custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
#             IBMProvider.save_account(
#                 token=qe_token,
#                 url=qe_url,
#                 hub=non_default_hgp.credentials.hub,
#                 group=non_default_hgp.credentials.group,
#                 project=non_default_hgp.credentials.project,
#             )
#             saved_provider = IBMProvider()
#             if saved_provider.backend._default_hgp != non_default_hgp:
#                 # Prevent tokens from being logged.
#                 saved_provider.backend._default_hgp.credentials.token = None
#                 non_default_hgp.credentials.token = None
#                 self.fail(
#                     "loaded default hgp ({}) != expected ({})".format(
#                         saved_provider.backend._default_hgp.credentials.__dict__,
#                         non_default_hgp.credentials.__dict__,
#                     )
#                 )

#         self.assertEqual(
#             saved_provider.backend._default_hgp.credentials.token, qe_token
#         )
#         self.assertEqual(
#             saved_provider.backend._default_hgp.credentials.auth_url, qe_url
#         )
#         self.assertEqual(
#             saved_provider.backend._default_hgp.credentials.hub,
#             non_default_hgp.credentials.hub,
#         )
#         self.assertEqual(
#             saved_provider.backend._default_hgp.credentials.group,
#             non_default_hgp.credentials.group,
#         )
#         self.assertEqual(
#             saved_provider.backend._default_hgp.credentials.project,
#             non_default_hgp.credentials.project,
#         )

#     def test_load_saved_account_invalid_hgp(self, qe_token, qe_url):
#         """Test loading an account that contains a saved hub/group/project that does not exist."""
#         if qe_url != QISKIT_IBM_API_URL:
#             # .save_account() expects an auth production URL.
#             self.skipTest("Test requires production auth URL")

#         # Hub, group, project in correct format but does not exists.
#         invalid_hgp_to_store = "invalid_hub/invalid_group/invalid_project"
#         with custom_qiskitrc(), no_envs(CREDENTIAL_ENV_VARS):
#             hgp_id = HubGroupProjectID.from_stored_format(invalid_hgp_to_store)
#             with self.assertRaises(IBMProviderError) as context_manager:
#                 IBMProvider.save_account(
#                     token=qe_token,
#                     url=qe_url,
#                     hub=hgp_id.hub,
#                     group=hgp_id.group,
#                     project=hgp_id.project,
#                 )
#                 IBMProvider()

#             self.assertIn(
#                 "No hub/group/project matches the specified criteria",
#                 str(context_manager.exception),
#             )

#     def test_active_account(self, qe_token, qe_url):
#         """Test get active account"""
#         provider = IBMProvider(qe_token, qe_url)
#         active_account = provider.active_account()
#         self.assertIsNotNone(active_account)
#         self.assertEqual(active_account["token"], qe_token)
#         self.assertEqual(active_account["url"], qe_url)


class TestIBMProviderHubGroupProject(IBMTestCase):
    """Tests for IBMProvider HubGroupProject related methods."""

    def _initialize_provider(self, qe_token=None, qe_url=None):
        """Initialize and return provider."""
        return IBMProvider(qe_token, qe_url)

    @integration_test_setup()
    def setUp(self, dependencies: IntegrationTestDependencies) -> None:
        """Initial test setup."""
        # pylint: disable=arguments-differ
        super().setUp()
        self.provider = self._initialize_provider(dependencies.token, dependencies.url)
        self.instance = dependencies.instance

    # TODO: check why test fails
    @skip("default hgp is different from set given hgp")
    def test_get_hgp(self):
        """Test get single hgp."""
        hgp = self.provider._get_hgp(instance=self.instance)
        self.assertEqual(self.provider.backend._default_hgp, hgp)

    def test_get_hgps_with_filter(self):
        """Test get hgps with a filter."""
        hgp = self.provider._get_hgps()[0]
        self.assertEqual(self.provider.backend._default_hgp, hgp)

    def test_get_hgps_no_filter(self):
        """Test get hgps without a filter."""
        hgps = self.provider._get_hgps()
        self.assertIn(self.provider.backend._default_hgp, hgps)


class TestIBMProviderServices(IBMTestCase, providers.ProviderTestCase):
    """Tests for services provided by the IBMProvider class."""

    provider_cls = IBMProvider
    backend_name = "ibmq_qasm_simulator"

    @classmethod
    @integration_test_setup_with_backend(simulator=False)
    def setUpClass(
        cls, backend: IBMBackend, dependencies: IntegrationTestDependencies
    ) -> None:
        """Initial class setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.instance = dependencies.instance
        cls.real_device_backend = backend
        cls.dependencies = dependencies

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        quantum_register = QuantumRegister(1)
        classical_register = ClassicalRegister(1)
        self.qc1 = QuantumCircuit(quantum_register, classical_register, name="circuit0")
        self.qc1.h(quantum_register[0])
        self.qc1.measure(quantum_register, classical_register)

    def test_remote_backends_exist_real_device(self):
        """Test if there are remote backends that are devices."""
        remotes = self.dependencies.provider.backends(
            simulator=False, instance=self.instance
        )
        self.assertTrue(remotes)

    def test_remote_backends_exist_simulator(self):
        """Test if there are remote backends that are simulators."""
        remotes = self.dependencies.provider.backends(
            simulator=True, instance=self.instance
        )
        self.assertTrue(remotes)

    def test_remote_backend_status(self):
        """Test backend_status."""
        remotes = self.dependencies.provider.backends(instance=self.instance)
        for backend in remotes:
            _ = backend.status()

    def test_remote_backend_configuration(self):
        """Test backend configuration."""
        remotes = self.dependencies.provider.backends(instance=self.instance)
        for backend in remotes:
            _ = backend.configuration()

    def test_remote_backend_properties(self):
        """Test backend properties."""
        remotes = self.provider.backends(simulator=False, instance=self.instance)
        for backend in remotes:
            properties = backend.properties()
            if backend.configuration().simulator:
                self.assertEqual(properties, None)

    def test_headers_in_result_sims(self):
        """Test that the qobj headers are passed onto the results for sims."""
        backend = self.dependencies.provider.get_backend("ibmq_qasm_simulator")

        custom_header = {"x": 1, "y": [1, 2, 3], "z": {"a": 4}}
        circuits = transpile(self.qc1, backend=backend)

        # TODO Use circuit metadata for individual header when terra PR-5270 is released.
        # qobj.experiments[0].header.some_field = 'extra info'

        job = backend.run(circuits, header=custom_header)
        result = job.result()
        self.assertTrue(custom_header.items() <= job.header().items())
        self.assertTrue(custom_header.items() <= result.header.to_dict().items())
        # self.assertEqual(result.results[0].header.some_field, 'extra info')

    @slow_test
    def test_headers_in_result_devices(self):
        """Test that the qobj headers are passed onto the results for devices."""
        custom_header = {"x": 1, "y": [1, 2, 3], "z": {"a": 4}}

        # TODO Use circuit metadata for individual header when terra PR-5270 is released.
        # qobj.experiments[0].header.some_field = 'extra info'

        job = self.real_device_backend.run(
            transpile(self.qc1, backend=self.real_device_backend), header=custom_header
        )
        job.wait_for_final_state(wait=300, callback=self.simple_job_callback)
        result = job.result()
        self.assertTrue(custom_header.items() <= job.header().items())
        self.assertTrue(custom_header.items() <= result.header.to_dict().items())
        # self.assertEqual(result.results[0].header.some_field, 'extra info')

    def test_aliases(self):
        """Test that display names of devices map the regular names."""
        aliased_names = self.dependencies.provider.backend._aliased_backend_names()

        for display_name, backend_name in aliased_names.items():
            with self.subTest(display_name=display_name, backend_name=backend_name):
                try:
                    backend_by_name = self.dependencies.provider.get_backend(
                        backend_name
                    )
                except QiskitBackendNotFoundError:
                    # The real name of the backend might not exist
                    pass
                else:
                    backend_by_display_name = self.provider.get_backend(display_name)
                    self.assertEqual(backend_by_name, backend_by_display_name)
                    self.assertEqual(backend_by_display_name.name(), backend_name)

    def test_remote_backend_properties_filter_date(self):
        """Test backend properties filtered by date."""
        backends = self.dependencies.provider.backends(simulator=False)

        datetime_filter = datetime(2019, 2, 1).replace(tzinfo=None)
        for backend in backends:
            with self.subTest(backend=backend):
                properties = backend.properties(datetime=datetime_filter)
                if isinstance(properties, BackendProperties):
                    last_update_date = properties.last_update_date.replace(tzinfo=None)
                    self.assertLessEqual(last_update_date, datetime_filter)
                else:
                    self.assertEqual(properties, None)

    def test_provider_backend(self):
        """Test provider backend has correct attributes."""
        backend_attributes = {
            back
            for back in dir(self.dependencies.provider.backend)
            if isinstance(getattr(self.dependencies.provider.backend, back), IBMBackend)
        }
        backends = {
            back.name().lower()
            for back in self.dependencies.provider.backend._backends.values()
        }
        self.assertEqual(backend_attributes, backends)

    def test_provider_services(self):
        """Test provider services."""
        services = self.dependencies.provider.services()
        self.assertIn("backend", services)
        self.assertIsInstance(services["backend"], IBMBackendService)
        self.assertIsInstance(
            self.dependencies.provider.service("backend"), IBMBackendService
        )
        self.assertIsInstance(self.dependencies.provider.backend, IBMBackendService)
