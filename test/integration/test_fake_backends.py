# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019, 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests fake backends compatibility with a sample of unit tests
taken from Qiskit's preset pass manager API test suite."""

import itertools
from unittest.mock import patch
from ddt import ddt, data, idata, unpack

from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
from qiskit.circuit import Qubit
from qiskit.compiler import transpile, assemble
from qiskit.transpiler import PassManager
from qiskit.circuit.library import U2Gate, U3Gate, QuantumVolume

from qiskit.converters import circuit_to_dag
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit.transpiler.passes import Collect2qBlocks, GatesInBasis

from qiskit_ibm_provider.fake_provider import (
    FakeBelem,
    FakeTenerife,
    FakeMelbourne,
    FakeJohannesburg,
    FakeRueschlikon,
    FakeTokyo,
    FakePoughkeepsie,
    FakeLagosV2,
)
from ..ibm_test_case import IBMTestCase


def emptycircuit():
    """Empty circuit"""
    return QuantumCircuit()


def circuit_2532():
    """See https://github.com/Qiskit/qiskit-terra/issues/2532"""
    circuit = QuantumCircuit(5)
    circuit.cx(2, 4)
    return circuit


@ddt
class TestFakeBackendsWithPresetPassManager(IBMTestCase):
    """Test preset passmanagers work as expected."""

    def test_alignment_constraints_called_with_by_default(self):
        """Test that TimeUnitConversion is not called if there is no delay in the circuit."""
        level = 3
        q = QuantumRegister(2, name="q")
        circuit = QuantumCircuit(q)
        circuit.h(q[0])
        circuit.cz(q[0], q[1])
        with patch("qiskit.transpiler.passes.TimeUnitConversion.run") as mock:
            transpile(circuit, backend=FakeJohannesburg(), optimization_level=level)
        mock.assert_not_called()

    def test_alignment_constraints_called_with_delay_in_circuit(self):
        """Test that TimeUnitConversion is called if there is a delay in the circuit."""
        level = 3
        q = QuantumRegister(2, name="q")
        circuit = QuantumCircuit(q)
        circuit.h(q[0])
        circuit.cz(q[0], q[1])
        circuit.delay(9.5, unit="ns")
        with patch(
            "qiskit.transpiler.passes.TimeUnitConversion.run",
            return_value=circuit_to_dag(circuit),
        ) as mock:
            transpile(circuit, backend=FakeJohannesburg(), optimization_level=level)
        mock.assert_called_once()

    def test_unroll_only_if_not_gates_in_basis(self):
        """Test that the list of passes _unroll only runs if a gate is not in the basis."""
        qcomp = FakeBelem()
        qv_circuit = QuantumVolume(3)
        gates_in_basis_true_count = 0
        collect_2q_blocks_count = 0

        # pylint: disable=unused-argument
        def counting_callback_func(pass_, dag, time, property_set, count):
            nonlocal gates_in_basis_true_count
            nonlocal collect_2q_blocks_count
            if isinstance(pass_, GatesInBasis) and property_set["all_gates_in_basis"]:
                gates_in_basis_true_count += 1
            if isinstance(pass_, Collect2qBlocks):
                collect_2q_blocks_count += 1

        transpile(
            qv_circuit,
            backend=qcomp,
            optimization_level=3,
            callback=counting_callback_func,
            translation_method="synthesis",
        )
        self.assertEqual(gates_in_basis_true_count + 1, collect_2q_blocks_count)


@ddt
class TestTranspileLevels(IBMTestCase):
    """Test transpiler on fake backend"""

    @idata(
        itertools.product(
            [emptycircuit, circuit_2532],
            [0, 1, 2, 3],
            [
                FakeTenerife(),
                FakeMelbourne(),
                FakeRueschlikon(),
                FakeTokyo(),
                FakePoughkeepsie(),
                None,
            ],
        )
    )
    @unpack
    def test(self, circuit, level, backend):
        """All the levels with all the backends"""
        result = transpile(
            circuit(), backend=backend, optimization_level=level, seed_transpiler=42
        )
        self.assertIsInstance(result, QuantumCircuit)


