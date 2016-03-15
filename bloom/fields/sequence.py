"""

  `Bloom SQL Sequenced Fields`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   The MIT License (MIT) © 2015 Jared Lunde
   http://github.com/jaredlunde/bloom-orm

"""
import warnings
from vital.debug import prepr

import psycopg2._psycopg
from psycopg2.extensions import register_adapter, adapt, AsIs

from bloom.etc.types import *
from bloom.etc.translator.postgres import OID_map
from bloom.expressions import *
from bloom.fields.field import Field
from bloom.fields.character import Text
from bloom.validators import ArrayValidator, EnumValidator


__all__ = ('Enum', 'OneOf', 'Array', 'ArrayLogic')


class ArrayLogic(BaseLogic):
    __slots__ = tuple()

    def contains(self, array, **kwargs):
        """ Creates a |@>| SQL expression
            @array: (#list) or #tuple object

            -> SQL :class:Expression object
            ===================================================================

            ``Usage Example``
            ..
                condition = model.array_field.contains([1, 2])
                model.where(condition)
            ..
            |array_field @> [1,2]|
        """
        return Expression(self, "@>", array, **kwargs)

    def contained_by(self, array, **kwargs):
        """ Creates a |<@| SQL expression
            @array: (#list) or #tuple object

            -> SQL :class:Expression object
            ===================================================================

            ``Usage Example``
            ..
                condition = model.array_field.is_contained_by([1, 2])
                model.where(condition)
            ..
            |array_field <@ [1,2]|
        """
        return Expression(self, "<@", array, **kwargs)

    def overlaps(self, array, **kwargs):
        """ Creates a |&&| (overlaps) SQL expression
            @array: (#list) or #tuple object

            -> SQL :class:Expression object
            ===================================================================

            ``Usage Example``
            ..
                condition = model.array_field.overlaps([1, 2])
                model.where(condition)
            ..
            |array_field && [1,2]|
        """
        return Expression(self, "&&", array, **kwargs)

    def all(self, target, **kwargs):
        """ Creates an |ALL| SQL expression
            @target: (#list) or #tuple object

            -> SQL :class:Expression object
            ===================================================================

            ``Usage Example``
            ..
                condition = model.array_field.all([1, 2])
                model.where(condition)
            ..
            |[1,2] = ALL(array_field)|
        """
        return Expression(target, "=", Function("ALL", self), **kwargs)

    def any(self, target, **kwargs):
        """ Creates an |ANY| SQL expression
            @target: (#list) or #tuple object

            -> SQL :class:Expression object
            ===================================================================

            ``Usage Example``
            ..
                condition = model.array_field.any([1, 2])
                model.where(condition)
            ..
            |[1,2] = ANY(array_field)|
        """
        return Expression(target, "=", Function("ANY", self), **kwargs)

    def some(self, target, **kwargs):
        """ Creates a |SOME| SQL expression
            @target: (#list) or #tuple object

            -> SQL :class:Expression object
            ===================================================================

            ``Usage Example``
            ..
                condition = model.array_field.some([1, 2])
                model.where(condition)
            ..
            |[1,2] = SOME(array_field)|
        """
        return Expression(target, "=", Function("SOME", self), **kwargs)

    def length(self, dimension=1, **kwargs):
        """ :see::meth:F.array_length """
        return F.array_length(self, dimension, **kwargs)

    def append_el(self, element, **kwargs):
        """ :see::meth:F.array_append """
        return F.array_append(self, element, **kwargs)

    def prepend_el(self, element, **kwargs):
        """ :see::meth:F.array_prepend """
        return F.array_prepend(self, element, **kwargs)

    def remove_el(self, element, **kwargs):
        """ :see::meth:F.array_remove """
        return F.array_remove(self, element, **kwargs)

    def replace_el(self, element, new_element, **kwargs):
        """ :see::meth:F.array_replace """
        return F.array_replace(self, element, new_element, **kwargs)

    def position(self, element, **kwargs):
        """ :see::meth:F.array_position """
        return F.array_pposition(self, element, **kwargs)

    def positions(self, element, **kwargs):
        """ :see::meth:F.array_positions """
        return F.array_positions(self, element, **kwargs)

    def ndims(self, **kwargs):
        """ :see::meth:F.array_ndims """
        return F.ndims(self, **kwargs)

    def dims(self, **kwargs):
        """ :see::meth:F.array_dims """
        return F.dims(self, **kwargs)

    def concat(self, other, **kwargs):
        """ :see::meth:F.array_concat """
        return F.array_cat(self, other, **kwargs)

    def unnest(self, **kwargs):
        """ :see::meth:F.unnest """
        return F.unnest(self, **kwargs)


