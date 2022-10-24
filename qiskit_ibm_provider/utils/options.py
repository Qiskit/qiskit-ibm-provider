# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Backend run options."""

from dataclasses import asdict, dataclass
from typing import Dict, List, Union, Any, Optional
from qiskit.circuit import QuantumCircuit, Parameter
from qiskit.pulse import Schedule, LoConfig
from qiskit.pulse.channels import PulseChannel
from qiskit.qobj.utils import MeasLevel, MeasReturnType


@dataclass
class QASM3Options:
    """Options for the QASM3 path."""

    circuits: Union[QuantumCircuit, List[QuantumCircuit]] = None
    merge_circuits: Optional[bool] = None
    shots: Optional[int] = None
    meas_level: Optional[Union[int, MeasLevel]] = None
    init_circuit: Optional[QuantumCircuit] = None
    init_delay: Optional[int] = None
    init_num_resets: Optional[int] = None
    run_config: Optional[Dict] = None
    exporter_config: Optional[Dict] = None
    skip_transpilation: Optional[bool] = None
    transpiler_config: Optional[Dict] = None
    use_measurement_mitigation: Optional[bool] = None
    qasm3_args: Optional[Union[Dict, List]] = None  # Deprecated

    def to_transport_dict(self) -> Dict[str, Any]:
        """Return None values so runtime defaults are used."""
        dict_ = asdict(self)
        for key in list(dict_.keys()):
            if dict_[key] is None:
                del dict_[key]
        return dict_


@dataclass
class QASM2Options:
    """Options for the QASM2 path."""

    circuits: Union[
        str, QuantumCircuit, Schedule, List[Union[QuantumCircuit, Schedule]]
    ] = None
    job_tags: str = None
    header: Dict = None
    shots: int = None
    memory: bool = None
    qubit_lo_freq: List[int] = None
    meas_lo_freq: List[int] = None
    schedule_los: Union[
        List[Union[Dict[PulseChannel, float], LoConfig]],
        Union[Dict[PulseChannel, float], LoConfig],
    ] = None
    meas_level: Union[int, MeasLevel] = None
    meas_return: Union[str, MeasReturnType] = None
    memory_slots: int = None
    memory_slot_size: int = None
    rep_time: int = None
    rep_delay: float = None
    init_qubits: bool = None
    parameter_binds: List[Dict[Parameter, float]] = None
    use_measure_esp: bool = None
    noise_model: Any = None
    seed_simulator: Any = None
