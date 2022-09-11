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

"""Qiskit runtime service."""

import logging
import traceback
import warnings
from collections import OrderedDict
from typing import Dict, Callable, Optional, Union, List, Any, Type
from dataclasses import asdict

from qiskit.providers.backend import BackendV1 as Backend
from qiskit.providers.provider import ProviderV1 as Provider
from qiskit.providers.exceptions import QiskitBackendNotFoundError
from qiskit.providers.providerutils import filter_backends

from qiskit_ibm_runtime import ibm_backend  # pylint: disable=unused-import
from ..api.clients import AuthClient, VersionClient
from ..api.clients.runtime import RuntimeClient
from .constants import QISKIT_IBM_RUNTIME_API_URL
from .exceptions import IBMNotAuthorizedError, IBMInputValueError, IBMAccountError
from ..api.exceptions import RequestsApiError

from .hub_group_project import HubGroupProject  # pylint: disable=cyclic-import

from ..utils import to_python_identifier
from ..utils.hgp import to_instance_format, from_instance_format
from ..utils.utils import validate_job_tags, validate_runtime_options
from .runtime_program import ParameterNamespace
from .program.result_decoder import ResultDecoder

from ..api.client_parameters import ClientParameters
from .runtime_job import RuntimeJob
from .runtime_options import RuntimeOptions

from .exceptions import (
    IBMRuntimeError,
    RuntimeProgramNotFound,
)

logger = logging.getLogger(__name__)

SERVICE_NAME = "runtime"

DEPRECATED_PROGRAMS = [
    "torch-train",
    "torch-infer",
    "sample-expval",
    "quantum_kernal_alignment",
]


