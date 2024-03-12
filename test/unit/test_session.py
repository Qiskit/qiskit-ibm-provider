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

from unittest import mock

try:
    from qiskit.providers.fake_provider import Fake5QV1
except ImportError:
    from qiskit.providers.fake_provider import FakeManila as Fake5QV1
from qiskit_ibm_provider import IBMBackend

from ..ibm_test_case import IBMTestCase


class TestSession(IBMTestCase):
    """Test Session module."""

    def test_open_session(self):
        """Test opening a session instance."""
        model_backend = Fake5QV1()
        backend = IBMBackend(
            configuration=model_backend.configuration(),
            provider=mock.MagicMock(),
            api_client=None,
        )

        backend.open_session()
        self.assertFalse(backend.session is None)

    def test_session_max_time(self):
        """Test max time parameter."""
        model_backend = Fake5QV1()
        backend = IBMBackend(
            configuration=model_backend.configuration(),
            provider=mock.MagicMock(),
            api_client=None,
        )

        max_times = [
            (42, 42),
            ("1h", 1 * 60 * 60),
            ("2h 30m 40s", 2 * 60 * 60 + 30 * 60 + 40),
            ("40s 1h", 40 + 1 * 60 * 60),
        ]
        for max_t, expected in max_times:
            with self.subTest(max_time=max_t):
                backend.open_session(max_time=max_t)
                self.assertEqual(backend.session._max_time, expected)
