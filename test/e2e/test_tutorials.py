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

"""Tests for the tutorials, copied from ``qiskit-iqx-tutorials``."""

import glob
import os
import warnings

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

from qiskit_ibm_provider.utils import to_python_identifier

from ..ibm_test_case import IBMTestCase

TUTORIAL_PATH = "docs/tutorials/**/*.ipynb"

SUPPORTED_TUTORIALS = [
    "2_jupyter_tools.ipynb",
]

SUPPORTED_TUTORIALS_IBM_QUANTUM = [
    "1_the_ibm_quantum_account.ipynb",
    *SUPPORTED_TUTORIALS,
]


def _is_supported(tutorial_filename: str) -> bool:
    """Not all tutorials work for all channel types. Check if the given tutorial is supported by the
    targeted environment."""

    return any(
        tutorial_filename.endswith(filename)
        for filename in SUPPORTED_TUTORIALS_IBM_QUANTUM
    )


class TutorialsTestCaseMeta(type):
    """Metaclass that dynamically appends a "test_TUTORIAL_NAME" method to the class."""

    def __new__(cls, name, bases, dict_):
        def create_test(filename):
            """Return a new test function."""

            def test_function(self):
                self._run_notebook(filename)

            return test_function

        tutorials = sorted(glob.glob(TUTORIAL_PATH, recursive=True))

        for filename in tutorials:
            # Add a new "test_file_name_ipynb()" function to the test case.
            test_name = "test_%s" % to_python_identifier(filename)
            dict_[test_name] = create_test(filename)
            dict_[test_name].__doc__ = 'Test tutorial "%s"' % filename
        return type.__new__(cls, name, bases, dict_)


class TestTutorials(IBMTestCase, metaclass=TutorialsTestCaseMeta):
    """Tests for tutorials."""

    def _run_notebook(self, filename):
        if not _is_supported(filename):
            self.skipTest(f"Tutorial {filename} not supported")

        # Create the preprocessor.
        execute_preprocessor = ExecutePreprocessor(timeout=6000, kernel_name="python3")

        # Open the notebook.
        file_path = os.path.dirname(os.path.abspath(filename))
        with open(filename, encoding="utf-8") as file_:
            notebook = nbformat.read(file_, as_version=4)

        with warnings.catch_warnings():
            # Silence some spurious warnings.
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            # Finally, run the notebook.
            execute_preprocessor.preprocess(notebook, {"metadata": {"path": file_path}})
