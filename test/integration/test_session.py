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

"""IBMBackend Test."""

from qiskit.result import Result

from qiskit_ibm_provider import IBMProvider

from ..decorators import (
    IntegrationTestDependencies,
    integration_test_setup,
)
from ..ibm_test_case import IBMTestCase
from ..utils import bell


class TestIntegrationSession(IBMTestCase):
    """Test Session module."""

    @classmethod
    @integration_test_setup()
    def setUpClass(cls, dependencies: IntegrationTestDependencies) -> None:
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.dependencies = dependencies

    def test_session_id(self):
        """Test that session_id is updated correctly and maintained throughout the session"""
        provider = IBMProvider(self.dependencies.token, self.dependencies.url)
        backend = provider.get_backend("ibmq_qasm_simulator")

        backend.open_session()
        self.assertEqual(backend.session.session_id, None)
        self.assertTrue(backend.session.active)
        job1 = backend.run(bell())
        self.assertEqual(job1._session_id, job1.job_id())
        job2 = backend.run(bell())
        self.assertFalse(job2._session_id == job2.job_id())

    def test_backend_run_with_session(self):
        """Test that 'shots' parameter is transferred correctly"""
        shots = 1000
        provider = IBMProvider(self.dependencies.token, self.dependencies.url)
        backend = provider.get_backend("ibmq_qasm_simulator")
        backend.open_session()
        result = backend.run(circuits=bell(), shots=shots).result()
        self.assertIsInstance(result, Result)
        self.assertEqual(result.results[0].shots, shots)
        self.assertAlmostEqual(
            result.get_counts()["00"], result.get_counts()["11"], delta=shots / 10
        )

    def test_session_cancel(self):
        """Test canceling a session"""
        provider = IBMProvider(self.dependencies.token, self.dependencies.url)
        backend = provider.get_backend("ibmq_qasm_simulator")
        backend.open_session()
        self.assertTrue(backend.session.active)
        backend.cancel_session()
        self.assertIsNone(backend.session)

    def test_session_close(self):
        """Test closing a session"""
        provider = IBMProvider(self.dependencies.token, self.dependencies.url)
        backend = provider.get_backend("ibmq_qasm_simulator")
        backend.open_session()
        self.assertTrue(backend.session.active)
        backend.close_session()
        self.assertIsNone(backend.session)

    def test_run_after_cancel(self):
        """Test running after session is cancelled."""
        provider = IBMProvider(self.dependencies.token, self.dependencies.url)
        backend = provider.get_backend("ibmq_qasm_simulator")
        job1 = backend.run(circuits=bell())
        self.assertIsNone(backend.session)
        self.assertIsNone(job1._session_id)

        backend.open_session()
        job2 = backend.run(bell())
        self.assertIsNotNone(job2._session_id)
        backend.cancel_session()

        job3 = backend.run(circuits=bell())
        self.assertIsNone(backend.session)
        self.assertIsNone(job3._session_id)

    def test_session_as_context_manager(self):
        """Test session as a context manager"""
        provider = IBMProvider(self.dependencies.token, self.dependencies.url)
        backend = provider.get_backend("ibmq_qasm_simulator")

        with backend.open_session() as session:
            job1 = backend.run(bell())
            session_id = session.session_id
            self.assertEqual(session_id, job1.job_id())
            job2 = backend.run(bell())
            self.assertFalse(session_id == job2.job_id())

    def test_run_after_cancel_as_context_manager(self):
        """Test run after cancel in context manager"""
        provider = IBMProvider(self.dependencies.token, self.dependencies.url)
        backend = provider.get_backend("ibmq_qasm_simulator")
        with backend.open_session() as session:
            _ = backend.run(bell())
        self.assertEqual(backend.session, session)
        backend.cancel_session()
        job = backend.run(circuits=bell())
        self.assertIsNone(backend.session)
        self.assertIsNone(job._session_id)
