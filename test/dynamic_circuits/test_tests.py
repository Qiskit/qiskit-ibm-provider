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

from qiskit_ibm_provider import dynamic_circuits

from ..ibm_test_case import IBMTestCase

class TestBasicServerPaths(IBMTestCase):

    def test_tests(self):
        self.assertEqual(dynamic_circuits.foo, 1)
