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

from dataclasses import dataclass
from typing import Dict, List, Union

# TODO how do we want to separate the options between qasm2 and qasm3?
@dataclass
class QASM3Options:
    """Options for qasm3 jobs."""

    exporter_config: Dict = None
    init_circuit: List[Dict] = None
    init_delay: int = None
    init_num_resets: int = None
    merge_circuits: bool = True
    qasm3_args: Union[Dict, List] = None
    run_config: Dict = None
    skip_transpiliation: bool = False
    transpiler_config: Dict = None
    use_measurement_mitigation: bool = False
