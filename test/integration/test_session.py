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

from qiskit import QuantumCircuit
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.result import Result

from qiskit_ibm_provider import IBMProvider
from qiskit_ibm_provider.session import Session


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
        backend = "ibmq_qasm_simulator"
        circuit = QuantumCircuit(2, 2)
        circuit.measure_all()

        with Session(backend_name=backend) as session:
            provider = IBMProvider(
                self.dependencies.token, self.dependencies.url, session=session
            )
            self.assertEqual(session.session_id, None)
            self.assertTrue(session._active)
            self.assertEqual(session._backend, backend)
            job1 = provider.backends(name=backend)[0].run(circuit)
            session_id = session.session_id
            self.assertEqual(session.session_id, job1.job_id())
            _ = provider.backends(name=backend)[0].run(circuit)
            self.assertEqual(session.session_id, session_id)

    def test_backend_run(self):
        """Test that session_id is updated correctly and maintained throughout the session"""
        backend_name = "ibmq_qasm_simulator"
        circuit = ReferenceCircuits.bell()
        shots = 1000

        with Session(backend_name=backend_name) as session:
            provider = IBMProvider(
                self.dependencies.token, self.dependencies.url, session=session
            )
            backend = provider.get_backend(name=backend_name)
            result = backend.run(circuit, shots=shots).result()
            self.assertIsInstance(result, Result)
            self.assertEqual(result.results[0].shots, shots)
            self.assertAlmostEqual(
                result.get_counts()["00"], result.get_counts()["11"], delta=shots / 10
            )

    def test_using_correct_instance(self):
        """Test the instance used when filtering backends is honored."""
        backend_name = "ibmq_qasm_simulator"
        instance = self.dependencies.instance
        with Session(backend_name=backend_name) as session:
            provider = IBMProvider(
                self.dependencies.token,
                self.dependencies.url,
                session=session,
                instance=instance,
            )
            backend = provider.get_backend(name=backend_name)
            job = backend.run(ReferenceCircuits.bell())
            self.assertEqual(instance, backend._instance)
            self.assertEqual(instance, job.backend()._instance)
