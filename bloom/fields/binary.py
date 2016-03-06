"""

  `Bloom SQL Binary Fields`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   The MIT License (MIT) © 2015 Jared Lunde
   http://github.com/jaredlunde/bloom-orm

"""
import binascii
import psycopg2
from base64 import b64encode, b64decode

from psycopg2.extensions import new_type, register_type, register_adapter

from vital.tools.encoding import uniorbytes

from bloom.etc.types import *
from bloom.expressions import *
from bloom.fields.field import Field


__all__ = ('BinaryLogic', 'Binary',)


class BinaryLogic(BaseLogic):

    def _cast_bytes(self, string):
        if isinstance(string, bytes):
            return psycopg2.extensions.Binary(string)
        return string

    def concat(self, string, **kwargs):
        """ String concatenation
            -> (:class:Expression)
        """
        string = self._cast_bytes(string)
        return Expression(self, '||', string, **kwargs)

    def octet_length(self, **kwargs):
        """ Number of bytes in binary string
            -> (:class:Function)
        """
        return Function('octet_length', self)

    def overlay(self, substring, from_, for_=None, **kwargs):
        """ Replace @substring
            -> (:class:Function)
        """
        substring = self._cast_bytes(substring)
        exps = [self,
                Expression(self.empty,
                           'placing',
                           Expression(substring, 'from', from_))]
        if for_:
            exps.append(Expression(self.empty, 'for', for_))
        return Function('overlay', Clause("", *exps), **kwargs)

    def position(self, substring):
        """ Location of specified @substring
            -> (:class:Function)
        """
        substring = self._cast_bytes(substring)
        return Function('position', Expression(substring, 'in', self))

    def substring(self, from_=None, for_=None, **kwargs):
        """ Extracts substring from @from_ to @for_
            -> (:class:Function)
        """
        exps = []
        if from_ is not None:
            exps.append(Expression(self.empty, 'from', from_))
        if for_ is not None:
            exps.append(Expression(self.empty, 'for', for_))
        return Function('substring', Clause("", self, *exps), **kwargs)

    def trim(self, bytes_, both=False, **kwargs):
        """ Remove the longest string containing only the bytes in @bytes_
            from the start and end of the string
            -> (:class:Expression)
        """
        bytes_ = self._cast_bytes(bytes_)
        exp = Expression(bytes_, 'from', self)
        if both:
            exp = Clause('both', exp)
        return Function('trim', exp, **kwargs)

    def encode(self, format, **kwargs):
        """ Encode binary data into a textual representation. Supported
            formats are: base64, hex, escape. escape converts zero bytes and
            high-bit-set bytes to octal sequences (\nnn) and doubles
            backslashes.
            -> (:class:Function)
        """
        return Functions.encode(self, format, **kwargs)

    def decode(self, format, **kwargs):
        """ Decode binary data from textual representation in string. Options
            for format are same as in encode.
            -> (:class:Function)
        """
        return Functions.decode(self, format, **kwargs)

    def get_bit(self, offset, **kwargs):
        """ Extract bit from @string
            -> (:class:Function)
        """
        return Functions.get_bit(self, offset, **kwargs)

    def get_byte(self, offset, **kwargs):
        """ Extract byte from @string
            -> (:class:Function)
        """
        return Functions.get_byte(self, offset, **kwargs)

    def set_bit(self, offset, new_value, **kwargs):
        """ Set bit in @string
            -> (:class:Function)
        """
        return Functions.set_bit(self, offset, new_value, **kwargs)

    def set_byte(self, offset, new_value, **kwargs):
        """ Set byte in @string
            -> (:class:Function)
        """
        return Functions.set_byte(self, offset, new_value, **kwargs)

    def length(self, **kwargs):
        """ Length of binary @string
            -> (:class:Function)
        """
        return Functions.length(self, **kwargs)

    def md5(self, **kwargs):
        """ Calculates the MD5 hash of @string, returning the result in
            hexadecimal.
            -> (:class:Function)
        """
        return Functions.md5(self, **kwargs)


class bloombytes(bytes):
    @staticmethod
    def to_db(value):
        return psycopg2.Binary(b64encode(value))


class Binary(Field, BinaryLogic):
    sqltype = BINARY
    __slots__ = (
        'field_name', 'primary', 'unique', 'index', 'not_null', 'value',
        'default', 'validation', 'validation_error', '_alias', 'table')

    def __init__(self, *args, **kwargs):
        """ `Binary`
            :see::meth:Field.__init__
        """
        super().__init__(*args, **kwargs)

    def __call__(self, value=Field.empty):
        if value is not self.empty:
            if value is not None:
                value = bloombytes(uniorbytes(value, bytes))
            self._set_value(value)
        return self.value

    @staticmethod
    def to_python(value, cur):
        try:
            return b64decode(psycopg2.BINARY(value, cur))
        except (TypeError, binascii.Error):
            return psycopg2.BINARY(value, cur)


register_adapter(bloombytes, bloombytes.to_db)
BINARYTYPE = new_type((BINARY,), "BINARY", Binary.to_python)
register_type(BINARYTYPE)
