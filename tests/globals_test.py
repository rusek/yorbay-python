#!/usr/bin/env python

import platform
import os
import sys
import time
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.globals import HourGlobal, OsGlobal


class TestHour(unittest.TestCase):
    def test_hour_uses_local_time(self):
        while True:
            hour_before = time.localtime().tm_hour
            val = HourGlobal().get()
            hour_after = time.localtime().tm_hour
            if hour_before == hour_after:
                self.assertEqual(val, hour_before)
                break


class TestOs(unittest.TestCase):
    def test_linux_platform(self):
        self.assertEqual(self.get(mocked_system='Linux'), 'linux')

    def test_mac_platform(self):
        self.assertEqual(self.get(mocked_system='Darwin'), 'mac')

    def test_windows_platform(self):
        for system in ('Windows', 'CYGWIN_NT-5.1', 'CYGWIN_NT-6.2-WOW64'):
            self.assertEqual(self.get(mocked_system=system), 'win')

    def test_unknown_platform(self):
        for system in ('Java', ''):
            self.assertEqual(self.get(mocked_system=system), 'unknown')

    def get(self, mocked_system):
        system = platform.system
        platform.system = lambda: mocked_system
        try:
            return OsGlobal().get()
        finally:
            platform.system = system


if __name__ == '__main__':
    unittest.main()
