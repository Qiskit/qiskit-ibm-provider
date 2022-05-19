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

"""Test Util Converters."""

from datetime import datetime
import pytz
from qiskit_ibm_provider.utils import converters
from ..ibm_test_case import IBMTestCase


class TestConverters(IBMTestCase):
    """Test util converter methods."""

    def test_utc_to_local(self):
        """Test utc to local method."""
        datetime_object = datetime.now(pytz.utc)
        utc_time = converters.local_to_utc(datetime_object)
        self.assertEqual(datetime_object, converters.utc_to_local(utc_time))

    def test_local_to_utc(self):
        """Test local to utc method."""
        datetime_object = datetime.now(pytz.utc)
        local_time = converters.utc_to_local(datetime_object)
        self.assertEqual(datetime_object, converters.local_to_utc(local_time))

    def test_local_to_utc_str(self):
        """Test local to utc string method."""
        datetime_object = datetime.now(pytz.utc)
        self.assertIsInstance(converters.local_to_utc_str(datetime_object), str)

    def test_str_to_utc(self):
        """Test str to utc method."""
        utc_string = "2022-05-19T02:13:46.168259Z"
        utc_datetime = converters.str_to_utc(utc_string)
        self.assertIsInstance(utc_datetime, datetime)

    def test_seconds_to_duration(self):
        """Test seconds to duration method."""
        self.assertEqual(converters.seconds_to_duration(1000), (0, 0, 16, 40, 0))

    def test_duration_difference(self):
        """Test duration difference method."""
        utc_date = datetime.now(pytz.utc)
        non_utc_date = datetime.now()
        self.assertIsInstance(converters.duration_difference(utc_date), str)
        self.assertIsInstance(converters.duration_difference(non_utc_date), str)

    def test_convert_tz(self):
        """Test convert tz method."""
        datetime_object = datetime.now(pytz.utc)
        utc_time = converters.local_to_utc(datetime_object)
        self.assertEqual(datetime_object, converters.convert_tz(utc_time, True))

    def test_utc_to_local_all(self):
        """Test utc to local all method."""
        date_list = converters.utc_to_local_all(
            [datetime(2022, 5, 10), datetime(2022, 5, 11)]
        )
        self.assertIsInstance(date_list[0], datetime)
        self.assertIsInstance(date_list[1], datetime)
