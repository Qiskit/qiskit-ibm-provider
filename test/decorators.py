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

"""Decorators used by unit tests."""

import os
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Optional

from qiskit_ibm_provider import IBMProvider
from .unit.mock.fake_provider import FakeProvider


def run_fake_provider(func):
    """Decorator that runs a test using a fake provider."""

    @wraps(func)
    def _wrapper(self, *args, **kwargs):
        fake_provider = FakeProvider(token="my_token", instance="h/g/p")
        for provider in [fake_provider]:
            with self.subTest(provider=provider):
                kwargs["provider"] = provider
                func(self, *args, **kwargs)

    return _wrapper


def _get_integration_test_config():
    token, url, instance = (
        os.getenv("QISKIT_IBM_TOKEN"),
        os.getenv("QISKIT_IBM_URL"),
        os.getenv("QISKIT_IBM_INSTANCE"),
    )
    return token, url, instance


def run_integration_test(func):
    """Decorator that injects preinitialized service and device parameters.

    To be used in combinatino with the integration_test_setup decorator function."""

    @wraps(func)
    def _wrapper(self, *args, **kwargs):
        with self.subTest(service=self.dependencies.service):
            if self.dependencies.service:
                kwargs["service"] = self.dependencies.service
            func(self, *args, **kwargs)

    return _wrapper


def integration_test_setup(
    init_service: Optional[bool] = True,
) -> Callable:
    """Returns a decorator for integration test initialization.

    Args:
        init_service: to initialize the IBMRuntimeService based on the current environment
            configuration and return it via the test dependencies

    Returns:
        A decorator that handles initialization of integration test dependencies.
    """

    def _decorator(func):
        @wraps(func)
        def _wrapper(self, *args, **kwargs):
            token, url, instance = _get_integration_test_config()
            if not all([token, url]):
                raise Exception("Configuration Issue. Token and URL must be set.")

            service = None
            if init_service:
                service = IBMProvider(token=token, url=url, instance=instance)
            dependencies = IntegrationTestDependencies(
                token=token,
                url=url,
                instance=instance,
                provider=service,
            )
            kwargs["dependencies"] = dependencies
            func(self, *args, **kwargs)

        return _wrapper

    return _decorator


@dataclass
class IntegrationTestDependencies:
    """Integration test dependencies."""

    provider: IBMProvider
    instance: Optional[str]
    token: str
    url: str
