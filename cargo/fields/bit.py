"""

  `Cargo SQL Bit Fields`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   The MIT License (MIT) © 2015 Jared Lunde
   http://github.com/jaredlunde/cargo-orm

"""
from bitstring import BitArray
from psycopg2.extensions import new_type, register_type, register_adapter,\
                                adapt, AsIs

from cargo.etc.types import *
from cargo.etc.translator.postgres import OID_map
from cargo.expressions import *
from cargo.fields.field import Field
from cargo.logic.bit import BitLogic
from cargo.validators import BitValidator, VarbitValidator


__all__ = ('Bit', 'Varbit',)


class Bit(Field, BitLogic):
    """ =======================================================================
        Field object for the PostgreSQL field type |BIT|.
    """
    OID = BIT
    __slots__ = (
        'field_name', 'primary', 'unique', 'index', 'not_null', 'value',
        'default', 'validator', '_alias', 'table', 'length')

    def __init__(self, length, *args, validator=BitValidator, **kwargs):
        """ `Bit`
            :see::meth:Field.__init__
        """
        self.length = length
        super().__init__(*args, validator=validator, **kwargs)

    def __call__(self, value=Field.empty):
        if value is not self.empty:
            if value is not None:
                value = BitArray(value)
            self.value = value
        return self.value

    @property
    def type_name(self):
        return '%s(%s)' % (OID_map[self.OID], self.length)

    @staticmethod
    def to_python(value, cur):
        if value is not None:
            return BitArray(bin=value)

    @staticmethod
    def to_db(value):
        return AsIs("B%s" % adapt(value.bin).getquoted().decode())

    @staticmethod
    def register_adapter():
        register_adapter(BitArray, Bit.to_db)
        BITTYPE = reg_type("BITTYPE", (BIT, VARBIT), Bit.to_python)
        reg_array_type('BITARRAYTYPE', (VARBITARRAY, BITARRAY), BITTYPE)

    def copy(self, *args, **kwargs):
        return Field.copy(self, self.length, *args, **kwargs)

    __copy__ = copy


class Varbit(Bit):
    """ =======================================================================
        Field object for the PostgreSQL field type |VARBIT|.
    """
    OID = VARBIT
    __slots__ = Bit.__slots__

    def __init__(self, length, *args, validator=VarbitValidator, **kwargs):
        """ `Bit Varying`
            :see::meth:Field.__init__
        """
        super().__init__(length, *args, validator=validator, **kwargs)