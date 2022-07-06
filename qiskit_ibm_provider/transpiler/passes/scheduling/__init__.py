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

"""
==============================================================
Scheduling (:mod:`qiskit_ibm_provider.transpiler.passes.scheduling`)
==============================================================

.. currentmodule:: qiskit_ibm_provider.transpiler.passes.scheduling

A collection of scheduling passes for working with IBM Quantum's next-generation
backends that support advanced "dynamic circuit" capabilities. Ie.,
circuits with support for classical control-flow/feedback based off
of measurement results.


Below we demonstrate how to schedule and pad a teleportation circuit with delays
for a dynamic circuit backend's execution model


.. jupyter-execute::

    from qiskit.transpiler.instruction_durations import InstructionDurations

    from qiskit_ibm_provider.transpiler.scheduling import DynamicCircuitScheduleAnalysis, PadDelay
    from qiskit_ibm_provider.test.ibm_provider_mock import mock_get_backend


    backend = mock_get_backend('FakePerth')

    durations = InstructionDurations.from_backend(backend)
    pm = PassManager([DynamicCircuitScheduleAnalysis(durations), PadDelay()])

    qr = QuantumRegister(3)
    crz = ClassicalRegister(1, name="crz")
    crx = ClassicalRegister(1, name="crx")
    result = ClassicalRegister(1, name="result")

    teleport = QuantumCircuit(qr, crz, crx, result, name="Teleport")

    teleport.h(qr[1])
    teleport.cx(qr[1], qr[2])
    teleport.cx(qr[0], qr[1])
    teleport.h(qr[0])
    teleport.measure(qr[0], crz)
    teleport.measure(qr[1], crx)
    teleport.z(qr[2]).c_if(crz, 1)
    teleport.x(qr[2]).c_if(crx, 1)
    teleport.measure(qr[2], result)

    scheduled_teleport = pm.run(teleport)

    teleport.draw(output="mpl")


Scheduling & Dynamical Decoupling
=================================
.. autosummary::
   :toctree: ../stubs/

    BasePadding
    DynamicCircuitScheduleAnalysis
    PadDelay



"""

from .pad_delay import PadDelay
from .scheduler import DynamicCircuitScheduleAnalysis
