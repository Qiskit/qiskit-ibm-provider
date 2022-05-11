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
from qiskit_ibm_provider.jupyter.live_data_widget import LiveDataVisualization, LivePlot

from ..ibm_test_case import IBMTestCase


class TestLiveDataVisualization(IBMTestCase):
    """Test Live Data Jupyter widget."""

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        self.backend = FakeBackend()
        self.livedata = LiveDataVisualization()

    def test_creating_visualization(self):
        """Test create_visualization method."""
        title = "example title"
        html_title = self.livedata.create_title("example title")
        visualization = self.livedata.create_visualization(
            self.backend, figsize=(11, 9), show_title=False
        )
        self.assertIn(title, str(html_title))
        self.assertTrue(visualization)


class TestLivePlot(IBMTestCase):
    """Test Live Plot"""

    def test_live_plot(self):
        """Test initializing live plot."""
        plot = LivePlot((1, 1))
        self.assertTrue(plot)
        self.assertEqual(plot.get_plotview_height(), 360)
