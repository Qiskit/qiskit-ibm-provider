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

"""Tests for Jupyter tools."""

from datetime import datetime, timedelta
from unittest import mock

from qiskit import transpile
from qiskit.test.reference_circuits import ReferenceCircuits

from qiskit_ibm_provider.jupyter.config_widget import config_tab
from qiskit_ibm_provider.jupyter.dashboard.backend_widget import make_backend_widget
from qiskit_ibm_provider.jupyter.dashboard.job_widgets import create_job_widget
from qiskit_ibm_provider.jupyter.dashboard.utils import BackendWithProviders
from qiskit_ibm_provider.jupyter.dashboard.watcher_monitor import _job_checker
from qiskit_ibm_provider.jupyter.gates_widget import gates_tab
from qiskit_ibm_provider.jupyter.jobs_widget import jobs_tab
from qiskit_ibm_provider.jupyter.qubits_widget import qubits_tab
from qiskit_ibm_provider.visualization.interactive.error_map import iplot_error_map
from ..decorators import (
    IntegrationTestDependencies,
    integration_test_setup,
)
from ..ibm_test_case import IBMTestCase


class TestBackendInfo(IBMTestCase):
    """Test backend information Jupyter widget."""

    @classmethod
    @integration_test_setup()
    def setUpClass(cls, dependencies: IntegrationTestDependencies) -> None:
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.dependencies = dependencies
        cls.backends = _get_backends(cls.dependencies.provider)

    def test_config_tab(self):
        """Test config tab."""
        for backend in self.backends:
            with self.subTest(backend=backend):
                tab_str = str(config_tab(backend))
                config = backend.configuration()
                status = backend.status()
                self.assertIn(config.backend_name, tab_str)
                self.assertIn(str(status.status_msg), tab_str)

    def test_qubits_tab(self):
        """Test qubits tab."""
        for backend in self.backends:
            with self.subTest(backend=backend):
                tab_str = str(qubits_tab(backend))
                props = backend.properties().to_dict()
                q0_t1 = round(props["qubits"][0][0]["value"], 3)
                q0_t2 = round(props["qubits"][0][1]["value"], 3)
                self.assertIn(str(q0_t1), tab_str)
                self.assertIn(str(q0_t2), tab_str)

    def test_gates_tab(self):
        """Test gates tab."""
        for backend in self.backends:
            with self.subTest(backend=backend):
                gates_tab(backend)

    def test_error_map_tab(self):
        """Test error map tab."""
        for backend in self.backends:
            with self.subTest(backend=backend):
                iplot_error_map(backend)

    def test_jobs_tab(self):
        """Test jobs tab."""
        for backend in self.backends:
            with self.subTest(backend=backend):
                limit = 5
                start_datetime = datetime.now() - timedelta(days=7)
                jobs_tab(backend, limit=limit, start_datetime=start_datetime)


class TestIBMDashboard(IBMTestCase):
    """Test backend information Jupyter widget."""

    @classmethod
    @integration_test_setup()
    def setUpClass(cls, dependencies: IntegrationTestDependencies):
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.dependencies = dependencies
        cls.backends = _get_backends(cls.dependencies.provider)

    def test_backend_widget(self):
        """Test devices tab."""
        for backend in self.backends:
            with self.subTest(backend=backend):
                backend_with_providers = BackendWithProviders(
                    backend=backend, providers=[self.dependencies.instance]
                )
                make_backend_widget(backend_with_providers)

    def test_job_widget(self):
        """Test jobs tab."""
        backend = self.dependencies.provider.get_backend("ibmq_qasm_simulator")
        job = backend.run(transpile(ReferenceCircuits.bell(), backend))
        create_job_widget(
            mock.MagicMock(), job, backend=backend.name, status=job.status().value
        )

    def test_watcher_monitor(self):
        """Test job watcher."""
        backend = self.dependencies.provider.get_backend("ibmq_qasm_simulator")
        job = backend.run(transpile(ReferenceCircuits.bell(), backend))
        _job_checker(job=job, status=job.status(), watcher=mock.MagicMock())


def _get_backends(provider):
    """Return backends for testing."""
    backends = []
    n_qubits = [1, 5]
    for n_qb in n_qubits:
        filtered_backends = provider.backends(
            operational=True, simulator=False, n_qubits=n_qb
        )
        if filtered_backends:
            backends.append(filtered_backends[0])
    return backends