@ddt
class TestPassesInspection(IBMTestCase):
    """Test run passes under different conditions"""

    def setUp(self):
        """Sets self.callback to set self.passes with the passes that have been executed"""
        super().setUp()
        self.passes = []

        def callback(**kwargs):
            self.passes.append(kwargs["pass_"].__class__.__name__)

        self.callback = callback

    @data(0, 1, 2, 3)
    def test_backend(self, level):
        """With backend a layout and a swapper is run"""
        qr = QuantumRegister(5, "q")
        qc = QuantumCircuit(qr)
        qc.cx(qr[2], qr[4])
        backend = FakeMelbourne()

        _ = transpile(qc, backend, optimization_level=level, callback=self.callback)

        self.assertIn("SetLayout", self.passes)
        self.assertIn("ApplyLayout", self.passes)
        self.assertIn("CheckGateDirection", self.passes)

    @data(0, 1, 2, 3)
    def test_5409(self, level):
        """The parameter layout_method='noise_adaptive' should be honored
        See: https://github.com/Qiskit/qiskit-terra/issues/5409
        """
        qr = QuantumRegister(5, "q")
        qc = QuantumCircuit(qr)
        qc.cx(qr[2], qr[4])
        backend = FakeMelbourne()

        _ = transpile(
            qc,
            backend,
            layout_method="noise_adaptive",
            optimization_level=level,
            callback=self.callback,
        )

        self.assertIn("SetLayout", self.passes)
        self.assertIn("ApplyLayout", self.passes)
        self.assertIn("NoiseAdaptiveLayout", self.passes)

    def test_level1_runs_vf2post_layout_when_routing_required(self):
        """Test that if we run routing as part of sabre layout VF2PostLayout runs."""
        target = FakeLagosV2()
        qc = QuantumCircuit(5)
        qc.h(0)
        qc.cy(0, 1)
        qc.cy(0, 2)
        qc.cy(0, 3)
        qc.cy(0, 4)
        qc.measure_all()
        _ = transpile(qc, target, optimization_level=1, callback=self.callback)
        # Expected call path for layout and routing is:
        # 1. TrivialLayout (no perfect match)
        # 2. VF2Layout (no perfect match)
        # 3. SabreLayout (heuristic layout and also runs routing)
        # 4. VF2PostLayout (applies a better layout)
        self.assertIn("TrivialLayout", self.passes)
        self.assertIn("VF2Layout", self.passes)
        self.assertIn("SabreLayout", self.passes)
        self.assertIn("VF2PostLayout", self.passes)
        #  Assert we don't run standalone sabre swap
        self.assertNotIn("SabreSwap", self.passes)


