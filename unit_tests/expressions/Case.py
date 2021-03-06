#!/usr/bin/python3 -S
# -*- coding: utf-8 -*-
"""
    `Unit tests for cargo.expressions.Case`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   2016 Jared Lunde © The MIT License (MIT)
   http://github.com/jaredlunde
"""
import unittest
from cargo import fields, ORM, safe
from cargo.expressions import Case

from unit_tests import configure
from unit_tests.configure import new_field


class TestCase(unittest.TestCase):

    def test_el(self):
        fielda = new_field(table='foo', name='bar')
        case = Case(fielda == 1, 'one', fielda == 2, 'two', el='three')

        caseb = Case()
        caseb.when(fielda == 1, 'one')
        caseb.when(fielda == 2, 'two')
        caseb.el('four')
        caseb.el('three')

        self.assertEqual(case.string % case.params,
                         'CASE WHEN foo.bar = 1 THEN one WHEN foo.bar = 2 ' +
                         'THEN two ELSE three END')
        self.assertEqual(case.string % case.params,
                         caseb.string % caseb.params)

    def test_alias(self):
        fielda = new_field(table='foo', name='bar')
        case = Case(fielda == 1, 'one', fielda == 2, 'two', el='three',
                    alias='foo_alias')

        self.assertEqual(case.string % case.params,
                         'CASE WHEN foo.bar = 1 THEN one WHEN foo.bar = 2 ' +
                         'THEN two ELSE three END foo_alias')

    def test_when(self):
        fielda = new_field(table='foo', name='bar')
        case = Case(fielda == 1, 'one', fielda == 2, 'two')

        caseb = Case()
        caseb.when(fielda == 1, 'one', fielda == 2, 'two')

        casec = Case()
        casec.when(fielda == 1, 'one')
        casec.when(fielda == 2, 'two')

        self.assertEqual(case.string % case.params,
                         'CASE WHEN foo.bar = 1 THEN one WHEN foo.bar = 2 ' +
                         'THEN two END')
        self.assertEqual(case.string % case.params,
                         caseb.string % caseb.params,
                         casec.string % casec.params)

    def test_use_field_name(self):
        fielda = new_field(table='foo', name='bar')
        case = Case(fielda == 1, 'one', fielda == 2, 'two',
                    use_field_name=True)

        caseb = Case(use_field_name=True)
        caseb.when(fielda == 1, 'one', fielda == 2, 'two')

        casec = Case(use_field_name=True)
        casec.when(fielda == 1, 'one')
        casec.when(fielda == 2, 'two')

        self.assertEqual(case.string % case.params,
                         'CASE WHEN bar = 1 THEN one WHEN bar = 2 ' +
                         'THEN two END')
        self.assertEqual(case.string % case.params,
                         caseb.string % caseb.params,
                         casec.string % casec.params)

    def test_select(self):
        orm = ORM()
        q = orm.select(Case(safe('1=1'), 'one',
                            safe('1=2'), 'two',
                            el='three', alias="foo"))
        self.assertIsInstance(q, list)
        self.assertEqual(q[0].foo, 'one')

        q = orm.select(Case(safe('1=1'), 'one',
                            safe('1=2'), 'two',
                            el='three'))
        self.assertIsInstance(q, list)
        self.assertEqual(q[0].case, 'one')


if __name__ == '__main__':
    # Unit test
    configure.run_tests(TestCase, failfast=True, verbosity=2)
