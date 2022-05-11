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
from qiskit_ibm_provider.jupyter.dashboard import dashboard

from ..ibm_test_case import IBMTestCase


class TestLiveDataVisualization(IBMTestCase):
    """Test Live Data Jupyter widget."""

    def test_creating_visualization(self):
        """Test create_visualization method."""
        title = "example title"
        backend = FakeBackend()
        visualization = LiveDataVisualization()
        html_title = visualization.create_title("example title")
        visualization.create_visualization(backend, figsize=(11, 9), show_title=False)
        self.assertIn(title, str(html_title))
        self.assertTrue(visualization)


class TestLivePlot(IBMTestCase):
    """Test Live Plot."""

    def test_live_plot(self):
        """Test initializing live plot."""
        plot = LivePlot((1, 1))
        self.assertTrue(plot)
        self.assertEqual(plot.get_plotview_height(), 360)


class TestJupyterDashboard(IBMTestCase):
    """Test Jupyter Dashboard."""

    def test_creating_accordion(self):
        """Test creating a dashboard accordion."""
        widget = dashboard.build_dashboard_widget()
        self.assertIsInstance(widget, dashboard.AccordionWithThread)
