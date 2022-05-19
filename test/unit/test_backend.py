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

from unittest import mock
from qiskit.test.mock.backends.bogota.fake_bogota import FakeBogota
from qiskit_ibm_provider.ibm_backend import IBMBackend
from .test_ibm_job_states import BaseFakeAPI
from ..ibm_test_case import IBMTestCase


class TestIBMBackend(IBMTestCase):
    """Testing backend methods."""

    def test_backend_properties(self):
        """Test backend properties."""
        backend = IBMBackend(
            FakeBogota().configuration(), mock.Mock(), api_client=BaseFakeAPI
        )
        self.assertIs(backend.properties(), None)
