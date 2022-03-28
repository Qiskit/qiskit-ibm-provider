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

"""Test serializing and deserializing data sent to the server."""

import json

from qiskit import assemble
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit import Parameter

from qiskit_ibm_provider.utils.json_encoder import IBMJsonEncoder
from ..ibm_test_case import IBMTestCase


class TestSerialization(IBMTestCase):
    """Test data serialization."""

    def test_exception_message(self):
        """Test executing job with Parameter in methadata."""
        quantum_register = QuantumRegister(1)
        classical_register = ClassicalRegister(1)
        my_circ_str = "test_metadata"
        my_circ = QuantumCircuit(
            quantum_register,
            classical_register,
            name=my_circ_str,
            metadata={Parameter("φ"): 0.2},
        )
        qobj = assemble(my_circ)
        qobj_dict = qobj.to_dict()
        json.dumps(qobj_dict, cls=IBMJsonEncoder)
        # There is no self.assert method because if we cannot pass Parameter as metadata
        # the last line throw:
        # "TypeError: keys must be str, int, float, bool or None, not Parameter"

    def test_encode_no_replace(self):
        """Test encode where there is no invalid key to replace."""
        test_dir = {"t1": 1, None: None, "list": [1, 2, {"ld": 1, 2: 3}]}

        self.assertEqual(
            '{"t1": 1, "null": null, "list": [1, 2, {"ld": 1, "2": 3}]}',
            IBMJsonEncoder().encode(test_dir),
        )

    def test_encode_replace(self):
        """Test encode where there is no invalid key to replace."""
        test_dir = {
            "t1": 1,
            None: None,
            Parameter("a"): 0.2,
            "list": [1, 2, {"ld": 1, 2: 3, Parameter("alfa"): 0.1}],
        }

        self.assertEqual(
            '{"t1": 1, "null": null, "a": 0.2, "list": [1, 2, {"ld": 1, "2": 3, "alfa": 0.1}]}',
            IBMJsonEncoder().encode(test_dir),
        )
