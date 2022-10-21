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

"""Utility functions for scheduling passes."""

from typing import Generator

from qiskit.circuit import Measure, Reset
from qiskit.dagcircuit import DAGCircuit, DAGOpNode


def block_order_op_nodes(dag: DAGCircuit) -> Generator[DAGOpNode, None, None]:
    """Yield nodes such that they are sorted into blocks that they minimize synchronization.

    This should be used when iterating nodes in order to find blocks within the circuit
    for IBM dynamic circuit hardware

    TODO: The need for this should be mitigated when Qiskit adds better support for
    blocks and walking them in its program representation.
    """
    # Dictionary is used as an ordered set of nodes to process
    next_nodes = dag.topological_op_nodes()
    while next_nodes:
        curr_nodes = next_nodes
        next_nodes_set = set()
        next_nodes = []
        for node in curr_nodes:
            # If we have added this node to the next set of nodes
            # skip for now.
            if node in next_nodes_set:
                next_nodes.append(node)
                continue
            # If we encounter one of these nodes we wish
            # to only process descendants after processing
            # all non-descendants first. This ensures
            # maximize the size of our "basic blocks"
            # and correspondingly minimize the total
            # number of blocks
            if isinstance(node.op, (Reset, Measure)):
                next_nodes_set |= set(
                    node
                    for node in dag.descendants(node)
                    if isinstance(node, DAGOpNode)
                )

            yield node
