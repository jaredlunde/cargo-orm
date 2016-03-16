#!/usr/bin/python3 -S
# -*- coding: utf-8 -*-
"""
    `Unit tests for bloom.builder.create_user`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   2016 Jared Lunde © The MIT License (MIT)
   http://github.com/jaredlunde
"""
import unittest

from kola import config
from bloom import ORM, db, create_kola_db
from bloom.builder import create_user, create_role


cfile = '/home/jared/apps/xfaps/vital.json'
config.bind(cfile)
create_kola_db()


class TestCreateRole(unittest.TestCase):
    orm = ORM()

    def test_create(self):
        print(db.select(1, 2, 3, 4, 5, 6, 7, 8, 9, 10))
        u = create_user(self.orm, 'foo', 'login', 'superuser', 'createrole',
                        'createuser', 'createdb', dry=True)
        u.password('fishtaco')
        u.in_role('cream', 'based', 'sauce')
        u.connlimit(1000)
        print(u.query.mogrified)


if __name__ == '__main__':
    # Unit test
    unittest.main()