class QiskitRuntimeService:
    """Class for interacting with the Qiskit Runtime service.

    Qiskit Runtime is a new architecture offered by IBM Quantum that
    streamlines computations requiring many iterations. These experiments will
    execute significantly faster within its improved hybrid quantum/classical
    process.

    A sample workflow of using the runtime service::

        from qiskit_ibm_runtime import QiskitRuntimeService, Session, Sampler, Estimator, Options
        from qiskit.test.reference_circuits import ReferenceCircuits
        from qiskit.circuit.library import RealAmplitudes
        from qiskit.quantum_info import SparsePauliOp

        # Initialize account.
        service = QiskitRuntimeService()

        # Set options, which can be overwritten at job level.
        options = Options(backend="ibmq_qasm_simulator")

        # Prepare inputs.
        bell = ReferenceCircuits.bell()
        psi = RealAmplitudes(num_qubits=2, reps=2)
        H1 = SparsePauliOp.from_list([("II", 1), ("IZ", 2), ("XI", 3)])
        theta = [0, 1, 1, 2, 3, 5]

        with Session(service) as session:
            # Submit a request to the Sampler primitive within the session.
            sampler = Sampler(session=session, options=options)
            job = sampler.run(circuits=bell)
            print(f"Sampler results: {job.result()}")

            # Submit a request to the Estimator primitive within the session.
            estimator = Estimator(session=session, options=options)
            job = estimator.run(
                circuits=[psi], observables=[H1], parameter_values=[theta]
            )
            print(f"Estimator results: {job.result()}")

    The example above uses the dedicated :class:`~qiskit_ibm_runtime.Sampler`
    and :class:`~qiskit_ibm_runtime.Estimator` classes. You can also
    use the :meth:`run` method directly to invoke a Qiskit Runtime program.

    If the program has any interim results, you can use the ``callback``
    parameter of the :meth:`run` method to stream the interim results.
    Alternatively, you can use the :meth:`RuntimeJob.stream_results` method to stream
    the results at a later time, but before the job finishes.

    The :meth:`run` method returns a
    :class:`RuntimeJob` object. You can use its
    methods to perform tasks like checking job status, getting job result, and
    canceling job.
    """

    def __init__(self, provider: Provider) -> None:
        """QiskitRuntimeService constructor

        An account is selected in the following order:

            - Account with the input `name`, if specified.
            - Default account for the `channel` type, if `channel` is specified but `token` is not.
            - Account defined by the input `channel` and `token`, if specified.
            - Account defined by the environment variables, if defined.
            - Default account for the ``ibm_cloud`` account, if one is available.
            - Default account for the ``ibm_quantum`` account, if one is available.

        `instance`, `proxies`, and `verify` can be used to overwrite corresponding
        values in the loaded account.

        Args:
            channel: Channel type. ``ibm_cloud`` or ``ibm_quantum``.
            auth: (DEPRECATED, use `channel` instead) Authentication type. ``cloud`` or ``legacy``.
            token: IBM Cloud API key or IBM Quantum API token.
            url: The API URL.
                Defaults to https://cloud.ibm.com (ibm_cloud) or
                https://auth.quantum-computing.ibm.com/api (ibm_quantum).
            name: Name of the account to load.
            instance: The service instance to use.
                For ``ibm_cloud`` runtime, this is the Cloud Resource Name (CRN) or the service name.
                For ``ibm_quantum`` runtime, this is the hub/group/project in that format.
            proxies: Proxy configuration. Supported optional keys are
                ``urls`` (a dictionary mapping protocol or protocol and host to the URL of the proxy,
                documented at https://docs.python-requests.org/en/latest/api/#requests.Session.proxies),
                ``username_ntlm``, ``password_ntlm`` (username and password to enable NTLM user
                authentication)
            verify: Whether to verify the server's TLS certificate.

        Returns:
            An instance of QiskitRuntimeService.

        Raises:
            IBMInputValueError: If an input is invalid.
        """
        self._provider = provider
        self._api_client = RuntimeClient(provider._client_params)
        self._client_params = provider._client_params
        self._account = provider._account

        self._channel = "ibm_quantum"
        self._backends: Dict[str, "ibm_backend.IBMBackend"] = {}

        auth_client = self._authenticate_ibm_quantum_account(self._client_params)
        # Update client parameters to use authenticated values.
        self._client_params.url = auth_client.current_service_urls()["services"][
            "runtime"
        ]
        self._client_params.token = auth_client.current_access_token()
        self._api_client = RuntimeClient(self._client_params)
        self._hgps = self._initialize_hgps(auth_client)
        for hgp in self._hgps.values():
            for backend_name, backend in hgp.backends.items():
                if backend_name not in self._backends:
                    self._backends[backend_name] = backend

    def _authenticate_ibm_quantum_account(
        self, client_params: ClientParameters
    ) -> AuthClient:
        """Authenticate against IBM Quantum and populate the hub/group/projects.

        Args:
            client_params: Parameters used for server connection.

        Raises:
            IBMInputValueError: If the URL specified is not a valid IBM Quantum authentication URL.
            IBMNotAuthorizedError: If the account is not authorized to use runtime.

        Returns:
            Authentication client.
        """
        version_info = self._check_api_version(client_params)
        # Check the URL is a valid authentication URL.
        if not version_info["new_api"] or "api-auth" not in version_info:
            raise IBMInputValueError(
                "The URL specified ({}) is not an IBM Quantum authentication URL. "
                "Valid authentication URL: {}.".format(
                    client_params.url, QISKIT_IBM_RUNTIME_API_URL
                )
            )
        auth_client = AuthClient(client_params)
        service_urls = auth_client.current_service_urls()
        if not service_urls.get("services", {}).get(SERVICE_NAME):
            raise IBMNotAuthorizedError(
                "This account is not authorized to use ``ibm_quantum`` runtime service."
            )
        return auth_client

    def _initialize_hgps(
        self,
        auth_client: AuthClient,
    ) -> Dict:
        """Authenticate against IBM Quantum and populate the hub/group/projects.

        Args:
            auth_client: Authentication data.

        Raises:
            IBMInputValueError: If the URL specified is not a valid IBM Quantum authentication URL.
            IBMAccountError: If no hub/group/project could be found for this account.

        Returns:
            The hub/group/projects for this account.
        """
        # pylint: disable=unsubscriptable-object
        hgps: OrderedDict[str, HubGroupProject] = OrderedDict()
        service_urls = auth_client.current_service_urls()
        user_hubs = auth_client.user_hubs()
        for hub_info in user_hubs:
            # Build credentials.
            hgp_params = ClientParameters(
                channel=self._account.channel,
                token=auth_client.current_access_token(),
                url=service_urls["http"],
                instance=to_instance_format(
                    hub_info["hub"], hub_info["group"], hub_info["project"]
                ),
                proxies=self._account.proxies,
                verify=self._account.verify,
            )

            # Build the hgp.
            try:
                hgp = HubGroupProject(
                    client_params=hgp_params, instance=hgp_params.instance, service=self
                )
                hgps[hgp.name] = hgp
            except Exception:  # pylint: disable=broad-except
                # Catch-all for errors instantiating the hgp.
                logger.warning(
                    "Unable to instantiate hub/group/project for %s: %s",
                    hub_info,
                    traceback.format_exc(),
                )
        if not hgps:
            raise IBMAccountError(
                "No hub/group/project that supports Qiskit Runtime could "
                "be found for this account."
            )
        # Move open hgp to end of the list
        if len(hgps) > 1:
            open_key, open_val = hgps.popitem(last=False)
            hgps[open_key] = open_val

        default_hgp = self._account.instance
        if default_hgp:
            if default_hgp in hgps:
                # Move user selected hgp to front of the list
                hgps.move_to_end(default_hgp, last=False)
            else:
                warnings.warn(
                    f"Default hub/group/project {default_hgp} not "
                    "found for the account and is ignored."
                )
        return hgps

    @staticmethod
    def _check_api_version(params: ClientParameters) -> Dict[str, Union[bool, str]]:
        """Check the version of the remote server in a set of client parameters.

        Args:
            params: Parameters used for server connection.

        Returns:
            A dictionary with version information.
        """
        version_finder = VersionClient(url=params.url, **params.connection_parameters())
        return version_finder.version()

    def _get_hgp(
        self,
        instance: Optional[str] = None,
        backend_name: Optional[str] = None,
    ) -> HubGroupProject:
        """Return an instance of `HubGroupProject`.

        This function also allows to find the `HubGroupProject` that contains a backend
        `backend_name`.

        Args:
            instance: The hub/group/project to use.
            backend_name: Name of the IBM Quantum backend.

        Returns:
            An instance of `HubGroupProject` that matches the specified criteria or the default.

        Raises:
            IBMInputValueError: If no hub/group/project matches the specified criteria,
                or if the input value is in an incorrect format.
            QiskitBackendNotFoundError: If backend cannot be found.
        """
        if instance:
            _ = from_instance_format(instance)  # Verify format
            if instance not in self._hgps:
                raise IBMInputValueError(
                    f"Hub/group/project {instance} "
                    "could not be found for this account."
                )
            if backend_name and not self._hgps[instance].backend(backend_name):
                raise QiskitBackendNotFoundError(
                    f"Backend {backend_name} cannot be found in "
                    f"hub/group/project {instance}"
                )
            return self._hgps[instance]

        if not backend_name:
            return list(self._hgps.values())[0]

        for hgp in self._hgps.values():
            if hgp.backend(backend_name):
                return hgp

        raise QiskitBackendNotFoundError(
            f"Backend {backend_name} cannot be found in any"
            f"hub/group/project for this account."
        )

    def _discover_backends(self) -> None:
        """Discovers the remote backends for this account, if not already known."""
        for backend in self._backends.values():
            backend_name = to_python_identifier(backend.name)
            # Append _ if duplicate
            while backend_name in self.__dict__:
                backend_name += "_"
            setattr(self, backend_name, backend)

    # pylint: disable=arguments-differ
    def backends(
        self,
        name: Optional[str] = None,
        min_num_qubits: Optional[int] = None,
        instance: Optional[str] = None,
        filters: Optional[Callable[[List["ibm_backend.IBMBackend"]], bool]] = None,
        **kwargs: Any,
    ) -> List["ibm_backend.IBMBackend"]:
        """Return all backends accessible via this account, subject to optional filtering.

        Args:
            name: Backend name to filter by.
            min_num_qubits: Minimum number of qubits the backend has to have.
            instance: This is only supported for ``ibm_quantum`` runtime and is in the
                hub/group/project format.
            filters: More complex filters, such as lambda functions.
                For example::

                    QiskitRuntimeService.backends(
                        filters=lambda b: b.configuration().quantum_volume > 16)
            **kwargs: Simple filters that specify a ``True``/``False`` criteria in the
                backend configuration or status.
                An example to get the operational real backends::

                    QiskitRuntimeService.backends(simulator=False, operational=True)

        Returns:
            The list of available backends that match the filter.

        Raises:
            IBMInputValueError: If an input is invalid.
        """
        # TODO filter out input_allowed not having runtime
        if self._channel == "ibm_quantum":
            if instance:
                backends = list(self._get_hgp(instance=instance).backends.values())
            else:
                backends = list(self._backends.values())
        else:
            if instance:
                raise IBMInputValueError(
                    "The 'instance' keyword is only supported for ``ibm_quantum`` runtime."
                )
            backends = list(self._backends.values())

        if name:
            kwargs["backend_name"] = name
        if min_num_qubits:
            backends = list(
                filter(lambda b: b.configuration().n_qubits >= min_num_qubits, backends)
            )
        return filter_backends(backends, filters=filters, **kwargs)

    def backend(
        self,
        name: str = None,
        instance: Optional[str] = None,
    ) -> Backend:
        """Return a single backend matching the specified filtering.

        Args:
            name: Name of the backend.
            instance: This is only supported for ``ibm_quantum`` runtime and is in the
                hub/group/project format.

        Returns:
            Backend: A backend matching the filtering.

        Raises:
            QiskitBackendNotFoundError: if no backend could be found.
        """
        # pylint: disable=arguments-differ
        backends = self.backends(name, instance=instance)
        if not backends:
            raise QiskitBackendNotFoundError("No backend matches the criteria")
        return backends[0]

    def run(
        self,
        program_id: str,
        inputs: Union[Dict, ParameterNamespace],
        options: Optional[Union[RuntimeOptions, Dict]] = None,
        callback: Optional[Callable] = None,
        result_decoder: Optional[Type[ResultDecoder]] = None,
        instance: Optional[str] = None,
        session_id: Optional[str] = None,
        job_tags: Optional[List[str]] = None,
        max_execution_time: Optional[int] = None,
        start_session: Optional[bool] = False,
    ) -> RuntimeJob:
        """Execute the runtime program.

        Args:
            program_id: Program ID.
            inputs: Program input parameters. These input values are passed
                to the runtime program.
            options: Runtime options that control the execution environment.
                The use of :class:`RuntimeOptions` has been deprecated.

                * backend: target backend to run on. This is required for ``ibm_quantum`` runtime.
                * image: the runtime image used to execute the program, specified in
                    the form of ``image_name:tag``. Not all accounts are
                    authorized to select a different image.
                * log_level: logging level to set in the execution environment. The valid
                    log levels are: ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, and ``CRITICAL``.
                    The default level is ``WARNING``.

            callback: Callback function to be invoked for any interim results and final result.
                The callback function will receive 2 positional parameters:

                    1. Job ID
                    2. Job result.

            result_decoder: A :class:`ResultDecoder` subclass used to decode job results.
                ``ResultDecoder`` is used if not specified.
            instance: This is only supported for ``ibm_quantum`` runtime and is in the
                hub/group/project format.
            session_id: Job ID of the first job in a runtime session.
            job_tags: Tags to be assigned to the job. The tags can subsequently be used
                as a filter in the :meth:`jobs()` function call.
            max_execution_time: Maximum execution time in seconds. This overrides
                the max_execution_time of the program and cannot exceed it.
            start_session: Set to True to explicitly start a runtime session. Defaults to False.

        Returns:
            A ``RuntimeJob`` instance representing the execution.

        Raises:
            IBMInputValueError: If input is invalid.
            RuntimeProgramNotFound: If the program cannot be found.
            IBMRuntimeError: An error occurred running the program.
        """
        if program_id in DEPRECATED_PROGRAMS:
            warnings.warn(
                f"The {program_id} program will be deprecated on August 29th.",
                DeprecationWarning,
                stacklevel=2,
            )
        validate_job_tags(job_tags, IBMInputValueError)

        if instance and self._channel != "ibm_quantum":
            raise IBMInputValueError(
                "The 'instance' keyword is only supported for ``ibm_quantum`` runtime. "
            )

        # If using params object, extract as dictionary
        if isinstance(inputs, ParameterNamespace):
            inputs.validate()
            inputs = vars(inputs)

        if options is None:
            options = {}
        elif isinstance(options, RuntimeOptions):
            options = asdict(options)
        options["backend"] = options.get("backend", options.get("backend_name", None))
        validate_runtime_options(options=options, channel=self.channel)

        backend = None
        hgp_name = None
        if self._channel == "ibm_quantum":
            # Find the right hgp
            hgp = self._get_hgp(instance=instance, backend_name=options["backend"])
            backend = hgp.backend(options["backend"])
            hgp_name = hgp.name

        result_decoder = result_decoder or ResultDecoder
        try:
            response = self._api_client.program_run(
                program_id=program_id,
                backend_name=options["backend"],
                params=inputs,
                image=options.get("image"),
                hgp=hgp_name,
                log_level=options.get("log_level"),
                session_id=session_id,
                job_tags=job_tags,
                max_execution_time=max_execution_time,
                start_session=start_session,
            )
        except RequestsApiError as ex:
            if ex.status_code == 404:
                raise RuntimeProgramNotFound(
                    f"Program not found: {ex.message}"
                ) from None
            raise IBMRuntimeError(f"Failed to run program: {ex}") from None

        if not backend:
            backend = self.backend(name=response["backend"])

        job = RuntimeJob(
            backend=backend,
            api_client=self._api_client,
            client_params=self._client_params,
            job_id=response["id"],
            program_id=program_id,
            params=inputs,
            user_callback=callback,
            result_decoder=result_decoder,
            image=options.get("image"),
        )
        return job

    @property
    def channel(self) -> str:
        """Return the channel type used.

        Returns:
            The channel type used.
        """
        return self._channel
