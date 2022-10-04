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

"""Module for interfacing with an IBM Quantum Backend."""

import copy
import logging
import warnings
from dataclasses import asdict
from datetime import datetime as python_datetime
from typing import Iterable, Dict, List, Union, Optional, Any

from qiskit.circuit import QuantumCircuit, Parameter, Delay
from qiskit.circuit.duration import duration_in_dt
from qiskit.providers.backend import BackendV2 as Backend
from qiskit.providers.models import (
    BackendStatus,
    BackendProperties,
    PulseDefaults,
    GateConfig,
    QasmBackendConfiguration,
    PulseBackendConfiguration,
)
from qiskit.providers.options import Options
from qiskit.pulse import Schedule, LoConfig
from qiskit.pulse.channels import (
    PulseChannel,
    AcquireChannel,
    ControlChannel,
    DriveChannel,
    MeasureChannel,
)

from qiskit.qobj.utils import MeasLevel, MeasReturnType
from qiskit.tools.events.pubsub import Publisher
from qiskit.transpiler.target import Target

from qiskit_ibm_provider import ibm_provider  # pylint: disable=unused-import
from .api.clients import AccountClient
from .backendjoblimit import BackendJobLimit
from .backendreservation import BackendReservation
from .exceptions import (
    IBMBackendError,
    IBMBackendValueError,
    IBMBackendApiError,
    IBMBackendApiProtocolError,
)
from .job import IBMJob, IBMCircuitJob
from .utils import validate_job_tags
from .utils.options import QASM2Options, QASM3Options
from .utils.backend import convert_reservation_data
from .utils.backend_converter import (
    convert_to_target,
)
from .utils.converters import local_to_utc
from .utils.json_decoder import defaults_from_server_data, properties_from_server_data
from .api.exceptions import RequestsApiError

logger = logging.getLogger(__name__)


