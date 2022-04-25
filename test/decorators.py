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

from qiskit_ibm_provider import IBMProvider, least_busy
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
    token, url, instance, instance_private = (
        os.getenv("QISKIT_IBM_TOKEN"),
        os.getenv("QISKIT_IBM_URL"),
        os.getenv("QISKIT_IBM_INSTANCE"),
        os.getenv("QISKIT_IBM_INSTANCE_PRIVATE"),
    )
    return token, url, instance, instance_private


def integration_test_setup_with_backend(
    backend_name: Optional[str] = None,
    simulator: Optional[bool] = True,
    min_num_qubits: Optional[int] = None,
) -> Callable:
    """Returns a decorator that retrieves the appropriate backend to use for testing.

    Either retrieves the backend via its name (if specified), or selects the least busy backend that
    matches all given filter criteria.

    Args:
        backend_name: The name of the backend.
        simulator: If set to True, the list of suitable backends is limited to simulators.
        min_num_qubits: Minimum number of qubits the backend has to have.

    Returns:
        Decorator that retrieves the appropriate backend to use for testing.
    """

    def _decorator(func):
        @wraps(func)
        @integration_test_setup()
        def _wrapper(self, *args, **kwargs):
            dependencies: IntegrationTestDependencies = kwargs["dependencies"]
            provider: IBMProvider = dependencies.provider
            if backend_name:
                _backend = provider.get_backend(
                    name=backend_name, instance=dependencies.instance
                )
            else:
                _backend = least_busy(
                    provider.backends(
                        simulator=simulator,
                        instance=dependencies.instance,
                        min_num_qubits=min_num_qubits,
                    )
                )
            if not _backend:
                raise Exception("Unable to find a suitable backend.")

            kwargs["backend"] = _backend
            func(self, *args, **kwargs)

        return _wrapper

    return _decorator


def integration_test_setup(
    init_provider: Optional[bool] = True,
) -> Callable:
    """Returns a decorator for integration test initialization.

    Args:
        init_provider: to initialize the IBMProvider based on the current environment
            configuration and return it via the test dependencies

    Returns:
        A decorator that handles initialization of integration test dependencies.
    """

    def _decorator(func):
        @wraps(func)
        def _wrapper(self, *args, **kwargs):
            token, url, instance, instance_private = _get_integration_test_config()
            if not all([token, url]):
                raise Exception("Configuration Issue. Token and URL must be set.")

            provider = None
            private_provider = None
            if init_provider:
                if instance:
                    provider = IBMProvider(token=token, url=url, instance=instance)
                if instance_private:
                    private_provider = IBMProvider(
                        token=token, url=url, instance=instance_private
                    )
            dependencies = IntegrationTestDependencies(
                token=token,
                url=url,
                instance=instance,
                instance_private=instance_private,
                provider=provider,
                private_provider=private_provider,
            )
            kwargs["dependencies"] = dependencies
            func(self, *args, **kwargs)

        return _wrapper

    return _decorator


@dataclass
class IntegrationTestDependencies:
    """Integration test dependencies."""

    provider: IBMProvider
    private_provider: IBMProvider
    instance: Optional[str]
    instance_private: Optional[str]
    token: str
    url: str

    def __getitem__(self, item):
        return getattr(self, item)
