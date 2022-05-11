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

"""Test jupyter dashboard widgets."""

from qiskit.test.mock import FakeBackendV2 as FakeBackend
from qiskit_ibm_provider.jupyter.live_data_widget import LiveDataVisualization

from ..ibm_test_case import IBMTestCase


class TestLiveDataVisualization(IBMTestCase):
    """Test Live Data Jupyter widget."""

    def test_live_data(self):
        """Test LiveDataVisualization class."""
        livedata = LiveDataVisualization()
        title = "example title"
        html_title = livedata.create_title("example title")
        backend = FakeBackend()
        visualization = livedata.create_visualization(
            backend, figsize=(11, 9), show_title=False
        )
        self.assertIn(title, str(html_title))
        self.assertTrue(visualization)