class IBMBackend(Backend):
    """Backend class interfacing with an IBM Quantum device.

    You can run experiments on a backend using the :meth:`run()` method. The
    :meth:`run()` method takes one or more :class:`~qiskit.circuit.QuantumCircuit`
    or :class:`~qiskit.pulse.Schedule` and returns
    an :class:`~qiskit_ibm_provider.job.IBMJob`
    instance that represents the submitted job. Each job has a unique job ID, which
    can later be used to retrieve the job. An example of this flow::

        from qiskit import transpile
        from qiskit_ibm_provider import IBMProvider
        from qiskit.circuit.random import random_circuit

        provider = IBMProvider()
        backend = provider.backend.ibmq_vigo
        qx = random_circuit(n_qubits=5, depth=4)
        transpiled = transpile(qx, backend=backend)
        job = backend.run(transpiled)
        retrieved_job = provider.backend.job(job.job_id())

    Note:

        * Unlike :meth:`qiskit.execute`, the :meth:`run` method does not transpile
          the circuits/schedules for you, so be sure to do so before submitting them.

        * You should not instantiate the ``IBMBackend`` class directly. Instead, use
          the methods provided by an :class:`IBMProvider` instance to retrieve and handle
          backends.

    Other methods return information about the backend. For example, the :meth:`status()` method
    returns a :class:`BackendStatus<qiskit.providers.models.BackendStatus>` instance.
    The instance contains the ``operational`` and ``pending_jobs`` attributes, which state whether
    the backend is operational and also the number of jobs in the server queue for the backend,
    respectively::

        status = backend.status()
        is_operational = status.operational
        jobs_in_queue = status.pending_jobs

    It is also possible to see the number of remaining jobs you are able to submit to the
    backend with the :meth:`job_limit()` method, which returns a
    :class:`BackendJobLimit<qiskit_ibm_provider.BackendJobLimit>` instance::

        job_limit = backend.job_limit()

    Here is list of attributes available on the ``IBMBackend`` class:
        * name: backend name.
        * backend_version: backend version in the form X.Y.Z.
        * num_qubits: number of qubits.
        * target: A :class:`qiskit.transpiler.Target` object for the backend.
        * basis_gates: list of basis gates names on the backend.
        * gates: list of basis gates on the backend.
        * local: backend is local or remote.
        * simulator: backend is a simulator.
        * conditional: backend supports conditional operations.
        * open_pulse: backend supports open pulse.
        * memory: backend supports memory.
        * max_shots: maximum number of shots supported.
        * coupling_map (list): The coupling map for the device
        * supported_instructions (List[str]): Instructions supported by the backend.
        * dynamic_reprate_enabled (bool): whether delay between programs can be set dynamically
          (ie via ``rep_delay``). Defaults to False.
        * rep_delay_range (List[float]): 2d list defining supported range of repetition
          delays for backend in μs. First entry is lower end of the range, second entry is
          higher end of the range. Optional, but will be specified when
          ``dynamic_reprate_enabled=True``.
        * default_rep_delay (float): Value of ``rep_delay`` if not specified by user and
          ``dynamic_reprate_enabled=True``.
        * n_uchannels: Number of u-channels.
        * u_channel_lo: U-channel relationship on device los.
        * meas_levels: Supported measurement levels.
        * qubit_lo_range: Qubit lo ranges for each qubit with form (min, max) in GHz.
        * meas_lo_range: Measurement lo ranges for each qubit with form (min, max) in GHz.
        * dt: Qubit drive channel timestep in nanoseconds.
        * dtm: Measurement drive channel timestep in nanoseconds.
        * rep_times: Supported repetition times (program execution time) for backend in μs.
        * meas_kernels: Supported measurement kernels.
        * discriminators: Supported discriminators.
        * hamiltonian: An optional dictionary with fields characterizing the system hamiltonian.
        * channel_bandwidth (list): Bandwidth of all channels
          (qubit, measurement, and U)
        * acquisition_latency (list): Array of dimension
          n_qubits x n_registers. Latency (in units of dt) to write a
          measurement result from qubit n into register slot m.
        * conditional_latency (list): Array of dimension n_channels
          [d->u->m] x n_registers. Latency (in units of dt) to do a
          conditional operation on channel n from register slot m
        * meas_map (list): Grouping of measurement which are multiplexed
        * max_circuits (int): The maximum number of experiments per job
        * sample_name (str): Sample name for the backend
        * n_registers (int): Number of register slots available for feedback
          (if conditional is True)
        * register_map (list): An array of dimension n_qubits X
          n_registers that specifies whether a qubit can store a
          measurement in a certain register slot.
        * configurable (bool): True if the backend is configurable, if the
          backend is a simulator
        * credits_required (bool): True if backend requires credits to run a
          job.
        * online_date (datetime): The date that the device went online
        * display_name (str): Alternate name field for the backend
        * description (str): A description for the backend
        * tags (list): A list of string tags to describe the backend
        * version: version of ``Backend`` class (Ex: 1, 2)
        * channels: An optional dictionary containing information of each channel -- their
          purpose, type, and qubits operated on.
        * parametric_pulses (list): A list of pulse shapes which are supported on the backend.
          For example: ``['gaussian', 'constant']``
        * processor_type (dict): Processor type for this backend. A dictionary of the
          form ``{"family": <str>, "revision": <str>, segment: <str>}`` such as
          ``{"family": "Canary", "revision": "1.0", segment: "A"}``.

            * family: Processor family of this backend.
            * revision: Revision version of this processor.
            * segment: Segment this processor belongs to within a larger chip.
    """

    id_warning_issued = False

    def __init__(
        self,
        configuration: Union[QasmBackendConfiguration, PulseBackendConfiguration],
        provider: "ibm_provider.IBMProvider",
        api_client: AccountClient,
    ) -> None:
        """IBMBackend constructor.

        Args:
            configuration: Backend configuration.
            provider: IBM Quantum account provider.
            api_client: IBM Quantum client used to communicate with the server.
        """
        super().__init__(
            provider=provider,
            name=configuration.backend_name,
            online_date=configuration.online_date,
            backend_version=configuration.backend_version,
        )
        self._api_client = api_client
        self._configuration = configuration
        self._properties = None
        self._defaults = None
        self._target = None
        self._max_circuits = configuration.max_experiments
        if not self._configuration.simulator:
            self.options.set_validator("noise_model", type(None))
            self.options.set_validator("seed_simulator", type(None))
        if hasattr(configuration, "max_shots"):
            self.options.set_validator("shots", (1, configuration.max_shots))
        if hasattr(configuration, "rep_delay_range"):
            self.options.set_validator(
                "rep_delay",
                (configuration.rep_delay_range[0], configuration.rep_delay_range[1]),
            )

    def __getattr__(self, name: str) -> Any:
        """Gets attribute from self or configuration
        This magic method executes when user accesses an attribute that
        does not yet exist on IBMBackend class.
        """
        # Prevent recursion since these properties are accessed within __getattr__
        if name in ["_properties", "_defaults", "_target"]:
            raise AttributeError(
                "'{}' object has no attribute '{}'".format(
                    self.__class__.__name__, name
                )
            )
        # Lazy load properties and pulse defaults and construct the target object.
        self._get_properties()
        self._get_defaults()
        self._convert_to_target()
        # Check if the attribute now is available on IBMBackend class due to above steps
        try:
            return super().__getattribute__(name)
        except AttributeError:
            pass
        # If attribute is still not available on IBMBackend class,
        # fallback to check if the attribute is available in configuration
        try:
            return self._configuration.__getattribute__(name)
        except AttributeError:
            raise AttributeError(
                "'{}' object has no attribute '{}'".format(
                    self.__class__.__name__, name
                )
            )

    def _get_properties(self) -> None:
        """Gets backend properties and decodes it"""
        if not self._properties:
            api_properties = self._api_client.backend_properties(self.name)
            if api_properties:
                backend_properties = properties_from_server_data(api_properties)
                self._properties = backend_properties

    def _get_defaults(self) -> None:
        """Gets defaults if pulse backend and decodes it"""
        if not self._defaults:
            api_defaults = self._api_client.backend_pulse_defaults(self.name)
            if api_defaults:
                self._defaults = defaults_from_server_data(api_defaults)

    def _convert_to_target(self) -> None:
        """Converts backend configuration, properties and defaults to Target object"""
        if not self._target:
            self._target = convert_to_target(
                configuration=self._configuration,
                properties=self._properties,
                defaults=self._defaults,
            )

    @classmethod
    def _default_options(cls) -> Options:
        """Default runtime options."""
        return Options(
            shots=4000,
            memory=False,
            qubit_lo_freq=None,
            meas_lo_freq=None,
            schedule_los=None,
            meas_level=MeasLevel.CLASSIFIED,
            meas_return=MeasReturnType.AVERAGE,
            memory_slots=None,
            memory_slot_size=100,
            rep_time=None,
            rep_delay=None,
            init_qubits=True,
            use_measure_esp=None,
            # Simulator only
            noise_model=None,
            seed_simulator=None,
        )

    @property
    def dtm(self) -> float:
        """Return the system time resolution of output signals
        Returns:
            dtm: The output signal timestep in seconds.
        """
        return self._configuration.dtm

    @property
    def max_circuits(self) -> int:
        """The maximum number of circuits
        The maximum number of circuits (or Pulse schedules) that can be
        run in a single job. If there is no limit this will return None.
        """
        return self._max_circuits

    @property
    def meas_map(self) -> List[List[int]]:
        """Return the grouping of measurements which are multiplexed
        This is required to be implemented if the backend supports Pulse
        scheduling.
        Returns:
            meas_map: The grouping of measurements which are multiplexed
        """
        return self._configuration.meas_map

    @property
    def target(self) -> Target:
        """A :class:`qiskit.transpiler.Target` object for the backend.
        Returns:
            Target
        """
        self._get_properties()
        self._get_defaults()
        self._convert_to_target()
        return self._target

    def run(
        self,
        circuits: Union[
            QuantumCircuit, Schedule, List[Union[QuantumCircuit, Schedule]]
        ],
        dynamic: bool = False,
        job_tags: Optional[List[str]] = None,
        header: Optional[Dict] = None,
        shots: Optional[Union[int, float]] = None,
        memory: Optional[bool] = None,
        qubit_lo_freq: Optional[List[int]] = None,
        meas_lo_freq: Optional[List[int]] = None,
        schedule_los: Optional[
            Union[
                List[Union[Dict[PulseChannel, float], LoConfig]],
                Union[Dict[PulseChannel, float], LoConfig],
            ]
        ] = None,
        meas_level: Optional[Union[int, MeasLevel]] = None,
        meas_return: Optional[Union[str, MeasReturnType]] = None,
        memory_slots: Optional[int] = None,
        memory_slot_size: Optional[int] = None,
        rep_time: Optional[int] = None,
        rep_delay: Optional[float] = None,
        init_qubits: Optional[bool] = None,
        parameter_binds: Optional[List[Dict[Parameter, float]]] = None,
        use_measure_esp: Optional[bool] = None,
        noise_model: Optional[Any] = None,
        **run_config: Dict,
    ) -> IBMJob:
        """Run on the backend.
        If a keyword specified here is also present in the ``options`` attribute/object,
        the value specified here will be used for this run.

        Args:
            circuits: An individual or a
                list of :class:`~qiskit.circuits.QuantumCircuit` or
                :class:`~qiskit.pulse.Schedule` object to run on the backend.
            dynamic: Whether the circuit is dynamic (uses in-circuit conditionals)
            job_tags: Tags to be assigned to the job. The tags can subsequently be used
                as a filter in the :meth:`jobs()` function call.
            header: User input that will be attached to the job and will be
                copied to the corresponding result header. Headers do not affect the run.
                This replaces the old ``Qobj`` header.
            shots: Number of repetitions of each circuit, for sampling. Default: 4000
                or ``max_shots`` from the backend configuration, whichever is smaller.
            memory: If ``True``, per-shot measurement bitstrings are returned as well
                (provided the backend supports it). For OpenPulse jobs, only
                measurement level 2 supports this option.
            qubit_lo_freq: List of default qubit LO frequencies in Hz. Will be overridden by
                ``schedule_los`` if set.
            meas_lo_freq: List of default measurement LO frequencies in Hz. Will be overridden
                by ``schedule_los`` if set.
            schedule_los: Experiment LO configurations, frequencies are given in Hz.
            meas_level: Set the appropriate level of the measurement output for pulse experiments.
            meas_return: Level of measurement data for the backend to return.
                For ``meas_level`` 0 and 1:
                * ``single`` returns information from every shot.
                * ``avg`` returns average measurement output (averaged over number of shots).
            memory_slots: Number of classical memory slots to use.
            memory_slot_size: Size of each memory slot if the output is Level 0.
            rep_time: Time per program execution in seconds. Must be from the list provided
                by the backend (``backend.configuration().rep_times``).
                Defaults to the first entry.
            rep_delay: Delay between programs in seconds. Only supported on certain
                backends (if ``backend.configuration().dynamic_reprate_enabled=True``).
                If supported, ``rep_delay`` will be used instead of ``rep_time`` and must be
                from the range supplied
                by the backend (``backend.configuration().rep_delay_range``). Default is given by
                ``backend.configuration().default_rep_delay``.
            init_qubits: Whether to reset the qubits to the ground state for each shot.
                Default: ``True``.
            parameter_binds: List of Parameter bindings over which the set of experiments will be
                executed. Each list element (bind) should be of the form
                {Parameter1: value1, Parameter2: value2, ...}. All binds will be
                executed across all experiments; e.g., if parameter_binds is a
                length-n list, and there are m experiments, a total of m x n
                experiments will be run (one for each experiment/bind pair).
            use_measure_esp: Whether to use excited state promoted (ESP) readout for measurements
                which are the terminal instruction to a qubit. ESP readout can offer higher fidelity
                than standard measurement sequences. See
                `here <https://arxiv.org/pdf/2008.08571.pdf>`_.
                Default: ``True`` if backend supports ESP readout, else ``False``. Backend support
                for ESP readout is determined by the flag ``measure_esp_enabled`` in
                ``backend.configuration()``.
            noise_model: Noise model. (Simulators only)
            **run_config: Extra arguments used to configure the run.

        Returns:
            The job to be executed.

        Raises:
            IBMBackendApiError: If an unexpected error occurred while submitting
                the job.
            IBMBackendApiProtocolError: If an unexpected value received from
                 the server.
            IBMBackendValueError:
                - If an input parameter value is not valid.
                - If ESP readout is used and the backend does not support this.
        """
        # pylint: disable=arguments-differ

        validate_job_tags(job_tags, IBMBackendValueError)

        status = self.status()
        if status.operational is True and status.status_msg != "active":
            warnings.warn(f"The backend {self.name} is currently paused.")

        program_id = "circuit-runner"
        if dynamic:
            program_id = "qasm3-runner"

        if isinstance(shots, float):
            shots = int(shots)
        if not self.configuration().simulator:
            circuits = self._deprecate_id_instruction(circuits)
        options = {"backend": self.name}

        run_config_dict = self._get_run_config(
            program_id=program_id,
            header=header,
            shots=shots,
            memory=memory,
            qubit_lo_freq=qubit_lo_freq,
            meas_lo_freq=meas_lo_freq,
            schedule_los=schedule_los,
            meas_level=meas_level,
            meas_return=meas_return,
            memory_slots=memory_slots,
            memory_slot_size=memory_slot_size,
            rep_time=rep_time,
            rep_delay=rep_delay,
            init_qubits=init_qubits,
            use_measure_esp=use_measure_esp,
            noise_model=noise_model,
            parameter_binds=parameter_binds,
            **run_config,
        )

        run_config_dict["circuits"] = circuits

        return self._runtime_run(
            program_id=program_id,
            inputs=run_config_dict,
            options=options,
            job_tags=job_tags,
        )

    def _runtime_run(
        self,
        program_id: str,
        inputs: Dict,
        options: Dict,
        job_tags: Optional[List[str]] = None,
    ) -> IBMCircuitJob:
        """Runs the runtime program and returns the corresponding job object"""
        hgp = self.provider._get_hgps()[0]
        hgp_name = hgp.name
        try:
            response = self.provider._runtime_client.program_run(
                program_id=program_id,
                backend_name=options["backend"],
                params=inputs,
                hgp=hgp_name,
                job_tags=job_tags,
            )
        except RequestsApiError as ex:
            raise IBMBackendApiError("Error submitting job: {}".format(str(ex))) from ex
        try:
            job_id = response["id"]
            job = IBMCircuitJob(
                backend=self,
                api_client=self._api_client,
                runtime_client=self.provider._runtime_client,
                job_id=job_id,
            )
            logger.debug("Job %s was successfully submitted.", job.job_id())
        except TypeError as err:
            logger.debug("Invalid job data received: %s", response)
            raise IBMBackendApiProtocolError(
                "Unexpected return value received from the server "
                "when submitting job: {}".format(str(err))
            ) from err
        Publisher().publish("ibm.job.start", job)
        return job

    def _get_run_config(self, program_id: str, **kwargs: Any) -> Dict:
        """Return the consolidated runtime configuration."""
        if program_id == "qasm3-runner":
            original_dict = asdict(QASM3Options())
            run_config_dict = copy.copy(asdict(QASM3Options(**original_dict)))
        else:
            original_dict = self.options.__dict__
            run_config_dict = copy.copy(asdict(QASM2Options(**original_dict)))
        for key, val in kwargs.items():
            if val is not None:
                run_config_dict[key] = val
                if key not in original_dict and not self.configuration().simulator:
                    warnings.warn(  # type: ignore[unreachable]
                        f"{key} is not a recognized runtime option and may be ignored by the backend.",
                        stacklevel=4,
                    )
        return run_config_dict

    def properties(
        self, refresh: bool = False, datetime: Optional[python_datetime] = None
    ) -> Optional[BackendProperties]:
        """Return the backend properties, subject to optional filtering.

        This data describes qubits properties (such as T1 and T2),
        gates properties (such as gate length and error), and other general
        properties of the backend.

        The schema for backend properties can be found in
        `Qiskit/ibm-quantum-schemas
        <https://github.com/Qiskit/ibm-quantum-schemas/blob/main/schemas/backend_properties_schema.json>`_.

        Args:
            refresh: If ``True``, re-query the server for the backend properties.
                Otherwise, return a cached version.
            datetime: By specifying `datetime`, this function returns an instance
                of the :class:`BackendProperties<qiskit.providers.models.BackendProperties>`
                whose timestamp is closest to, but older than, the specified `datetime`.

        Returns:
            The backend properties or ``None`` if the backend properties are not
            currently available.

        Raises:
            TypeError: If an input argument is not of the correct type.
        """
        # pylint: disable=arguments-differ
        if self._configuration.simulator:
            # Simulators do not have backend properties.
            return None
        if not isinstance(refresh, bool):
            raise TypeError(
                "The 'refresh' argument needs to be a boolean. "
                "{} is of type {}".format(refresh, type(refresh))
            )
        if datetime and not isinstance(datetime, python_datetime):
            raise TypeError("'{}' is not of type 'datetime'.")

        if datetime:
            datetime = local_to_utc(datetime)

        if datetime or refresh or self._properties is None:
            api_properties = self._api_client.backend_properties(
                self.name, datetime=datetime
            )
            if not api_properties:
                return None
            backend_properties = properties_from_server_data(api_properties)
            if datetime:  # Don't cache result.
                return backend_properties
            self._properties = backend_properties
        return self._properties

    def status(self) -> BackendStatus:
        """Return the backend status.

        Note:
            If the returned :class:`~qiskit.providers.models.BackendStatus`
            instance has ``operational=True`` but ``status_msg="internal"``,
            then the backend is accepting jobs but not processing them.

        Returns:
            The status of the backend.

        Raises:
            IBMBackendApiProtocolError: If the status for the backend cannot be formatted properly.
        """
        api_status = self._api_client.backend_status(self.name)

        try:
            return BackendStatus.from_dict(api_status)
        except TypeError as ex:
            raise IBMBackendApiProtocolError(
                "Unexpected return value received from the server when "
                "getting backend status: {}".format(str(ex))
            ) from ex

    def defaults(self, refresh: bool = False) -> Optional[PulseDefaults]:
        """Return the pulse defaults for the backend.

        The schema for default pulse configuration can be found in
        `Qiskit/ibm-quantum-schemas
        <https://github.com/Qiskit/ibm-quantum-schemas/blob/main/schemas/default_pulse_configuration_schema.json>`_.

        Args:
            refresh: If ``True``, re-query the server for the backend pulse defaults.
                Otherwise, return a cached version.

        Returns:
            The backend pulse defaults or ``None`` if the backend does not support pulse.
        """
        if refresh or self._defaults is None:
            api_defaults = self._api_client.backend_pulse_defaults(self.name)
            if api_defaults:
                self._defaults = defaults_from_server_data(api_defaults)
            else:
                self._defaults = None

        return self._defaults

    def job_limit(self) -> BackendJobLimit:
        """Return the job limit for the backend.

        The job limit information includes the current number of active jobs
        you have on the backend and the maximum number of active jobs you can have
        on it.

        Note:
            Job limit information for a backend is provider specific.
            For example, if you have access to the same backend via
            different providers, the job limit information might be
            different for each provider.

        If the method call was successful, you can inspect the job limit for
        the backend by accessing the ``maximum_jobs`` and ``active_jobs`` attributes
        of the :class:`BackendJobLimit<BackendJobLimit>` instance returned. For example::

            backend_job_limit = backend.job_limit()
            maximum_jobs = backend_job_limit.maximum_jobs
            active_jobs = backend_job_limit.active_jobs

        If ``maximum_jobs`` is equal to ``None``, then there is
        no limit to the maximum number of active jobs you could
        have on the backend.

        Returns:
            The job limit for the backend, with this provider.

        Raises:
            IBMBackendApiProtocolError: If an unexpected value is received from the server.
        """
        api_job_limit = self._api_client.backend_job_limit(self.name)

        try:
            job_limit = BackendJobLimit(**api_job_limit)
            if job_limit.maximum_jobs == -1:
                # Manually set `maximum` to `None` if backend has no job limit.
                job_limit.maximum_jobs = None
            return job_limit
        except TypeError as ex:
            raise IBMBackendApiProtocolError(
                "Unexpected return value received from the server when "
                "querying job limit data for the backend: {}.".format(ex)
            ) from ex

    def remaining_jobs_count(self) -> Optional[int]:
        """Return the number of remaining jobs that could be submitted to the backend.

        Note:
            The number of remaining jobs for a backend is provider
            specific. For example, if you have access to the same backend
            via different providers, the number of remaining jobs might
            be different for each. See :class:`BackendJobLimit<BackendJobLimit>`
            for the job limit information of a backend.

        If ``None`` is returned, there are no limits to the maximum
        number of active jobs you could have on the backend.

        Returns:
            The remaining number of jobs a user could submit to the backend, with
            this provider, before the maximum limit on active jobs is reached.

        Raises:
            IBMBackendApiProtocolError: If an unexpected value is received from the server.
        """
        job_limit = self.job_limit()

        if job_limit.maximum_jobs is None:
            return None

        return job_limit.maximum_jobs - job_limit.active_jobs

    def active_jobs(self, limit: int = 10) -> List[IBMJob]:
        """Return the unfinished jobs submitted to this backend.

        Return the jobs submitted to this backend, with this provider, that are
        currently in an unfinished job status state. The unfinished
        :class:`JobStatus<qiskit.providers.jobstatus.JobStatus>` states
        include: ``INITIALIZING``, ``VALIDATING``, ``QUEUED``, and ``RUNNING``.

        Args:
            limit: Number of jobs to retrieve.

        Returns:
            A list of the unfinished jobs for this backend on this provider.
        """
        return self.provider.backend.jobs(status="pending", limit=limit)

    def reservations(
        self,
        start_datetime: Optional[python_datetime] = None,
        end_datetime: Optional[python_datetime] = None,
    ) -> List[BackendReservation]:
        """Return backend reservations.

        If start_datetime and/or end_datetime is specified, reservations with
        time slots that overlap with the specified time window will be returned.

        Some of the reservation information is only available if you are the
        owner of the reservation.

        Args:
            start_datetime: Filter by the given start date/time, in local timezone.
            end_datetime: Filter by the given end date/time, in local timezone.

        Returns:
            A list of reservations that match the criteria.
        """
        start_datetime = local_to_utc(start_datetime) if start_datetime else None
        end_datetime = local_to_utc(end_datetime) if end_datetime else None
        raw_response = self._api_client.backend_reservations(
            self.name, start_datetime, end_datetime
        )
        return convert_reservation_data(raw_response, self.name)

    def configuration(
        self,
    ) -> Union[QasmBackendConfiguration, PulseBackendConfiguration]:
        """Return the backend configuration.

        Backend configuration contains fixed information about the backend, such
        as its name, number of qubits, basis gates, coupling map, quantum volume, etc.

        The schema for backend configuration can be found in
        `Qiskit/ibm-quantum-schemas
        <https://github.com/Qiskit/ibm-quantum-schemas/blob/main/schemas/backend_configuration_schema.json>`_.

        Returns:
            The configuration for the backend.
        """
        return self._configuration

    def drive_channel(self, qubit: int) -> DriveChannel:
        """Return the drive channel for the given qubit.

        Returns:
            DriveChannel: The Qubit drive channel
        """
        return self._configuration.drive(qubit=qubit)

    def measure_channel(self, qubit: int) -> MeasureChannel:
        """Return the measure stimulus channel for the given qubit.

        Returns:
            MeasureChannel: The Qubit measurement stimulus line
        """
        return self._configuration.measure(qubit=qubit)

    def acquire_channel(self, qubit: int) -> AcquireChannel:
        """Return the acquisition channel for the given qubit.

        Returns:
            AcquireChannel: The Qubit measurement acquisition line.
        """
        return self._configuration.acquire(qubit=qubit)

    def control_channel(self, qubits: Iterable[int]) -> List[ControlChannel]:
        """Return the secondary drive channel for the given qubit.

        This is typically utilized for controlling multiqubit interactions.
        This channel is derived from other channels.

        Args:
            qubits: Tuple or list of qubits of the form
                ``(control_qubit, target_qubit)``.

        Returns:
            List[ControlChannel]: The Qubit measurement acquisition line.
        """
        return self._configuration.control(qubits=qubits)

    def __repr__(self) -> str:
        return "<{}('{}')>".format(self.__class__.__name__, self.name)

    def _deprecate_id_instruction(
        self,
        circuits: Union[
            QuantumCircuit, Schedule, List[Union[QuantumCircuit, Schedule]]
        ],
    ) -> Union[QuantumCircuit, Schedule, List[Union[QuantumCircuit, Schedule]]]:
        """Raise a DeprecationWarning if any circuit contains an 'id' instruction.

        Additionally, if 'delay' is a 'supported_instruction', replace each 'id'
        instruction (in-place) with the equivalent ('sx'-length) 'delay' instruction.

        Args:
            circuits: The individual or list of :class:`~qiskit.circuits.QuantumCircuit` or
                :class:`~qiskit.pulse.Schedule` objects passed to
                :meth:`IBMBackend.run()<IBMBackend.run>`. Modified in-place.

        Returns:
            A modified copy of the original circuit where 'id' instructions are replaced with
            'delay' instructions. A copy is used so the original circuit is not modified.
            If there are no 'id' instructions or 'delay' is not supported, return the original circuit.
        """

        id_support = "id" in getattr(self.configuration(), "basis_gates", [])
        delay_support = "delay" in getattr(
            self.configuration(), "supported_instructions", []
        )

        if not delay_support:
            return circuits

        if not isinstance(circuits, List):
            circuits = [circuits]

        circuit_has_id = any(
            instr.name == "id"
            for circuit in circuits
            if isinstance(circuit, QuantumCircuit)
            for instr, qargs, cargs in circuit.data
        )

        if not circuit_has_id:
            return circuits

        if not self.id_warning_issued:
            if id_support and delay_support:
                warnings.warn(
                    "Support for the 'id' instruction has been deprecated "
                    "from IBM hardware backends. Any 'id' instructions "
                    "will be replaced with their equivalent 'delay' instruction. "
                    "Please use the 'delay' instruction instead.",
                    DeprecationWarning,
                    stacklevel=4,
                )
            else:
                warnings.warn(
                    "Support for the 'id' instruction has been removed "
                    "from IBM hardware backends. Any 'id' instructions "
                    "will be replaced with their equivalent 'delay' instruction. "
                    "Please use the 'delay' instruction instead.",
                    DeprecationWarning,
                    stacklevel=4,
                )

            self.id_warning_issued = True

        dt_in_s = self.configuration().dt

        circuits_copy = copy.deepcopy(circuits)
        for circuit in circuits_copy:
            if isinstance(circuit, Schedule):
                continue

            for idx, (instr, qargs, cargs) in enumerate(circuit.data):
                if instr.name == "id":

                    sx_duration = self.properties().gate_length("sx", qargs[0].index)
                    sx_duration_in_dt = duration_in_dt(sx_duration, dt_in_s)

                    delay_instr = Delay(sx_duration_in_dt)

                    circuit.data[idx] = (delay_instr, qargs, cargs)
        return circuits_copy


