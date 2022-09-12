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

"""Client for accessing IBM Quantum runtime service."""

import logging
from typing import Dict, List, Optional

from qiskit_ibm_runtime.api.session import RetrySession

from ..rest.runtime import Runtime
from ..client_parameters import ClientParameters
from ...utils.hgp import from_instance_format

logger = logging.getLogger(__name__)


class RuntimeClient:
    """Client for accessing runtime service."""

    def __init__(
        self,
        params: ClientParameters,
    ) -> None:
        """RuntimeClient constructor.

        Args:
            params: Connection parameters.
        """
        self._session = RetrySession(
            base_url=params.get_runtime_api_base_url(),
            auth=params.get_auth_handler(),
            **params.connection_parameters()
        )
        self._api = Runtime(self._session)

    def program_run(
        self,
        program_id: str,
        backend_name: Optional[str],
        params: Dict,
        image: Optional[str],
        hgp: Optional[str],
        log_level: Optional[str],
        session_id: Optional[str],
        job_tags: Optional[List[str]] = None,
        max_execution_time: Optional[int] = None,
        start_session: Optional[bool] = False,
    ) -> Dict:
        """Run the specified program.

        Args:
            program_id: Program ID.
            backend_name: Name of the backend to run the program.
            params: Parameters to use.
            image: The runtime image to use.
            hgp: Hub/group/project to use.
            log_level: Log level to use.
            session_id: Job ID of the first job in a runtime session.
            job_tags: Tags to be assigned to the job.
            max_execution_time: Maximum execution time in seconds.
            start_session: Set to True to explicitly start a runtime session. Defaults to False.

        Returns:
            JSON response.
        """
        hgp_dict = {}
        if hgp:
            hub, group, project = from_instance_format(hgp)
            hgp_dict = {"hub": hub, "group": group, "project": project}
        return self._api.program_run(
            program_id=program_id,
            backend_name=backend_name,
            params=params,
            image=image,
            log_level=log_level,
            session_id=session_id,
            job_tags=job_tags,
            max_execution_time=max_execution_time,
            start_session=start_session,
            **hgp_dict
        )

    def job_get(self, job_id: str) -> Dict:
        """Get job data.

        Args:
            job_id: Job ID.

        Returns:
            JSON response.
        """
        response = self._api.program_job(job_id).get()
        logger.debug("Runtime job get response: %s", response)
        return response

    def job_results(self, job_id: str) -> str:
        """Get the results of a program job.

        Args:
            job_id: Program job ID.

        Returns:
            Job result.
        """
        return self._api.program_job(job_id).results()

    def job_interim_results(self, job_id: str) -> str:
        """Get the interim results of a program job.

        Args:
            job_id: Program job ID.

        Returns:
            Job interim results.
        """
        return self._api.program_job(job_id).interim_results()

    def job_cancel(self, job_id: str) -> None:
        """Cancel a job.

        Args:
            job_id: Runtime job ID.
        """
        self._api.program_job(job_id).cancel()

    def job_delete(self, job_id: str) -> None:
        """Delete a job.

        Args:
            job_id: Runtime job ID.
        """
        self._api.program_job(job_id).delete()

    def job_logs(self, job_id: str) -> str:
        """Get the job logs.

        Args:
            job_id: Program job ID.

        Returns:
            Job logs.
        """
        return self._api.program_job(job_id).logs()

    def job_metadata(self, job_id: str) -> str:
        """Get job metadata.

        Args:
            job_id: Program job ID.

        Returns:
            Job metadata.
        """
        return self._api.program_job(job_id).metadata()
