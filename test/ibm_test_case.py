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

"""Custom TestCase for IBM Provider."""

import inspect
import logging
import os
import time
from typing import List, Any
from unittest import TestCase
from unittest.util import safe_repr
from qiskit import QuantumCircuit
from qiskit_ibm_provider import QISKIT_IBM_PROVIDER_LOGGER_NAME, IBMBackend, IBMJob
from qiskit_ibm_provider.apiconstants import ApiJobStatus, API_JOB_FINAL_STATES
from qiskit_ibm_provider.job.exceptions import IBMJobNotFoundError
from .utils import setup_test_logging
from .decorators import IntegrationTestDependencies


class IBMTestCase(TestCase):
    """Custom TestCase for use with qiskit-ibm-provider."""

    log: logging.Logger
    dependencies: IntegrationTestDependencies
    sim_backend: IBMBackend
    backend: IBMBackend
    bell: QuantumCircuit
    real_device_backend: IBMBackend
    sim_job: IBMJob

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.log = logging.getLogger(cls.__name__)
        filename = "%s.log" % os.path.splitext(inspect.getfile(cls))[0]
        setup_test_logging(cls.log, filename)
        cls._set_logging_level(logging.getLogger(QISKIT_IBM_PROVIDER_LOGGER_NAME))

    @classmethod
    def simple_job_callback(cls, job_id, job_status, job, **kwargs):
        """A callback function that logs current job status."""
        # pylint: disable=unused-argument
        queue_info = kwargs.get("queue_info", "unknown")
        cls.log.info(
            "Job %s status is %s, queue_info is %s", job_id, job_status, queue_info
        )

    @classmethod
    def _set_logging_level(cls, logger: logging.Logger) -> None:
        """Set logging level for the input logger.

        Args:
            logger: Logger whose level is to be set.
        """
        if logger.level is logging.NOTSET:
            try:
                logger.setLevel(cls.log.level)
            except Exception as ex:  # pylint: disable=broad-except
                logger.warning(
                    'Error while trying to set the level for the "%s" logger to %s. %s.',
                    logger,
                    os.getenv("LOG_LEVEL"),
                    str(ex),
                )
        if not any(
            isinstance(handler, logging.StreamHandler) for handler in logger.handlers
        ):
            logger.addHandler(logging.StreamHandler())
            logger.propagate = False

    def assert_dict_almost_equal(
        self, dict1, dict2, delta=None, msg=None, places=None, default_value=0
    ):
        """Assert two dictionaries with numeric values are almost equal.

        Fail if the two dictionaries are unequal as determined by
        comparing that the difference between values with the same key are
        not greater than delta (default 1e-8), or that difference rounded
        to the given number of decimal places is not zero. If a key in one
        dictionary is not in the other the default_value keyword argument
        will be used for the missing value (default 0). If the two objects
        compare equal then they will automatically compare almost equal.

        Args:
            dict1 (dict): a dictionary.
            dict2 (dict): a dictionary.
            delta (number): threshold for comparison (defaults to 1e-8).
            msg (str): return a custom message on failure.
            places (int): number of decimal places for comparison.
            default_value (number): default value for missing keys.

        Raises:
            TypeError: if the arguments are not valid (both `delta` and
                `places` are specified).
            AssertionError: if the dictionaries are not almost equal.
        """

        error_msg = self.dicts_almost_equal(dict1, dict2, delta, places, default_value)

        if error_msg:
            msg = self._formatMessage(msg, error_msg)
            raise self.failureException(msg)

    def dicts_almost_equal(
        self, dict1, dict2, delta=None, places=None, default_value=0
    ):
        """Test if two dictionaries with numeric values are almost equal.

        Fail if the two dictionaries are unequal as determined by
        comparing that the difference between values with the same key are
        not greater than delta (default 1e-8), or that difference rounded
        to the given number of decimal places is not zero. If a key in one
        dictionary is not in the other the default_value keyword argument
        will be used for the missing value (default 0). If the two objects
        compare equal then they will automatically compare almost equal.

        Args:
            dict1 (dict): a dictionary.
            dict2 (dict): a dictionary.
            delta (number): threshold for comparison (defaults to 1e-8).
            places (int): number of decimal places for comparison.
            default_value (number): default value for missing keys.

        Raises:
            TypeError: if the arguments are not valid (both `delta` and
                `places` are specified).

        Returns:
            String: Empty string if dictionaries are almost equal. A description
                of their difference if they are deemed not almost equal.
        """

        def valid_comparison(value):
            """compare value to delta, within places accuracy"""
            if places is not None:
                return round(value, places) == 0
            else:
                return value < delta

        # Check arguments.
        if dict1 == dict2:
            return ""
        if places is not None:
            if delta is not None:
                raise TypeError("specify delta or places not both")
            msg_suffix = " within %s places" % places
        else:
            delta = delta or 1e-8
            msg_suffix = " within %s delta" % delta

        # Compare all keys in both dicts, populating error_msg.
        error_msg = ""
        for key in set(dict1.keys()) | set(dict2.keys()):
            val1 = dict1.get(key, default_value)
            val2 = dict2.get(key, default_value)
            if not valid_comparison(abs(val1 - val2)):
                error_msg += (
                    f"({safe_repr(key)}: {safe_repr(val1)} != {safe_repr(val2)}), "
                )

        if error_msg:
            return error_msg[:-2] + msg_suffix
        else:
            return ""

    def setUp(self) -> None:
        """Test level setup."""
        super().setUp()
        # Record submitted jobs.
        self._jobs: List[Any] = []

    def tearDown(self) -> None:
        """Test level tear down."""
        super().tearDown()
        failed = False
        # It's surprisingly difficult to find out whether the test failed.
        # Using a private attribute is not ideal but it'll have to do.
        if self._outcome and hasattr(self._outcome, "errors"):  # type: ignore[attr-defined]
            for _, exc_info in self._outcome.errors:  # type: ignore[attr-defined]
                if exc_info is not None:
                    failed = True

        if not failed:
            for client, job_id in self._jobs:
                try:
                    job_status = client.job_get(job_id)["status"]
                    if ApiJobStatus(job_status) not in API_JOB_FINAL_STATES:
                        client.job_cancel(job_id)
                        time.sleep(1)
                    retry = 3
                    while retry > 0:
                        try:
                            client.job_delete(job_id)
                            time.sleep(1)
                            retry -= 1
                        except IBMJobNotFoundError:
                            retry = 0
                except Exception:  # pylint: disable=broad-except
                    pass
