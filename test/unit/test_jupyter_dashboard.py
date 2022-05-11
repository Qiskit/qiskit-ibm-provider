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

from unittest import mock

# import ipywidgets as wid
from qiskit.test.mock import FakeBackendV2 as FakeBackend
from qiskit.test.mock.backends.bogota.fake_bogota import FakeBogota

# from qiskit_ibm_provider.jupyter.dashboard.utils import BackendWithProviders
from qiskit_ibm_provider.ibm_backend import IBMBackend
from qiskit_ibm_provider.jupyter.dashboard import dashboard
from qiskit_ibm_provider.jupyter.live_data_widget import LiveDataVisualization, LivePlot
from qiskit_ibm_provider.visualization.interactive.gate_map import iplot_gate_map
from qiskit_ibm_provider.visualization.interactive.plotly_wrapper import (
    PlotlyFigure,
    PlotlyWidget,
)

# from qiskit_ibm_provider.jupyter.gates_widget import gates_tab
from .test_ibm_job_states import BaseFakeAPI

# from ..unit.mock.fake_provider import FakeProvider
# from ..fake_account_client import BaseFakeAccountClient
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

    def test_gate_map(self):
        """Test creating a gate map."""
        backend = IBMBackend(
            FakeBogota().configuration(), mock.Mock(), api_client=BaseFakeAPI()
        )
        gate_map = iplot_gate_map(backend)
        gate_map_widget = iplot_gate_map(backend, as_widget=True)
        self.assertTrue(gate_map)
        self.assertIsInstance(gate_map, PlotlyFigure)
        self.assertIsInstance(gate_map_widget, PlotlyWidget)
