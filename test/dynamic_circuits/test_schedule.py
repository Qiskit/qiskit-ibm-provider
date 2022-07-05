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

import unittest

from ddt import ddt, data, unpack
from qiskit import QuantumCircuit
from qiskit.pulse import Schedule, Play, Constant, DriveChannel
from qiskit.test import QiskitTestCase
from qiskit.transpiler.instruction_durations import InstructionDurations
from qiskit.transpiler.passes import (
    PadDelay,
    SetIOLatency,
)
from qiskit.transpiler.passmanager import PassManager
from qiskit.transpiler.exceptions import TranspilerError

from qiskit_ibm_provider.dynamic_circuits.pad_delay import PadDelay
from qiskit_ibm_provider.dynamic_circuits.schedule import DynamicCircuitScheduleAnalysis


@ddt
class TestSchedulingAndPaddingPass(QiskitTestCase):
    """Tests the Scheduling passes"""

    def test_classically_controlled_gate_after_measure(self):
        """Test if schedules circuits with c_if after measure with a common clbit.
        See: https://github.com/Qiskit/qiskit-terra/issues/7654
        (input)
             ┌─┐
        q_0: ┤M├───────────
             └╥┘   ┌───┐
        q_1: ─╫────┤ X ├───
              ║    └─╥─┘
              ║ ┌────╨────┐
        c: 1/═╩═╡ c_0 = T ╞
              0 └─────────┘
        (scheduled)
                                ┌─┐┌────────────────┐
        q_0: ───────────────────┤M├┤ Delay(200[dt]) ├
             ┌─────────────────┐└╥┘└─────┬───┬──────┘
        q_1: ┤ Delay(1000[dt]) ├─╫───────┤ X ├───────
             └─────────────────┘ ║       └─╥─┘
                                 ║    ┌────╨────┐
        c: 1/════════════════════╩════╡ c_0=0x1 ╞════
                                 0    └─────────┘
        """
        qc = QuantumCircuit(2, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, True)

        durations = InstructionDurations([("x", None, 200), ("measure", None, 1000)])
        pm = PassManager([DynamicCircuitScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 1)
        expected.measure(0, 0)
        expected.delay(1000, 1)  # x.c_if starts after measure
        expected.x(1).c_if(0, True)
        expected.delay(200, 0)

        self.assertEqual(expected, scheduled)

    def test_measure_after_measure(self):
        """Test if schedules circuits with measure after measure with a common clbit.

        Note: There is no delay to write into the same clbit with IBM backends.

        (input)
               ┌───┐┌─┐
          q_0: ┤ X ├┤M├───
               └───┘└╥┘┌─┐
          q_1: ──────╫─┤M├
                     ║ └╥┘
          c: 1/══════╩══╩═
                    0  0
        (scheduled)
                     ┌───┐       ┌─┐    ░
          q_0: ──────┤ X ├───────┤M├────░─
               ┌─────┴───┴──────┐└╥┘┌─┐ ░
          q_1: ┤ Delay(200[dt]) ├─╫─┤M├─░─
               └────────────────┘ ║ └╥┘ ░
          c: 1/═══════════════════╩══╩════
                              0  0

        """
        qc = QuantumCircuit(2, 1)
        qc.x(0)
        qc.measure(0, 0)
        qc.measure(1, 0)

        durations = InstructionDurations([("x", None, 200), ("measure", None, 1000)])
        pm = PassManager([DynamicCircuitScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 1)
        expected.x(0)
        expected.delay(200, 1)
        expected.measure(0, 0)
        expected.measure(1, 0)
        expected.barrier()
        self.assertEqual(expected, scheduled)

    def test_measure_block_end(self):
        """Tests that measures trigger the end of a scheduling block and that measurements are grouped by block.

        (input)
               ┌───┐┌─┐
          q_0: ┤ X ├┤M├───
               └───┘└╥┘┌─┐
          q_1: ──────╫─┤M├
                     ║ └╥┘
          c: 1/══════╩══╩═
                    0  0
        (scheduled)
                     ┌───┐       ┌─┐    ░
          q_0: ──────┤ X ├───────┤M├────░─
               ┌─────┴───┴──────┐└╥┘┌─┐ ░
          q_1: ┤ Delay(200[dt]) ├─╫─┤M├─░─
               └────────────────┘ ║ └╥┘ ░
          c: 1/═══════════════════╩══╩════
                              0  0

        """
        qc = QuantumCircuit(3, 1)
        qc.x(0)
        qc.measure(0, 0)
        qc.measure(1, 0)
        qc.x(2)
        qc.measure(1, 0)
        qc.measure(2, 0)

        durations = InstructionDurations([("x", None, 200), ("measure", None, 1000)])
        pm = PassManager([DynamicCircuitScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.x(0)
        expected.delay(200, 1)
        expected.x(2)
        expected.delay(1000, 2)
        expected.measure(0, 0)
        expected.measure(1, 0)
        expected.barrier()
        expected.delay(1000, 0)
        expected.measure(1, 0)
        expected.measure(2, 0)
        expected.barrier()



        import pdb;pdb.set_trace()
        self.assertEqual(expected, scheduled)

    def test_c_if_on_different_qubits(self):
        """Test if schedules circuits with `c_if`s on different qubits.
        (input)
             ┌─┐
        q_0: ┤M├──────────────────────
             └╥┘   ┌───┐
        q_1: ─╫────┤ X ├──────────────
              ║    └─╥─┘      ┌───┐
        q_2: ─╫──────╫────────┤ X ├───
              ║      ║        └─╥─┘
              ║ ┌────╨────┐┌────╨────┐
        c: 1/═╩═╡ c_0 = T ╞╡ c_0 = T ╞
              0 └─────────┘└─────────┘
        (scheduled)
                                ┌─┐┌────────────────┐
        q_0: ───────────────────┤M├┤ Delay(200[dt]) ├───────────
             ┌─────────────────┐└╥┘└─────┬───┬──────┘
        q_1: ┤ Delay(1000[dt]) ├─╫───────┤ X ├──────────────────
             ├─────────────────┤ ║       └─╥─┘          ┌───┐
        q_2: ┤ Delay(1000[dt]) ├─╫─────────╫────────────┤ X ├───
             └─────────────────┘ ║         ║            └─╥─┘
                                 ║    ┌────╨────┐    ┌────╨────┐
        c: 1/════════════════════╩════╡ c_0=0x1 ╞════╡ c_0=0x1 ╞
                                 0    └─────────┘    └─────────┘
        """
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, True)
        qc.x(2).c_if(0, True)

        durations = InstructionDurations([("x", None, 200), ("measure", None, 1000)])
        pm = PassManager([DynamicCircuitScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.measure(0, 0)
        expected.delay(1000, 1)
        expected.delay(1000, 2)
        expected.x(1).c_if(0, True)
        expected.x(2).c_if(0, True)
        expected.delay(200, 0)

        self.assertEqual(expected, scheduled)

    def test_shorter_measure_after_measure(self):
        """Test if schedules circuits with shorter measure after measure with a common clbit.

        Note: For dynamic circuits support we currently group measurements to start at the same time which in turn trigger
        the end of a block.

        (input)
               ┌─┐
          q_0: ┤M├───
               └╥┘┌─┐
          q_1: ─╫─┤M├
                ║ └╥┘
          q_2: ─╫──╫─
                ║  ║
          c: 1/═╩══╩═
               0  0
        (scheduled)
               ┌─┐                                         ░
          q_0: ┤M├─────────────────────────────────────────░─
               └╥┘                   ┌─┐┌────────────────┐ ░
          q_1: ─╫────────────────────┤M├┤ Delay(300[dt]) ├─░─
                ║ ┌─────────────────┐└╥┘└────────────────┘ ░
          q_2: ─╫─┤ Delay(1000[dt]) ├─╫────────────────────░─
                ║ └─────────────────┘ ║                    ░
          c: 1/═╩═════════════════════╩══════════════════════
               0                     0
        """
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.measure(1, 0)

        durations = InstructionDurations(
            [("measure", [0], 1000), ("measure", [1], 700)]
        )
        pm = PassManager([DynamicCircuitScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(3, 1)
        expected.measure(0, 0)
        expected.measure(1, 0)
        expected.delay(300, 1)
        expected.delay(1000, 2)
        expected.barrier()

        import pdb
        pdb.set_trace()

        self.assertEqual(expected, scheduled)

    def test_measure_after_c_if(self):
        """Test if schedules circuits with c_if after measure with a common clbit.

        Note: This test is not yet correct as we should schedule the conditional block
        qubits with delays as well.

        (input)
               ┌─┐
          q_0: ┤M├──────────────
               └╥┘   ┌───┐
          q_1: ─╫────┤ X ├──────
                ║    └─╥─┘   ┌─┐
          q_2: ─╫──────╫─────┤M├
                ║ ┌────╨────┐└╥┘
          c: 1/═╩═╡ c_0 = T ╞═╩═
                0 └─────────┘ 0
        (scheduled)
                                  ┌─┐ ░             ░ ┌─────────────────┐
          q_0: ───────────────────┤M├─░─────────────░─┤ Delay(1000[dt]) ├
               ┌─────────────────┐└╥┘ ░    ┌───┐    ░ ├─────────────────┤
          q_1: ┤ Delay(1000[dt]) ├─╫──░────┤ X ├────░─┤ Delay(1000[dt]) ├
               ├─────────────────┤ ║  ░    └─╥─┘    ░ └───────┬─┬───────┘
          q_2: ┤ Delay(1000[dt]) ├─╫──░──────╫──────░─────────┤M├────────
               └─────────────────┘ ║  ░ ┌────╨────┐ ░         └╥┘
          c: 1/════════════════════╩════╡ c_0=0x1 ╞════════════╩═════════
                                   0    └─────────┘            0
        """
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, 1)
        qc.measure(2, 0)

        durations = InstructionDurations([("x", None, 200), ("measure", None, 1000)])
        pm = PassManager([DynamicCircuitScheduleAnalysis(durations), PadDelay()])
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

        self.assertEqual(expected, scheduled)

    def test_parallel_gate_different_length(self):
        """Test circuit having two parallel instruction with different length.
        (input)
             ┌───┐┌─┐
        q_0: ┤ X ├┤M├───
             ├───┤└╥┘┌─┐
        q_1: ┤ X ├─╫─┤M├
             └───┘ ║ └╥┘
        c: 2/══════╩══╩═
                   0  1
        (expected)
             ┌───┐┌─┐┌────────────────┐
        q_0: ┤ X ├┤M├┤ Delay(200[dt]) ├
             ├───┤└╥┘└──────┬─┬───────┘
        q_1: ┤ X ├─╫────────┤M├────────
             └───┘ ║        └╥┘
        c: 2/══════╩═════════╩═════════
                   0         1
        """
        qc = QuantumCircuit(2, 2)
        qc.x(0)
        qc.x(1)
        qc.measure(0, 0)
        qc.measure(1, 1)

        durations = InstructionDurations(
            [("x", [0], 200), ("x", [1], 400), ("measure", None, 1000)]
        )

        pm = PassManager([DynamicCircuitScheduleAnalysis(durations), PadDelay()])
        qc_sched = pm.run(qc)

        sched_expected = QuantumCircuit(2, 2)
        sched_expected.x(0)
        sched_expected.x(1)
        sched_expected.measure(0, 0)  # immediately start after X gate
        sched_expected.measure(1, 1)
        sched_expected.delay(200, 0)

        self.assertEqual(qc_sched, sched_expected)

    def test_parallel_gate_different_length_with_barrier(self):
        """Test circuit having two parallel instruction with different length with barrier.
        (input)
             ┌───┐┌─┐
        q_0: ┤ X ├┤M├───
             ├───┤└╥┘┌─┐
        q_1: ┤ X ├─╫─┤M├
             └───┘ ║ └╥┘
        c: 2/══════╩══╩═
                   0  1
        (expected)
             ┌───┐┌────────────────┐ ░ ┌─┐
        q_0: ┤ X ├┤ Delay(200[dt]) ├─░─┤M├───
             ├───┤└────────────────┘ ░ └╥┘┌─┐
        q_1: ┤ X ├───────────────────░──╫─┤M├
             └───┘                   ░  ║ └╥┘
        c: 2/═══════════════════════════╩══╩═
                                        0  1
        """
        qc = QuantumCircuit(2, 2)
        qc.x(0)
        qc.x(1)
        qc.barrier()
        qc.measure(0, 0)
        qc.measure(1, 1)

        durations = InstructionDurations(
            [("x", [0], 200), ("x", [1], 400), ("measure", None, 1000)]
        )

        pm = PassManager([DynamicCircuitScheduleAnalysis(durations), PadDelay()])
        qc_sched = pm.run(qc)

        sched_expected = QuantumCircuit(2, 2)
        sched_expected.x(0)
        sched_expected.delay(200, 0)
        sched_expected.x(1)
        sched_expected.barrier()
        sched_expected.measure(0, 0)
        sched_expected.measure(1, 1)

        self.assertEqual(qc_sched, sched_expected)

    def test_measure_after_c_if_on_edge_locking(self):
        """Test if schedules circuits with c_if after measure with a common clbit.
        The scheduler is configured to reproduce behavior of the 0.20.0,
        in which clbit lock is applied to the end-edge of measure instruction.
        See https://github.com/Qiskit/qiskit-terra/pull/7655
        (input)
             ┌─┐
        q_0: ┤M├──────────────
             └╥┘   ┌───┐
        q_1: ─╫────┤ X ├──────
              ║    └─╥─┘   ┌─┐
        q_2: ─╫──────╫─────┤M├
              ║ ┌────╨────┐└╥┘
        c: 1/═╩═╡ c_0 = T ╞═╩═
              0 └─────────┘ 0
        (scheduled)
                                ┌─┐┌────────────────┐
        q_0: ───────────────────┤M├┤ Delay(200[dt]) ├─────────────────────
             ┌─────────────────┐└╥┘└─────┬───┬──────┘
        q_1: ┤ Delay(1000[dt]) ├─╫───────┤ X ├────────────────────────────
             └─────────────────┘ ║       └─╥─┘       ┌─┐┌────────────────┐
        q_2: ────────────────────╫─────────╫─────────┤M├┤ Delay(200[dt]) ├
                                 ║    ┌────╨────┐    └╥┘└────────────────┘
        c: 1/════════════════════╩════╡ c_0=0x1 ╞═════╩═══════════════════
                                 0    └─────────┘     0
        """
        qc = QuantumCircuit(3, 1)
        qc.measure(0, 0)
        qc.x(1).c_if(0, 1)
        qc.measure(2, 0)

        durations = InstructionDurations([("x", None, 200), ("measure", None, 1000)])

        # lock at the end edge
        actual_sched = PassManager(
            [
                SetIOLatency(clbit_write_latency=1000),
                DynamicCircuitScheduleAnalysis(durations),
                PadDelay(),
            ]
        ).run(qc)

        expected_sched = QuantumCircuit(3, 1)
        expected_sched.measure(0, 0)
        expected_sched.delay(1000, 1)
        expected_sched.x(1).c_if(0, 1)
        expected_sched.measure(2, 0)
        expected_sched.delay(200, 0)
        expected_sched.delay(200, 2)
        self.assertEqual(expected_sched, actual_sched)

    @data([100, 200], [500, 0], [1000, 200])
    @unpack
    def test_active_reset_circuit(self, write_lat, cond_lat):
        """Test practical example of reset circuit.
        Because of the stimulus pulse overlap with the previous XGate on the q register,
        measure instruction is always triggered after XGate regardless of write latency.
        Thus only conditional latency matters in the scheduling.
        (input)
             ┌─┐   ┌───┐   ┌─┐   ┌───┐   ┌─┐   ┌───┐
          q: ┤M├───┤ X ├───┤M├───┤ X ├───┤M├───┤ X ├───
             └╥┘   └─╥─┘   └╥┘   └─╥─┘   └╥┘   └─╥─┘
              ║ ┌────╨────┐ ║ ┌────╨────┐ ║ ┌────╨────┐
        c: 1/═╩═╡ c_0=0x1 ╞═╩═╡ c_0=0x1 ╞═╩═╡ c_0=0x1 ╞
              0 └─────────┘ 0 └─────────┘ 0 └─────────┘
        """
        qc = QuantumCircuit(1, 1)
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)
        qc.measure(0, 0)
        qc.x(0).c_if(0, 1)

        durations = InstructionDurations([("x", None, 100), ("measure", None, 1000)])

        actual_sched = PassManager(
            [
                SetIOLatency(
                    clbit_write_latency=write_lat, conditional_latency=cond_lat
                ),
                DynamicCircuitScheduleAnalysis(durations),
                PadDelay(),
            ]
        ).run(qc)

        expected = QuantumCircuit(1, 1)
        expected.measure(0, 0)
        if cond_lat > 0:
            expected.delay(cond_lat, 0)
        expected.x(0).c_if(0, 1)
        expected.measure(0, 0)
        if cond_lat > 0:
            expected.delay(cond_lat, 0)
        expected.x(0).c_if(0, 1)
        expected.measure(0, 0)
        if cond_lat > 0:
            expected.delay(cond_lat, 0)
        expected.x(0).c_if(0, 1)

        self.assertEqual(expected, actual_sched)

    def test_dag_introduces_extra_dependency_between_conditionals(self):
        """Test dependency between conditional operations in the scheduling.
        In the below example circuit, the conditional x on q1 could start at time 0,
        however it must be scheduled after the conditional x on q0 in scheduling.
        That is because circuit model used in the transpiler passes (DAGCircuit)
        interprets instructions acting on common clbits must be run in the order
        given by the original circuit (QuantumCircuit).
        (input)
             ┌────────────────┐   ┌───┐
        q_0: ┤ Delay(100[dt]) ├───┤ X ├───
             └─────┬───┬──────┘   └─╥─┘
        q_1: ──────┤ X ├────────────╫─────
                   └─╥─┘            ║
                ┌────╨────┐    ┌────╨────┐
        c: 1/═══╡ c_0=0x1 ╞════╡ c_0=0x1 ╞
                └─────────┘    └─────────┘
        (scheduled)
             ┌────────────────┐   ┌───┐
        q_0: ┤ Delay(100[dt]) ├───┤ X ├──────────────
             ├────────────────┤   └─╥─┘      ┌───┐
        q_1: ┤ Delay(100[dt]) ├─────╫────────┤ X ├───
             └────────────────┘     ║        └─╥─┘
                               ┌────╨────┐┌────╨────┐
        c: 1/══════════════════╡ c_0=0x1 ╞╡ c_0=0x1 ╞
                               └─────────┘└─────────┘
        """
        qc = QuantumCircuit(2, 1)
        qc.delay(100, 0)
        qc.x(0).c_if(0, True)
        qc.x(1).c_if(0, True)

        durations = InstructionDurations([("x", None, 160)])
        pm = PassManager([DynamicCircuitScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2, 1)
        expected.delay(100, 0)
        expected.delay(100, 1)  # due to extra dependency on clbits
        expected.x(0).c_if(0, True)
        expected.x(1).c_if(0, True)

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

        durations = InstructionDurations([("x", None, 160), ("cx", None, 600)])
        pm = PassManager([DynamicCircuitScheduleAnalysis(durations), PadDelay()])
        scheduled = pm.run(qc)

        expected = QuantumCircuit(2)
        expected.x(0)
        expected.delay(300, 1)
        expected.cx(0, 1)
        expected.x(1)
        expected.delay(160, 0)
        expected.cx(0, 1)
        expected.add_calibration("x", (0,), xsched)

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
        This circuit will be unchanged after scheduling/padding.
             ┌────────────────┐┌─┐
        q_0: ┤ Delay(100[dt]) ├┤M├
             └─────┬───┬──────┘└╥┘
        q_1: ──────┤ X ├────────╫─
                   └───┘        ║
        c: 1/═══════════════════╩═
                                0
        """
        qc = QuantumCircuit(2, 1)
        qc.delay(100, 0)
        qc.x(1)
        qc.measure(0, 0)

        durations = InstructionDurations([("x", None, 160), ("measure", None, 1000)])

        scheduled = PassManager(
            [
                DynamicCircuitScheduleAnalysis(durations),
                PadDelay(fill_very_end=False),
            ]
        ).run(qc)

        self.assertEqual(scheduled, qc)


if __name__ == "__main__":
    unittest.main()
