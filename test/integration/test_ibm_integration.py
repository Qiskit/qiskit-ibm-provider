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

"""Integration tests."""

import time

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister, execute
from qiskit.compiler import transpile
from qiskit.result import Result
from qiskit.test.reference_circuits import ReferenceCircuits

from qiskit_ibm_provider import IBMBackend
from qiskit_ibm_provider.job.exceptions import IBMJobApiError
from ..decorators import (
    IntegrationTestDependencies,
    integration_test_setup_with_backend,
)
from ..ibm_test_case import IBMTestCase


class TestIBMIntegration(IBMTestCase):
    """Integration tests."""

    @classmethod
    @integration_test_setup_with_backend(simulator=False, min_num_qubits=2)
    def setUpClass(
        cls, backend: IBMBackend, dependencies: IntegrationTestDependencies
    ) -> None:
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.sim_backend = dependencies.provider.get_backend(
            "ibmq_qasm_simulator", instance=dependencies.instance
        )
        cls.real_device_backend = backend
        cls.dependencies = dependencies

    def setUp(self):
        super().setUp()
        quantum_register = QuantumRegister(1)
        classical_register = ClassicalRegister(1)
        self._qc1 = QuantumCircuit(quantum_register, classical_register, name="qc1")
        self._qc2 = QuantumCircuit(quantum_register, classical_register, name="qc2")
        self._qc1.measure(quantum_register[0], classical_register[0])
        self._qc2.x(quantum_register[0])
        self._qc2.measure(quantum_register[0], classical_register[0])

    def test_ibm_result_fields(self):
        """Test components of a result from a remote simulator."""
        remote_result = execute(self._qc1, self.sim_backend).result()
        self.assertIsInstance(remote_result, Result)
        self.assertIn(
            remote_result.backend_name, [self.sim_backend.name, "qasm_simulator"]
        )
        self.assertIsInstance(remote_result.job_id, str)
        self.assertEqual(remote_result.status, "COMPLETED")
        self.assertEqual(remote_result.results[0].status, "DONE")

    def test_compile_remote(self):
        """Test transpile with a remote backend."""
        qubit_reg = QuantumRegister(2, name="q")
        clbit_reg = ClassicalRegister(2, name="c")
        quantum_circuit = QuantumCircuit(qubit_reg, clbit_reg, name="bell")
        quantum_circuit.h(qubit_reg[0])
        quantum_circuit.cx(qubit_reg[0], qubit_reg[1])
        quantum_circuit.measure(qubit_reg, clbit_reg)

        circuits = transpile(quantum_circuit, backend=self.real_device_backend)
        self.assertIsInstance(circuits, QuantumCircuit)

    def test_compile_two_remote(self):
        """Test transpile with a remote backend on two circuits."""
        qubit_reg = QuantumRegister(2, name="q")
        clbit_reg = ClassicalRegister(2, name="c")
        quantum_circuit = QuantumCircuit(qubit_reg, clbit_reg, name="bell")
        quantum_circuit.h(qubit_reg[0])
        quantum_circuit.cx(qubit_reg[0], qubit_reg[1])
        quantum_circuit.measure(qubit_reg, clbit_reg)
        qc_extra = QuantumCircuit(qubit_reg, clbit_reg, name="extra")
        qc_extra.measure(qubit_reg, clbit_reg)
        circuits = transpile([quantum_circuit, qc_extra], self.real_device_backend)
        self.assertIsInstance(circuits[0], QuantumCircuit)
        self.assertIsInstance(circuits[1], QuantumCircuit)

    def test_compile_two_run_remote(self):
        """Test transpile and run two circuits."""
        qubit_reg = QuantumRegister(2, name="q")
        clbit_reg = ClassicalRegister(2, name="c")
        quantum_circuit = QuantumCircuit(qubit_reg, clbit_reg, name="bell")
        quantum_circuit.h(qubit_reg[0])
        quantum_circuit.cx(qubit_reg[0], qubit_reg[1])
        quantum_circuit.measure(qubit_reg, clbit_reg)
        qc_extra = QuantumCircuit(qubit_reg, clbit_reg, name="extra")
        qc_extra.measure(qubit_reg, clbit_reg)
        circs = transpile(
            [quantum_circuit, qc_extra],
            backend=self.sim_backend,
        )
        job = self.sim_backend.run(circs)
        result = job.result()
        self.assertIsInstance(result, Result)

    def test_execute_two_remote(self):
        """Test executing two circuits on a remote backend."""
        quantum_circuit = ReferenceCircuits.bell()
        qc_extra = QuantumCircuit(2, 2)
        qc_extra.measure_all()
        job = execute([quantum_circuit, qc_extra], self.sim_backend)
        results = job.result()
        self.assertIsInstance(results, Result)

    def test_private_job(self):
        """Test a private job."""
        if not self.dependencies.instance_private:
            print(self.skipTest("Skip test because no private instance is configured"))

        backend = self.dependencies.provider.get_backend(
            "ibmq_qasm_simulator", instance=self.dependencies.instance_private
        )
        quantum_circuit = ReferenceCircuits.bell()
        job = execute(quantum_circuit, backend=backend)
        self.assertIsNotNone(job.circuits())
        self.assertIsNotNone(job.result())

        # Wait a bit for databases to update.
        time.sleep(2)
        rjob = self.dependencies.provider.backend.retrieve_job(job.job_id())

        with self.assertRaises(IBMJobApiError) as err_cm:
            rjob.circuits()
        self.assertIn("2801", str(err_cm.exception))

        with self.assertRaises(IBMJobApiError) as err_cm:
            rjob.result()
        self.assertIn("2801", str(err_cm.exception))
