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
from typing import List, Dict, Any, Optional

from .base import BaseClient
from ..client_parameters import ClientParameters
from ..rest import Account
from ..session import RetrySession
from ...utils.hgp import from_instance_format

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
        hub, group, project = from_instance_format(params.instance)
        # base_api is used to handle endpoints that don't include h/g/p.
        # account_api is for h/g/p.
        self.account_api = Account(
            session=self._session,
            hub=hub,
            group=group,
            project=project,
        )

    # Backend-related public functions.

    def list_backends(self, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """Return backends available for this provider.

        Args:
            timeout: Number of seconds to wait for the request.

        Returns:
            Backends available for this provider.
        """
        return self.account_api.backends(timeout=timeout)