@ddt
class TestInitialLayouts(IBMTestCase):
    """Test transpiling with different layouts"""

    @data(0, 1, 2, 3)
    def test_layout_1711(self, level):
        """Test that a user-given initial layout is respected,
        in the qobj.

        See: https://github.com/Qiskit/qiskit-terra/issues/1711
        """
        # build a circuit which works as-is on the coupling map, using the initial layout
        qr = QuantumRegister(3, "q")
        cr = ClassicalRegister(3)
        ancilla = QuantumRegister(13, "ancilla")
        qc = QuantumCircuit(qr, cr)
        qc.cx(qr[2], qr[1])
        qc.cx(qr[2], qr[0])
        initial_layout = {0: qr[1], 2: qr[0], 15: qr[2]}
        final_layout = {
            0: qr[1],
            1: ancilla[0],
            2: qr[0],
            3: ancilla[1],
            4: ancilla[2],
            5: ancilla[3],
            6: ancilla[4],
            7: ancilla[5],
            8: ancilla[6],
            9: ancilla[7],
            10: ancilla[8],
            11: ancilla[9],
            12: ancilla[10],
            13: ancilla[11],
            14: ancilla[12],
            15: qr[2],
        }

        backend = FakeRueschlikon()

        qc_b = transpile(
            qc, backend, initial_layout=initial_layout, optimization_level=level
        )
        qobj = assemble(qc_b)

        self.assertEqual(qc_b._layout.initial_layout._p2v, final_layout)

        compiled_ops = qobj.experiments[0].instructions
        for operation in compiled_ops:
            if operation.name == "cx":
                self.assertIn(operation.qubits, backend.configuration().coupling_map)
                self.assertIn(operation.qubits, [[15, 0], [15, 2]])

    @data(0, 1, 2, 3)
    def test_layout_2532(self, level):
        """Test that a user-given initial layout is respected,
        in the transpiled circuit.

        See: https://github.com/Qiskit/qiskit-terra/issues/2532
        """
        # build a circuit which works as-is on the coupling map, using the initial layout
        qr = QuantumRegister(5, "q")
        cr = ClassicalRegister(2)
        ancilla = QuantumRegister(9, "ancilla")
        qc = QuantumCircuit(qr, cr)
        qc.cx(qr[2], qr[4])
        initial_layout = {
            qr[2]: 11,
            qr[4]: 3,  # map to [11, 3] connection
            qr[0]: 1,
            qr[1]: 5,
            qr[3]: 9,
        }
        final_layout = {
            0: ancilla[0],
            1: qr[0],
            2: ancilla[1],
            3: qr[4],
            4: ancilla[2],
            5: qr[1],
            6: ancilla[3],
            7: ancilla[4],
            8: ancilla[5],
            9: qr[3],
            10: ancilla[6],
            11: qr[2],
            12: ancilla[7],
            13: ancilla[8],
        }
        backend = FakeMelbourne()

        qc_b = transpile(
            qc, backend, initial_layout=initial_layout, optimization_level=level
        )

        self.assertEqual(qc_b._layout.initial_layout._p2v, final_layout)

        output_qr = qc_b.qregs[0]
        for instruction in qc_b:
            if instruction.operation.name == "cx":
                for qubit in instruction.qubits:
                    self.assertIn(qubit, [output_qr[11], output_qr[3]])

    @data(0, 1, 2, 3)
    def test_layout_2503(self, level):
        """Test that a user-given initial layout is respected,
        even if cnots are not in the coupling map.

        See: https://github.com/Qiskit/qiskit-terra/issues/2503
        """
        # build a circuit which works as-is on the coupling map, using the initial layout
        qr = QuantumRegister(3, "q")
        cr = ClassicalRegister(2)
        ancilla = QuantumRegister(17, "ancilla")

        qc = QuantumCircuit(qr, cr)
        qc.append(U3Gate(0.1, 0.2, 0.3), [qr[0]])
        qc.append(U2Gate(0.4, 0.5), [qr[2]])
        qc.barrier()
        qc.cx(qr[0], qr[2])
        initial_layout = [6, 7, 12]

        final_layout = {
            0: ancilla[0],
            1: ancilla[1],
            2: ancilla[2],
            3: ancilla[3],
            4: ancilla[4],
            5: ancilla[5],
            6: qr[0],
            7: qr[1],
            8: ancilla[6],
            9: ancilla[7],
            10: ancilla[8],
            11: ancilla[9],
            12: qr[2],
            13: ancilla[10],
            14: ancilla[11],
            15: ancilla[12],
            16: ancilla[13],
            17: ancilla[14],
            18: ancilla[15],
            19: ancilla[16],
        }

        backend = FakePoughkeepsie()

        qc_b = transpile(
            qc, backend, initial_layout=initial_layout, optimization_level=level
        )

        self.assertEqual(qc_b._layout.initial_layout._p2v, final_layout)

        output_qr = qc_b.qregs[0]
        self.assertIsInstance(qc_b[0].operation, U3Gate)
        self.assertEqual(qc_b[0].qubits[0], output_qr[6])
        self.assertIsInstance(qc_b[1].operation, U2Gate)
        self.assertEqual(qc_b[1].qubits[0], output_qr[12])


