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

"""Scheduler for dynamic circuit backends."""

import qiskit
from qiskit.circuit import Measure
from qiskit.transpiler.exceptions import TranspilerError
from qiskit.transpiler.passes.scheduling.scheduling.base_scheduler import BaseScheduler


class DynamicCircuitScheduleAnalysis(BaseScheduler):
    """Dynamic circuits scheduling analysis pass.

    This is a scheduler designed to work for the unique scheduling constraints of the dynamic circuits
    backends due to the limitations imposed by hardware. This is expected to evolve overtime as the
    dynamic circuit backends also change.

    In its current form this is slow to Qiskit's ASAP scheduler in which instructions start asas early as possible.

    The primary differences are that:

    * Measurements currently trigger the end of a "quantum block". The period between the end of the block and the next is *indeterministic*
        ie., we do not know when the next block will begin (as we could be evaluating a classical function of indeterministic length) and
        therefore the next block starts at a *relative* t=0.
    * It is possible to apply gates during a measurement.
    * Measurements on disjoint qubits happen simulataneously and are part of the same block. Measurements that are not lexigraphically
        neighbors in the generated QASM3 will happen in separate blocks.

    """

    def __init__(self, durations: qiskit.transpiler.instruction_durations.InstructionDurations):
        """Scheduler for dynamic circuit backends.

        Args:
            durations: Durations of instructions to be used in scheduling.
        """

        self._dag = None

        self._conditional_latency = 0
        self._clbit_write_latency = 0

        self._node_start_time = None
        self._idle_after = None
        self._bit_indices = None

        super().__init__(durations)

    def run(self, dag):
        """Run the ASAPSchedule pass on `dag`.
        Args:
            dag (DAGCircuit): DAG to schedule.
        Returns:
            DAGCircuit: A scheduled DAG.
        Raises:
            TranspilerError: if the circuit is not mapped on physical qubits.
            TranspilerError: if conditional bit is added to non-supported instruction.
        """
        self._init_run(dag)

        for node in dag.topological_op_nodes():
            self._visit_node(node)

        self.property_set["node_start_time"] = self._node_start_time

    def _init_run(self, dag):
        """Setup for initial run."""

        self._dag = dag

        if len(dag.qregs) != 1 or dag.qregs.get("q", None) is None:
            raise TranspilerError("ASAP schedule runs on physical circuits only")

        self._conditional_latency = self.property_set.get("conditional_latency", 0)
        self._clbit_write_latency = self.property_set.get("clbit_write_latency", 0)

        self._node_start_time = dict()
        self._idle_after = {q: 0 for q in dag.qubits + dag.clbits}
        self._bit_indices = {q: index for index, q in enumerate(dag.qubits)}

    def _get_node_duration(self, node):
        return super()._get_node_duration(node, self._bit_indices, self._dag)

    def _visit_node(self, node):
        # compute t0, t1: instruction interval, note that
        # t0: start time of instruction
        # t1: end time of instruction
        if isinstance(node.op, self.CONDITIONAL_SUPPORTED):
            t0, t1 = self._visit_conditional_node(node)
        else:
            if node.op.condition_bits:
                raise TranspilerError(
                    f"Conditional instruction {node.op.name} is not supported in ASAP scheduler."
                )

            if isinstance(node.op, Measure):
                t0, t1 = self._visit_measure(node)
            else:
                t0, t1 = self._visit_generic(node)

        for bit in node.qargs:
            self._idle_after[bit] = t1

        self._node_start_time[node] = t0

    def _visit_conditional_node(self, node):
        op_duration = self._get_node_duration(node)

        t0q = max(self._idle_after[q] for q in node.qargs)
        if node.op.condition_bits:
            # conditional is bit tricky due to conditional_latency
            t0c = max(self._idle_after[bit] for bit in node.op.condition_bits)
            if t0q > t0c:
                # This is situation something like below
                #
                #           |t0q
                # Q ▒▒▒▒▒▒▒▒▒░░
                # C ▒▒▒░░░░░░░░
                #     |t0c
                #
                # In this case, you can insert readout access before tq0
                #
                #           |t0q
                # Q ▒▒▒▒▒▒▒▒▒▒▒
                # C ▒▒▒░░░▒▒░░░
                #         |t0q - conditional_latency
                #
                t0c = max(t0q - self._conditional_latency, t0c)
            t1c = t0c + self._conditional_latency
            for bit in node.op.condition_bits:
                # Lock clbit until state is read
                self._idle_after[bit] = t1c
            # It starts after register read access
            t0 = max(t0q, t1c)
        else:
            t0 = t0q
            t1 = t0 + op_duration

        t1 = t0 + op_duration
        return t0, t1

    def _visit_measure(self, node):
        op_duration = self._get_node_duration(node)

        # measure instruction handling is bit tricky due to clbit_write_latency
        t0q = max(self._idle_after[q] for q in node.qargs)
        t0c = max(self._idle_after[c] for c in node.cargs)
        # Assume following case (t0c > t0q)
        #
        #       |t0q
        # Q ▒▒▒▒░░░░░░░░░░░░
        # C ▒▒▒▒▒▒▒▒░░░░░░░░
        #           |t0c
        #
        # In this case, there is no actual clbit access until clbit_write_latency.
        # The node t0 can be push backward by this amount.
        #
        #         |t0q' = t0c - clbit_write_latency
        # Q ▒▒▒▒░░▒▒▒▒▒▒▒▒▒▒
        # C ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
        #           |t0c' = t0c
        #
        # rather than naively doing
        #
        #           |t0q' = t0c
        # Q ▒▒▒▒░░░░▒▒▒▒▒▒▒▒
        # C ▒▒▒▒▒▒▒▒░░░▒▒▒▒▒
        #              |t0c' = t0c + clbit_write_latency
        #
        t0 = max(t0q, t0c - self._clbit_write_latency)
        t1 = t0 + op_duration
        for clbit in node.cargs:
            self._idle_after[clbit] = t1

        return t0, t1

    def _visit_generic(self, node):
        """Visit a generic node such as a gate or barrier."""
        op_duration = self._get_node_duration(node)

        # It happens to be directives such as barrier
        t0 = max(self._idle_after[bit] for bit in node.qargs + node.cargs)
        t1 = t0 + op_duration
        return t0, t1
