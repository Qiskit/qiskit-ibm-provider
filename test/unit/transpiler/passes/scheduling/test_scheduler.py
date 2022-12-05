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

"""Test the dynamic circuits scheduling analysis"""

from qiskit import QuantumCircuit
from qiskit.pulse import Schedule, Play, Constant, DriveChannel
from qiskit.test import QiskitTestCase
from qiskit.transpiler.passmanager import PassManager
from qiskit.transpiler.exceptions import TranspilerError

from qiskit_ibm_provider.transpiler.passes.scheduling.pad_delay import PadDelay
from qiskit_ibm_provider.transpiler.passes.scheduling.scheduler import (
    ALAPScheduleAnalysis,
    ASAPScheduleAnalysis,
)
from qiskit_ibm_provider.transpiler.passes.scheduling.utils import (
    DynamicCircuitInstructionDurations,
)

# pylint: disable=invalid-name


class TestASAPSchedulingAndPaddingPass(QiskitTestCase):
    """Tests the ASAP Scheduling passes"""

    def test_classically_controlled_gate_after_measure(self):
        """Test if schedules circuits with c_if after measure with a common clbit.
        See: https://github.com/Qiskit/qiskit-terra/issues/7654"""
        qc = QuantumCircuit(2, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, True)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 1)
        expected.delay(1000, 1)
        expected.measure(0, 0)
        expected.barrier()
        expected.x(1).c_if(0, True)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_measure_after_measure(self):
        """Test if schedules circuits with measure after measure with a common clbit.

        Note: There is no delay to write into the same clbit with IBM backends."""
        qc = QuantumCircuit(2, 1)
        qc.x(0)
        qc.measure(0, 0)
        qc.measure(1, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 1)
        expected.x(0)
        expected.delay(200, 1)
        expected.measure(0, 0)
        expected.measure(1, 0)
        expected.barrier()
        self.assertEqual(expected, scheduled)

    def test_measure_block_not_end(self):
        """Tests that measures trigger do not trigger the end of a scheduling block."""
        qc = QuantumCircuit(3, 1)
        qc.x(0)
        qc.measure(0, 0)
        qc.measure(1, 0)
        qc.x(2)
        qc.measure(1, 0)
        qc.measure(2, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.x(0)
        expected.delay(200, 1)
        expected.x(2)
        expected.delay(1000, 2)
        expected.measure(0, 0)
        expected.measure(1, 0)
        expected.delay(1000, 0)
        expected.measure(1, 0)
        expected.measure(2, 0)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_reset_block_end(self):
        """Tests that measures trigger do trigger the end of a scheduling block."""
        qc = QuantumCircuit(3, 1)
        qc.x(0)
        qc.reset(0)
        qc.measure(1, 0)
        qc.x(2)
        qc.measure(1, 0)
        qc.measure(2, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840), ("reset", None, 840)]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.x(0)
        expected.delay(200, 1)
        expected.x(2)
        expected.delay(1000, 2)
        expected.reset(0)
        expected.measure(1, 0)
        expected.barrier()
        expected.delay(1000, 0)
        expected.measure(1, 0)
        expected.measure(2, 0)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_c_if_on_different_qubits(self):
        """Test if schedules circuits with `c_if`s on different qubits."""
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, True)
        qc.x(2).c_if(0, True)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.delay(1000, 1)
        expected.delay(1000, 2)
        expected.measure(0, 0)
        expected.barrier()
        expected.x(1).c_if(0, True)
        expected.x(2).c_if(0, True)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_shorter_measure_after_measure(self):
        """Test if schedules circuits with shorter measure after measure
        with a common clbit.

        Note: For dynamic circuits support we currently group measurements
        to start at the same time which in turn trigger the end of a block."""
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.measure(1, 0)

        durations = DynamicCircuitInstructionDurations(
            [("measure", [0], 840), ("measure", [1], 540)]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.measure(0, 0)
        expected.measure(1, 0)
        expected.delay(300, 1)
        expected.delay(1000, 2)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_measure_after_c_if(self):
        """Test if schedules circuits with c_if after measure with a common clbit.

        Note: This test is not yet correct as we should schedule the conditional block
        qubits with delays as well.
        """
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, 1)
        qc.measure(2, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.delay(1000, 1)
        expected.delay(1000, 2)
        expected.measure(0, 0)
        expected.barrier()
        expected.x(1).c_if(
            0, 1
        )  # Not yet correct as we should insert delays for idle qubits in conditional.
        expected.barrier()
        expected.delay(1000, 0)
        expected.measure(2, 0)
        expected.delay(1000, 1)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_parallel_gate_different_length(self):
        """Test circuit having two parallel instruction with different length."""
        qc = QuantumCircuit(2, 2)
        qc.x(0)
        qc.x(1)
        qc.measure(0, 0)
        qc.measure(1, 1)

        durations = DynamicCircuitInstructionDurations(
            [("x", [0], 200), ("x", [1], 400), ("measure", None, 840)]
        )

        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 2)
        expected.x(0)
        expected.x(1)
        expected.delay(200, 0)
        expected.measure(0, 0)  # immediately start after X gate
        expected.measure(1, 1)
        expected.barrier()

        self.assertEqual(scheduled, expected)

    def test_parallel_gate_different_length_with_barrier(self):
        """Test circuit having two parallel instruction with different length with barrier."""
        qc = QuantumCircuit(2, 2)
        qc.x(0)
        qc.x(1)
        qc.barrier()
        qc.measure(0, 0)
        qc.measure(1, 1)

        durations = DynamicCircuitInstructionDurations(
            [("x", [0], 200), ("x", [1], 400), ("measure", None, 840)]
        )

        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 2)
        expected.x(0)
        expected.delay(200, 0)
        expected.x(1)
        expected.barrier()
        expected.measure(0, 0)
        expected.measure(1, 1)
        expected.barrier()

        self.assertEqual(scheduled, expected)

    def test_measure_after_c_if_on_edge_locking(self):
        """Test if schedules circuits with c_if after measure with a common clbit.
        The scheduler is configured to reproduce behavior of the 0.20.0,
        in which clbit lock is applied to the end-edge of measure instruction.
        See https://github.com/Qiskit/qiskit-terra/pull/7655"""
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, 1)
        qc.measure(2, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )

        # lock at the end edge
        scheduled = PassManager(
            [
                ASAPScheduleAnalysis(durations),
                PadDelay(),
            ]
        ).run(qc)

        expected = QuantumCircuit(3, 1)
        expected.delay(1000, 1)
        expected.delay(1000, 2)
        expected.measure(0, 0)
        expected.barrier()
        expected.x(1).c_if(0, 1)
        expected.barrier()
        expected.delay(1000, 0)
        expected.delay(1000, 1)
        expected.measure(2, 0)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_active_reset_circuit(self):
        """Test practical example of reset circuit.

        Because of the stimulus pulse overlap with the previous XGate on the q register,
        measure instruction is always triggered after XGate regardless of write latency.
        Thus only conditional latency matters in the scheduling."""
        qc = QuantumCircuit(1, 1)
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 100), ("measure", None, 840)]
        )

        scheduled = PassManager(
            [
                ASAPScheduleAnalysis(durations),
                PadDelay(),
            ]
        ).run(qc)

        expected = QuantumCircuit(1, 1)
        expected.measure(0, 0)
        expected.x(0).c_if(0, 1)
        expected.barrier()
        expected.measure(0, 0)
        expected.x(0).c_if(0, 1)
        expected.barrier()
        expected.measure(0, 0)
        expected.x(0).c_if(0, 1)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_dag_introduces_extra_dependency_between_conditionals(self):
        """Test dependency between conditional operations in the scheduling.

        In the below example circuit, the conditional x on q1 could start at time 0,
        however it must be scheduled after the conditional x on q0 in scheduling.
        That is because circuit model used in the transpiler passes (DAGCircuit)
        interprets instructions acting on common clbits must be run in the order
        given by the original circuit (QuantumCircuit)."""
        qc = QuantumCircuit(2, 1)
        qc.delay(100, 0)
        qc.x(0).c_if(0, True)
        qc.x(1).c_if(0, True)

        durations = DynamicCircuitInstructionDurations([("x", None, 160)])
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 1)
        expected.delay(100, 0)
        expected.delay(100, 1)
        expected.barrier()
        expected.x(0).c_if(0, True)
        expected.x(1).c_if(0, True)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_scheduling_with_calibration(self):
        """Test if calibrated instruction can update node duration."""
        qc = QuantumCircuit(2)
        qc.x(0)
        qc.cx(0, 1)
        qc.x(1)
        qc.cx(0, 1)

        xsched = Schedule(Play(Constant(300, 0.1), DriveChannel(0)))
        qc.add_calibration("x", (0,), xsched)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 160), ("cx", None, 600)]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2)
        expected.x(0)
        expected.delay(300, 1)
        expected.cx(0, 1)
        expected.x(1)
        expected.delay(160, 0)
        expected.cx(0, 1)
        expected.add_calibration("x", (0,), xsched)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_padding_not_working_without_scheduling(self):
        """Test padding fails when un-scheduled DAG is input."""
        qc = QuantumCircuit(1, 1)
        qc.delay(100, 0)
        qc.x(0)
        qc.measure(0, 0)

        with self.assertRaises(TranspilerError):
            PassManager(PadDelay()).run(qc)

    def test_no_pad_very_end_of_circuit(self):
        """Test padding option that inserts no delay at the very end of circuit.

        This circuit will be unchanged after scheduling/padding."""
        qc = QuantumCircuit(2, 1)
        qc.delay(100, 0)
        qc.x(1)
        qc.measure(0, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 160), ("measure", None, 840)]
        )

        scheduled = PassManager(
            [
                ASAPScheduleAnalysis(durations),
                PadDelay(fill_very_end=False),
            ]
        ).run(qc)

        expected = qc.copy()
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_reset_terminates_block(self):
        """Test if reset operations terminate the block scheduled.

        Note: For dynamic circuits support we currently group resets
        to start at the same time which in turn trigger the end of a block."""
        qc = QuantumCircuit(3, 1)
        qc.x(0)
        qc.reset(0)
        qc.measure(1, 0)
        qc.x(0)

        durations = DynamicCircuitInstructionDurations(
            [
                ("x", None, 200),
                (
                    "reset",
                    [0],
                    840,
                ),  # ignored as only the duration of the measurement is used for scheduling
                (
                    "reset",
                    [1],
                    740,
                ),  # ignored as only the duration of the measurement is used for scheduling
                ("measure", [0], 440),
                ("measure", [1], 540),
            ]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.x(0)
        expected.delay(200, 1)
        expected.delay(900, 2)
        expected.reset(0)
        expected.delay(100, 0)
        expected.measure(1, 0)
        expected.barrier()
        expected.x(0)
        expected.delay(200, 1)
        expected.delay(200, 2)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_reset_merged_with_measure(self):
        """Test if reset operations terminate the block scheduled.

        Note: For dynamic circuits support we currently group resets to start
        at the same time which in turn trigger the end of a block."""
        qc = QuantumCircuit(3, 1)
        qc.x(0)
        qc.reset(0)
        qc.measure(1, 0)

        durations = DynamicCircuitInstructionDurations(
            [
                ("x", None, 200),
                (
                    "reset",
                    [0],
                    840,
                ),  # ignored as only the duration of the measurement is used for scheduling
                (
                    "reset",
                    [1],
                    740,
                ),  # ignored as only the duration of the measurement is used for scheduling
                ("measure", [0], 440),
                ("measure", [1], 540),
            ]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.x(0)
        expected.delay(200, 1)
        expected.delay(900, 2)
        expected.reset(0)
        expected.measure(1, 0)
        expected.delay(100, 0)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_scheduling_is_idempotent(self):
        """Test that padding can be applied back to back without changing the circuit."""
        qc = QuantumCircuit(3, 2)
        qc.x(2)
        qc.cx(0, 1)
        qc.barrier()
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 100), ("measure", None, 840), ("cx", None, 500)]
        )

        scheduled0 = PassManager(
            [
                ASAPScheduleAnalysis(durations),
                PadDelay(),
            ]
        ).run(qc)

        scheduled1 = PassManager(
            [
                ASAPScheduleAnalysis(durations),
                PadDelay(),
            ]
        ).run(scheduled0)

        self.assertEqual(scheduled0, scheduled1)

    def test_gate_on_measured_qubit(self):
        """Test that a gate on a previously measured qubit triggers the end of the block"""
        qc = QuantumCircuit(2, 1)
        qc.measure(0, 0)
        qc.x(0)
        qc.x(1)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 1)
        expected.x(1)
        expected.delay(1000, 1)
        expected.measure(0, 0)
        expected.x(0)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_grouped_measurements_prior_control_flow(self):
        """Test that measurements are grouped prior to control-flow"""
        qc = QuantumCircuit(3, 3)
        qc.measure(0, 0)
        qc.measure(1, 1)
        qc.x(2).c_if(0, 1)
        qc.x(2).c_if(1, 1)
        qc.measure(2, 2)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 3)
        expected.delay(1000, 2)
        expected.measure(0, 0)
        expected.measure(1, 1)
        expected.barrier()
        expected.x(2).c_if(0, 1)
        expected.x(2).c_if(1, 1)
        expected.barrier()
        expected.delay(1000, 0)
        expected.delay(1000, 1)
        expected.measure(2, 2)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_back_to_back_c_if(self):
        """Test back to back c_if scheduling"""

        qc = QuantumCircuit(3, 1)
        qc.delay(800, 1)
        qc.x(1).c_if(0, True)
        qc.x(2).c_if(0, True)
        qc.delay(1000, 2)
        qc.x(1)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ASAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.delay(800, 0)
        expected.delay(800, 1)
        expected.delay(800, 2)
        expected.barrier()
        expected.x(1).c_if(0, True)
        expected.x(2).c_if(0, True)
        expected.barrier()
        expected.delay(1000, 0)
        expected.x(1)
        expected.delay(800, 1)
        expected.delay(1000, 2)
        expected.barrier()

        self.assertEqual(expected, scheduled)


