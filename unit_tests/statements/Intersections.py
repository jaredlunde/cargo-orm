#!/usr/bin/python3 -S
# -*- coding: utf-8 -*-
"""
    `Unit tests for cargo.statements.SetOperations`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   2016 Jared Lunde © The MIT License (MIT)
   http://github.com/jaredlunde
"""
from cargo import *
from cargo.statements import SetOperations

from unit_tests import configure


class TestSetOperations(configure.StatementTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.orm.set_table('foo')
        self.orm.state.add_fields(safe('1 as foo, 2 as bar, 3 as foobar'))
        self.q1 = Select(self.orm)
        self.orm.reset()
        self.orm.state.add_fields(safe('1, 2, 5'))
        self.q2 = Select(self.orm)
        self.orm.reset()
        self.orm.state.add_fields(safe('2, 3, 4'))
        self.q3 = Select(self.orm)
        self.orm.reset()
        self.orm.state.add_fields(safe('4, 5, 6'))
        self.q4 = Select(self.orm)
        self.orm.reset()

    def test___init__(self):
        q = SetOperations(self.orm, self.q1, self.q2)
        self.assertIs(q.orm, self.orm)
        self.assertEqual(len(q.operations), 2)
        self.assertIn(self.q1, q.operations)
        self.assertIn(self.q2, q.operations)

    def test_union(self):
        q = self.q1
        for x in range(1, 6):
            q = q & self.q2
            self.assertEqual(q.query.count('UNION'), x)

    def test_union_all(self):
        q = self.q1
        for x in range(1, 6):
            q = q + self.q2
            self.assertEqual(q.query.count('UNION ALL'), x)

    def test_union_distinct(self):
        q = self.q1
        for x in range(1, 6):
            q = q - self.q2
            self.assertEqual(q.query.count('UNION DISTINCT'), x)

    def test_intersect(self):
        q = self.q1
        for x in range(1, 6):
            q = q > self.q2
            self.assertEqual(q.query.count('INTERSECT'), x)

    def test_intersect_all(self):
        q = self.q1
        for x in range(1, 6):
            q = q >= self.q2
            self.assertEqual(q.query.count('INTERSECT ALL'), x)

    def test_intersect_distinct(self):
        q = self.q1
        for x in range(1, 6):
            q = q >> self.q2
            self.assertEqual(q.query.count('INTERSECT DISTINCT'), x)

    def test_except_(self):
        q = self.q1
        for x in range(1, 6):
            q = q < self.q2
            self.assertEqual(q.query.count('EXCEPT'), x)

    def test_except_all(self):
        q = self.q1
        for x in range(1, 6):
            q = q <= self.q2
            self.assertEqual(q.query.count('EXCEPT ALL'), x)

    def test_except_distinct(self):
        q = self.q1
        for x in range(1, 6):
            q = q << self.q2
            self.assertEqual(q.query.count('EXCEPT DISTINCT'), x)

    def test_execute(self):
        q = self.q1 + self.q2
        res = q.execute().fetchall()
        self.assertEqual(len(res), 2)
        self.assertEqual(len(res[0]), 3)

    def test_compile(self):
        q = self.q1
        for x in range(1, 6):
            q = q & self.q2
            self.assertEqual(q.query.count('UNION'), x)
            self.assertIn(self.q1.query, q.query)
            self.assertEqual(q.query.count(self.q2.query.strip()), x)


if __name__ == '__main__':
    # Unit test
    configure.run_tests(TestSetOperations, failfast=True, verbosity=2)
