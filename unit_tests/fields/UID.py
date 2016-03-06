#!/usr/bin/python3 -S
# -*- coding: utf-8 -*-
from bloom import Function, safe
from bloom.fields import UID

from unit_tests.fields.BigInt import TestBigInt
from unit_tests import configure


class TestUID(configure.IdentifierTestCase, TestBigInt):
    orm = configure.UIDModel()

    @property
    def base(self):
        return self.orm.uid

    def test_init_(self):
        base = UID()
        self.assertEqual(base.value, base.empty)
        self.assertTrue(base.primary)
        self.assertIsNone(base.unique)
        self.assertIsNone(base.index)
        self.assertIsInstance(base.default, Function)
        self.assertIsNone(base.not_null)
        self.assertEqual(base.minval, 1)
        self.assertEqual(base.maxval, 9223372036854775807)

    def test___call__(self):
        for check in [2223372036854775807, '2223372036854775808']:
            self.base(check)
            self.assertEqual(self.base(), int(check))

    def test_value(self):
        self.base(10)
        self.assertIs(self.base.value, self.base.value)
        self.base.clear()
        self.assertIs(self.base.value, self.base.empty)
        self.base(None)
        self.assertIsNone(self.base.value)

    def test_insert(self):
        self.orm.insert(self.base)

    def test_select(self):
        self.orm.insert(self.base)
        self.assertEqual(
            getattr(self.orm.new().get(), self.base.field_name).value,
            self.base.value)


if __name__ == '__main__':
    # Unit test
    configure.run_tests(TestUID, verbosity=2, failfast=True)
