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

"""Qiskit Runtime flexible session."""

from typing import Dict, Optional, Type, Union
from types import TracebackType
from functools import wraps
from contextvars import ContextVar

from qiskit.circuit import QuantumCircuit


def _active_session(func):  # type: ignore
    """Decorator used to ensure the session is active."""

    @wraps(func)
    def _wrapper(self, *args, **kwargs):  # type: ignore
        if not self._active:
            raise RuntimeError("The session is closed.")
        return func(self, *args, **kwargs)

    return _wrapper


class Session:
    """Class for creating a flexible Qiskit Runtime session.

    A Qiskit Runtime ``session`` allows you to group a collection of iterative calls to
    the quantum computer. A session is started when the first job within the session
    is started. Subsequent jobs within the session are prioritized by the scheduler.
    Data used within a session, such as transpiled circuits, is also cached to avoid
    unnecessary overhead.

    You can open a Qiskit Runtime session using this ``Session`` class and submit jobs
    to one or more primitives.

    For example::

        from qiskit.test.reference_circuits import ReferenceCircuits
        from qiskit_ibm_runtime import Sampler, Session, Options

        options = Options(optimization_level=3)

        with Session(backend="ibmq_qasm_simulator") as session:
            sampler = Sampler(session=session, options=options)
            job = sampler.run(circ)
            print(f"Sampler job ID: {job.job_id()}")
            print(f"Sampler job result:" {job.result()})
            # Close the session only if all jobs are finished and
            # you don't need to run more in the session.
            session.close()
    """

    def __init__(
        self,
        # provider: "qiskit_ibm_provider.IBMProvider",
        backend_name: Optional[str] = None,
        max_time: Optional[Union[int, str]] = None,
    ):  # pylint: disable=line-too-long
        """Session constructor.

        Args:
            service: Optional instance of the ``QiskitRuntimeService`` class.
                If ``None``, the service associated with the backend, if known, is used.
                Otherwise ``QiskitRuntimeService()`` is used to initialize
                your default saved account.
            backend: Optional instance of :class:`qiskit_ibm_runtime.IBMBackend` class or
                string name of backend. An instance of :class:`qiskit_ibm_provider.IBMBackend` will not work.
                If not specified, a backend will be selected automatically (IBM Cloud channel only).

            max_time: (EXPERIMENTAL setting, can break between releases without warning)
                Maximum amount of time, a runtime session can be open before being
                forcibly closed. Can be specified as seconds (int) or a string like "2h 30m 40s".
                This value must be in between 300 seconds and the
                `system imposed maximum
                <https://qiskit.org/documentation/partners/qiskit_ibm_runtime/faqs/max_execution_time.html>`_.

        Raises:
            ValueError: If an input value is invalid.
        """
        self._instance = None
        self._backend = backend_name
        self._session_id: Optional[str] = None
        self._active = True
        self._circuits_map: Dict[str, QuantumCircuit] = {}

        # for now ignore hms_to_seconds in order not to copy it from qiskit_ibm_runtime
        # self._max_time = (
        #     max_time
        #     if max_time is None or isinstance(max_time, int)
        #     else hms_to_seconds(max_time, "Invalid max_time value: ")
        # )
        self._max_time = max_time

    # def close(self) -> None:
    #     """Close the session."""
    #     self._active = False
    #     if self._session_id:
    #         self._service._api_client.close_session(self._session_id)

    def backend(self) -> Optional[str]:
        """Return backend for this session.

        Returns:
            Backend for this session. None if unknown.
        """
        return self._backend

    @property
    def session_id(self) -> str:
        """Return the session ID.

        Returns:
            Session ID. None until a job runs in the session.
        """
        return self._session_id

    def __enter__(self) -> "Session":
        set_cm_session(self)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        set_cm_session(None)


# Default session
_DEFAULT_SESSION: ContextVar[Optional[Session]] = ContextVar(
    "_DEFAULT_SESSION", default=None
)
_IN_SESSION_CM: ContextVar[bool] = ContextVar("_IN_SESSION_CM", default=False)


def set_cm_session(session: Optional[Session]) -> None:
    """Set the context manager session."""
    _DEFAULT_SESSION.set(session)
    _IN_SESSION_CM.set(session is not None)


def get_cm_session() -> Session:
    """Return the context managed session."""
    return _DEFAULT_SESSION.get()
