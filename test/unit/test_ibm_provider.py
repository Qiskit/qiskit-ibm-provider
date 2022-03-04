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

"""Tests for the IBMProvider class."""

import os
from configparser import ConfigParser
from unittest import skipIf

from qiskit_ibm_provider.apiconstants import QISKIT_IBM_API_URL
from qiskit_ibm_provider.credentials.hub_group_project_id import HubGroupProjectID
from qiskit_ibm_provider.exceptions import (
    IBMProviderError,
    IBMProviderValueError,
    IBMProviderCredentialsInvalidUrl,
    IBMProviderCredentialsInvalidToken,
    IBMProviderCredentialsNotFound,
)
from qiskit_ibm_provider.ibm_provider import IBMProvider
from ..contextmanagers import custom_qiskitrc, no_envs, CREDENTIAL_ENV_VARS
from ..ibm_test_case import IBMTestCase

API_URL = "https://api.quantum-computing.ibm.com/api"
AUTH_URL = "https://auth.quantum-computing.ibm.com/api"


class TestIBMProviderEnableAccount(IBMTestCase):
    """Tests for IBMProvider."""

    # Enable Account Tests

    def test_provider_init_non_auth_url(self):
        """Test initializing IBMProvider with a non-auth URL."""
        qe_token = "invalid"
        qe_url = API_URL

        with self.assertRaises(IBMProviderCredentialsInvalidUrl) as context_manager:
            IBMProvider(token=qe_token, url=qe_url)

        self.assertIn("authentication URL", str(context_manager.exception))

    def test_provider_init_non_auth_url_with_hub(self):
        """Test initializing IBMProvider with a non-auth URL containing h/g/p."""
        qe_token = "invalid"
        qe_url = API_URL + "/Hubs/X/Groups/Y/Projects/Z"

        with self.assertRaises(IBMProviderCredentialsInvalidUrl) as context_manager:
            IBMProvider(token=qe_token, url=qe_url)

        self.assertIn("authentication URL", str(context_manager.exception))

    def test_provider_init_no_credentials(self):
        """Test initializing IBMProvider with no credentials."""
        with custom_qiskitrc(), self.assertRaises(
            IBMProviderCredentialsNotFound
        ) as context_manager, no_envs(CREDENTIAL_ENV_VARS):
            IBMProvider()

        self.assertIn(
            "No IBM Quantum credentials found.", str(context_manager.exception)
        )


@skipIf(os.name == "nt", "Test not supported in Windows")
class TestIBMProviderAccounts(IBMTestCase):
    """Tests for account handling."""

    @classmethod
    def setUpClass(cls):
        """Initial class setup."""
        super().setUpClass()
        cls.token = "API_TOKEN"

    def test_save_account(self):
        """Test saving an account."""
        with custom_qiskitrc():
            IBMProvider.save_account(self.token, url=QISKIT_IBM_API_URL)
            stored_cred = IBMProvider.saved_account()

        self.assertEqual(stored_cred["token"], self.token)
        self.assertEqual(stored_cred["url"], QISKIT_IBM_API_URL)

    def test_save_account_specified_provider(self):
        """Test saving an account with a specified hub/group/project."""
        default_hgp_to_save = "ibm-q/open/main"

        with custom_qiskitrc() as custom_qiskitrc_cm:
            hgp_id = HubGroupProjectID.from_stored_format(default_hgp_to_save)
            IBMProvider.save_account(
                token=self.token,
                url=QISKIT_IBM_API_URL,
                hub=hgp_id.hub,
                group=hgp_id.group,
                project=hgp_id.project,
            )

            # Ensure the `default_provider` name was written to the config file.
            config_parser = ConfigParser()
            config_parser.read(custom_qiskitrc_cm.tmp_file.name)

            for name in config_parser.sections():
                single_credentials = dict(config_parser.items(name))
                self.assertIn("default_provider", single_credentials)
                self.assertEqual(
                    single_credentials["default_provider"], default_hgp_to_save
                )

    def test_save_account_specified_provider_invalid(self):
        """Test saving an account without specifying all the hub/group/project fields."""
        invalid_hgp_ids_to_save = [
            HubGroupProjectID("", "default_group", ""),
            HubGroupProjectID("default_hub", None, "default_project"),
        ]
        for invalid_hgp_id in invalid_hgp_ids_to_save:
            with self.subTest(invalid_hgp_id=invalid_hgp_id), custom_qiskitrc():
                with self.assertRaises(IBMProviderValueError) as context_manager:
                    IBMProvider.save_account(
                        token=self.token,
                        url=QISKIT_IBM_API_URL,
                        hub=invalid_hgp_id.hub,
                        group=invalid_hgp_id.group,
                        project=invalid_hgp_id.project,
                    )
                self.assertIn(
                    "The hub, group, and project parameters must all be specified",
                    str(context_manager.exception),
                )

    def test_delete_account(self):
        """Test deleting an account."""
        with custom_qiskitrc():
            IBMProvider.save_account(self.token, url=QISKIT_IBM_API_URL)
            IBMProvider.delete_account()
            stored_cred = IBMProvider.saved_account()

        self.assertEqual(len(stored_cred), 0)

    def test_load_saved_account_invalid_hgp_format(self):
        """Test loading an account that contains a saved provider in an invalid format."""
        # Format {'test_case_input': 'error message from raised exception'}
        invalid_hgps = {
            "hub_group_project": 'Use the "<hub_name>/<group_name>/<project_name>" format',
            "default_hub//default_project": "Every field must be specified",
            "default_hub/default_group/": "Every field must be specified",
        }

        for invalid_hgp, error_message in invalid_hgps.items():
            with self.subTest(invalid_hgp=invalid_hgp):
                with custom_qiskitrc() as temp_qiskitrc, no_envs(CREDENTIAL_ENV_VARS):
                    # Save the account.
                    IBMProvider.save_account(token=self.token, url=QISKIT_IBM_API_URL)
                    # Add an invalid provider field to the account stored.
                    with open(
                        temp_qiskitrc.tmp_file.name, "a", encoding="utf-8"
                    ) as _file:
                        _file.write("default_provider = {}".format(invalid_hgp))
                    # Ensure an error is raised if the stored provider is in an invalid format.
                    with self.assertRaises(IBMProviderError) as context_manager:
                        IBMProvider()
                    self.assertIn(error_message, str(context_manager.exception))

    def test_save_token_invalid(self):
        """Test saving an account with invalid tokens. See #391."""
        invalid_tokens = [None, "", 0]
        for invalid_token in invalid_tokens:
            with self.subTest(invalid_token=invalid_token):
                with self.assertRaises(
                    IBMProviderCredentialsInvalidToken
                ) as context_manager:
                    IBMProvider.save_account(
                        token=invalid_token, url=QISKIT_IBM_API_URL
                    )
                self.assertIn(
                    "Invalid IBM Quantum token found", str(context_manager.exception)
                )