class OneOf(Field, NumericLogic, StringLogic):
    """ =======================================================================
        Field object for PostgreSQL enumerated types.

        Validates that a given value is in the specified group of enumerated
        types.

        =======================================================================
        ``Usage Example``
        ..
            one_of = OneOf('cat', 'dog', 'mouse')
            one_of('goat')
        ..
        |ValueError: `goat` not in ('cat', 'dog', 'mouse')|
    """
    __slots__ = ('field_name', 'primary', 'unique', 'index', 'not_null',
                 'value', 'validator', '_alias', 'default', 'types', 'table',
                 '_type_name')
    OID = ENUM

    def __init__(self, *types, type_name=None, validator=EnumValidator,
                 **kwargs):
        """ `OneOf`
            :see::meth:Field.__init__
            @*types: one or several enumerated types to choose from
            @type_name: (#str) name of the type within the db, if |None|,
                one will be autogenerated
            See [this postgres guide](http://postgresguide.com/sexy/enums.html)
            for more valuable information.
        """
        if not len(types):
            raise TypeError('Must include one or more `types`. '
                            'See http://docs.bloom-orm.com/OneOf')
        self.types = types
        self._type_name = type_name
        super().__init__(validator=validator, **kwargs)

    @prepr('types', 'name', 'value', _no_keys=True)
    def __repr__(self):
        return

    def __call__(self, value=Field.empty):
        if value is not Field.empty:
            if value is None or value in self.types:
                self.value = value
            else:
                raise ValueError("`{}` not in {}".format(value, self.types))
        return self.value

    def register_type(self, db):
        try:
            typ, atyp = db.get_type_OID(self.type_name)
            ENUMTYPE = reg_type(self.type_name.upper(), typ, psycopg2.STRING)
            ARRAYENUMTYPE = reg_array_type(self.type_name.upper() + 'ARRAY',
                                           atyp,
                                           ENUMTYPE)
        except ValueError:
            warnings.warn('Type `%s` not found in the database.' %
                          self.type_name)

    @property
    def type_name(self):
        return (self._type_name or self.field_name or "") + '_enum_type'

    def index_of(self, type=None):
        return self.types.index(type or self.value)

    def copy(self, **kwargs):
        cls = self._copy(*self.types, **kwargs)
        return cls

    __copy__ = copy


Enum = OneOf


class arraylist(list):
    @staticmethod
    def to_db(value):
        try:
            arr = "%s::%s[]" % (
                psycopg2._psycopg.List(value).getquoted().decode(),
                value.__bloomtype__)
            return AsIs(arr)
        except AttributeError:
            return adapt(list(value))

register_adapter(arraylist, arraylist.to_db)


class Array(Field, ArrayLogic):
    """ =======================================================================
        Field object for the PostgreSQL field type |ARRAY|.
        The values passed to this object must be iterable.

        It can be manipulated similar to a python list.
    """
    __slots__ = ('primary', 'unique', 'index', 'not_null', 'value',
                 'validator', '_alias', 'default', 'minlen', 'maxlen',
                 'type', 'dimensions')
    OID = ARRAY

    def __init__(self, type=None, dimensions=1, minlen=0, maxlen=-1,
                 default=None, validator=ArrayValidator, **kwargs):
        """ `Array`
            :see::meth:Field.__init__
            @type: (initialized :class:Field) the data type represented by
                this array, defaults to :class:Text
            @dimensions: (#int) number of array dimensions or depth assigned
                to the field
        """
        self.minlen = minlen
        self.maxlen = maxlen
        self.type = type.copy() if type is not None else Text()
        self.dimensions = dimensions
        super().__init__(validator=validator, **kwargs)
        self.default = default

    @prepr('type.__class__.__name__', 'name', 'value', _no_keys=True)
    def __repr__(self): return

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
        arr.__bloomtype__ = self._get_type_name()
        return arr

    def _cast(self, value, dimension=1):
        """ Casts @value to its correct type, e.g. #int or #str """
        if dimension > self.dimensions:
            raise ValueError('Invalid dimensions ({}): max depth is set to {}'
                             .format(dimension, repr(self.dimensions)))
        next_dimension = dimension + 1
        arr = arraylist(self.type(x) if not isinstance(x, list) else
                        self._cast(x, next_dimension)
                        for x in value)
        return self._add_arr_type(arr)

    def _select_cast(self, value, dimension=1):
        return self.type(value)\
               if not isinstance(value, list) else\
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
        return [self.type.copy(value=val)
                if not isinstance(val, list)
                else self._to_fields(val)
                for val in value]

    def to_fields(self):
        """ Wraps the values in the array with :prop:type """
        return self._to_fields(self.value)

    def clear(self):
        self.value = self.empty
        self.type.clear()

    def register_adapter(self):
        try:
            self.type.register_adapter()
        except AttributeError:
            pass

    def register_type(self, db):
        try:
            self.type.register_type(db)
        except AttributeError:
            pass

    def copy(self, *args, **kwargs):
        return self._copy(*args,
                          type=self.type.copy(),
                          dimensions=self.dimensions,
                          minlen=self.minlen,
                          maxlen=self.maxlen,
                          **kwargs)

    __copy__ = copy
