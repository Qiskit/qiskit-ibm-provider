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

from abc import abstractmethod
from typing import Dict, Optional, Union, Set, Tuple
import itertools

import qiskit
from qiskit.circuit import Clbit, Measure, Qubit, Reset, Barrier
from qiskit.dagcircuit import DAGCircuit, DAGNode
from qiskit.transpiler.exceptions import TranspilerError
from qiskit.transpiler.passes.scheduling.scheduling.base_scheduler import BaseScheduler

from .utils import block_order_op_nodes


class BaseDynamicCircuitAnalysis(BaseScheduler):
    """Base class for scheduling analysis

    This is a scheduler designed to work for the unique scheduling constraints of the dynamic circuits
    backends due to the limitations imposed by hardware. This is expected to evolve over time as the
    dynamic circuit backends also change.

    The primary differences are that:

    * Resets and control-flow currently trigger the end of a "quantum block". The period between the end
        of the block and the next is *nondeterministic*
        ie., we do not know when the next block will begin (as we could be evaluating a classical
        function of nondeterministic length) and therefore the
        next block starts at a *relative* t=0.
    * During a measurement it is possible to apply gates in parallel on disjoint qubits.
    * Measurements and resets on disjoint qubits happen simultaneously and are part of the same block.
    """

    def __init__(
        self, durations: qiskit.transpiler.instruction_durations.InstructionDurations
    ) -> None:
        """Scheduler for dynamic circuit backends.

        Args:
            durations: Durations of instructions to be used in scheduling.
        """

        self._dag = None

        self._current_block_idx = 0
        self._max_block_t1: Optional[Dict[int, int]] = None
        # Track as we build to avoid extra pass
        self._conditional_block = False
        self._node_start_time: Optional[Dict[DAGNode, Tuple[int, int]]] = None
        self._node_stop_time: Optional[Dict[DAGNode, Tuple[int, int]]] = None
        self._bit_stop_times: Optional[Dict[int, Dict[Union[Qubit, Clbit], int]]] = None
        # Dictionary of blocks each containing a dictionary with the key for each bit
        # in the block and its value being the final time of the bit within the block.
        self._current_block_measures: Set[DAGNode] = set()
        self._current_block_fast_path_nodes: Set[DAGNode] = set()
        self._current_block_measures_has_reset: bool = False
        self._node_tied_to: Optional[Dict[DAGNode, Set[DAGNode]]] = None
        # Nodes that the scheduling of this node is tied to.
        self._bit_indices: Optional[Dict[Qubit, int]] = None

        # Last node to touch a bit
        self._last_node_to_touch: Optional[Dict[Qubit, DAGNode]] = None

        super().__init__(durations)

    @property
    def _current_block_bit_times(self) -> Dict[Union[Qubit, Clbit], int]:
        return self._bit_stop_times[self._current_block_idx]

    @abstractmethod
    def _visit_node(self, node: DAGNode) -> None:
        raise NotImplementedError

    def _init_run(self, dag: DAGCircuit) -> None:
        """Setup for initial run."""

        self._dag = dag
        self._current_block_idx = 0
        self._max_block_t1 = {}
        self._conditional_block = False

        if len(dag.qregs) != 1 or dag.qregs.get("q", None) is None:
            raise TranspilerError("ASAP schedule runs on physical circuits only")

        self._node_start_time = {}
        self._node_stop_time = {}
        self._bit_stop_times = {0: {q: 0 for q in dag.qubits + dag.clbits}}
        self._current_block_measures = set()
        self._current_block_measures_has_reset = False
        self._node_tied_to = {}
        self._bit_indices = {q: index for index, q in enumerate(dag.qubits)}
        self._last_node_to_touch = {}

    def _get_duration(self, node: DAGNode) -> int:
        if node.op.condition_bits:
            # As we cannot currently schedule through conditionals model
            # as zero duration to avoid padding.
            return 0
        return super()._get_node_duration(node, self._bit_indices, self._dag)

    def _update_bit_times(  # pylint: disable=invalid-name
        self, node: DAGNode, t0: int, t1: int, update_cargs: bool = True
    ) -> None:
        self._max_block_t1[self._current_block_idx] = max(
            self._max_block_t1.get(self._current_block_idx, 0), t1
        )

        update_bits = (
            itertools.chain(node.qargs, node.cargs) if update_cargs else node.qargs
        )
        for bit in update_bits:
            self._current_block_bit_times[bit] = t1

        self._node_start_time[node] = (self._current_block_idx, t0)
        self._node_stop_time[node] = (self._current_block_idx, t1)

    def _begin_new_circuit_block(self) -> None:
        """Create a new timed circuit block completing the previous block."""
        self._current_block_idx += 1
        self._conditional_block = False
        self._bit_stop_times[self._current_block_idx] = {
            q: 0 for q in self._dag.qubits + self._dag.clbits
        }
        self._last_node_to_touch = {}
        self._flush_measures()

    def _flush_measures(self) -> None:
        """Flush currently accumulated measurements by resetting block measures."""
        for node in self._current_block_measures:
            self._node_tied_to[node] = self._current_block_measures.copy()

        self._current_block_measures = set()
        self._current_block_measures_has_reset = False

    def _current_block_measure_qargs(self) -> Set[Qubit]:
        return set(
            qarg for measure in self._current_block_measures for qarg in measure.qargs
        )

    def _will_use_fast_path(self, node: DAGNode) -> bool:
        """Check if this conditional operation will be scheduled on the fastpath.

        This will happen if
        1. This operation is a direct descendent of a current measurement block to be flushed
        2. The operation only operates on the qubit that is measured.
        """
        condition_bits = node.op.condition_bits
        for bit in condition_bits:
            last_node = self._last_node_to_touch.get(bit, None)
            if not (
                last_node is not None
                and isinstance(last_node.op, Measure)
                and set(node.qargs) == set(last_node.qargs)
            ):
                return False
        return True

    def _last_node_to_touch_was_conditional(self, node: DAGNode) -> bool:
        for arg in itertools.chain(node.qargs, node.cargs):
            last_node = self._last_node_to_touch.get(arg, None)
            if last_node is not None:
                if last_node.op.condition_bits or isinstance(last_node.op, Reset):
                    return True
        return False


