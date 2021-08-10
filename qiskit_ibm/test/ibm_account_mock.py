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

"""Mock for qiskit_ibm.IBMAccount."""

from unittest.mock import MagicMock
from qiskit.test import mock as backend_mocks


def get_mock_ibm_account(backend):
    """Replace qiskit_ibm.IBMAccount with a mock that returns a single backend.
    Note this will set the value of qiskit_ibm.IBMAccount to a MagicMock object. It is
    intended to be run as part of docstrings with jupyter-example in a hidden
    cell so that later examples which rely on ibm quantum devices so that the docs can
    be built without requiring configured credentials. If used outside of this
    context be aware that you will have to manually restore qiskit_ibm.IBMAccount the
    value to qiskit_ibm.IBMAccount after you finish using your mock.
    Args:
        backend (str): The class name as a string for the fake device to
            return. For example, FakeVigo.
    Raises:
        NameError: If the specified value of backend
    """
    mock_ibm_account = MagicMock()
    mock_provider = MagicMock()
    if not hasattr(backend_mocks, backend):
        raise NameError("The specified backend name is not a valid mock from " "qiskit.test.mock")
    fake_backend = getattr(backend_mocks, backend)()
    mock_provider.get_backend.return_value = fake_backend
    mock_ibm_account.get_provider.return_value = mock_provider
    return mock_ibm_account
