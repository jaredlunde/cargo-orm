#!/usr/bin/python3 -S
# -*- coding: utf-8 -*-
"""
    `Unit tests for cargo.builder.create_user`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   2016 Jared Lunde © The MIT License (MIT)
   http://github.com/jaredlunde
"""
import unittest
import psycopg2

from vital.security import randkey

from cargo import ORM, db, fields, safe
from cargo.builder import create_rule
from cargo.builder.rules import Rule


def new_field(type='char', value=None, name=None, table=None):
    field = getattr(fields, type.title())(value=value)
    field.field_name = name or randkey(24)
    field.table = table or randkey(24)
    return field


class TestCreateRule(unittest.TestCase):
    orm = ORM()

    def test_create(self):
        rule = create_rule(self.orm,
                           'dont_update',
                           'UPDATE',
                           'foo',
                           self.orm.dry().select(1),
                           dry=True)
        print(rule.query.mogrified)
        rule = Rule(self.orm,
                    'dont_update',
                    'UPDATE',
                    'foo',
                    self.orm.dry().select(1))
        rule.replace()
        rule.instead()
        rule.condition(safe('foo.bar').gt(5))
        print(rule.query)
        print(rule.query.mogrified)


if __name__ == '__main__':
    # Unit test
    unittest.main()