@ddt
class TestFinalLayouts(IBMTestCase):
    """Test final layouts after preset transpilation"""

    @data(0, 1, 2, 3)
    def test_layout_tokyo_2845(self, level):
        """Test that final layout in tokyo #2845
        See: https://github.com/Qiskit/qiskit-terra/issues/2845
        """
        qr1 = QuantumRegister(3, "qr1")
        qr2 = QuantumRegister(2, "qr2")
        qc = QuantumCircuit(qr1, qr2)
        qc.cx(qr1[0], qr1[1])
        qc.cx(qr1[1], qr1[2])
        qc.cx(qr1[2], qr2[0])
        qc.cx(qr2[0], qr2[1])

        trivial_layout = {
            0: Qubit(QuantumRegister(3, "qr1"), 0),
            1: Qubit(QuantumRegister(3, "qr1"), 1),
            2: Qubit(QuantumRegister(3, "qr1"), 2),
            3: Qubit(QuantumRegister(2, "qr2"), 0),
            4: Qubit(QuantumRegister(2, "qr2"), 1),
            5: Qubit(QuantumRegister(15, "ancilla"), 0),
            6: Qubit(QuantumRegister(15, "ancilla"), 1),
            7: Qubit(QuantumRegister(15, "ancilla"), 2),
            8: Qubit(QuantumRegister(15, "ancilla"), 3),
            9: Qubit(QuantumRegister(15, "ancilla"), 4),
            10: Qubit(QuantumRegister(15, "ancilla"), 5),
            11: Qubit(QuantumRegister(15, "ancilla"), 6),
            12: Qubit(QuantumRegister(15, "ancilla"), 7),
            13: Qubit(QuantumRegister(15, "ancilla"), 8),
            14: Qubit(QuantumRegister(15, "ancilla"), 9),
            15: Qubit(QuantumRegister(15, "ancilla"), 10),
            16: Qubit(QuantumRegister(15, "ancilla"), 11),
            17: Qubit(QuantumRegister(15, "ancilla"), 12),
            18: Qubit(QuantumRegister(15, "ancilla"), 13),
            19: Qubit(QuantumRegister(15, "ancilla"), 14),
        }

        vf2_layout = {
            0: Qubit(QuantumRegister(15, "ancilla"), 0),
            1: Qubit(QuantumRegister(15, "ancilla"), 1),
            2: Qubit(QuantumRegister(15, "ancilla"), 2),
            3: Qubit(QuantumRegister(15, "ancilla"), 3),
            4: Qubit(QuantumRegister(15, "ancilla"), 4),
            5: Qubit(QuantumRegister(15, "ancilla"), 5),
            6: Qubit(QuantumRegister(3, "qr1"), 1),
            7: Qubit(QuantumRegister(15, "ancilla"), 6),
            8: Qubit(QuantumRegister(15, "ancilla"), 7),
            9: Qubit(QuantumRegister(15, "ancilla"), 8),
            10: Qubit(QuantumRegister(3, "qr1"), 0),
            11: Qubit(QuantumRegister(3, "qr1"), 2),
            12: Qubit(QuantumRegister(15, "ancilla"), 9),
            13: Qubit(QuantumRegister(15, "ancilla"), 10),
            14: Qubit(QuantumRegister(15, "ancilla"), 11),
            15: Qubit(QuantumRegister(15, "ancilla"), 12),
            16: Qubit(QuantumRegister(2, "qr2"), 0),
            17: Qubit(QuantumRegister(2, "qr2"), 1),
            18: Qubit(QuantumRegister(15, "ancilla"), 13),
            19: Qubit(QuantumRegister(15, "ancilla"), 14),
        }
        # Trivial layout
        expected_layout_level0 = trivial_layout
        # Dense layout
        expected_layout_level1 = vf2_layout
        # CSP layout
        expected_layout_level2 = vf2_layout
        expected_layout_level3 = vf2_layout

        expected_layouts = [
            expected_layout_level0,
            expected_layout_level1,
            expected_layout_level2,
            expected_layout_level3,
        ]
        backend = FakeTokyo()
        result = transpile(qc, backend, optimization_level=level, seed_transpiler=42)
        self.assertEqual(result._layout.initial_layout._p2v, expected_layouts[level])

    @data(0, 1, 2, 3)
    def test_layout_tokyo_fully_connected_cx(self, level):
        """Test that final layout in tokyo in a fully connected circuit"""
        qr = QuantumRegister(5, "qr")
        qc = QuantumCircuit(qr)
        for qubit_target in qr:
            for qubit_control in qr:
                if qubit_control != qubit_target:
                    qc.cx(qubit_control, qubit_target)

        ancilla = QuantumRegister(15, "ancilla")

        trivial_layout = {
            0: qr[0],
            1: qr[1],
            2: qr[2],
            3: qr[3],
            4: qr[4],
            5: ancilla[0],
            6: ancilla[1],
            7: ancilla[2],
            8: ancilla[3],
            9: ancilla[4],
            10: ancilla[5],
            11: ancilla[6],
            12: ancilla[7],
            13: ancilla[8],
            14: ancilla[9],
            15: ancilla[10],
            16: ancilla[11],
            17: ancilla[12],
            18: ancilla[13],
            19: ancilla[14],
        }

        sabre_layout = {
            0: ancilla[0],
            1: ancilla[1],
            2: ancilla[2],
            3: ancilla[3],
            4: ancilla[4],
            5: qr[2],
            6: qr[1],
            7: ancilla[6],
            8: ancilla[7],
            9: ancilla[8],
            10: qr[3],
            11: qr[0],
            12: ancilla[9],
            13: ancilla[10],
            14: ancilla[11],
            15: ancilla[5],
            16: qr[4],
            17: ancilla[12],
            18: ancilla[13],
            19: ancilla[14],
        }

        sabre_layout_lvl_2 = {
            0: ancilla[0],
            1: ancilla[1],
            2: ancilla[2],
            3: ancilla[3],
            4: ancilla[4],
            5: qr[2],
            6: qr[1],
            7: ancilla[6],
            8: ancilla[7],
            9: ancilla[8],
            10: qr[3],
            11: qr[0],
            12: ancilla[9],
            13: ancilla[10],
            14: ancilla[11],
            15: ancilla[5],
            16: qr[4],
            17: ancilla[12],
            18: ancilla[13],
            19: ancilla[14],
        }

        sabre_layout_lvl_3 = {
            0: ancilla[0],
            1: ancilla[1],
            2: ancilla[2],
            3: ancilla[3],
            4: ancilla[4],
            5: qr[2],
            6: qr[1],
            7: ancilla[6],
            8: ancilla[7],
            9: ancilla[8],
            10: qr[3],
            11: qr[0],
            12: ancilla[9],
            13: ancilla[10],
            14: ancilla[11],
            15: ancilla[5],
            16: qr[4],
            17: ancilla[12],
            18: ancilla[13],
            19: ancilla[14],
        }

        expected_layout_level0 = trivial_layout
        expected_layout_level1 = sabre_layout
        expected_layout_level2 = sabre_layout_lvl_2
        expected_layout_level3 = sabre_layout_lvl_3

        expected_layouts = [
            expected_layout_level0,
            expected_layout_level1,
            expected_layout_level2,
            expected_layout_level3,
        ]
        backend = FakeTokyo()
        result = transpile(qc, backend, optimization_level=level, seed_transpiler=42)
        self.assertEqual(result._layout.initial_layout._p2v, expected_layouts[level])

    @data(0)
    def test_trivial_layout(self, level):
        """Test that trivial layout is preferred in level 0
        See: https://github.com/Qiskit/qiskit-terra/pull/3657#pullrequestreview-342012465
        """
        qr = QuantumRegister(10, "qr")
        qc = QuantumCircuit(qr)
        qc.cx(qr[0], qr[1])
        qc.cx(qr[1], qr[2])
        qc.cx(qr[2], qr[6])
        qc.cx(qr[3], qr[8])
        qc.cx(qr[4], qr[9])
        qc.cx(qr[9], qr[8])
        qc.cx(qr[8], qr[7])
        qc.cx(qr[7], qr[6])
        qc.cx(qr[6], qr[5])
        qc.cx(qr[5], qr[0])

        ancilla = QuantumRegister(10, "ancilla")
        trivial_layout = {
            0: qr[0],
            1: qr[1],
            2: qr[2],
            3: qr[3],
            4: qr[4],
            5: qr[5],
            6: qr[6],
            7: qr[7],
            8: qr[8],
            9: qr[9],
            10: ancilla[0],
            11: ancilla[1],
            12: ancilla[2],
            13: ancilla[3],
            14: ancilla[4],
            15: ancilla[5],
            16: ancilla[6],
            17: ancilla[7],
            18: ancilla[8],
            19: ancilla[9],
        }

        expected_layouts = [trivial_layout, trivial_layout]

        backend = FakeTokyo()
        result = transpile(qc, backend, optimization_level=level, seed_transpiler=42)
        self.assertEqual(result._layout.initial_layout._p2v, expected_layouts[level])

    @data(0, 1, 2, 3)
    def test_initial_layout(self, level):
        """When a user provides a layout (initial_layout), it should be used."""
        qr = QuantumRegister(10, "qr")
        qc = QuantumCircuit(qr)
        qc.cx(qr[0], qr[1])
        qc.cx(qr[1], qr[2])
        qc.cx(qr[2], qr[3])
        qc.cx(qr[3], qr[9])
        qc.cx(qr[4], qr[9])
        qc.cx(qr[9], qr[8])
        qc.cx(qr[8], qr[7])
        qc.cx(qr[7], qr[6])
        qc.cx(qr[6], qr[5])
        qc.cx(qr[5], qr[0])

        initial_layout = {
            0: qr[0],
            2: qr[1],
            4: qr[2],
            6: qr[3],
            8: qr[4],
            10: qr[5],
            12: qr[6],
            14: qr[7],
            16: qr[8],
            18: qr[9],
        }

        backend = FakeTokyo()
        result = transpile(
            qc,
            backend,
            optimization_level=level,
            initial_layout=initial_layout,
            seed_transpiler=42,
        )

        for physical, virtual in initial_layout.items():
            self.assertEqual(result._layout.initial_layout._p2v[physical], virtual)


