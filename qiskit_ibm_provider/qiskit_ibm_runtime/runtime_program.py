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

"""Qiskit runtime program."""

import logging
from typing import Dict
from types import SimpleNamespace
from qiskit_ibm_runtime.exceptions import IBMInputValueError

logger = logging.getLogger(__name__)


class ParameterNamespace(SimpleNamespace):
    """A namespace for program parameters with validation.

    This class provides a namespace for program parameters with auto-completion
    and validation support.
    """

    def __init__(self, parameters: Dict):
        """ParameterNamespace constructor.

        Args:
            parameters: The program's input parameters.
        """
        super().__init__()
        # Allow access to the raw program parameters dict
        self.__metadata = parameters
        # For localized logic, create store of parameters in dictionary
        self.__program_params: dict = {}

        for parameter_name, parameter_value in parameters.get("properties", {}).items():
            # (1) Add parameters to a dict by name
            setattr(self, parameter_name, None)
            # (2) Store the program params for validation
            self.__program_params[parameter_name] = parameter_value

    @property
    def metadata(self) -> Dict:
        """Returns the parameter metadata"""
        return self.__metadata

    def validate(self) -> None:
        """Validate program input values.

        Note:
            This method only verifies that required parameters have values. It
            does not fail the validation if the namespace has extraneous parameters.

        Raises:
            IBMInputValueError: if validation fails
        """

        # Iterate through the user's stored inputs
        for parameter_name, _ in self.__program_params.items():
            # Set invariants: User-specified parameter value (value) and if it's required (req)
            value = getattr(self, parameter_name, None)
            # Check there exists a program parameter of that name.
            if value is None and parameter_name in self.metadata.get("required", []):
                raise IBMInputValueError(
                    "Param (%s) missing required value!" % parameter_name
                )

    def __str__(self) -> str:
        """Creates string representation of object"""
        # Header
        header = "| {:10.10} | {:12.12} | {:12.12} " "| {:8.8} | {:>15} |".format(
            "Name", "Value", "Type", "Required", "Description"
        )
        params_str = "\n".join(
            [
                "| {:10.10} | {:12.12} | {:12.12}| {:8.8} | {:>15} |".format(
                    parameter_name,
                    str(getattr(self, parameter_name, "None")),
                    str(parameter_value.get("type", "None")),
                    str(parameter_name in self.metadata.get("required", [])),
                    str(parameter_value.get("description", "None")),
                )
                for parameter_name, parameter_value in self.__program_params.items()
            ]
        )

        return "ParameterNamespace (Values):\n%s\n%s\n%s" % (
            header,
            "-" * len(header),
            params_str,
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return self.__program_params
