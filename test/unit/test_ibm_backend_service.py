# This code is part of Qiskit.
#
# (C) Copyright IBM 2023.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""IBMBackendService Unit Test."""

import inspect

from typing import List, Dict, Any, Optional
from unittest.mock import MagicMock, patch

from qiskit_ibm_provider import IBMBackendService
from qiskit_ibm_provider.api.clients import AccountClient, RuntimeClient
from qiskit_ibm_provider.hub_group_project import HubGroupProject
from qiskit_ibm_provider.ibm_provider import IBMProvider
from ..ibm_test_case import IBMTestCase

SIZE_OF_FAKE_RETURN_DATA = 112


class TestIBMBackendService(IBMTestCase):
    """Test ibm_backend_service module."""

    @classmethod
    def setUpClass(cls) -> None:
        """Initial class level setup."""
        # pylint: disable=arguments-differ
        super().setUpClass()
        mock_ibm_provider = MagicMock(spec=IBMProvider)
        mock_account_client = MagicMock(spec=AccountClient)
        mock_runtime_client = MagicMock(spec=RuntimeClient)
        mock_hgp = MagicMock(spec=HubGroupProject)

        mock_account_client.list_jobs.side_effect = fake_list_jobs

        mock_runtime_client.jobs_get.side_effect = fake_jobs_get

        mock_hgp._api_client = mock_account_client

        mock_ibm_provider._get_hgps.return_value = [mock_hgp]
        mock_ibm_provider._runtime_client = mock_runtime_client

        cls.mock_service = IBMBackendService(mock_ibm_provider, mock_hgp)
        cls.default_limit = cls.get_jobs_default_limit()

    @classmethod
    def get_jobs_default_limit(cls):
        """Gets the default limit for IBMBackendService.jobs()"""
        params = inspect.signature(IBMBackendService.jobs).parameters
        return params["limit"].default

    def test_retrieve_jobs_default_limit(self):
        """Test retrieving jobs with no explicit limit given"""
        mock_service = self.mock_service
        with patch(
            "qiskit_ibm_provider.ibm_backend_service.IBMBackendService._restore_circuit_job",
            side_effect=fake_restore_circuit_job,
        ):
            job_list = mock_service.jobs()
            print(f"job_list: {job_list}")

        self.assertEqual(len(job_list), self.default_limit)

    def test_retrieve_jobs_small_limit(self):
        """Test retrieving jobs with limit smaller than default given"""
        mock_service = self.mock_service
        small_limit = self.default_limit // 2
        with patch(
            "qiskit_ibm_provider.ibm_backend_service.IBMBackendService._restore_circuit_job",
            side_effect=fake_restore_circuit_job,
        ):
            job_list = mock_service.jobs(limit=small_limit)

        self.assertEqual(len(job_list), small_limit)

    def test_retrieve_jobs_no_limit(self):
        """Test retrieving jobs with 'None' limit"""
        mock_service = self.mock_service

        with patch(
            "qiskit_ibm_provider.ibm_backend_service.IBMBackendService._restore_circuit_job",
            side_effect=fake_restore_circuit_job,
        ):
            job_list = mock_service.jobs(limit=None, descending=False)

        self.assertEqual(len(job_list), SIZE_OF_FAKE_RETURN_DATA)

    def test_retrieve_legacy_jobs_default_limit(self):
        """Test retrieving legacy jobs with no explicit limit given"""
        mock_service = self.mock_service
        with patch(
            "qiskit_ibm_provider.ibm_backend_service.IBMBackendService._restore_circuit_job",
            side_effect=fake_restore_circuit_job,
        ):
            job_list = mock_service.jobs(legacy=True)

        self.assertEqual(len(job_list), self.default_limit)

    def test_retrieve_legacy_jobs_small_limit(self):
        """Test retrieving legacy jobs with limit smaller than default given"""
        mock_service = self.mock_service
        small_limit = self.default_limit // 2
        with patch(
            "qiskit_ibm_provider.ibm_backend_service.IBMBackendService._restore_circuit_job",
            side_effect=fake_restore_circuit_job,
        ):
            job_list = mock_service.jobs(legacy=True, limit=small_limit)

        self.assertEqual(len(job_list), small_limit)

    def test_retrieve_legacy_jobs_no_limit(self):
        """Test retrieving legacy jobs with 'None' limit"""
        mock_service = self.mock_service

        with patch(
            "qiskit_ibm_provider.ibm_backend_service.IBMBackendService._restore_circuit_job",
            side_effect=fake_restore_circuit_job,
        ):
            job_list = mock_service.jobs(limit=None, legacy=True, descending=False)

        self.assertEqual(len(job_list), SIZE_OF_FAKE_RETURN_DATA)


def fake_list_jobs(
    limit: int = 10,
    skip: int = 0,
    descending: bool = True,
    extra_filter: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Mock method definition for AccountClient.list_jobs()"""
    if extra_filter:
        pass  # Parameter is passed by unused in this mock
    effective_limit = limit if (limit is not None and limit <= 50) else 50
    if skip >= SIZE_OF_FAKE_RETURN_DATA:
        return []
    if descending:
        first_job = SIZE_OF_FAKE_RETURN_DATA - skip
        last_job = (
            first_job - effective_limit if first_job - effective_limit >= 0 else 0
        )
        job_range = range(first_job, last_job, -1)
    else:
        first_job = 1 + skip
        last_job = (
            first_job + effective_limit
            if first_job + effective_limit <= SIZE_OF_FAKE_RETURN_DATA
            else SIZE_OF_FAKE_RETURN_DATA + 1
        )
        job_range = range(first_job, last_job)

    return [
        {"program": {"id": "circuit-runner", "data": f"mock job {i}"}}
        for i in job_range
    ]


def fake_jobs_get(
    limit: int = None,
    skip: int = None,
    descending: bool = True,
) -> Dict:
    """Mock method definition for RuntimeClient.jobs_get()"""
    return {"jobs": fake_list_jobs(limit=limit, skip=skip, descending=descending)}


def fake_restore_circuit_job(
    job_info: Dict, raise_error: bool, legacy: bool = False
) -> List:
    """Mock method definition for IBMBackendService._restore_circuit_job()"""
    if raise_error or legacy:
        pass  # Parameter is passed by unused in this mock
    return [job_info]
