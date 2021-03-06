"""

  `Cargo SQL Sequenced Fields`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   The MIT License (MIT) © 2015 Jared Lunde
   http://github.com/jaredlunde/cargo-orm

"""
import warnings
from vital.debug import preprX

import psycopg2._psycopg
from psycopg2.extensions import register_adapter, adapt, AsIs, string_types

from cargo.etc.types import *
from cargo.etc.translator.postgres import OID_map
from cargo.expressions import *
from cargo.fields.field import Field
from cargo.fields.character import Text
from cargo.logic import EnumLogic, ArrayLogic
from cargo.validators import ArrayValidator, EnumValidator



__all__ = ('Enum', 'OneOf', 'Array')



class OneOf(Field, EnumLogic):
    """ ======================================================================
        Field object for PostgreSQL enumerated types.

        Validates that a given value is in the specified group of enumerated
        types.

        ======================================================================
        ``Usage Example``
        ..
            one_of = OneOf('cat', 'dog', 'mouse')
            one_of('goat')
        ..
        |ValueError: `goat` not in ('cat', 'dog', 'mouse')|
    """
    __slots__ = ('field_name', 'primary', 'unique', 'index', 'not_null',
                 'value', 'validator', '_alias', 'default', 'types', 'table',
                 '_type_name', '_type_oid', '_type_array_oid')
    OID = ENUM

    def __init__(self, *types, type_name=None, validator=EnumValidator,
                 **kwargs):
        """`OneOf`
            ==================================================================
            @*types: one or several enumerated types to choose from
            @type_name: (#str) name of the type within the db, if |None|,
                one will be autogenerated
            See [this postgres guide](http://postgresguide.com/sexy/enums.html)
            for more valuable information.
            ==================================================================
            :see::meth:Field.__init__
        """
        if not len(types):
            raise TypeError('Must include one or more `types`. '
                            'See http://docs.cargo-orm.com/OneOf')
        self.types = types
        self._type_name = type_name
        self._type_oid = None
        self._type_array_oid = None
        super().__init__(validator=validator, **kwargs)

    __repr__ = preprX('types', 'name', 'value', keyless=True)

    def __call__(self, value=Field.empty):
        if value is not Field.empty:
            if value is None or value in self.types:
                self.value = value
            else:
                raise ValueError("`{}` not in {}".format(value, self.types))
        return self.value

    def _register_oid(self, db):
        if self._type_oid is None and self._type_array_oid is None:
            OIDs = db.get_type_OID(self.type_name)
            self._type_oid, self._type_array_oid = OIDs

    def register_type(self, db):
        try:
            self._register_oid(db)
            ENUMTYPE = reg_type(self.type_name.upper(),
                                self._type_oid,
                                psycopg2.STRING)
            reg_array_type(self.type_name.upper() + 'ARRAY',
                           self._type_array_oid,
                           ENUMTYPE)
        except ValueError:
            warnings.warn('Type `%s` not found in the database.' %
                          self.type_name)

    @property
    def type_name(self):
        tname = self._type_name or '%s_%s_enumtype' % (self.table or "",
                                                       self.field_name or "")
        return tname

    def index_of(self, type=None):
        return self.types.index(type or self.value)

    def clear_copy(self, **kwargs):
        cls = Field.clear_copy(self, *self.types, type_name=self._type_name, **kwargs)
        cls._type_oid = self._type_oid
        cls._type_array_oid = self._type_array_oid
        return cls


Enum = OneOf


class _ListAdapter(object):
    def __init__(self, value, type=None):
        self.value = value
        try:
            self.type = value.__cargotype__
        except AttributeError:
            self.value = None

    def prepare(self, conn):
        self.conn = conn

    def getquoted(self):
        if not len(self.value) or not self.type:
            adapter = psycopg2._psycopg.List(self.value)
            adapter.prepare(self.conn)
            return adapter.getquoted()
        else:
            adapter = psycopg2._psycopg.List(self.value)
            adapter.prepare(self.conn)
            return b"%s::%s[]" % (adapter.getquoted(),
                                  self.type.encode())


class arraylist(list):
    pass


