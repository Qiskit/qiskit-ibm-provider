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

from qiskit.test.mock import FakeBackendV2 as FakeBackend
from qiskit.test.mock.backends.bogota.fake_bogota import FakeBogota

from qiskit_ibm_provider.ibm_backend import IBMBackend
from qiskit_ibm_provider.jupyter.live_data_widget import (
    LiveDataVisualization,
    LivePlot,
    ProgressBar,
)
from qiskit_ibm_provider.visualization.interactive.gate_map import iplot_gate_map
from qiskit_ibm_provider.visualization.interactive.plotly_wrapper import (
    PlotlyFigure,
    PlotlyWidget,
)

from .test_ibm_job_states import BaseFakeAPI
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


class TestProgressBar(IBMTestCase):
    """Test Progress Bar."""

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        self.progress_bar = ProgressBar()

    def test_update_progress_bar(self):
        """Test updating a progress bar."""
        progress_bar = self.progress_bar
        progress_bar.get_widget()
        progress_bar.update_progress_bar(_max=20, _value=5, _min=1)
        self.assertIs(progress_bar._progress_bar.max, 20)
        self.assertIs(progress_bar._progress_bar.value, 5)
        self.assertIs(progress_bar._progress_bar.min, 1)

    def test_reset_progress_bar(self):
        """Test reseting a progress bar."""
        progress_bar = self.progress_bar
        progress_bar.get_widget()
        progress_bar.update_progress_bar(_max=30, _value=20)
        self.assertIs(progress_bar._progress_bar.value, 20)
        progress_bar.reset_progress_bar()
        self.assertIs(progress_bar._progress_bar.value, 0)

    def test_complete_progress_bar(self):
        """Test completing a progress bar."""
        progress_bar = self.progress_bar
        progress_bar.get_widget()
        self.assertIs(progress_bar._progress_bar.value, 0)
        progress_bar.complete_progress_bar()
        self.assertIs(progress_bar._progress_bar.value, 10)


class TestLivePlot(IBMTestCase):
    """Test Live Plot."""

    def setUp(self):
        """Initial test setup."""
        super().setUp()
        self.plot = LivePlot((1, 1))

    def test_live_plot(self):
        """Test initializing live plot."""
        self.assertTrue(self.plot)
        self.assertEqual(self.plot.get_plotview_height(), 360)

    def test_live_plot_widget(self):
        """Test creating an area widget."""
        widget = self.plot.widget()
        self.assertIs(self.plot.view, widget)

    def test_show_widget(self):
        """Test showing widget."""
        self.plot.widget()
        self.plot.show()
        self.assertIs(self.plot.view.layout.visibility, "visible")

    def test_hide_widget(self):
        """Test hiding widget."""
        self.plot.widget()
        self.plot.hide()
        self.assertIs(self.plot.view.layout.visibility, "hidden")

    def test_clear_plot(self):
        """Test hiding widget."""
        self.plot.fig = 1
        self.plot.clear()
        self.assertIs(self.plot.fig, None)


class TestJupyterDashboard(IBMTestCase):
    """Test Jupyter Dashboard."""

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
