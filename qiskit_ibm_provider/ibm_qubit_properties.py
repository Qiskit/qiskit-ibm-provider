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

"""Module for Qubit Properties of an IBM Quantum Backend."""

from qiskit.providers.backend import QubitProperties


class IBMQubitProperties(QubitProperties):
    """A representation of the properties of a qubit on an IBM backend."""

    __slots__ = (
        "t1",
        "t2",
        "frequency",
        "anharmonicity",
        "readout_error",
        "readout_length",
        "prob_meas0_prep1",
        "prob_meas1_prep0",
    )

    def __init__(  # type: ignore[no-untyped-def]
        self,
        t1=None,
        t2=None,
        frequency=None,
        anharmonicity=None,
        readout_error=None,
        readout_length=None,
        prob_meas0_prep1=None,
        prob_meas1_prep0=None,
    ):
        """Create a new ``IBMQubitProperties`` object

        Args:
            t1: The T1 time for a qubit in us
            t2: The T2 time for a qubit in us
            frequency: The frequency of a qubit in GHz
            anharmonicity: The anharmonicity of a qubit in GHz
            readout_error: The readout assignment error of a qubit
            readout_length: The readout length of a qubit in ns
            prob_meas0_prep1: Prob meas0 prep1
            prob_meas1_prep0: Prob meas1 prep0
        """
        super().__init__(t1=t1, t2=t2, frequency=frequency)
        self.anharmonicity = anharmonicity
        self.readout_error = readout_error
        self.readout_length = readout_length
        self.prob_meas0_prep1 = prob_meas0_prep1
        self.prob_meas1_prep0 = prob_meas1_prep0

    def __repr__(self):  # type: ignore[no-untyped-def]
        return (
            f"IBMQubitProperties(t1={self.t1}, t2={self.t2}, frequency={self.frequency},"
            f"anharmonicity={self.anharmonicity}, readout_error={self.readout_error},"
            f"readout_length={self.readout_length}, prob_meas0_prep1={self.prob_meas0_prep1},"
            f"prob_meas1_prep0={self.prob_meas1_prep0})"
        )
