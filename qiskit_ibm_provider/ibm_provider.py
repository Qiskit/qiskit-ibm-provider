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

"""Provider for a single IBM Quantum account."""

import logging
import os
import traceback
from collections import OrderedDict
from typing import Dict, List, Optional, Any, Callable, Tuple, Union

from qiskit.providers import ProviderV1 as Provider  # type: ignore[attr-defined]
from qiskit.providers.backend import BackendV1 as Backend
from qiskit.providers.exceptions import QiskitBackendNotFoundError

from .api.clients import AuthClient, VersionClient
from .apiconstants import QISKIT_IBM_API_URL
from .credentials import Credentials, HubGroupProjectID, discover_credentials
from .credentials.configrc import (
    remove_credentials,
    read_credentials_from_qiskitrc,
    store_credentials,
)
from .credentials.exceptions import HubGroupProjectIDInvalidStateError
from .exceptions import (
    IBMNotAuthorizedError,
    IBMInputValueError,
    IBMProviderCredentialsNotFound,
    IBMProviderCredentialsInvalidFormat,
    IBMProviderCredentialsInvalidToken,
    IBMProviderCredentialsInvalidUrl,
    IBMProviderError,
    IBMProviderValueError,
    IBMProviderMultipleCredentialsFound,
)
from .hub_group_project import HubGroupProject  # pylint: disable=cyclic-import
from .ibm_backend import IBMBackend  # pylint: disable=cyclic-import
from .ibm_backend_service import IBMBackendService  # pylint: disable=cyclic-import

logger = logging.getLogger(__name__)


