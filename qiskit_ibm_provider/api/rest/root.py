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

"""Root REST adapter."""

import logging
from typing import Dict, List, Any, Union, Optional
import json

from .base import RestAdapterBase
from .analysis_result import AnalysisResult

logger = logging.getLogger(__name__)


class Api(RestAdapterBase):
    """Rest adapter for general endpoints."""

    URL_MAP = {
        "login": "/users/loginWithToken",
        "user_info": "/users/me",
        "hubs": "/Network",
        "version": "/version",
        "bookings": "/Network/bookings/v2",
        "experiment_devices": "/devices",
        "analysis_results": "/analysis_results",
        "device_components": "/device_components",
    }

    def analysis_result(self, analysis_result_id: str) -> AnalysisResult:
        """Return an adapter for the analysis result.

        Args:
            analysis_result_id: UUID of the analysis result.

        Returns:
            The analysis result adapter.
        """
        return AnalysisResult(self.session, analysis_result_id)

    # Client functions.

    def hubs(self) -> List[Dict[str, Any]]:
        """Return the list of hub/group/project sets available to the user.

        Returns:
            JSON response.
        """
        url = self.get_url("hubs")
        return self.session.get(url).json()

    def version(self) -> Dict[str, Union[str, bool]]:
        """Return the version information.

        Returns:
            A dictionary with information about the API version,
            with the following keys:

                * ``new_api`` (bool): Whether the new API is being used

            And the following optional keys:

                * ``api-*`` (str): The versions of each individual API component
        """
        url = self.get_url("version")
        response = self.session.get(url)

        try:
            version_info = response.json()
            version_info["new_api"] = True
        except json.JSONDecodeError:
            return {"new_api": False, "api": response.text}

        return version_info

    def login(self, api_token: str) -> Dict[str, Any]:
        """Login with token.

        Args:
            api_token: API token.

        Returns:
            JSON response.
        """
        url = self.get_url("login")
        return self.session.post(url, json={"apiToken": api_token}).json()

    def user_info(self) -> Dict[str, Any]:
        """Return user information.

        Returns:
            JSON response of user information.
        """
        url = self.get_url("user_info")
        response = self.session.get(url).json()

        return response

    def reservations(self) -> List:
        """Return reservation information.

        Returns:
            JSON response.
        """
        url = self.get_url("bookings")
        return self.session.get(url).json()

    def analysis_results(
        self,
        limit: Optional[int],
        marker: Optional[str],
        backend_name: Optional[str] = None,
        device_components: Optional[Union[str, List[str]]] = None,
        experiment_uuid: Optional[str] = None,
        result_type: Optional[str] = None,
        quality: Optional[List[str]] = None,
        verified: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        created_at: Optional[List] = None,
        sort_by: Optional[str] = None,
    ) -> str:
        """Return all analysis results.

        Args:
            limit: Number of analysis results to retrieve.
            marker: Marker used to indicate where to start the next query.
            backend_name: Name of the backend.
            device_components: A list of device components used for filtering.
            experiment_uuid: Experiment UUID used for filtering.
            result_type: Analysis result type used for filtering.
            quality: Quality value used for filtering.
            verified: Indicates whether this result has been verified.
            tags: Filter by tags assigned to analysis results.
            created_at: A list of timestamps used to filter by creation time.
            sort_by: Indicates how the output should be sorted.

        Returns:
            Server response.
        """
        url = self.get_url("analysis_results")
        params = {}  # type: Dict[str, Any]
        if backend_name:
            params["device_name"] = backend_name
        if device_components:
            params["device_components"] = device_components
        if experiment_uuid:
            params["experiment_uuid"] = experiment_uuid
        if quality:
            params["quality"] = quality
        if result_type:
            params["type"] = result_type
        if limit:
            params["limit"] = limit
        if marker:
            params["marker"] = marker
        if verified is not None:
            params["verified"] = "true" if verified else "false"
        if tags:
            params["tags"] = tags
        if created_at:
            params["created_at"] = created_at
        if sort_by:
            params["sort"] = sort_by
        return self.session.get(url, params=params).text

    def analysis_result_upload(self, result: str) -> Dict:
        """Upload an analysis result.

        Args:
            result: The analysis result to upload.

        Returns:
            JSON response.
        """
        url = self.get_url("analysis_results")
        return self.session.post(
            url, data=result, headers=self._HEADER_JSON_CONTENT
        ).json()

    def device_components(self, backend_name: Optional[str] = None) -> Dict:
        """Return a list of device components for the backend.

        Args:
            backend_name: Name of the backend.

        Returns:
            JSON response.
        """
        params = {}
        if backend_name:
            params["device_name"] = backend_name
        url = self.get_url("device_components")
        return self.session.get(url, params=params).json()