class TestALAPSchedulingAndPaddingPass(QiskitTestCase):
    """Tests the ALAP Scheduling passes"""

    def test_alap(self):
        """Test standard ALAP scheduling"""
        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.x(1)

        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.measure(0, 0)
        expected.delay(800, 1)
        expected.x(1)
        expected.delay(1000, 2)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_classically_controlled_gate_after_measure(self):
        """Test if schedules circuits with c_if after measure with a common clbit.
        See: https://github.com/Qiskit/qiskit-terra/issues/7654"""
        qc = QuantumCircuit(2, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, True)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 1)
        expected.delay(1000, 1)
        expected.measure(0, 0)
        expected.barrier()
        expected.x(1).c_if(0, True)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_measure_after_measure(self):
        """Test if schedules circuits with measure after measure with a common clbit.

        Note: There is no delay to write into the same clbit with IBM backends."""
        qc = QuantumCircuit(2, 1)
        qc.x(0)
        qc.measure(0, 0)
        qc.measure(1, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 1)
        expected.x(0)
        expected.delay(200, 1)
        expected.measure(0, 0)
        expected.measure(1, 0)
        expected.barrier()
        self.assertEqual(expected, scheduled)

    def test_measure_block_not_end(self):
        """Tests that measures trigger do not trigger the end of a scheduling block."""
        qc = QuantumCircuit(3, 1)
        qc.x(0)
        qc.measure(0, 0)
        qc.measure(1, 0)
        qc.x(2)
        qc.measure(1, 0)
        qc.measure(2, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.x(0)
        expected.delay(200, 1)
        expected.delay(1000, 2)
        expected.x(2)
        expected.measure(0, 0)
        expected.delay(1000, 0)
        expected.measure(1, 0)
        expected.measure(1, 0)
        expected.measure(2, 0)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_reset_block_end(self):
        """Tests that measures trigger do trigger the end of a scheduling block."""
        qc = QuantumCircuit(3, 1)
        qc.x(0)
        qc.reset(0)
        qc.measure(1, 0)
        qc.x(2)
        qc.measure(1, 0)
        qc.measure(2, 0)
        qc.measure(0, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840), ("reset", None, 840)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.x(0)
        expected.reset(0)
        expected.delay(200, 1)
        expected.delay(1000, 2)
        expected.x(2)
        expected.measure(1, 0)
        expected.barrier()
        expected.measure(1, 0)
        expected.measure(2, 0)
        expected.measure(0, 0)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_c_if_on_different_qubits(self):
        """Test if schedules circuits with `c_if`s on different qubits."""
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, True)
        qc.x(2).c_if(0, True)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.delay(1000, 1)
        expected.delay(1000, 2)
        expected.measure(0, 0)
        expected.barrier()
        expected.x(1).c_if(0, True)
        expected.x(2).c_if(0, True)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_shorter_measure_after_measure(self):
        """Test if schedules circuits with shorter measure after measure
        with a common clbit.

        Note: For dynamic circuits support we currently group measurements
        to start at the same time which in turn trigger the end of a block."""
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.measure(1, 0)

        durations = DynamicCircuitInstructionDurations(
            [("measure", [0], 840), ("measure", [1], 540)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.delay(1000, 2)
        expected.measure(0, 0)
        expected.measure(1, 0)
        expected.delay(300, 1)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_measure_after_c_if(self):
        """Test if schedules circuits with c_if after measure with a common clbit.

        Note: This test is not yet correct as we should schedule the conditional block
        qubits with delays as well.
        """
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, 1)
        qc.measure(2, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.delay(1000, 1)
        expected.delay(1000, 2)
        expected.measure(0, 0)
        expected.barrier()
        expected.x(1).c_if(
            0, 1
        )  # Not yet correct as we should insert delays for idle qubits in conditional.
        expected.barrier()
        expected.delay(1000, 0)
        expected.measure(2, 0)
        expected.delay(1000, 1)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_parallel_gate_different_length(self):
        """Test circuit having two parallel instruction with different length."""
        qc = QuantumCircuit(2, 2)
        qc.x(0)
        qc.x(1)
        qc.measure(0, 0)
        qc.measure(1, 1)

        durations = DynamicCircuitInstructionDurations(
            [("x", [0], 200), ("x", [1], 400), ("measure", None, 840)]
        )

        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 2)
        expected.delay(200, 0)
        expected.x(0)
        expected.x(1)
        expected.measure(0, 0)  # immediately start after X gate
        expected.measure(1, 1)
        expected.barrier()

        self.assertEqual(scheduled, expected)

    def test_parallel_gate_different_length_with_barrier(self):
        """Test circuit having two parallel instruction with different length with barrier."""
        qc = QuantumCircuit(2, 2)
        qc.x(0)
        qc.x(1)
        qc.barrier()
        qc.measure(0, 0)
        qc.measure(1, 1)

        durations = DynamicCircuitInstructionDurations(
            [("x", [0], 200), ("x", [1], 400), ("measure", None, 840)]
        )

        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 2)
        expected.delay(200, 0)
        expected.x(0)
        expected.x(1)
        expected.barrier()
        expected.measure(0, 0)
        expected.measure(1, 1)
        expected.barrier()

        self.assertEqual(scheduled, expected)

    def test_measure_after_c_if_on_edge_locking(self):
        """Test if schedules circuits with c_if after measure with a common clbit.
        The scheduler is configured to reproduce behavior of the 0.20.0,
        in which clbit lock is applied to the end-edge of measure instruction.
        See https://github.com/Qiskit/qiskit-terra/pull/7655"""
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, 1)
        qc.measure(2, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )

        # lock at the end edge
        scheduled = PassManager(
            [
                ALAPScheduleAnalysis(durations),
                PadDelay(),
            ]
        ).run(qc)

        expected = QuantumCircuit(3, 1)
        expected.delay(1000, 1)
        expected.delay(1000, 2)
        expected.measure(0, 0)
        expected.barrier()
        expected.x(1).c_if(0, 1)
        expected.barrier()
        expected.delay(1000, 0)
        expected.delay(1000, 1)
        expected.measure(2, 0)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_active_reset_circuit(self):
        """Test practical example of reset circuit.

        Because of the stimulus pulse overlap with the previous XGate on the q register,
        measure instruction is always triggered after XGate regardless of write latency.
        Thus only conditional latency matters in the scheduling."""
        qc = QuantumCircuit(1, 1)
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 100), ("measure", None, 840)]
        )

        scheduled = PassManager(
            [
                ALAPScheduleAnalysis(durations),
                PadDelay(),
            ]
        ).run(qc)

        expected = QuantumCircuit(1, 1)
        expected.measure(0, 0)
        expected.x(0).c_if(0, 1)
        expected.barrier()
        expected.measure(0, 0)
        expected.x(0).c_if(0, 1)
        expected.barrier()
        expected.measure(0, 0)
        expected.x(0).c_if(0, 1)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_dag_introduces_extra_dependency_between_conditionals(self):
        """Test dependency between conditional operations in the scheduling.

        In the below example circuit, the conditional x on q1 could start at time 0,
        however it must be scheduled after the conditional x on q0 in scheduling.
        That is because circuit model used in the transpiler passes (DAGCircuit)
        interprets instructions acting on common clbits must be run in the order
        given by the original circuit (QuantumCircuit)."""
        qc = QuantumCircuit(2, 1)
        qc.delay(100, 0)
        qc.x(0).c_if(0, True)
        qc.x(1).c_if(0, True)

        durations = DynamicCircuitInstructionDurations([("x", None, 160)])
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 1)
        expected.delay(100, 0)
        expected.delay(100, 1)
        expected.barrier()
        expected.x(0).c_if(0, True)
        expected.x(1).c_if(0, True)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_scheduling_with_calibration(self):
        """Test if calibrated instruction can update node duration."""
        qc = QuantumCircuit(2)
        qc.x(0)
        qc.cx(0, 1)
        qc.x(1)
        qc.cx(0, 1)

        xsched = Schedule(Play(Constant(300, 0.1), DriveChannel(0)))
        qc.add_calibration("x", (0,), xsched)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 160), ("cx", None, 600)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2)
        expected.x(0)
        expected.delay(300, 1)
        expected.cx(0, 1)
        expected.x(1)
        expected.delay(160, 0)
        expected.cx(0, 1)
        expected.add_calibration("x", (0,), xsched)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_padding_not_working_without_scheduling(self):
        """Test padding fails when un-scheduled DAG is input."""
        qc = QuantumCircuit(1, 1)
        qc.delay(100, 0)
        qc.x(0)
        qc.measure(0, 0)

        with self.assertRaises(TranspilerError):
            PassManager(PadDelay()).run(qc)

    def test_no_pad_very_end_of_circuit(self):
        """Test padding option that inserts no delay at the very end of circuit.

        This circuit will be unchanged after scheduling/padding."""
        qc = QuantumCircuit(2, 1)
        qc.delay(100, 0)
        qc.x(1)
        qc.measure(0, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 160), ("measure", None, 840)]
        )

        scheduled = PassManager(
            [
                ALAPScheduleAnalysis(durations),
                PadDelay(fill_very_end=False),
            ]
        ).run(qc)

        expected = QuantumCircuit(2, 1)
        expected.delay(100, 0)
        expected.measure(0, 0)
        expected.delay(940, 1)
        expected.x(1)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_reset_terminates_block(self):
        """Test if reset operations terminate the block scheduled.

        Note: For dynamic circuits support we currently group resets
        to start at the same time which in turn trigger the end of a block."""
        qc = QuantumCircuit(3, 1)
        qc.x(0)
        qc.reset(0)
        qc.measure(1, 0)
        qc.x(0)

        durations = DynamicCircuitInstructionDurations(
            [
                ("x", None, 200),
                (
                    "reset",
                    [0],
                    840,
                ),  # ignored as only the duration of the measurement is used for scheduling
                (
                    "reset",
                    [1],
                    740,
                ),  # ignored as only the duration of the measurement is used for scheduling
                ("measure", [0], 440),
                ("measure", [1], 540),
            ]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.x(0)
        expected.delay(200, 1)
        expected.delay(900, 2)
        expected.reset(0)
        expected.delay(100, 0)
        expected.measure(1, 0)
        expected.barrier()
        expected.x(0)
        expected.delay(200, 1)
        expected.delay(200, 2)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_reset_merged_with_measure(self):
        """Test if reset operations terminate the block scheduled.

        Note: For dynamic circuits support we currently group resets to start
        at the same time which in turn trigger the end of a block."""
        qc = QuantumCircuit(3, 1)
        qc.x(0)
        qc.reset(0)
        qc.measure(1, 0)

        durations = DynamicCircuitInstructionDurations(
            [
                ("x", None, 200),
                (
                    "reset",
                    [0],
                    840,
                ),  # ignored as only the duration of the measurement is used for scheduling
                (
                    "reset",
                    [1],
                    740,
                ),  # ignored as only the duration of the measurement is used for scheduling
                ("measure", [0], 440),
                ("measure", [1], 540),
            ]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.x(0)
        expected.delay(200, 1)
        expected.delay(900, 2)
        expected.reset(0)
        expected.delay(100, 0)
        expected.measure(1, 0)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_already_scheduled(self):
        """Test no changes to pre-scheduled"""
        qc = QuantumCircuit(3, 2)
        qc.cx(0, 1)
        qc.delay(400, 2)
        qc.x(2)
        qc.barrier()
        qc.measure(0, 0)
        qc.delay(1000, 1)
        qc.delay(1000, 2)
        qc.barrier()
        qc.x(0).c_if(0, 1)
        qc.barrier()
        qc.measure(0, 0)
        qc.delay(1000, 1)
        qc.delay(1000, 2)
        qc.barrier()

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 100), ("measure", None, 840), ("cx", None, 500)]
        )

        scheduled = PassManager(
            [
                ALAPScheduleAnalysis(durations),
                PadDelay(),
            ]
        ).run(qc)

        self.assertEqual(qc, scheduled)

    def test_scheduling_is_idempotent(self):
        """Test that padding can be applied back to back without changing the circuit."""
        qc = QuantumCircuit(3, 2)
        qc.x(2)
        qc.cx(0, 1)
        qc.barrier()
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)
        qc.measure(0, 0)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 100), ("measure", None, 840), ("cx", None, 500)]
        )

        scheduled0 = PassManager(
            [
                ALAPScheduleAnalysis(durations),
                PadDelay(),
            ]
        ).run(qc)

        print("here")
        scheduled1 = PassManager(
            [
                ALAPScheduleAnalysis(durations),
                PadDelay(),
            ]
        ).run(scheduled0)

        self.assertEqual(scheduled0, scheduled1)

    def test_gate_on_measured_qubit(self):
        """Test that a gate on a previously measured qubit triggers the end of the block"""
        qc = QuantumCircuit(2, 1)
        qc.measure(0, 0)
        qc.x(0)
        qc.x(1)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 1)
        expected.delay(1000, 1)
        expected.x(1)
        expected.measure(0, 0)
        expected.x(0)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_grouped_measurements_prior_control_flow(self):
        """Test that measurements are grouped prior to control-flow"""
        qc = QuantumCircuit(3, 3)
        qc.measure(0, 0)
        qc.measure(1, 1)
        qc.x(2).c_if(0, 1)
        qc.x(2).c_if(1, 1)
        qc.measure(2, 2)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 3)
        expected.delay(1000, 2)
        expected.measure(0, 0)
        expected.measure(1, 1)
        expected.barrier()
        expected.x(2).c_if(0, 1)
        expected.x(2).c_if(1, 1)
        expected.barrier()
        expected.delay(1000, 0)
        expected.delay(1000, 1)
        expected.measure(2, 2)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_fast_path_eligible_scheduling(self):
        """Test scheduling of the fast-path eligible blocks.
        Verify that no barrier is inserted between measurements and fast-path conditionals.
        """
        qc = QuantumCircuit(4, 3)
        qc.x(0)
        qc.delay(1500, 1)
        qc.delay(1500, 2)
        qc.x(3)
        qc.barrier(1, 2, 3)
        qc.measure(0, 0)
        qc.measure(1, 1)
        qc.x(0).c_if(0, 1)
        qc.x(1).c_if(1, 1)
        qc.x(0)
        qc.x(0)
        qc.x(1)
        qc.x(2)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(4, 3)
        expected.delay(1300, 0)
        expected.x(0)
        expected.delay(1500, 1)
        expected.delay(1500, 2)
        expected.delay(1300, 3)
        expected.x(3)
        expected.barrier(1, 2, 3)
        expected.measure(0, 0)
        expected.measure(1, 1)
        expected.delay(1000, 2)
        expected.delay(1000, 3)
        expected.x(0).c_if(0, 1)
        expected.x(1).c_if(1, 1)
        expected.barrier()
        expected.x(0)
        expected.x(0)
        expected.delay(200, 1)
        expected.x(1)
        expected.delay(200, 2)
        expected.x(2)
        expected.delay(400, 3)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_back_to_back_c_if(self):
        """Test back to back c_if scheduling"""

        qc = QuantumCircuit(3, 1)
        qc.delay(800, 1)
        qc.x(1).c_if(0, True)
        qc.x(2).c_if(0, True)
        qc.delay(1000, 2)
        qc.x(1)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 200), ("measure", None, 840)]
        )
        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.delay(800, 0)
        expected.delay(800, 1)
        expected.delay(800, 2)
        expected.barrier()
        expected.x(1).c_if(0, True)
        expected.x(2).c_if(0, True)
        expected.barrier()
        expected.delay(1000, 0)
        expected.delay(800, 1)
        expected.x(1)
        expected.delay(1000, 2)
        expected.barrier()

        self.assertEqual(expected, scheduled)

    def test_issue_458_extra_idle_bug_0(self):
        """Regression test for https://github.com/Qiskit/qiskit-ibm-provider/issues/458

        This demonstrates that delays on idle qubits are pushed to the last schedulable
        region. This may happen if Terra's default scheduler is used and then the
        dynamic circuit scheduler is applied.
        """

        qc = QuantumCircuit(4, 3)

        qc.cx(0, 1)
        qc.delay(700, 0)
        qc.delay(700, 2)
        qc.cx(1, 2)
        qc.delay(3560, 3)
        qc.barrier([0, 1, 2])

        qc.delay(1160, 0)
        qc.delay(1000, 2)
        qc.measure(1, 0)
        qc.delay(160, 1)
        qc.x(2).c_if(0, 1)
        qc.barrier([0, 1, 2])
        qc.measure(0, 1)
        qc.delay(1000, 1)
        qc.measure(2, 2)

        durations = DynamicCircuitInstructionDurations(
            [("x", None, 160), ("cx", None, 700), ("measure", None, 840)]
        )

        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(4, 3)

        expected.cx(0, 1)
        expected.delay(700, 0)
        expected.delay(700, 2)
        expected.cx(1, 2)
        expected.barrier([0, 1, 2])
        expected.delay(2560, 3)

        expected.delay(1160, 0)
        expected.delay(1160, 2)
        expected.measure(1, 0)
        expected.delay(160, 1)
        expected.barrier()
        expected.x(2).c_if(0, 1)
        expected.barrier()
        expected.delay(2560, 0)
        expected.delay(2560, 1)
        expected.delay(2560, 2)
        expected.delay(3560, 3)
        expected.barrier([0, 1, 2])
        expected.delay(1000, 1)
        expected.measure(0, 1)
        expected.measure(2, 2)
        expected.barrier()

        self.assertEqual(scheduled, expected)

    def test_issue_458_extra_idle_bug_1(self):
        """Regression test for https://github.com/Qiskit/qiskit-ibm-provider/issues/458

        This demonstrates that a bug with a double-delay insertion has been resolved.
        """

        qc = QuantumCircuit(3, 3)

        qc.rz(0, 2)
        qc.barrier()
        qc.measure(1, 0)

        durations = DynamicCircuitInstructionDurations(
            [("rz", None, 0), ("cx", None, 700), ("measure", None, 840)]
        )

        pm = PassManager([ALAPScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 3)

        expected.rz(0, 2)
        expected.barrier()
        expected.delay(1000, 0)
        expected.measure(1, 0)
        expected.delay(1000, 2)
        expected.barrier()

        self.assertEqual(scheduled, expected)
