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
import warnings

import numpy as np
from ddt import data, ddt

from qiskit import assemble, QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit import Parameter

try:
    from qiskit.providers.fake_provider import Fake7QPulseV1
except ImportError:
    from qiskit.providers.fake_provider import FakeNairobi as Fake7QPulseV1

from qiskit_aer.noise import NoiseModel

from qiskit_ibm_provider.utils.json_encoder import IBMJsonEncoder
from qiskit_ibm_provider.utils.json import RuntimeEncoder, RuntimeDecoder
from ..ibm_test_case import IBMTestCase


@ddt
class TestSerialization(IBMTestCase):
    """Test data serialization."""

    def test_exception_message(self):
        """Test executing job with Parameter in metadata."""
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

    @data(
        np.arange(0, 10, 1),
        np.arange(0.0, 10.0, 1),
        np.int32(1),
        np.int64(2),
        np.float64(3.1),
        complex(1, 1),
        np.complex64(complex(1, 3)),
        "TEST",
    )
    def test_circuit_metadata(self, metadata_test):
        """Test serializing circuit metadata."""
        circ = QuantumCircuit(1)
        circ.metadata = {"test": metadata_test}
        payload = {"circuits": [circ]}

        self.assertTrue(json.dumps(payload, cls=RuntimeEncoder))

    def test_noise_model(self):
        """Test encoding and decoding a noise model."""
        noise_model = NoiseModel.from_backend(Fake7QPulseV1())
        self.assertIsInstance(noise_model, NoiseModel)
        encoded = json.dumps(noise_model, cls=RuntimeEncoder)
        self.assertIsInstance(encoded, str)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=DeprecationWarning,
            )
            decoded = json.loads(encoded, cls=RuntimeDecoder)
        self.assertIsInstance(decoded, NoiseModel)
        self.assertEqual(noise_model.noise_qubits, decoded.noise_qubits)
        self.assertEqual(noise_model.noise_instructions, decoded.noise_instructions)

    def test_param(self):
        """Test encoding and decoding a parameter."""
        param = Parameter("a")
        encoded = json.dumps(param, cls=RuntimeEncoder)
        self.assertIsInstance(encoded, str)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=DeprecationWarning,
            )
            decoded = json.loads(encoded, cls=RuntimeDecoder)
        self.assertIsInstance(decoded, Parameter)
        self.assertEqual(param.name, decoded.name)
        self.assertEqual(param._uuid, decoded._uuid)