class IBMProvider(Provider):
    """Provides access to the IBM Quantum services available to an account.

    Authenticate against IBM Quantum for use from saved credentials or during session.

    Credentials can be saved to disk by calling the `save_account()` method::

        from qiskit_ibm_provider import IBMProvider
        IBMProvider.save_account(token=<INSERT_IBM_QUANTUM_TOKEN>)

    You can set the default project using the `hub`, `group`, and `project` keywords
    in `save_account()`. Once credentials are saved you can simply instantiate the
    provider like below to load the saved account and default project::

        from qiskit_ibm_provider import IBMProvider
        provider = IBMProvider()

    Instead of saving credentials to disk, you can also set the environment
    variables QISKIT_IBM_API_TOKEN, QISKIT_IBM_API_URL, QISKIT_IBM_HUB, QISKIT_IBM_GROUP
    and QISKIT_IBM_PROJECT and then instantiate the provider like below::

        from qiskit_ibm_provider import IBMProvider
        provider = IBMProvider()

    You can also enable an account just for the current session by instantiating
    the provider with the API token::

        from qiskit_ibm_provider import IBMProvider
        provider = IBMProvider(token=<INSERT_IBM_QUANTUM_TOKEN>)

    `token` is the only required attribute that needs to be set using one of the above methods.
    If no `url` is set, it defaults to 'https://auth.quantum-computing.ibm.com/api'.

    Note:
        The hub/group/project is selected based on the below selection order,
        in decreasing order of priority.

        * The hub/group/project you explicity specify when calling a service.
          Ex: `provider.get_backend()`, etc.
        * The hub/group/project required for the service.
        * The default hub/group/project you set using `save_account()`.
        * A premium hub/group/project in your account.
        * An open access hub/group/project.

    The IBMProvider offers different services. The main service,
    :class:`~qiskit_ibm_provider.ibm_backend_service.IBMBackendService` gives access to IBM Quantum
    devices and simulators.

    You can obtain an instance of a service using the :meth:`service()` method
    or as an attribute of this ``IBMProvider`` instance. For example::

        backend_service = provider.service('backend')
        backend_service = provider.backend

    Since :class:`~qiskit_ibm_provider.ibm_backend_service.IBMBackendService`
    is the main service, some of the backend-related methods are available
    through this class for convenience.

    The :meth:`backends()` method returns all the backends available to this account::

        backends = provider.backends()

    The :meth:`get_backend()` method returns a backend that matches the filters
    passed as argument. An example of retrieving a backend that matches a
    specified name::

        simulator_backend = provider.get_backend('ibmq_qasm_simulator')

    It is also possible to use the ``backend`` attribute to reference a backend.
    As an example, to retrieve the same backend from the example above::

        simulator_backend = provider.backend.ibmq_qasm_simulator

    Note:
        The ``backend`` attribute can be used to autocomplete the names of
        backends available to this account. To autocomplete, press ``tab``
        after ``provider.backend.``. This feature may not be available
        if an error occurs during backend discovery. Also note that
        this feature is only available in interactive sessions, such as
        in Jupyter Notebook and the Python interpreter.
    """

    def __init__(
        self, token: Optional[str] = None, url: Optional[str] = None, **kwargs: Any
    ) -> None:
        """IBMProvider constructor

        Args:
            token: IBM Quantum token.
            url: URL for the IBM Quantum authentication server.
            **kwargs: Additional settings for the connection:

                * proxies (dict): proxy configuration.
                * verify (bool): verify the server's TLS certificate.

        Returns:
            An instance of IBMProvider

        Raises:
            IBMProviderCredentialsInvalidFormat: If the default hub/group/project saved on
                disk could not be parsed.
            IBMProviderCredentialsNotFound: If no IBM Quantum credentials can be found.
            IBMProviderCredentialsInvalidUrl: If the URL specified is not
                a valid IBM Quantum authentication URL.
            IBMProviderCredentialsInvalidToken: If the `token` is not a valid IBM Quantum token.
        """
        # pylint: disable=unused-argument,unsubscriptable-object
        super().__init__()
        account_credentials, account_preferences = self._resolve_credentials(
            token=token, url=url, **kwargs
        )
        self._initialize_hgps(
            credentials=account_credentials, preferences=account_preferences
        )
        self._initialize_services()

    def _resolve_credentials(
        self, token: Optional[str] = None, url: Optional[str] = None, **kwargs: Any
    ) -> Tuple[Credentials, Dict]:
        """Resolve credentials after looking up env variables and credentials saved on disk

        Args:
            token: IBM Quantum token.
            url: URL for the IBM Quantum authentication server.
            **kwargs: Additional settings for the connection:

                * proxies (dict): proxy configuration.
                * verify (bool): verify the server's TLS certificate.

        Returns:
            Tuple of account_credentials, preferences

        Raises:
            IBMProviderCredentialsInvalidFormat: If the default hub/group/project saved on
                disk could not be parsed.
            IBMProviderCredentialsNotFound: If no IBM Quantum credentials can be found.
            IBMProviderCredentialsInvalidToken: If the `token` is not a valid IBM Quantum token.
            IBMProviderMultipleCredentialsFound: If multiple IBM Quantum credentials are found.
        """
        if token:
            if not isinstance(token, str):
                raise IBMProviderCredentialsInvalidToken(
                    "Invalid IBM Quantum token "
                    'found: "{}" of type {}.'.format(token, type(token))
                )
            url = url or os.getenv("QISKIT_IBM_API_URL") or QISKIT_IBM_API_URL
            account_credentials = Credentials(
                token=token, url=url, auth_url=url, **kwargs
            )
            preferences: Optional[Dict] = {}
        else:
            # Check for valid credentials in env variables or qiskitrc file.
            try:
                saved_credentials, preferences = discover_credentials()
            except HubGroupProjectIDInvalidStateError as ex:
                raise IBMProviderCredentialsInvalidFormat(
                    "Invalid hub/group/project data found {}".format(str(ex))
                ) from ex
            credentials_list = list(saved_credentials.values())
            if not credentials_list:
                raise IBMProviderCredentialsNotFound(
                    "No IBM Quantum credentials found."
                )
            if len(credentials_list) > 1:
                raise IBMProviderMultipleCredentialsFound(
                    "Multiple IBM Quantum Experience credentials found."
                )
            account_credentials = credentials_list[0]
        return account_credentials, preferences

    def _initialize_hgps(
        self, credentials: Credentials, preferences: Optional[Dict] = None
    ) -> None:
        """Authenticate against IBM Quantum and populate the hub/group/projects.

        Args:
            credentials: Credentials for IBM Quantum.
            preferences: Account preferences.

        Raises:
            IBMProviderCredentialsInvalidUrl: If the URL specified is not
                a valid IBM Quantum authentication URL.
            IBMProviderError: If no hub/group/project could be found for this account.
        """
        self._hgps: Dict[HubGroupProjectID, HubGroupProject] = OrderedDict()
        version_info = self._check_api_version(credentials)
        # Check the URL is a valid authentication URL.
        if not version_info["new_api"] or "api-auth" not in version_info:
            raise IBMProviderCredentialsInvalidUrl(
                "The URL specified ({}) is not an IBM Quantum authentication URL. "
                "Valid authentication URL: {}.".format(
                    credentials.url, QISKIT_IBM_API_URL
                )
            )
        auth_client = AuthClient(
            credentials.token,
            credentials.base_url,
            **credentials.connection_parameters(),
        )
        service_urls = auth_client.current_service_urls()
        user_hubs = auth_client.user_hubs()
        preferences = preferences or {}
        is_open = True  # First hgp is open access
        for hub_info in user_hubs:
            # Build credentials.
            hgp_credentials = Credentials(
                credentials.token,
                access_token=auth_client.current_access_token(),
                url=service_urls["http"],
                auth_url=credentials.auth_url,
                websockets_url=service_urls["ws"],
                proxies=credentials.proxies,
                verify=credentials.verify,
                services=service_urls.get("services", {}),
                default_provider=credentials.default_provider,
                **hub_info,
            )
            hgp_credentials.preferences = preferences.get(
                hgp_credentials.unique_id(), {}
            )
            # Build the hgp.
            try:
                hgp = HubGroupProject(
                    credentials=hgp_credentials, provider=self, is_open=is_open
                )
                self._hgps[hgp.credentials.unique_id()] = hgp
                is_open = False  # hgps after first are premium and not open access
            except Exception:  # pylint: disable=broad-except
                # Catch-all for errors instantiating the hgp.
                logger.warning(
                    "Unable to instantiate hub/group/project for %s: %s",
                    hub_info,
                    traceback.format_exc(),
                )
        if not self._hgps:
            raise IBMProviderError(
                "No hub/group/project could be found for this account."
            )
        # Move open hgp to end of the list
        if len(self._hgps) > 1:
            open_hgp = self._get_hgp()
            self._hgps.move_to_end(open_hgp.credentials.unique_id())
        if credentials.default_provider:
            # Move user selected hgp to front of the list
            hub, group, project = credentials.default_provider.to_tuple()
            default_hgp = self._get_hgp(hub=hub, group=group, project=project)
            self._hgps.move_to_end(default_hgp.credentials.unique_id(), last=False)

    @staticmethod
    def _check_api_version(credentials: Credentials) -> Dict[str, Union[bool, str]]:
        """Check the version of the remote server in a set of credentials.

        Args:
            credentials: IBM Quantum Credentials

        Returns:
            A dictionary with version information.
        """
        version_finder = VersionClient(
            credentials.base_url, **credentials.connection_parameters()
        )
        return version_finder.version()

    def _get_hgp(
        self,
        hub: Optional[str] = None,
        group: Optional[str] = None,
        project: Optional[str] = None,
        backend_name: Optional[str] = None,
        service_name: Optional[str] = None,
    ) -> HubGroupProject:
        """Return an instance of `HubGroupProject` for a single hub/group/project combination.

        This function also allows to find the `HubGroupProject` that contains a backend
        `backend_name` providing service `service_name`.

        Args:
            hub: Name of the hub.
            group: Name of the group.
            project: Name of the project.
            backend_name: Name of the IBM Quantum backend.
            service_name: Name of the IBM Quantum service.

        Returns:
            An instance of `HubGroupProject` that matches the specified criteria or the default.

        Raises:
            IBMProviderError: If no hub/group/project matches the specified criteria,
                if more than one hub/group/project matches the specified criteria, if
                no hub/group/project could be found for this account or if no backend matches the
                criteria.
        """
        # If any `hub`, `group`, or `project` is specified, make sure all parameters are set.
        if any([hub, group, project]) and not all([hub, group, project]):
            raise IBMProviderError(
                "The hub, group, and project parameters must all be "
                "specified. "
                'hub = "{}", group = "{}", project = "{}"'.format(hub, group, project)
            )
        hgps = self._get_hgps(hub=hub, group=group, project=project)
        if any([hub, group, project]):
            if not hgps:
                raise IBMProviderError(
                    "No hub/group/project matches the specified criteria: "
                    "hub = {}, group = {}, project = {}".format(hub, group, project)
                )
            if len(hgps) > 1:
                raise IBMProviderError(
                    "More than one hub/group/project matches the "
                    "specified criteria. hub = {}, group = {}, project = {}".format(
                        hub, group, project
                    )
                )
        elif not hgps:
            # Prevent edge case where no hub/group/project is available.
            raise IBMProviderError(
                "No hub/group/project could be found for this account."
            )
        elif backend_name and service_name:
            for hgp in hgps:
                if hgp.has_service(service_name) and hgp.get_backend(backend_name):
                    return hgp
            raise IBMProviderError("No backend matches the criteria.")
        return hgps[0]

    def _get_hgps(
        self,
        hub: Optional[str] = None,
        group: Optional[str] = None,
        project: Optional[str] = None,
    ) -> List[HubGroupProject]:
        """Return a list of `HubGroupProject` instances, subject to optional filtering.

        Args:
            hub: Name of the hub.
            group: Name of the group.
            project: Name of the project.

        Returns:
            A list of `HubGroupProject` instances that match the specified criteria.
        """
        filters: List[Callable[[HubGroupProjectID], bool]] = []
        if hub:
            filters.append(lambda hgp: hgp.hub == hub)
        if group:
            filters.append(lambda hgp: hgp.group == group)
        if project:
            filters.append(lambda hgp: hgp.project == project)
        hgps = [hgp for key, hgp in self._hgps.items() if all(f(key) for f in filters)]
        return hgps

    def _initialize_services(self) -> None:
        """Initialize all services."""
        self._backend = None
        hgps = self._get_hgps()
        for hgp in hgps:
            # Initialize backend service
            if not self._backend:
                self._backend = IBMBackendService(self, hgp)
            if self._backend:
                break
        self._services = {"backend": self._backend}

    @property
    def backend(self) -> IBMBackendService:
        """Return the backend service.

        Returns:
            The backend service instance.
        """
        return self._backend

    def active_account(self) -> Optional[Dict[str, str]]:
        """Return the IBM Quantum account currently in use for the session.

        Returns:
            A dictionary with information about the account currently in the session,
                None if there is no active account in session
        """
        if not self._hgps:
            return None
        first_hgp = self._get_hgp()
        return {
            "token": first_hgp.credentials.token,
            "url": first_hgp.credentials.auth_url,
        }

    @staticmethod
    def delete_account() -> None:
        """Delete the saved account from disk.

        Raises:
            IBMProviderCredentialsNotFound: If no valid IBM Quantum
                credentials can be found on disk.
            IBMProviderCredentialsInvalidUrl: If invalid IBM Quantum
                credentials are found on disk.
        """
        stored_credentials, _ = read_credentials_from_qiskitrc()
        if not stored_credentials:
            raise IBMProviderCredentialsNotFound(
                "No IBM Quantum credentials found on disk."
            )
        credentials = list(stored_credentials.values())[0]
        if credentials.url != QISKIT_IBM_API_URL:
            raise IBMProviderCredentialsInvalidUrl(
                "Invalid IBM Quantum credentials found on disk. "
            )
        remove_credentials(credentials)

    @staticmethod
    def save_account(
        token: str,
        url: str = QISKIT_IBM_API_URL,
        hub: Optional[str] = None,
        group: Optional[str] = None,
        project: Optional[str] = None,
        overwrite: bool = False,
        **kwargs: Any,
    ) -> None:
        """Save the account to disk for future use.

        Note:
            If storing a default hub/group/project to disk, all three parameters
            `hub`, `group`, `project` must be specified.

        Args:
            token: IBM Quantum token.
            url: URL for the IBM Quantum authentication server.
            hub: Name of the hub.
            group: Name of the group.
            project: Name of the project.
            overwrite: Overwrite existing credentials.
            **kwargs:
                * proxies (dict): Proxy configuration for the server.
                * verify (bool): If False, ignores SSL certificates errors

        Raises:
            IBMProviderCredentialsInvalidUrl: If the `url` is not a valid
                IBM Quantum authentication URL.
            IBMProviderCredentialsInvalidToken: If the `token` is not a valid
                IBM Quantum token.
            IBMProviderValueError: If only one or two parameters from `hub`, `group`,
                `project` are specified.
        """
        if url != QISKIT_IBM_API_URL:
            raise IBMProviderCredentialsInvalidUrl(
                "Invalid IBM Quantum credentials found."
            )
        if not token or not isinstance(token, str):
            raise IBMProviderCredentialsInvalidToken(
                "Invalid IBM Quantum token "
                'found: "{}" of type {}.'.format(token, type(token))
            )
        # If any `hub`, `group`, or `project` is specified, make sure all parameters are set.
        if any([hub, group, project]) and not all([hub, group, project]):
            raise IBMProviderValueError(
                "The hub, group, and project parameters must all be "
                "specified when storing a default hub/group/project to "
                'disk: hub = "{}", group = "{}", project = "{}"'.format(
                    hub, group, project
                )
            )
        # If specified, get the hub/group/project to store.
        default_hgp_id = (
            HubGroupProjectID(hub, group, project)
            if all([hub, group, project])
            else None
        )
        credentials = Credentials(
            token=token, url=url, default_provider=default_hgp_id, **kwargs
        )
        store_credentials(credentials, overwrite=overwrite)

    @staticmethod
    def saved_account() -> Dict[str, str]:
        """List the account saved on disk.

        Returns:
            A dictionary with information about the account saved on disk.

        Raises:
            IBMProviderCredentialsInvalidUrl: If invalid IBM Quantum
                credentials are found on disk.
        """
        stored_credentials, _ = read_credentials_from_qiskitrc()
        if not stored_credentials:
            return {}
        credentials = list(stored_credentials.values())[0]
        if credentials.url != QISKIT_IBM_API_URL:
            raise IBMProviderCredentialsInvalidUrl(
                "Invalid IBM Quantum credentials found on disk."
            )
        return {"token": credentials.token, "url": credentials.url}

    def backends(
        self,
        name: Optional[str] = None,
        filters: Optional[Callable[[List[IBMBackend]], bool]] = None,
        min_num_qubits: Optional[int] = None,
        input_allowed: Optional[Union[str, List[str]]] = None,
        hub: Optional[str] = None,
        group: Optional[str] = None,
        project: Optional[str] = None,
        **kwargs: Any,
    ) -> List[IBMBackend]:
        """Return all backends accessible via this account, subject to optional filtering.

        Args:
            name: Backend name to filter by.
            filters: More complex filters, such as lambda functions.
                For example::

                    IBMProvider.backends(filters=lambda b: b.configuration().quantum_volume > 16)
            min_num_qubits: Minimum number of qubits the backend has to have.
            input_allowed: Filter by the types of input the backend supports.
                Valid input types are ``job`` (circuit job) and ``runtime`` (Qiskit Runtime).
                For example, ``inputs_allowed='runtime'`` will return all backends
                that support Qiskit Runtime. If a list is given, the backend must
                support all types specified in the list.
            hub: Name of the hub.
            group: Name of the group.
            project: Name of the project.
            **kwargs: Simple filters that specify a ``True``/``False`` criteria in the
                backend configuration, backends status, or provider credentials.
                An example to get the operational backends with 5 qubits::

                    IBMProvider.backends(n_qubits=5, operational=True)

        Returns:
            The list of available backends that match the filter.
        """
        # pylint: disable=arguments-differ
        return self._backend.backends(
            name=name,
            filters=filters,
            min_num_qubits=min_num_qubits,
            input_allowed=input_allowed,
            hub=hub,
            group=group,
            project=project,
            **kwargs,
        )

    def get_backend(
        self,
        name: str = None,
        hub: Optional[str] = None,
        group: Optional[str] = None,
        project: Optional[str] = None,
        **kwargs: Any,
    ) -> Backend:
        """Return a single backend matching the specified filtering.

        Args:
            name (str): name of the backend.
            hub: Name of the hub.
            group: Name of the group.
            project: Name of the project.
            **kwargs: dict used for filtering.

        Returns:
            Backend: a backend matching the filtering.

        Raises:
            QiskitBackendNotFoundError: if no backend could be found or
                more than one backend matches the filtering criteria.
            IBMProviderValueError: If only one or two parameters from `hub`, `group`,
                `project` are specified.
        """
        # pylint: disable=arguments-differ
        backends = self.backends(name, hub=hub, group=group, project=project, **kwargs)
        if len(backends) > 1:
            raise QiskitBackendNotFoundError(
                "More than one backend matches the criteria"
            )
        if not backends:
            raise QiskitBackendNotFoundError("No backend matches the criteria")
        return backends[0]

    def has_service(self, name: str) -> bool:
        """Check if this account has access to the service.

        Args:
            name: Name of the service.

        Returns:
            Whether the account has access to the service.

        Raises:
            IBMInputValueError: If an unknown service name is specified.
        """
        if name not in self._services:
            raise IBMInputValueError(f"Unknown service {name} specified.")
        if self._services[name] is None:
            return False
        return True

    def service(self, name: str) -> Any:
        """Return the specified service.

        Args:
            name: Name of the service.

        Returns:
            The specified service.

        Raises:
            IBMInputValueError: If an unknown service name is specified.
            IBMNotAuthorizedError: If the account is not authorized to use
                the service.
        """
        if name not in self._services:
            raise IBMInputValueError(f"Unknown service {name} specified.")
        if self._services[name] is None:
            raise IBMNotAuthorizedError("You are not authorized to use this service.")
        return self._services[name]

    def services(self) -> Dict:
        """Return all available services.

        Returns:
            All services available to this account.
        """
        return {key: val for key, val in self._services.items() if val is not None}

    def __repr__(self) -> str:
        return "<{}>".format(self.__class__.__name__)