class ASAPScheduleAnalysis(BaseDynamicCircuitAnalysis):
    """Dynamic circuits as-soon-as-possible (ASAP) scheduling analysis pass.

    This is a scheduler designed to work for the unique scheduling constraints of the dynamic circuits
    backends due to the limitations imposed by hardware. This is expected to evolve over time as the
    dynamic circuit backends also change.

    In its current form this is similar to Qiskit's ASAP scheduler in which instructions
    start as early as possible.

    The primary differences are that:

    * Resets and control-flow currently trigger the end of a "quantum block". The period between the end
        of the block and the next is *nondeterministic*
        ie., we do not know when the next block will begin (as we could be evaluating a classical
        function of nondeterministic length) and therefore the
        next block starts at a *relative* t=0.
    * During a measurement it is possible to apply gates in parallel on disjoint qubits.
    * Measurements and resets on disjoint qubits happen simultaneously and are part of the same block.
    """

    def run(self, dag: DAGCircuit) -> None:
        """Run the ALAPSchedule pass on `dag`.
        Args:
            dag (DAGCircuit): DAG to schedule.
        Raises:
            TranspilerError: if the circuit is not mapped on physical qubits.
            TranspilerError: if conditional bit is added to non-supported instruction.
        """
        self._init_run(dag)

        for node in block_order_op_nodes(dag):
            self._visit_node(node)

        # Final flush
        self._flush_measures()
        self.property_set["node_start_time"] = self._node_start_time

    def _visit_node(self, node: DAGNode) -> None:
        # compute t0, t1: instruction interval, note that
        # t0: start time of instruction
        # t1: end time of instruction
        if isinstance(node.op, self.CONDITIONAL_SUPPORTED) and node.op.condition_bits:
            self._visit_conditional_node(node)
        else:
            if node.op.condition_bits:
                raise TranspilerError(
                    f"Conditional instruction {node.op.name} is not supported in ASAP scheduler."
                )

            if isinstance(node.op, Measure):
                self._visit_measure(node)
            elif isinstance(node.op, Reset):
                self._visit_reset(node)
            else:
                self._visit_generic(node)

    def _visit_conditional_node(self, node: DAGNode) -> None:
        """Handling case of a conditional execution.

        Conditional execution durations are currently non-deterministic. as we do not know
        the time it will take to begin executing the block. We do however know the
        duration of the block contents execution (provided it does not also contain
        conditional executions).

        TODO: Update for support of general control-flow, not just single conditional operations.
        """
        # Don't trigger if we're using the fast-path as these will be parallelized
        # and inserting a barrier would interrupt this.
        if not self._will_use_fast_path(node) and not self._conditional_block:
            # We group conditional operations within
            # a conditional block to allow the backend
            # a chance to optimize them. If we did
            # not do this barriers would be inserted
            # between conditional operations.
            # Therefore only trigger the start of a conditional
            # block if we are not already within one.
            self._begin_new_circuit_block()

        self._last_node_to_touch.update(
            {
                bit: node
                for bit in itertools.chain(
                    node.qargs, node.cargs, node.op.condition_bits
                )
            }
        )

        # This block is now by definition a "conditional_block".
        self._conditional_block = True

        op_duration = self._get_duration(node)

        t0q = max(self._current_block_bit_times[q] for q in node.qargs)
        # conditional is bit tricky due to conditional_latency
        t0c = max(self._current_block_bit_times[bit] for bit in node.op.condition_bits)
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
            #         |t0c
            #
            t0c = t0q
        t1c = t0c
        for bit in node.op.condition_bits:
            # Lock clbit until state is read
            self._current_block_bit_times[bit] = t1c

        # It starts after register read access
        t0 = max(t0q, t1c)  # pylint: disable=invalid-name

        t1 = t0 + op_duration  # pylint: disable=invalid-name
        self._update_bit_times(node, t0, t1)

    def _visit_measure(self, node: DAGNode) -> None:
        """Visit a measurement node.

        Measurement currently triggers the end of a deterministically scheduled block
        of instructions in IBM dynamic circuits hardware.
        This means that it is possible to schedule *up to* a measurement (and during its pulses)
        but the measurement will be followed by a period of indeterminism.
        All measurements on disjoint qubits that topologically follow another
        measurement will be collected and performed in parallel. A measurement on a qubit
        intersecting with the set of qubits to be measured in parallel will trigger the
        end of a scheduling block with said measurement occurring in a following block
        which begins another grouping sequence. This behavior will change in future
        backend software updates."""
        # If True we are coming from a conditional block.
        # start a new block for the unconditional operations.
        if self._conditional_block and self._last_node_to_touch_was_conditional(node):
            self._begin_new_circuit_block()

        self._last_node_to_touch.update({bit: node for bit in node.qargs + node.cargs})

        current_block_measure_qargs = self._current_block_measure_qargs()
        # We handle a set of qubits here as _visit_reset currently calls
        # this method and a reset may have multiple qubits.
        measure_qargs = set(node.qargs)

        t0q = max(
            self._current_block_bit_times[q] for q in measure_qargs
        )  # pylint: disable=invalid-name

        # If the measurement qubits overlap, we need to flush measurements and start a
        # new scheduling block.
        if current_block_measure_qargs & measure_qargs:
            if self._current_block_measures_has_reset:
                # If a reset is included we must trigger the end of a block.
                self._begin_new_circuit_block()
                t0q = 0
            else:
                # Otherwise just trigger a measurement flush
                self._flush_measures()
        else:
            # Otherwise we need to increment all measurements to start at the same time within the block.
            t0q = max(  # pylint: disable=invalid-name
                itertools.chain(
                    [t0q],
                    (
                        self._node_start_time[measure][1]
                        for measure in self._current_block_measures
                    ),
                )
            )

        # Insert this measure into the block
        self._current_block_measures.add(node)

        for measure in self._current_block_measures:
            t0 = t0q  # pylint: disable=invalid-name
            bit_indices = {bit: index for index, bit in enumerate(self._dag.qubits)}
            measure_duration = self.durations.get(
                Measure(), [bit_indices[qarg] for qarg in measure.qargs], unit="dt"
            )
            t1 = t0 + measure_duration  # pylint: disable=invalid-name
            self._update_bit_times(measure, t0, t1)

    def _visit_reset(self, node: DAGNode) -> None:
        """Visit a reset node.

        Reset currently triggers the end of a pulse block in IBM dynamic circuits hardware
        as conditional reset is performed internally using a c_if. This means that it is
        possible to schedule *up to* a reset (and during its measurement pulses)
        but the reset will be followed by a period of conditional indeterminism.
        All resets on disjoint qubits will be collected on the same qubits to be run simultaneously.
        """
        # Process as measurement
        self._current_block_measures_has_reset = True
        self._visit_measure(node)
        # Then set that we are now a conditional node.
        self._conditional_block = True

    def _visit_generic(self, node: DAGNode) -> None:
        """Visit a generic node such as a gate or barrier."""
        # If True we are coming from a conditional block.
        # start a new block for the unconditional operations.
        if self._conditional_block:
            self._begin_new_circuit_block()

        op_duration = self._get_duration(node)

        # If the measurement qubits overlap, we need to flush the measurement group
        if self._current_block_measure_qargs() & set(node.qargs):
            self._flush_measures()

        t0 = max(  # pylint: disable=invalid-name
            self._current_block_bit_times[bit] for bit in node.qargs + node.cargs
        )

        t1 = t0 + op_duration  # pylint: disable=invalid-name
        self._update_bit_times(node, t0, t1)