@ddt
class TestOptimizationWithCondition(IBMTestCase):
    """Test optimization levels with condition in the circuit"""

    @data(0, 1, 2, 3)
    def test_optimization_condition(self, level):
        """Test optimization levels with condition in the circuit"""
        qr = QuantumRegister(2)
        cr = ClassicalRegister(1)
        qc = QuantumCircuit(qr, cr)
        qc.cx(0, 1).c_if(cr, 1)
        backend = FakeJohannesburg()
        circ = transpile(qc, backend, optimization_level=level)
        self.assertIsInstance(circ, QuantumCircuit)


@ddt
class TestGeenratePresetPassManagers(IBMTestCase):
    """Test generate_preset_pass_manager function."""

    @data(0, 1, 2, 3)
    def test_with_backend(self, optimization_level):
        """Test a passmanager is constructed when only a backend and optimization level."""
        target = FakeTokyo()
        pm = generate_preset_pass_manager(optimization_level, target)
        self.assertIsInstance(pm, PassManager)

    @data(0, 1, 2, 3)
    def test_with_no_backend(self, optimization_level):
        """Test a passmanager is constructed with no backend and optimization level."""
        target = FakeLagosV2()
        pm = generate_preset_pass_manager(
            optimization_level,
            coupling_map=target.coupling_map,
            basis_gates=target.operation_names,
            inst_map=target.instruction_schedule_map,
            instruction_durations=target.instruction_durations,
            timing_constraints=target.target.timing_constraints(),
            target=target.target,
        )
        self.assertIsInstance(pm, PassManager)

    @data(0, 1, 2, 3)
    def test_with_no_backend_only_target(self, optimization_level):
        """Test a passmanager is constructed with a manual target and optimization level."""
        target = FakeLagosV2()
        pm = generate_preset_pass_manager(optimization_level, target=target.target)
        self.assertIsInstance(pm, PassManager)