class IBMRetiredBackend(IBMBackend):
    """Backend class interfacing with an IBM Quantum device no longer available."""

    def __init__(
        self,
        configuration: Union[QasmBackendConfiguration, PulseBackendConfiguration],
        provider: "ibm_provider.IBMProvider",
        api_client: AccountClient,
    ) -> None:
        """IBMRetiredBackend constructor.

        Args:
            configuration: Backend configuration.
            provider: IBM Quantum account provider.
            credentials: IBM Quantum credentials.
            api_client: IBM Quantum client used to communicate with the server.
        """
        super().__init__(configuration, provider, api_client)
        self._status = BackendStatus(
            backend_name=self.name,
            backend_version=self.configuration().backend_version,
            operational=False,
            pending_jobs=0,
            status_msg="This backend is no longer available.",
        )

    @classmethod
    def _default_options(cls) -> Options:
        """Default runtime options."""
        return super()._default_options()

    def properties(
        self, refresh: bool = False, datetime: Optional[python_datetime] = None
    ) -> None:
        """Return the backend properties."""
        return None

    def defaults(self, refresh: bool = False) -> None:
        """Return the pulse defaults for the backend."""
        return None

    def status(self) -> BackendStatus:
        """Return the backend status."""
        return self._status

    def job_limit(self) -> None:
        """Return the job limits for the backend."""
        return None

    def remaining_jobs_count(self) -> None:
        """Return the number of remaining jobs that could be submitted to the backend."""
        return None

    def active_jobs(self, limit: int = 10) -> None:
        """Return the unfinished jobs submitted to this backend."""
        return None

    def reservations(
        self,
        start_datetime: Optional[python_datetime] = None,
        end_datetime: Optional[python_datetime] = None,
    ) -> List[BackendReservation]:
        return []

    def run(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Run a Circuit."""
        # pylint: disable=arguments-differ
        raise IBMBackendError(
            "This backend ({}) is no longer available.".format(self.name)
        )

    @classmethod
    def from_name(
        cls,
        backend_name: str,
        provider: "ibm_provider.IBMProvider",
        api: AccountClient,
    ) -> "IBMRetiredBackend":
        """Return a retired backend from its name."""
        configuration = QasmBackendConfiguration(
            backend_name=backend_name,
            backend_version="0.0.0",
            online_date="2019-10-16T04:00:00Z",
            n_qubits=1,
            basis_gates=[],
            simulator=False,
            local=False,
            conditional=False,
            open_pulse=False,
            memory=False,
            max_shots=1,
            gates=[GateConfig(name="TODO", parameters=[], qasm_def="TODO")],
            coupling_map=[[0, 1]],
            max_experiments=300,
        )
        return cls(configuration, provider, api)