class ALAPScheduleAnalysis(BaseDynamicCircuitAnalysis):
    """Dynamic circuits as-late-as-possible (ALAP) scheduling analysis pass.

    This is a scheduler designed to work for the unique scheduling constraints of the dynamic circuits
    backends due to the limitations imposed by hardware. This is expected to evolve over time as the
    dynamic circuit backends also change.

    In its current form this is similar to Qiskit's ALAP scheduler in which instructions
    start as late as possible.

    The primary differences are that:

    * Resets and control-flow currently trigger the end of a "quantum block". The period between the end
        of the block and the next is *nondeterministic*
        ie., we do not know when the next block will begin (as we could be evaluating a classical
        function of nondeterministic length) and therefore the
        next block starts at a *relative* t=0.
    * During a measurement it is possible to apply gates in parallel on disjoint qubits.
    * Measurements and resets on disjoint qubits happen simultaneously and are part of the same block.
    """

    def run(self, dag: DAGCircuit) -> None:
        """Run the ASAPSchedule pass on `dag`.
        Args:
            dag (DAGCircuit): DAG to schedule.
        Raises:
            TranspilerError: if the circuit is not mapped on physical qubits.
            TranspilerError: if conditional bit is added to non-supported instruction.
        """
        self._init_run(dag)

        for node in block_order_op_nodes(dag):
            self._visit_node(node)
        # Final flush
        self._flush_measures()
        # Inverse schedule after determining durations of each block
        self._push_block_durations()
        self.property_set["node_start_time"] = self._node_start_time

    def _visit_node(self, node: DAGNode) -> None:
        # compute t0, t1: instruction interval, note that
        # t0: start time of instruction
        # t1: end time of instruction
        if isinstance(node.op, self.CONDITIONAL_SUPPORTED) and node.op.condition_bits:
            self._visit_conditional_node(node)
        else:
            if node.op.condition_bits:
                raise TranspilerError(
                    f"Conditional instruction {node.op.name} is not supported in ASAP scheduler."
                )

            if isinstance(node.op, Measure):
                self._visit_measure(node)
            elif isinstance(node.op, Reset):
                self._visit_reset(node)
            else:
                self._visit_generic(node)

    def _visit_conditional_node(self, node: DAGNode) -> None:
        """Handling case of a conditional execution.

        Conditional execution durations are currently non-deterministic. as we do not know
        the time it will take to begin executing the block. We do however know the
        duration of the block contents execution (provided it does not also contain
        conditional executions).

        TODO: Update for support of general control-flow, not just single conditional operations.
        """
        # Don't trigger if we're using the fast-path as these will be parallelized
        # and inserting a barrier would interrupt this.
        if not self._will_use_fast_path(node) and not self._conditional_block:
            # We group conditional operations within
            # a conditional block to allow the backend
            # a chance to optimize them. If we did
            # not do this barriers would be inserted
            # between conditional operations.
            # Therefore only trigger the start of a conditional
            # block if we are not already within one.
            self._begin_new_circuit_block()

        self._last_node_to_touch.update(
            {
                bit: node
                for bit in itertools.chain(
                    node.qargs, node.cargs, node.op.condition_bits
                )
            }
        )

        # This block is now by definition a "conditional_block".
        self._conditional_block = True

        op_duration = self._get_duration(node)

        t0q = max(self._current_block_bit_times[q] for q in node.qargs)
        # conditional is bit tricky due to conditional_latency
        t0c = max(self._current_block_bit_times[bit] for bit in node.op.condition_bits)

        t0 = max(t0q, t0c)  # pylint: disable=invalid-name
        t1 = t0 + op_duration  # pylint: disable=invalid-name

        self._update_bit_times(node, t0, t1, update_cargs=False)

    def _visit_measure(self, node: DAGNode) -> None:
        """Visit a measurement node.

        Measurement currently triggers the end of a deterministically scheduled block
        of instructions in IBM dynamic circuits hardware.
        This means that it is possible to schedule *up to* a measurement (and during its pulses)
        but the measurement will be followed by a period of indeterminism.
        All measurements on disjoint qubits that topologically follow another
        measurement will be collected and performed in parallel. A measurement on a qubit
        intersecting with the set of qubits to be measured in parallel will trigger the
        end of a scheduling block with said measurement occurring in a following block
        which begins another grouping sequence. This behavior will change in future
        backend software updates."""

        # If True we are coming from a conditional block.
        # start a new block for the unconditional operations.
        if self._conditional_block and self._last_node_to_touch_was_conditional(node):
            self._begin_new_circuit_block()

        self._last_node_to_touch.update({bit: node for bit in node.qargs + node.cargs})

        current_block_measure_qargs = self._current_block_measure_qargs()
        # We handle a set of qubits here as _visit_reset currently calls
        # this method and a reset may have multiple qubits.
        measure_qargs = set(node.qargs)

        t0q = max(
            self._current_block_bit_times[q] for q in measure_qargs
        )  # pylint: disable=invalid-name

        # If the measurement qubits overlap, we need to flush measurements and start a
        # new scheduling block.
        if current_block_measure_qargs & measure_qargs:
            if self._current_block_measures_has_reset:
                # If a reset is included we must trigger the end of a block.
                self._begin_new_circuit_block()
                t0q = 0
            else:
                # Otherwise just trigger a measurement flush
                self._flush_measures()
        else:
            # Otherwise we need to increment all measurements to start at the same time within the block.
            t0q = max(  # pylint: disable=invalid-name
                itertools.chain(
                    [t0q],
                    (
                        self._node_start_time[measure][1]
                        for measure in self._current_block_measures
                    ),
                )
            )

        # Insert this measure into the block
        self._current_block_measures.add(node)

        for measure in self._current_block_measures:
            t0 = t0q  # pylint: disable=invalid-name
            bit_indices = {bit: index for index, bit in enumerate(self._dag.qubits)}
            measure_duration = self.durations.get(
                Measure(), [bit_indices[qarg] for qarg in measure.qargs], unit="dt"
            )
            t1 = t0 + measure_duration  # pylint: disable=invalid-name
            self._update_bit_times(measure, t0, t1)

    def _visit_reset(self, node: DAGNode) -> None:
        """Visit a reset node.

        Reset currently triggers the end of a pulse block in IBM dynamic circuits hardware
        as conditional reset is performed internally using a c_if. This means that it is
        possible to schedule *up to* a reset (and during its measurement pulses)
        but the reset will be followed by a period of conditional indeterminism.
        All resets on disjoint qubits will be collected on the same qubits to be run simultaneously.
        """
        # Process as measurement
        self._current_block_measures_has_reset = True
        self._visit_measure(node)
        # Then set that we are now a conditional node.
        self._conditional_block = True

    def _visit_generic(self, node: DAGNode) -> None:
        """Visit a generic node such as a gate or barrier."""

        # If True we are coming from a conditional block.
        # start a new block for the unconditional operations.
        if self._conditional_block:
            self._begin_new_circuit_block()

        self._last_node_to_touch.update({bit: node for bit in node.qargs})

        op_duration = self._get_duration(node)

        # If the measurement qubits overlap, we need to flush the measurement group
        if self._current_block_measure_qargs() & set(node.qargs):
            self._flush_measures()

        t0 = max(  # pylint: disable=invalid-name
            self._current_block_bit_times[bit] for bit in node.qargs + node.cargs
        )

        t1 = t0 + op_duration  # pylint: disable=invalid-name
        self._update_bit_times(node, t0, t1)

    def _push_block_durations(self) -> None:
        """After scheduling of each block, pass over and push the times of all nodes."""

        # Store the next available time to push to for the block by bit
        block_bit_times = {}
        # Iterated nodes starting at the first, from the node with the
        # last time, preferring barriers over non-barriers

        def order_ops(
            item: Tuple[DAGNode, Tuple[int, int]]
        ) -> Tuple[int, int, bool, int]:
            """Iterated nodes ordering by channel, time and preferring that barriers are processed
            first."""
            return (
                item[1][0],
                -item[1][1],
                not isinstance(item[0].op, Barrier),
                self._get_duration(item[0]),
            )

        iterate_nodes = sorted(self._node_stop_time.items(), key=order_ops)

        new_node_start_time = {}
        new_node_stop_time = {}

        def _calculate_new_times(
            block: int, node: DAGNode, block_bit_times: Dict[int, Dict[Qubit, int]]
        ) -> int:
            max_block_time = min(block_bit_times[block][bit] for bit in node.qargs)

            t0 = self._node_start_time[node][1]  # pylint: disable=invalid-name
            t1 = self._node_stop_time[node][1]  # pylint: disable=invalid-name
            # Determine how much to shift by
            node_offset = max_block_time - t1
            new_t0 = t0 + node_offset
            return new_t0

        scheduled = set()

        def _update_time(
            block: int,
            node: DAGNode,
            new_time: int,
            block_bit_times: Dict[int, Dict[Qubit, int]],
        ) -> None:
            scheduled.add(node)

            new_node_start_time[node] = (block, new_time)
            new_node_stop_time[node] = (block, new_time + self._get_duration(node))

            # Update available times by bit
            for bit in node.qargs:
                block_bit_times[block][bit] = new_time

        for node, (
            block,
            _,
        ) in iterate_nodes:  # pylint: disable=invalid-name
            # skip already scheduled
            if node in scheduled:
                continue
            # Start with last time as the time to push to
            if block not in block_bit_times:
                block_bit_times[block] = {
                    q: self._max_block_t1[block]
                    for q in self._dag.qubits + self._dag.clbits
                }

            # Calculate the latest available time to push to collectively for tied nodes
            tied_nodes = self._node_tied_to.get(node, None)
            if tied_nodes is not None:
                # Take the minimum time that will be schedulable
                # self._node_tied_to includes the node itself.
                new_times = [
                    _calculate_new_times(block, tied_node, block_bit_times)
                    for tied_node in self._node_tied_to[node]
                ]
                new_time = min(new_times)
                for tied_node in tied_nodes:
                    _update_time(block, tied_node, new_time, block_bit_times)

            else:
                new_t0 = _calculate_new_times(block, node, block_bit_times)
                _update_time(block, node, new_t0, block_bit_times)

        self._node_start_time = new_node_start_time
        self._node_stop_time = new_node_stop_time
