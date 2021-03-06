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

from cargo import ORM, db, fields
from cargo.builder import create_operator
from cargo.builder.operators import Operator


def new_field(type='char', value=None, name=None, table=None):
    field = getattr(fields, type.title())(value=value)
    field.field_name = name or randkey(24)
    field.table = table or randkey(24)
    return field


class TestCreateOperator(unittest.TestCase):
    orm = ORM()

    def test_create(self):
        operator = create_operator(self.orm, '''~+~''', 'int8', dry=True)
        print(operator.query.mogrified)
        operator = Operator(self.orm, '~-~', 'int8')
        operator.opts(LEFTARG='foo', rightarg='bar')
        operator.hashes()
        print(operator.query)
        print(operator.query.mogrified)


if __name__ == '__main__':
    # Unit test
    unittest.main()
