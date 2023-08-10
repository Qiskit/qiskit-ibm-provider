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

from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.result import Result

from qiskit_ibm_provider import IBMProvider

from ..decorators import (
    IntegrationTestDependencies,
    integration_test_setup,
)
from ..ibm_test_case import IBMTestCase


class TestSession(IBMTestCase):
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
        self.assertTrue(backend.session._active)
        job1 = backend.run(ReferenceCircuits.bell())
        session_id = backend.session.session_id
        self.assertEqual(session_id, job1.job_id())
        job2 = backend.run(ReferenceCircuits.bell())
        self.assertFalse(session_id == job2.job_id())

    def test_backend_run_with_session(self):
        """Test that 'shots' parameter is transferred correctly"""
        shots = 1000
        provider = IBMProvider(self.dependencies.token, self.dependencies.url)
        backend = provider.get_backend("ibmq_qasm_simulator")
        backend.open_session()
        result = backend.run(circuits=ReferenceCircuits.bell(), shots=shots).result()
        self.assertIsInstance(result, Result)
        self.assertEqual(result.results[0].shots, shots)
        self.assertAlmostEqual(
            result.get_counts()["00"], result.get_counts()["11"], delta=shots / 10
        )

    def test_session_close(self):
        """Test closing a session"""
        provider = IBMProvider(self.dependencies.token, self.dependencies.url)
        backend = provider.get_backend("ibmq_qasm_simulator")
        backend.open_session()
        self.assertTrue(backend.session._active)
        backend.close_session()
        self.assertFalse(backend.session._active)

    def test_run_after_close(self):
        """Test running after session is closed."""
        provider = IBMProvider(self.dependencies.token, self.dependencies.url)
        backend = provider.get_backend("ibmq_qasm_simulator")
        backend.open_session()
        _ = backend.run(ReferenceCircuits.bell())
        backend.close_session()
        with self.assertRaises(RuntimeError):
            backend.run(
                circuits=ReferenceCircuits.bell(),
                program_id="program_id",
                inputs={},
            )

    def test_session_id_as_context_manager(self):
        """Test that the provider uses or doesn't use session correctly"""
        provider = IBMProvider(self.dependencies.token, self.dependencies.url)
        backend = provider.get_backend("ibmq_qasm_simulator")

        with backend.open_session() as session:
            job1 = backend.run(ReferenceCircuits.bell())
            session_id = session.session_id
            self.assertEqual(session_id, job1.job_id())
            job2 = backend.run(ReferenceCircuits.bell())
            self.assertFalse(session_id == job2.job_id())
