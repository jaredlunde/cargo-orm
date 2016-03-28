"""

  `Cargo SQL Networking Fields`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   The MIT License (MIT) © 2015 Jared Lunde
   http://github.com/jaredlunde/cargo-orm

"""
import copy
from netaddr import *

import psycopg2
from psycopg2.extensions import *

from cargo.etc.types import *
from cargo.expressions import *
from cargo.fields.field import Field
from cargo.logic.networking import NetworkingLogic


__all__ = ('IP', 'Inet', 'Cidr', 'MacAddress')


class IP(Field, NetworkingLogic):
    """ =======================================================================
        Field object for the PostgreSQL field type |INET|.
    """
    __slots__ = ('field_name', 'primary', 'unique', 'index', 'not_null',
                 'value', 'validator', '_alias', '_default', 'table',
                 '_request')
    OID = IPTYPE
    current = -1

    def __init__(self, request=None, *args, default=None, **kwargs):
        """ `IP Address`
            :see::meth:Field.__init__
            @request: Django, Flask or Bottle-like request object
        """
        self._default = default
        self._request = request
        super().__init__(*args, **kwargs)

    def __getattr__(self, name):
        try:
            return self.__getattribute__(name)
        except AttributeError:
            return self.value.__getattribute__(name)

    def __call__(self, value=Field.empty):
        if value is not Field.empty:
            if value == self.current:
                value = self.request_ip
            if value is not None:
                value = IPAddress(value)
            self.value = value
        return self.value

    def __int__(self):
        return int(self.value)

    @property
    def request_ip(self):
        if self._request is None:
            return None
        if hasattr(self._request, 'remote_addr'):
            return self._request.remote_addr
        elif hasattr(self._request, 'META'):
            x_forwarded_for = self._request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[-1].strip()
            else:
                return self._request.META.get('REMOTE_ADDR')
        return None

    @property
    def default(self):
        if self._default == self.current:
            return self.request_ip
        return self._default

    def __getstate__(self):
        return dict((slot, getattr(self, slot))
                    for slot in self.__slots__
                    if hasattr(self, slot))

    def __setstate__(self, state):
        for slot, value in state.items():
            setattr(self, slot, value)

    @staticmethod
    def to_db(value):
        return AsIs("%s::inet" % adapt(str(value)).getquoted().decode())

    @staticmethod
    def to_python(value, cur):
        if value is None:
            return value
        return IPAddress(value)

    @staticmethod
    def register_adapter():
        register_adapter(IPAddress, IP.to_db)
        IPTYPE_ = reg_type('IPTYPE', IPTYPE, IP.to_python)
        reg_array_type('IPARRAYTYPE', IPARRAY, IPTYPE_)

    def copy(self, *args, **kwargs):
        cls = Field.copy(self, self._request, *args, **kwargs)
        cls._default = self._default
        return cls

    __copy__ = copy


Inet = IP


class Cidr(Field, StringLogic):
    """ =======================================================================
        Field object for the PostgreSQL field type |CIDR|.
    """
    __slots__ = Field.__slots__
    OID = CIDR

    def __init__(self, *args, **kwargs):
        """ `Cidr Addresses`
            :see::meth:Field.__init__
        """
        super().__init__(*args, **kwargs)

    def __getattr__(self, name):
        try:
            return self.__getattribute__(name)
        except AttributeError:
            return self.value.__getattribute__(name)

    def __call__(self, value=Field.empty):
        if value is not Field.empty:
            if value is not None:
                value = IPNetwork(value)
            self.value = value
        return self.value

    def __int__(self):
        return int(self.value)

    @staticmethod
    def to_python(value, cur):
        if value is None:
            return value
        return IPNetwork(value)

    @staticmethod
    def register_adapter():
        register_adapter(IPNetwork, Cidr.to_db)
        CIDRTYPE = reg_type('CIDRTYPE', CIDR, Cidr.to_python)
        reg_array_type('CIDRARRAYTYPE', CIDRARRAY, CIDRTYPE)

    @staticmethod
    def to_db(value):
        return AsIs("%s::cidr" % adapt(str(value)).getquoted().decode())


class MacAddress(Cidr):
    """ =======================================================================
        Field object for the PostgreSQL field type |MACADDR|.
    """
    OID = MACADDR
    __slots__ = Field.__slots__

    def __init__(self, *args, **kwargs):
        """ `Mac Addresses`
            :see::meth:Field.__init__
        """
        super().__init__(*args, **kwargs)

    def __getattr__(self, name):
        try:
            return self.__getattribute__(name)
        except AttributeError:
            return self.value.__getattribute__(name)

    def __call__(self, value=Field.empty):
        if value is not Field.empty:
            if value is not None:
                value = EUI(value)
            self.value = value
        return self.value

    @staticmethod
    def to_python(value, cur):
        if value is None:
            return value
        return EUI(value)

    @staticmethod
    def to_db(value):
        return AsIs("%s::macaddr" % adapt(str(value)).getquoted().decode())

    @staticmethod
    def register_adapter():
        register_adapter(EUI, MacAddress.to_db)
        MACADDRTYPE = reg_type('MACADDRTYPE', MACADDR, MacAddress.to_python)
        reg_array_type('MACADDRARRAYTYPE', MACADDRARRAY, MACADDRTYPE)

    def trunc(self, *args, **kwargs):
        """ Sets last 3 bytes to zero
            -> (:class:Function)
        """
        return Function(trunc, self, *args, **kwargs)