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

"""Padding pass to fill timeslots for IBM (dynamic circuit) backends."""

from typing import Any, Dict, List, Optional, Union

from qiskit.circuit import Qubit, Clbit, Instruction
from qiskit.circuit.library import Barrier
from qiskit.circuit.delay import Delay
from qiskit.dagcircuit import DAGCircuit, DAGNode
from qiskit.transpiler.basepasses import TransformationPass
from qiskit.transpiler.exceptions import TranspilerError

from .utils import block_order_op_nodes


class BlockBasePadder(TransformationPass):
    """The base class of padding pass.

    This pass requires one of scheduling passes to be executed before itself.
    Since there are multiple scheduling strategies, the selection of scheduling
    pass is left in the hands of the pass manager designer.
    Once a scheduling analysis pass is run, ``node_start_time`` is generated
    in the :attr:`property_set`.  This information is represented by a python dictionary of
    the expected instruction execution times keyed on the node instances.
    The padding pass expects all ``DAGOpNode`` in the circuit to be scheduled.

    This base class doesn't define any sequence to interleave, but it manages
    the location where the sequence is inserted, and provides a set of information necessary
    to construct the proper sequence. Thus, a subclass of this pass just needs to implement
    :meth:`_pad` method, in which the subclass constructs a circuit block to insert.
    This mechanism removes lots of boilerplate logic to manage whole DAG circuits.

    Note that padding pass subclasses should define interleaving sequences satisfying:

        - Interleaved sequence does not change start time of other nodes
        - Interleaved sequence should have total duration of the provided ``time_interval``.

    Any manipulation violating these constraints may prevent this base pass from correctly
    tracking the start time of each instruction,
    which may result in violation of hardware alignment constraints.
    """

    def __init__(self) -> None:
        self._node_start_time = None
        self._idle_after: Optional[Dict[Qubit, int]] = None
        self._dag = None
        self._prev_node: Optional[DAGNode] = None
        self._block_duration = 0
        self._current_block_idx = 0
        self._conditional_block = False

        super().__init__()

    def run(self, dag: DAGCircuit) -> DAGCircuit:
        """Run the padding pass on ``dag``.

        Args:
            dag: DAG to be checked.

        Returns:
            DAGCircuit: DAG with idle time filled with instructions.

        Raises:
            TranspilerError: When a particular node is not scheduled, likely some transform pass
                is inserted before this node is called.
        """
        self._pre_runhook(dag)

        self._init_run(dag)

        # Compute fresh circuit duration from the node start time dictionary and op duration.
        # Note that pre-scheduled duration may change within the alignment passes, i.e.
        # if some instruction time t0 violating the hardware alignment constraint,
        # the alignment pass may delay t0 and accordingly the circuit duration changes.
        for node in block_order_op_nodes(dag):
            if node in self._node_start_time:
                if isinstance(node.op, Delay):
                    self._visit_delay(node)
                else:
                    self._visit_generic(node)

            else:
                raise TranspilerError(
                    f"Operation {repr(node)} is likely added after the circuit is scheduled. "
                    "Schedule the circuit again if you transformed it."
                )

            self._prev_node = node

        # terminate final block
        self._terminate_block(self._block_duration, self._current_block_idx, None)

        return self._dag

    def _init_run(self, dag: DAGCircuit) -> None:
        """Setup for initial run."""
        self._node_start_time = self.property_set["node_start_time"].copy()
        self._idle_after = {bit: 0 for bit in dag.qubits}
        self._current_block_idx = 0
        self._conditional_block = False
        self._block_duration = 0

        # Prepare DAG to pad
        self._dag = DAGCircuit()
        for qreg in dag.qregs.values():
            self._dag.add_qreg(qreg)
        for creg in dag.cregs.values():
            self._dag.add_creg(creg)

        # Update start time dictionary for the new_dag.
        # This information may be used for further scheduling tasks,
        # but this is immediately invalidated because most node ids are updated in the new_dag.
        self.property_set["node_start_time"].clear()

        self._dag.name = dag.name
        self._dag.metadata = dag.metadata
        self._dag.unit = self.property_set["time_unit"]
        self._dag.calibrations = dag.calibrations
        self._dag.global_phase = dag.global_phase

        self._prev_node = None

    def _pre_runhook(self, dag: DAGCircuit) -> None:
        """Extra routine inserted before running the padding pass.

        Args:
            dag: DAG circuit on which the sequence is applied.

        Raises:
            TranspilerError: If the whole circuit or instruction is not scheduled.
        """
        if "node_start_time" not in self.property_set:
            raise TranspilerError(
                f"The input circuit {dag.name} is not scheduled. Call one of scheduling passes "
                f"before running the {self.__class__.__name__} pass."
            )

    def _pad(
        self,
        block_idx: int,
        qubit: Qubit,
        t_start: int,
        t_end: int,
        next_node: DAGNode,
        prev_node: DAGNode,
    ) -> None:
        """Interleave instruction sequence in between two nodes.

        .. note::
            If a DAGOpNode is added here, it should update node_start_time property
            in the property set so that the added node is also scheduled.
            This is achieved by adding operation via :meth:`_apply_scheduled_op`.

        .. note::

            This method doesn't check if the total duration of new DAGOpNode added here
            is identical to the interval (``t_end - t_start``).
            A developer of the pass must guarantee this is satisfied.
            If the duration is greater than the interval, your circuit may be
            compiled down to the target code with extra duration on the backend compiler,
            which is then played normally without error. However, the outcome of your circuit
            might be unexpected due to erroneous scheduling.

        Args:
            block_idx: Execution block index for this node.
            qubit: The wire that the sequence is applied on.
            t_start: Absolute start time of this interval.
            t_end: Absolute end time of this interval.
            next_node: Node that follows the sequence.
            prev_node: Node ahead of the sequence.
        """
        raise NotImplementedError

    def _get_node_duration(self, node: DAGNode) -> int:
        """Get the duration of a node."""
        if node.op.condition_bits:
            # As we cannot currently schedule through conditionals model
            # as zero duration to avoid padding.
            return 0
        return node.op.duration

    def _visit_delay(self, node: DAGNode) -> None:
        """The padding class considers a delay instruction as idle time
        rather than instruction. Delay node is not added so that
        we can extract non-delay predecessors.
        """
        block_idx, t0 = self._node_start_time[node]  # pylint: disable=invalid-name
        # Trigger the end of a block
        if block_idx > self._current_block_idx:
            self._terminate_block(self._block_duration, self._current_block_idx, node)

        self._conditional_block = bool(node.op.condition_bits)

        self._current_block_idx = block_idx

        t1 = t0 + self._get_node_duration(node)  # pylint: disable=invalid-name
        self._block_duration = max(self._block_duration, t1)

    def _visit_generic(self, node: DAGNode) -> None:
        """Visit a generic node to pad."""
        # Note: t0 is the relative time with respect to the current block specified
        # by block_idx.
        block_idx, t0 = self._node_start_time[node]  # pylint: disable=invalid-name

        # Trigger the end of a block
        if block_idx > self._current_block_idx:
            self._terminate_block(self._block_duration, self._current_block_idx, node)

        # This block will not be padded as it is conditional.
        # See TODO below.
        self._conditional_block = bool(node.op.condition_bits)

        # Now set the current block index.
        self._current_block_idx = block_idx

        t1 = t0 + self._get_node_duration(node)  # pylint: disable=invalid-name
        self._block_duration = max(self._block_duration, t1)

        for bit in node.qargs:
            # Fill idle time with some sequence
            if t0 - self._idle_after[bit] > 0:
                # Find previous node on the wire, i.e. always the latest node on the wire
                prev_node = next(self._dag.predecessors(self._dag.output_map[bit]))
                self._pad(
                    block_idx=block_idx,
                    qubit=bit,
                    t_start=self._idle_after[bit],
                    t_end=t0,
                    next_node=node,
                    prev_node=prev_node,
                )

            self._idle_after[bit] = t1

        self._apply_scheduled_op(block_idx, t0, node.op, node.qargs, node.cargs)

    def _terminate_block(
        self, block_duration: int, block_idx: int, node: Optional[DAGNode]
    ) -> None:
        """Terminate the end of a block scheduling region."""
        # Update all other qubits as not idle so that delays are *not*
        # inserted. This is because we need the delays to be inserted in
        # the conditional circuit block. However, c_if currently only
        # allows writing a single conditional gate.
        # TODO: This should be reworked to instead apply a transformation
        # pass to rewrite all ``c_if`` operations as ``if_else``
        # blocks that are in turn scheduled.
        self._pad_until_block_end(block_duration, block_idx)

        def _is_terminating_barrier(node: Optional[DAGNode]) -> bool:
            return (
                node
                and isinstance(node.op, Barrier)
                and len(node.qargs) == self._dag.num_qubits()
            )

        # Only add a barrier to the end if a viable barrier is not already present on all qubits
        is_terminating_barrier = _is_terminating_barrier(
            self._prev_node
        ) or _is_terminating_barrier(node)
        if not is_terminating_barrier:
            # Terminate with a barrier to be clear timing is non-deterministic
            # across the barrier.
            barrier_node = self._apply_scheduled_op(
                block_idx,
                block_duration,
                Barrier(self._dag.num_qubits()),
                self._dag.qubits,
                [],
            )
            barrier_node.op.duration = 0

        # Reset idles for the new block.
        self._idle_after = {bit: 0 for bit in self._dag.qubits}
        self._block_duration = 0
        self._conditional_block = False

    def _pad_until_block_end(self, block_duration: int, block_idx: int) -> None:
        # Add delays until the end of circuit.
        for bit in self._dag.qubits:
            if block_duration - self._idle_after[bit] > 0:
                node = self._dag.output_map[bit]
                prev_node = next(self._dag.predecessors(node))
                self._pad(
                    block_idx=block_idx,
                    qubit=bit,
                    t_start=self._idle_after[bit],
                    t_end=block_duration,
                    next_node=node,
                    prev_node=prev_node,
                )

    def _apply_scheduled_op(
        self,
        block_idx: int,
        t_start: int,
        oper: Instruction,
        qubits: Union[Qubit, List[Qubit]],
        clbits: Optional[Union[Clbit, List[Clbit]]] = None,
    ) -> DAGNode:
        """Add new operation to DAG with scheduled information.

        This is identical to apply_operation_back + updating the node_start_time propety.

        Args:
            block_idx: Execution block index for this node.
            t_start: Start time of new node.
            oper: New operation that is added to the DAG circuit.
            qubits: The list of qubits that the operation acts on.
            clbits: The list of clbits that the operation acts on.

        Returns:
            The DAGNode applied to.
        """
        if isinstance(qubits, Qubit):
            qubits = [qubits]
        if isinstance(clbits, Clbit):
            clbits = [clbits]

        new_node = self._dag.apply_operation_back(oper, qargs=qubits, cargs=clbits)
        self.property_set["node_start_time"][new_node] = (block_idx, t_start)
        return new_node
