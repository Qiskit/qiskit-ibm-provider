# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Client for accessing an individual IBM Quantum account."""

import logging

from .base import BaseClient
from ..client_parameters import ClientParameters
from ..session import RetrySession

logger = logging.getLogger(__name__)


class AccountClient(BaseClient):
    """Client for accessing an individual IBM Quantum account."""

    def __init__(self, params: ClientParameters) -> None:
        """AccountClient constructor.

        Args:
            params: Parameters used for server connection.
        """
        self._session = RetrySession(
            params.url, auth=params.get_auth_handler(), **params.connection_parameters()
        )
        self._params = params
