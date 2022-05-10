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

"""E2E tests against real devices."""

import time
import re
from unittest import SkipTest

from qiskit import (
    transpile,
    ClassicalRegister,
    QuantumCircuit,
    QuantumRegister,
)
from qiskit.test.reference_circuits import ReferenceCircuits
from qiskit.providers.jobstatus import JobStatus
from qiskit_ibm_provider import least_busy
from qiskit_ibm_provider.job.exceptions import IBMJobFailureError

from qiskit_ibm_provider.ibm_backend import IBMBackend

from ..ibm_test_case import IBMTestCase
from ..utils import (
    cancel_job,
    get_large_circuit,
    submit_job_one_bad_instr,
)
from ..decorators import (
    IntegrationTestDependencies,
    integration_test_setup_with_backend,
)


class TestRealDevices(IBMTestCase):
    """Compilation of slow tests from all test suites."""

    @classmethod
    @integration_test_setup_with_backend(simulator=False, min_num_qubits=2)
    def setUpClass(
        cls, backend: IBMBackend, dependencies: IntegrationTestDependencies
    ) -> None:
        # pylint: disable=arguments-differ
        super().setUpClass()
        cls.dependencies = dependencies
        cls.real_device_backend = backend

    def test_job_submission(self):
        """Test running a job against a device."""
        for provider in ["provider", "private_provider"]:
            if not self.dependencies.instance_private:
                raise self.skipTest("Skip test because there is no private provider")
            backend = self.dependencies[provider].backends(
                simulator=False,
                operational=True,
                filters=lambda b: b.configuration().n_qubits >= 5,
            )[0]
            with self.subTest(provider=provider, backend=backend):
                job = self._submit_job_with_retry(ReferenceCircuits.bell(), backend)

                # Fetch the results.
                result = job.result()
                self.assertTrue(result.success)

                # Fetch the circuits.
                circuit = (
                    self.dependencies[provider].backend.job(job.job_id()).circuits()
                )
                self.assertEqual(circuit, job.circuits())

    def test_job_backend_properties_and_status(self):
        """Test the backend properties and status of a job."""
        for provider in ["provider", "private_provider"]:
            if not self.dependencies.instance_private:
                raise self.skipTest("Skip test because there is no private provider")
            backend = self.dependencies[provider].backends(
                simulator=False,
                operational=True,
                filters=lambda b: b.configuration().n_qubits >= 5,
            )[0]
            with self.subTest(backend=backend):
                job = self._submit_job_with_retry(ReferenceCircuits.bell(), backend)
                self.assertIsNotNone(job.properties())
                self.assertTrue(job.status())
                # Cancel job so it doesn't consume more resources.
                cancel_job(job, verify=True)

    def test_run_device(self):
        """Test running in a real device."""
        shots = 8192
        job = self.real_device_backend.run(
            transpile(ReferenceCircuits.bell(), backend=self.real_device_backend),
            shots=shots,
        )

        job.wait_for_final_state(wait=300, callback=self.simple_job_callback)
        result = job.result()
        counts_qx = result.get_counts(0)
        counts_ex = {"00": shots / 2, "11": shots / 2}
        self.assertDictAlmostEqual(counts_qx, counts_ex, shots * 0.2)

        # Test fetching the job properties, as this is a real backend and is
        # guaranteed to have them.
        self.assertIsNotNone(job.properties())

    def test_run_multiple_device(self):
        """Test running multiple jobs in a real device."""

        backend = self.real_device_backend
        num_qubits = 5
        quantum_register = QuantumRegister(num_qubits, "qr")
        classical_register = ClassicalRegister(num_qubits, "cr")
        quantum_circuit = QuantumCircuit(quantum_register, classical_register)
        for i in range(num_qubits - 1):
            quantum_circuit.cx(quantum_register[i], quantum_register[i + 1])
        quantum_circuit.measure(quantum_register, classical_register)
        num_jobs = 3
        job_array = [
            backend.run(transpile(quantum_circuit, backend=backend))
            for _ in range(num_jobs)
        ]
        time.sleep(3)  # give time for jobs to start (better way?)
        job_status = [job.status() for job in job_array]
        num_init = sum([status is JobStatus.INITIALIZING for status in job_status])
        num_queued = sum([status is JobStatus.QUEUED for status in job_status])
        num_running = sum([status is JobStatus.RUNNING for status in job_status])
        num_done = sum([status is JobStatus.DONE for status in job_status])
        num_error = sum([status is JobStatus.ERROR for status in job_status])
        self.log.info(
            "number of currently initializing jobs: %d/%d", num_init, num_jobs
        )
        self.log.info("number of currently queued jobs: %d/%d", num_queued, num_jobs)
        self.log.info("number of currently running jobs: %d/%d", num_running, num_jobs)
        self.log.info("number of currently done jobs: %d/%d", num_done, num_jobs)
        self.log.info("number of errored jobs: %d/%d", num_error, num_jobs)
        self.assertTrue(num_jobs - num_error - num_done > 0)

        # Wait for all the results.
        for job in job_array:
            job.wait_for_final_state(wait=300, callback=self.simple_job_callback)
        result_array = [job.result() for job in job_array]

        # Ensure all jobs have finished.
        self.assertTrue(all((job.status() is JobStatus.DONE for job in job_array)))
        self.assertTrue(all((result.success for result in result_array)))

        # Ensure job ids are unique.
        job_ids = [job.job_id() for job in job_array]
        self.assertEqual(sorted(job_ids), sorted(list(set(job_ids))))

    def test_pulse_job(self):
        """Test running a pulse job."""
        backends = self.dependencies.provider.backends(
            open_pulse=True, operational=True
        )
        if not backends:
            raise SkipTest("Skipping pulse test since no pulse backend found.")

        backend = least_busy(backends)
        config = backend.configuration()
        defaults = backend.defaults()
        inst_map = defaults.instruction_schedule_map

        # Run 2 experiments - 1 with x pulse and 1 without
        x_pulse = inst_map.get("x", 0)
        measure = inst_map.get("measure", range(config.n_qubits)) << x_pulse.duration
        ground_sched = measure
        excited_sched = x_pulse | measure
        schedules = [ground_sched, excited_sched]

        job = backend.run(schedules, meas_level=1, shots=256)
        job.wait_for_final_state(wait=300, callback=self.simple_job_callback)
        self.assertTrue(
            job.done(), "Job {} didn't complete successfully.".format(job.job_id())
        )
        self.assertIsNotNone(job.result(), "Job {} has no result.".format(job.job_id()))

    def test_running_job_properties(self):
        """Test fetching properties of a running job."""

        backend = self.real_device_backend

        def _job_callback(job_id, job_status, cjob, **kwargs):
            self.simple_job_callback(job_id, job_status, cjob, **kwargs)
            if job_status is JobStatus.RUNNING:
                job_properties[0] = cjob.properties()
                cancel_job(cjob)

        job_properties = [None]
        large_qx = get_large_circuit(backend=backend)
        job = backend.run(transpile(large_qx, backend=backend))
        job.wait_for_final_state(wait=None, callback=_job_callback)
        self.assertIsNotNone(job_properties[0])

    def test_error_message_device(self):
        """Test retrieving job error messages from a device backend."""
        backend = self.real_device_backend
        job = submit_job_one_bad_instr(backend)
        job.wait_for_final_state(wait=300, callback=self.simple_job_callback)

        rjob = self.dependencies.provider.backend.job(job.job_id())

        for q_job, partial in [(job, False), (rjob, True)]:
            with self.subTest(partial=partial):
                with self.assertRaises(IBMJobFailureError) as err_cm:
                    q_job.result(partial=partial)
                for msg in (err_cm.exception.message, q_job.error_message()):
                    self.assertIn("bad_instruction", msg)
                    self.assertIsNotNone(
                        re.search(r"Error code: [0-9]{4}\.$", msg), msg
                    )

    def test_headers_in_result_devices(self):
        """Test that the qobj headers are passed onto the results for devices."""
        custom_header = {"x": 1, "y": [1, 2, 3], "z": {"a": 4}}

        # TODO Use circuit metadata for individual header when terra PR-5270 is released.
        # qobj.experiments[0].header.some_field = 'extra info'

        quantum_register = QuantumRegister(1)
        classical_register = ClassicalRegister(1)

        qc1 = QuantumCircuit(quantum_register, classical_register, name="circuit0")
        qc1.h(quantum_register[0])
        qc1.measure(quantum_register, classical_register)
        job = self.real_device_backend.run(
            transpile(qc1, backend=self.real_device_backend), header=custom_header
        )
        job.wait_for_final_state(wait=300, callback=self.simple_job_callback)
        result = job.result()
        self.assertTrue(custom_header.items() <= job.header().items())
        self.assertTrue(custom_header.items() <= result.header.to_dict().items())
        # self.assertEqual(result.results[0].header.some_field, 'extra info')

    def test_websockets_device(self):
        """Test checking status of a job via websockets for a device."""
        job = self.real_device_backend.run(
            transpile(ReferenceCircuits.bell(), self.real_device_backend), shots=1
        )

        # Manually disable the non-websocket polling.
        # job._api_client._job_final_status_polling = self._job_final_status_polling
        job.wait_for_final_state(wait=300, callback=self.simple_job_callback)
        result = job.result()

        self.assertTrue(result.success)
