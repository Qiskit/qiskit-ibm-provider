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

from qiskit_ibm_provider import IBMProvider
from qiskit_ibm_provider.session import Session
from qiskit_ibm_provider.exceptions import IBMInputValueError

from ..ibm_test_case import IBMTestCase


class TestSession(IBMTestCase):
    """Test Session module."""

    def test_provider_and_no_backend(self):
        """Test missing backend."""
        backend = "ibmq_qasm_simulator"
        session = Session()
        provider = IBMProvider(session=session)
        _ = provider.get_backend(name=backend)
        self.assertTrue(session.backend() is None)
        self.assertEqual(provider._session, session)

    def test_passing_ibm_backend(self):
        """Test passing in IBMBackend instance."""
        backend_name = "ibm_gotham"
        session = Session(backend_name=backend_name)
        self.assertEqual(session.backend(), "ibm_gotham")

    def test_max_time(self):
        """Test max time."""
        max_times = [
            (42, 42),
            ("1h", 1 * 60 * 60),
            ("2h 30m 40s", 2 * 60 * 60 + 30 * 60 + 40),
            ("40s 1h", 40 + 1 * 60 * 60),
        ]
        for max_t, expected in max_times:
            with self.subTest(max_time=max_t):
                session = Session(backend_name="ibm_gotham", max_time=max_t)
                self.assertEqual(session._max_time, expected)

    # def test_run_after_close(self):
    #     """Test running after session is closed."""
    #     backend_name = "ibm_gotham"
    #     with Session(backend_name=backend_name) as session:
    #         provider = IBMProvider(session=session)
    #         backend = provider.get_backend(name=backend_name)
    #         session.close()
    #         with self.assertRaises(RuntimeError):
    #             backend.run(program_id="program_id", inputs={})

    def test_session_close(self):
        """Test closing a session"""
        backend_name = "ibmq_qasm_simulator"
        with Session(backend_name=backend_name) as session:
            provider = IBMProvider(session=session)
            provider.close_session(session_id=session.session_id)
        self.assertFalse(session._active)