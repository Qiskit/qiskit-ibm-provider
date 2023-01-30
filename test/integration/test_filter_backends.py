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

"""Backends Filtering Test."""

from unittest import mock

from qiskit_ibm_provider import least_busy
from qiskit_ibm_provider.ibm_backend import IBMBackend
from ..decorators import (
    IntegrationTestDependencies,
    integration_test_setup_with_backend,
)
from ..ibm_test_case import IBMTestCase


class TestBackendFilters(IBMTestCase):
    """Qiskit Backend Filtering Tests."""

    @classmethod
    @integration_test_setup_with_backend()
    def setUpClass(
        cls, backend: IBMBackend, dependencies: IntegrationTestDependencies
    ) -> None:
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.backend = backend
        cls.dependencies = dependencies

    def test_filter_config_properties(self):
        """Test filtering by configuration properties."""
        # Use the default backend as a reference for the filter.
        n_qubits = self.backend.configuration().n_qubits

        filtered_backends = self.dependencies.provider.backends(
            n_qubits=n_qubits, local=False, instance=self.dependencies.instance
        )
        self.assertTrue(filtered_backends)
        for filtered_backend in filtered_backends[:5]:
            with self.subTest(filtered_backend=filtered_backend):
                self.assertEqual(n_qubits, filtered_backend.configuration().n_qubits)
                self.assertFalse(filtered_backend.configuration().local)

    def test_filter_status_dict(self):
        """Test filtering by dictionary of mixed status/configuration properties."""
        filtered_backends = self.dependencies.provider.backends(
            operational=True,  # from status
            local=False,
            simulator=True,  # from configuration
            instance=self.dependencies.instance,
        )

        self.assertTrue(filtered_backends)
        for backend in filtered_backends[:5]:
            with self.subTest(backend=backend):
                self.assertTrue(backend.status().operational)
                self.assertFalse(backend.configuration().local)
                self.assertTrue(backend.configuration().simulator)

    def test_filter_config_callable(self):
        """Test filtering by lambda function on configuration properties."""
        filtered_backends = self.dependencies.provider.backends(
            filters=lambda x: (
                not x.configuration().simulator and x.configuration().n_qubits >= 5
            ),
            instance=self.dependencies.instance,
        )

        self.assertTrue(filtered_backends)
        for backend in filtered_backends[:5]:
            with self.subTest(backend=backend):
                self.assertFalse(backend.configuration().simulator)
                self.assertGreaterEqual(backend.configuration().n_qubits, 5)

    def test_filter_least_busy(self):
        """Test filtering by least busy function."""
        backends = self.dependencies.provider.backends(
            instance=self.dependencies.instance
        )
        least_busy_backend = least_busy(backends)
        self.assertTrue(least_busy_backend)

    def test_filter_least_busy_paused(self):
        """Test filtering by least busy function, with paused backend."""
        backends = self.dependencies.provider.backends(
            instance=self.dependencies.instance
        )
        if len(backends) < 2:
            self.skipTest("Test needs at least 2 backends.")
        paused_backend = backends[0]
        paused_status = paused_backend.status()
        paused_status.status_msg = "internal"
        paused_status.pending_jobs = 0
        paused_backend.status = mock.MagicMock(return_value=paused_status)

        least_busy_backend = least_busy(backends)
        self.assertTrue(least_busy_backend)
        self.assertNotEqual(least_busy_backend.name, paused_backend.name)
        self.assertEqual(least_busy_backend.status().status_msg, "active")

    def test_filter_min_num_qubits(self):
        """Test filtering by minimum number of qubits."""
        filtered_backends = self.dependencies.provider.backends(
            min_num_qubits=5,
            simulator=False,
            filters=lambda b: b.configuration().quantum_volume >= 10,
            instance=self.dependencies.instance,
        )

        self.assertTrue(filtered_backends)
        for backend in filtered_backends[:5]:
            with self.subTest(backend=backend):
                self.assertGreaterEqual(backend.configuration().n_qubits, 5)
                self.assertTrue(backend.configuration().quantum_volume, 10)

    def test_filter_dynamic_circuits(self):
        """Test filtering by dynamic ciruits."""
        filtered = self.dependencies.provider.backends(dynamic_circuits=True)
        for backend in filtered:
            self.assertTrue("qasm3" in backend.configuration().supported_features)
