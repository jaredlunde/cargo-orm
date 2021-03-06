#!/usr/bin/python3 -S
# -*- coding: utf-8 -*-
from cargo.fields import Bool

from unit_tests.fields.Field import TestField
from unit_tests import configure


class TestBool(configure.BooleanTestCase, TestField):

    @property
    def base(self):
        return self.orm.boolean

    def test_validate(self):
        a = Bool()
        self.assertTrue(a.validate())
        a = Bool(not_null=True)
        self.assertFalse(a.validate())
        a(True)
        self.assertTrue(a.validate())
        a(False)
        self.assertTrue(a.validate())
        a(None)
        self.assertFalse(a.validate())

    def test___call__(self):
        a = Bool()
        self.assertIs(a(), a.empty)
        a(True)
        self.assertTrue(a())
        a(False)
        self.assertFalse(a())
        a(1)
        self.assertTrue(a())
        a(0)
        self.assertFalse(a())
        a('0')
        self.assertTrue(a())

    def test_insert(self):
        self.base(True)
        self.orm.insert(self.base)
        self.base(False)
        self.orm.insert(self.base)
        self.base(None)
        self.orm.insert(self.base)

    def test_select(self):
        self.base(True)
        self.orm.insert(self.base)
        self.assertEqual(self.orm.new().desc(self.orm.uid).get().boolean.value,
                         True)
        self.base(False)
        self.orm.naked().insert(self.base)
        self.assertEqual(self.orm.new().desc(self.orm.uid).get().boolean.value,
                         False)
        self.base(None)
        self.orm.insert(self.base)
        self.assertEqual(self.orm.new().desc(self.orm.uid).get().boolean.value,
                         None)

    def test_array_insert(self):
        arr = [True, True, False]
        self.base_array(arr)
        val = getattr(self.orm.naked().insert(self.base_array),
                      self.base_array.field_name)
        self.assertListEqual(val, arr)

    def test_array_select(self):
        arr = [True, True, False]
        self.base_array(arr)
        val = getattr(self.orm.naked().insert(self.base_array),
                      self.base_array.field_name)
        val_b = getattr(self.orm.naked().desc(self.orm.uid).get(),
                        self.base_array.field_name)
        self.assertListEqual(val, val_b)

    def test_type_name(self):
        self.assertEqual(self.base.type_name, 'boolean')
        self.assertEqual(self.base_array.type_name, 'boolean[]')


if __name__ == '__main__':
    # Unit test
    configure.run_tests(TestBool, failfast=True, verbosity=2)
