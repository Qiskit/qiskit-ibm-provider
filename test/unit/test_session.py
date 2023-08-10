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

from qiskit_ibm_provider import IBMProvider
from ..ibm_test_case import IBMTestCase


class TestSession(IBMTestCase):
    """Test Session module."""

    def test_open_session(self):
        """Test opening a session instance."""
        provider = IBMProvider()
        backend = provider.get_backend("ibmq_qasm_simulator")
        backend.open_session()
        self.assertFalse(backend._session is None)

    def test_session_max_time(self):
        """Test max time parameter."""
        provider = IBMProvider()
        backend = provider.get_backend("ibmq_qasm_simulator")
        max_times = [
            (42, 42),
            ("1h", 1 * 60 * 60),
            ("2h 30m 40s", 2 * 60 * 60 + 30 * 60 + 40),
            ("40s 1h", 40 + 1 * 60 * 60),
        ]
        for max_t, expected in max_times:
            with self.subTest(max_time=max_t):
                backend.open_session(max_time=max_t)
                self.assertEqual(backend._session._max_time, expected)
