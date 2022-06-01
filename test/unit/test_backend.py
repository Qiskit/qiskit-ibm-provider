# This code is part of Qiskit.
#
# (C) Copyright IBM 2022.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Test Backend Methods."""
import os
from unittest import mock, skipIf
from test.fake_account_client import BaseFakeAccountClient
from qiskit.test.mock.backends.bogota.fake_bogota import FakeBogota
from qiskit.transpiler.target import Target
from qiskit import transpile
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit_ibm_provider.ibm_backend import IBMBackend
from qiskit_ibm_provider.job.exceptions import IBMJobNotFoundError
from .mock.fake_provider import FakeProvider
from .test_ibm_job_states import BaseFakeAPI
from ..ibm_test_case import IBMTestCase


class TestIBMBackend(IBMTestCase):
    """Testing backend methods."""

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        self.backend = IBMBackend(
            FakeBogota().configuration(), mock.Mock(), api_client=BaseFakeAPI
        )

    def test_backend_properties(self):
        """Test backend properties."""
        self.assertIs(self.backend.properties(), None)

    def test_backend_target(self):
        """Test backend target method."""
        self.assertIsInstance(self.backend.target, Target)

    def test_backend_defaults(self):
        """Test backend defaults."""
        self.assertIs(self.backend.defaults(), None)

    def test_job_limits(self):
        """Test job limits."""
        self.assertEqual(self.backend.job_limit().active_jobs, 0)
        self.assertIs(self.backend.remaining_jobs_count(), None)

    def test_reservations(self):
        """Test resvervations."""
        self.assertEqual(self.backend.reservations(), [])

    def test_backend_attributes(self):
        """Test backend attributes."""
        self.assertEqual(self.backend.max_circuits, 900)
        self.assertEqual(self.backend.num_qubits, 5)
        self.assertEqual(self.backend.name, "fake_bogota")


@skipIf(os.name == "nt", "Test not supported in Windows")
class TestIBMBackendServce(IBMTestCase):
    """Test backend service methods."""

    def test_getting_backends(self):
        """Test getting backends from backend service."""
        service = FakeProvider()
        backends = service.backend.backends()
        common_backends = service.backend.backends(name="common_backend")
        self.assertTrue(len(backends) > 0)
        self.assertEqual(common_backends[0].name, "common_backend")

    def test_getting_jobs(self):
        """Test getting jobs from backend service."""
        service = FakeProvider()
        fake_client = BaseFakeAccountClient()
        backend = service.backend._default_hgp.backend("common_backend")
        backend._api_client = fake_client
        service.backend._default_hgp._api_client = fake_client
        circuit = transpile(ReferenceCircuits.bell())
        num_jobs = 3
        job_array = [backend.run(circuit) for _ in range(num_jobs)]
        job_ids = [job.job_id() for job in job_array]
        backend_service_job_ids = [job.job_id() for job in service.backend.jobs()]
        self.assertEqual(job_ids, backend_service_job_ids)

    def test_getting_single_job(self):
        """Test getting job from backend service."""
        service = FakeProvider()
        fake_client = BaseFakeAccountClient()
        backend = service.backend._default_hgp.backend("common_backend")
        backend._api_client = fake_client
        service.backend._default_hgp._api_client = fake_client
        circuit = transpile(ReferenceCircuits.bell())
        with self.assertRaises(IBMJobNotFoundError):
            service.backend.job("test")
        job = backend.run(circuit)
        self.assertEqual(service.backend.job(job.job_id()).job_id(), job.job_id())

    def test_getting_job_ids(self):
        """Test getting job ids from backend service."""
        service = FakeProvider()
        fake_client = BaseFakeAccountClient()
        backend = service.backend._default_hgp.backend("common_backend")
        backend._api_client = fake_client
        service.backend._default_hgp._api_client = fake_client
        circuit = transpile(ReferenceCircuits.bell())
        num_jobs = 3
        job_array = [backend.run(circuit) for _ in range(num_jobs)]
        for job in job_array:
            job.wait_for_final_state(wait=300)
        job_ids = [job.job_id() for job in job_array]
        backend_service_job_ids = [job["id"] for job in service.backend.job_ids(limit=3)]
        self.assertEqual(job_ids, backend_service_job_ids)