class Array(Field, ArrayLogic):
    """ ======================================================================
        Field object for the PostgreSQL field type |ARRAY|.
        The values passed to this object must be iterable.

        It can be manipulated similar to a python list.
    """
    __slots__ = ('primary', 'unique', 'index', 'not_null', 'value',
                 'validator', '_alias', 'default', 'minlen', 'maxlen',
                 'type', 'dimensions')
    OID = ARRAY

    def __init__(self, type=None, dimensions=1, minlen=0, maxlen=-1,
                 validator=ArrayValidator, **kwargs):
        """`Array`
            ==================================================================
            @type: (initialized :class:Field) the data type represented by
                this array, defaults to :class:Text
            @dimensions: (#int) number of array dimensions or depth assigned
                to the field
            ==================================================================
            :see::meth:Field.__init__
        """
        self.minlen = minlen
        self.maxlen = maxlen
        self.type = type.copy() if type is not None else Text()
        self.dimensions = dimensions
        super().__init__(validator=validator, **kwargs)

    __repr__ = preprX('type.__class__.__name__', 'name', 'value', keyless=True)

    def __call__(self, value=Field.empty):
        if value is not Field.empty:
            self.value = self._cast(value) if value is not None else None
        return self.value

    @property
    def field_name(self):
        return self.type.field_name

    @property
    def type_name(self):
        return self._get_type_name() + '[]'

    @field_name.setter
    def field_name(self, value):
        self.type.field_name = value

    @property
    def table(self):
        return self.type.table

    @table.setter
    def table(self, value):
        self.type.table = value

    def __getitem__(self, index):
        """ -> the item at @index """
        return self.value[index]

    def __setitem__(self, index, value):
        """ Sets the item at @index to @value """
        self._make_list()
        self.value[index] = self._select_cast(value)

    def __delitem__(self, index):
        """ Deletes the item at @index """
        del self.value[index]

    def __contains__(self, value):
        """ Checks if @value is in the local array data """
        return self._select_cast(value) in self.value

    def __iter__(self):
        return iter(self.value)

    def __reversed__(self):
        return reversed(self.value)

    def _make_list(self):
        if self.value_is_null:
            self.value = self._add_arr_type(arraylist())

    def _get_type_name(self):
        try:
            return self.type.type_name
        except AttributeError:
            return OID_map[self.type.OID]

    def _add_arr_type(self, arr):
        arr.__cargotype__ = self._get_type_name()
        return arr

    def _cast(self, value, dimension=1):
        """ Casts @value to its correct type, e.g. #int or #str """
        if self.dimensions and dimension > self.dimensions:
            raise ValueError('Invalid dimensions ({}): max depth is set to {}'
                             .format(dimension, repr(self.dimensions)))

        next_dimension = dimension + 1
        arr = (self.type(x) if not isinstance(x, list) else
               self._cast(x, next_dimension)
               for x in value)

        if dimension > 1:
            return list(arr)
        else:
            return self._add_arr_type(arraylist(arr))

    def _select_cast(self, value, dimension=1):
        return self.type(value)\
               if not isinstance(value, (list, tuple)) else\
               self._cast(value, dimension=dimension)

    def append(self, value):
        """ Appends @value to the array """
        self._make_list()
        self.value.append(self._select_cast(value, dimension=2))

    def pop(self, index=0):
        """ Pops @index from the array """
        return self.value.pop(index)

    def insert(self, index, value):
        """ Inserts @value to the array at @index """
        self._make_list()
        self.value.insert(index, self._select_cast(value, dimension=2))

    def remove(self, value):
        """ Removes @value from the array """
        self.value.remove(value)

    def array_index(self, value):
        """ Finds the index of @value in the array """
        return self.value.index(value)

    def extend(self, value):
        """ Extends the array with @value """
        self._make_list()
        self.value.extend(self._select_cast(value))

    def reverse(self):
        """ Reverses the array in place """
        self.value.reverse()

    def sort(self, key=None, reverse=False):
        """ Sorts the array in place """
        self.value.sort(key=key, reverse=reverse)

    def _to_fields(self, value):
        """ Wraps the values in the array with :prop:type """
        fields = []
        add_field = fields.append
        for val in value:
            if not isinstance(val, list):
                field = self.type.copy()
                field(val)
                add_field(field)
            else:
                more_fields = []
                add_more_fields = more_fields.append
                for field in self._to_fields(val):
                    add_more_fields(field)
                add_field(more_fields)
        return fields

    def to_fields(self):
        return self._to_fields(self.value)

    def _recurse_for_json(self, field):
        if isinstance(field, list):
            return [self._recurse_for_json(f) for f in field]
        else:
            return field.for_json()

    def for_json(self):
        """:see::meth:Field.for_json"""
        if self.value_is_not_null:
            return [self._recurse_for_json(field) for field in self.to_fields()]
        return None

    def clear(self):
        self.value = self.empty
        self.type.clear()

    def register_adapter(self):
        register_adapter(arraylist, _ListAdapter)
        try:
            self.type.register_adapter()
        except AttributeError:
            pass

    def register_type(self, db):
        try:
            self.type.register_type(db)
        except AttributeError:
            pass

    def clear_copy(self, *args, **kwargs):
        return Field.clear_copy(self,
                                *args,
                                type=self.type.copy(),
                                dimensions=self.dimensions,
                                minlen=self.minlen,
                                maxlen=self.maxlen,
                                **kwargs)
