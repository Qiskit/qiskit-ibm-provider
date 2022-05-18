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

"""Test Provider Version."""

from qiskit_ibm_provider.version import get_version_info, git_version
from ..ibm_test_case import IBMTestCase


class TestProviderVersion(IBMTestCase):
    """Test version methods."""

    def test_provider_version(self):
        """Testing provider version."""
        version = git_version()
        self.assertTrue(version)

    def test_full_version(self):
        """Test getting full version."""
        version = get_version_info()
        self.assertTrue(version)
