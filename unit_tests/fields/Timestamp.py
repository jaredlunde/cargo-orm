#!/usr/bin/python3 -S
# -*- coding: utf-8 -*-
import sys
import unittest
import datetime
from dateutil import tz

import arrow
from docr import Docr
from bloom import *
from bloom.fields import Timestamp

from unit_tests.fields.Time import *


class TestTimestamp(TestTime):

    def test_descriptors(self):
        self.base('October 31, 1984 at 11:17am')
        d = Docr('bloom.Timestamp')
        for attr, obj in d.data_descriptors.items():
            pass

    def test_real_value(self):
        self.base('October 31, 1941 at 11:17am')
        self.assertIsInstance(self.base.value, arrow.Arrow)


if __name__ == '__main__':
    # Unit test
    unittest.main()
