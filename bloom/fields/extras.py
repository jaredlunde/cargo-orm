"""

  `Bloom ORM Special Fields`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   The MIT License (MIT) © 2015 Jared Lunde
   http://github.com/jaredlunde/bloom-orm

"""
import re
import sys
import copy
import string
import warnings
import datetime
import phonenumbers

try:
    from cnamedtuple import namedtuple
except ImportError:
    from collections import namedtuple

import psycopg2
from psycopg2.extensions import register_adapter, adapt

from slugify import slugify as _slugify

import argon2
from argon2 import PasswordHasher
from passlib.context import CryptContext

from vital.debug import prepr, Timer, line
from vital.security import randkey
from vital.tools import strings as string_tools

from bloom.etc import passwords, usernames
from bloom.etc.types import *
from bloom.expressions import *
from bloom.exceptions import IncorrectPasswordError

from bloom.fields.field import Field
from bloom.fields.integer import Int
from bloom.fields.character import Text
from bloom.fields.numeric import Double
from bloom.validators import *


__all__ = (
    'Username',
    'Email',
    'Hasher',
    'Argon2Hasher',
    'BcryptHasher',
    'Bcrypt256Hasher',
    'PBKDF2Hasher',
    'SHA512Hasher',
    'SHA256Hasher',
    'Password',
    'Slug',
    'SlugFactory',
    'Key',
    'Duration',
    'PhoneNumber')


class SlugFactory(object):
    __slots__ = ('slugify_opt',)

    def __init__(self, **slugify_opt):
        """ :see::func:slugify """
        self.slugify_opt = slugify_opt

    def __call__(self, value):
        return _slugify(value, **self.slugify_opt)


class Slug(Text):
    """ =======================================================================
        Field object for the PostgreSQL field type |TEXT|
    """
    __slots__ = ('field_name', 'primary', 'unique', 'index', 'not_null',
                 'value', 'validator', '_alias', 'default', 'minlen', 'maxlen',
                 '_factory', 'table')
    OID = SLUG

    def __init__(self, maxlen=-1, slug_factory=None, **kwargs):
        """ `Slug`
            :see::meth:Field.__init__
            @maxlen: (#int) maximum length of the slug
            @slug_factory: (:class:SlugFactory)
        """
        self._factory = slug_factory
        super().__init__(minlen=1, maxlen=maxlen, **kwargs)

    def __call__(self, value=Field.empty):
        if value is not Field.empty:
            if value is None:
                value = None
            else:
                value = self.slugify(str(value))
            self.value = value
        return self.value

    def slugify(self, value):
        if self._factory is not None:
            return self._factory(value)
        else:
            return _slugify(value, max_length=self.maxlen, word_boundary=False)

    def copy(self, *args, **kwargs):
        cls = self._copy(*args, maxlen=self.maxlen, slug_factory=self._factory,
                         **kwargs)
        return cls

    __copy__ = copy


def _get_pwd_context():
    #: sha1 and md5 are included for migration purposes
    schemes = ('bcrypt', 'bcrypt_sha256', 'pbkdf2_sha512', 'pbkdf2_sha256',
               'sha512_crypt', 'sha256_crypt', 'sha1_crypt', 'md5_crypt')
    return CryptContext(
        schemes=schemes,
        all__min_rounds=5,
        bcrypt__ident='2b',
        pbkdf2_sha512__min_rounds=2500,
        sha512_crypt__min_rounds=2500,
        sha256_crypt__min_rounds=2500)

_pwd_context = _get_pwd_context()


class HashIdentifier(object):
    __slots__ = tuple()
    scheme = None
    schemes = {}

    @classmethod
    def register_scheme(cls, scheme):
        """ Registers @scheme for :prop:identify and :prop:find_class
            @scheme: (:class:Hasher)
        """
        cls.schemes[scheme.scheme] = scheme

    @classmethod
    def is_hash(cls, value):
        """ Tests whether or not a given @value is already hashed or
            is plain-text
        """
        if value is None or not isinstance(value, (str, bytes)):
            return False
        scheme = HashIdentifier.identify(value)
        return scheme is not None

    @classmethod
    def find_class(cls, scheme):
        try:
            return cls.schemes[scheme]
        except KeyError:
            g = globals()
            for x, c in g.items():
                if x.startswith('__'):
                    continue
                try:
                    if issubclass(c, Hasher) and scheme == c.scheme and\
                       c.scheme is not None:
                        return c
                except (KeyError, TypeError):
                    continue

    @classmethod
    def identify(cls, value, find_class=False):
        """ Identifies the password hashing scheme used in @value.
            @find_class: (#bool) True to return the :class:Hasher instead
                of the name
            -> (#str) scheme name if @find_class is |False|, otherwise
                returns the :class:Hasher for the scheme
        """
        if value is None or not isinstance(value, (str, bytes)):
            return None
        scheme = _pwd_context.identify(value)
        cls_found = None
        if scheme is None:
            try:
                _null, scheme, *_ = value.split('$')
                cls_found = cls.find_class(scheme)
                if cls_found is None:
                    scheme = None
            except ValueError:
                scheme = None
        if find_class:
            return cls.find_class(scheme) if cls_found is None else cls_found
        return scheme


class Hasher(HashIdentifier):
    __slots__ = ('rounds', 'context', 'raises')

    def __init__(self, rounds=None, raises=False, context=None):
        """ ```Password Hasher```
            @rounds: (#int) Defines the amount of computation realized and
                therefore the execution time, given in number of iterations
                (also known as time cost).
            @raises: (#bool) |True| to raise an exception when password
                verification fails
            @context: password context object with either an
                |encrypt(passwordh)| or |hash(password)| method and
                a |verify(password, hash)| method. e.g. :class:CryptContext
                or :class:PasswordHasher
        """
        self.rounds = rounds
        self.raises = raises
        self.context = context or _pwd_context

    @prepr('scheme', _no_keys=True)
    def __repr__(self): return

    def _verify(self, value, hash):
        return self.context.verify(value, hash)

    @staticmethod
    def _raise_if(raises):
        if raises is True:
            raise IncorrectPasswordError('The given password is incorrect.')

    @property
    def _hash_opts(self):
        return {'scheme': self.scheme, 'rounds': self.rounds}

    def hash(self, value):
        """ Hashes @value
            -> (#str) hash
        """
        try:
            return self.context.hash(value, **self._hash_opts)
        except AttributeError:
            return self.context.encrypt(value, **self._hash_opts)

    def verify(self, value, hash):
        """ Verifies @value against @hash.
            -> (#bool) |True| if the given @value is correct, raises
                IncorrectPasswordError if :prop:raises is set to |True|
        """
        if hash is None or value is None:
            self._raise_if(self.raises)
            return False
        try:
            verify = self._verify(value, hash)
        except (argon2.exceptions.VerificationError, ValueError):
            verify = False
        self._raise_if(self.raises)
        return verify

    @property
    def tries_per_second(self):
        """ Calculates the verification tries per second possibile on this
            machine with this :class:Hasher
            ..
                hasher = Argon2Hasher()
                hasher.tries_per_second
                # Loading =‒‒‒‒‒↦                           ☉ (18%)
            ..
            |‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒|
            |Intervals: 10000      |
            |     Mean: 3.58ms     |
            |      Min: 3.55ms     |
            |   Median: 3.58ms     |
            |      Max: 6.15ms     |
            | St. Dev.: 73.41µs    |
            |    Total: 35.8s      |
            |‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒‒|
            |'279 tries per second'|
        """
        line('‒')
        h = self.hash('foobar')
        t = Timer(self.verify)
        t.time(1E3, 'foobar', h)
        line('‒')
        return '%d tries per second' % (1.0 // t.mean)


class Argon2Hasher(Hasher):
    __slots__ = ('rounds', 'context', 'raises')
    scheme = 'argon2i'

    def __init__(self, rounds=2, raises=False, salt_size=16,
                 memory_cost=1 << 12, parallelism=2, length=32,
                 encoding='utf8', context=None):
        """ `Argon2i`
            :see::meth:Hasher.__init__
            @salt_size: (#int) Defines the size in bytes for the hash salt.
            @memory_cost: (#int) Defines the memory usage, given in kibibytes.
            @parallelism: (#int) Defines the number of parallel threads
                (changes the resulting hash value).
            @length: (#int) Length of the hash in bytes.
            @encoding: (#str) The Argon2 C library expects bytes. So if hash()
                or verify() are passed a unicode string, it will be encoded
                using this encoding.
            @context: (:class:PasswordHasher)
        """
        super().__init__(rounds, raises)
        self.context = context or PasswordHasher(time_cost=self.rounds,
                                                 memory_cost=memory_cost,
                                                 parallelism=parallelism,
                                                 hash_len=length,
                                                 salt_len=salt_size,
                                                 encoding=encoding)

    @property
    def _hash_opts(self):
        return {}

    def _verify(self, value, hash):
        return self.context.verify(hash, value)


class BcryptHasher(Hasher):
    __slots__ = Hasher.__slots__
    scheme = 'bcrypt'

    def __init__(self, rounds=6, raises=False, context=None):
        """ `Bcrypt`
            :see::meth:Hasher.__init__

            Salts for this :class:Hasher are automatically generated with
            the correct size.
        """
        super().__init__(rounds, raises, context)


class Bcrypt256Hasher(Hasher):
    __slots__ = Hasher.__slots__
    scheme = 'bcrypt_sha256'

    def __init__(self, rounds=6, raises=False, context=None):
        """ `Bcrypt with SHA-256`
            :see::meth:Hasher.__init__

            Salts for this :class:Hasher are automatically generated with
            the correct size.
        """
        super().__init__(rounds, raises, context)


class PBKDF2Hasher(Hasher):
    __slots__ = Hasher.__slots__
    scheme = 'pbkdf2_sha512'

    def __init__(self, rounds=6400, raises=False, context=None):
        """ `PBKDF2-SHA-512`
            :see::meth:Hasher.__init__

            Salts for this :class:Hasher are automatically generated with
            the correct size.
        """
        super().__init__(rounds, raises, context)


class SHA512Hasher(Hasher):
    __slots__ = Hasher.__slots__
    scheme = 'sha512_crypt'

    def __init__(self, rounds=9600, raises=False, context=None):
        """ `Bcrypt with SHA-256`
            :see::meth:Hasher.__init__

            Salts for this :class:Hasher are automatically generated with
            the correct size.
        """
        super().__init__(rounds, raises, context)


class SHA256Hasher(Hasher):
    __slots__ = Hasher.__slots__
    scheme = 'sha256_crypt'

    def __init__(self, rounds=12800, raises=False, context=None):
        """ `Bcrypt with SHA-256`
            :see::meth:Hasher.__init__

            Salts for this :class:Hasher are automatically generated with
            the correct size.
        """
        super().__init__(rounds, raises, context)


class Password(Field, StringLogic):
    """ =======================================================================
        Field wrapper for PostgreSQL |TEXT| type.

        This object also validates that a password fits given requirements
        such as |minlen| and hashes plain text with supplied hash schemes
        using :class:Hasher

        =======================================================================
        ``Usage Example``
        ..
            password = Password('somepassword')
            print(password.value)
        ..
        |$pbkdf2-sha512$19083$VsoZY6y1NmYsZWxtDQEAoBQCoJRSaq01BiAEQMg5JwQg5P...|

        ..
            password.verify('somepasswords')
            # False
            password.verify('somepassword')
            # True
        ..
    """
    __slots__ = ('field_name', 'primary', 'unique', 'index', 'not_null',
                 'value', 'validator', 'validation_value', '_alias', 'default',
                 'minlen', 'maxlen', 'table', 'hasher', 'blacklist')
    OID = PASSWORD

    def __init__(self, hasher=Argon2Hasher(), minlen=8, maxlen=-1,
                 validator=PasswordValidator, blacklist=passwords.blacklist,
                 **kwargs):
        """ `Password`
            :see::meth:Field.__init__
            @hasher: (:class:Hasher) the password hasher to use
            @blacklist: (#set) passwords which cannot be used due to their
                predictability and popularity, defaults to
                :attr:bloom.etc.passwords.blacklist
            @minlen: (#int) minimum length of the password
            @maxlen: (#int) maximum length of the password
        """
        self.hasher = hasher
        super().__init__(validator=validator, **kwargs)
        self.minlen = minlen
        self.maxlen = maxlen
        self.blacklist = blacklist
        self.validation_value = Field.empty

    def __call__(self, value=Field.empty):
        if value is not Field.empty:
            is_hash = self.hasher.is_hash(value)
            if not is_hash and value is not None:
                self.validation_value = str(value)
                value = self.hasher.hash(str(value))
            else:
                self.validation_value = None
                value = value
            self.value = value
        return self.value

    def hash(self, value):
        """ Hashes @value with the local :class:Hasher at :prop:hasher """
        return self.hasher.hash(value)

    def _get_hasher_for(self, value):
        """ Gets the correct hasher for a given @value, this is useful for
            migrating and managing passwords using multiple algorithms.
        """
        hasher = HashIdentifier.identify(self.value, find_class=True)
        try:
            return hasher()
        except TypeError:
            return self.hasher

    def verify(self, value, hash=None):
        """ Verifies @value against the local hash stored in :prop:value, or
            alternatively @hash.
        """
        hash = hash or (None if self.value_is_null else self.value)
        if hash is None or value is None:
            return False
        hasher = self._get_hasher_for(value)
        return hasher.verify(value, hash)

    def verify_and_migrate(self, value):
        """ Verifies @value against the local hash stored in :prop:value
            and changes itself to a newly generated hash if @value verifies,
            migrating from whichever previous hashing algorithm was used to
            the local :class:Hasher in :prop:hasher. If the local
            :class:Hasher is the same as the hash in @value, the hash will
            not be updated.

            !! This will only work with hashers which are included in this
               package or registered with :meth:Hasher.register !!
            ..
                password = Password(BcryptHasher())
                password('somepassword')
                # $2b$06$SBHX9IEQ1FzyOVUuBglPE.zLLlicbyiRMc/U9C6IbM34KbkATdeQW
                password.verify('somepassword')
                # True

                password.hasher = Argon2Hasher()
                password.verify_and_update('somepassword2')
                # False
                password.verify_and_update('somepassword')
                # True
                # $2b$06$yyxzotqz6ToY2aqBoQnd4.7TNH9jXEqlvICIo5ELtio5jti3xPEZe
            ..
        """
        if self.value_is_null or value is None:
            return False
        hasher = self._get_hasher_for(value)
        verified = hasher.verify(value, self.value)
        if verified and hasher.scheme is not self.hasher.scheme:
            self.__call__(value)
        return verified

    def verify_and_refresh(self, value):
        """ Verifies @value against the local hash stored in :prop:value
            and changes itself to a newly generated hash if @value verifies.
            The hash will use the same hashing algorithm it received on its
            way in.

            Similar to :meth:verify_and_migrate
        """
        if self.value_is_null or value is None:
            return False
        hasher = self._get_hasher_for(value)
        verified = hasher.verify(value, self.value)
        if verified:
            self.__call__(hasher.hash(value))
        return verified

    @staticmethod
    def generate(size=256, keyspace=string.ascii_letters+string.digits+'/.#+'):
        """ Generates a cryptographically secure and random password of
            @size in bits of entropy
        """
        return Key.generate(size=size, keyspace=keyspace)

    def new(self, *args, **kwargs):
        """ Generates a cryptographically secure and random password of
            @size in bits of entropy and sets the :prop:value of this field
            to the generated value
        """
        self.validation_value = self.generate(*args, **kwargs)
        return self.__call__(self.validation_value)

    def clear(self):
        self.validation_value = self.empty
        self.value = self.empty

    def copy(self, *args, **kwargs):
        cls = self._copy(*args,
                         hasher=self.hasher,
                         minlen=self.minlen,
                         maxlen=self.maxlen,
                         blacklist=self.blacklist,
                         **kwargs)
        cls.validation_value = self.validation_value
        return cls

    __copy__ = copy


class Key(Field, StringLogic):
    """ =======================================================================
        Field object for PostgreSQL CHAR/TEXT types.

        Generates random keys of @size bits of entropy.

        =======================================================================
        ``Usage Example``
        ..
            akey = Key()
            akey.generate(256)
        ..
        |v+mwqKTshyGNcoChT1HFHnSr.umyotPhAXMZ/pxEJWrFH|
    """
    __slots__ = ('field_name', 'primary', 'unique', 'index', 'not_null',
                 'value', 'validator', '_alias', 'size', 'keyspace',
                 'table', 'rng')
    OID = KEY

    def __init__(self, size=256,
                 keyspace=string.ascii_letters + string.digits+'/.#+',
                 rng=None, validator=NullValidator, **kwargs):
        """ `Key`
            :see::meth:Field.__init__
            @size: (#int) size in bits to generate
            @keyspace: (#str) iterable chars to include in the key
            @rng: the random number generator implementation to use.
                :class:random.SystemRandom by default
        """
        super().__init__(validator=validator, **kwargs)
        self.size = size
        self.keyspace = keyspace
        self.rng = rng

    @prepr('name', 'size', 'value', _no_keys=True)
    def __repr__(self): return

    def __call__(self, value=Field.empty):
        if value is not Field.empty:
            self.value = str(value) if value is not None else value
        return self.value

    @classmethod
    def generate(cls, size=256,
                 keyspace=string.ascii_letters+string.digits+'/.#+',
                 rng=None):
        """ Generates a high-entropy random key. First, a @size pseudo-random
            bit integer is generated using /dev/urandom, which is transformed
            into a string of the same approximate bit length using
            :class:vital.security.strkey

            @size: (#int) size in bits to generate
            @keyspace: (#str) iterable chars to include in the key
            @rng: the random number generator implementation to use.
                :class:random.SystemRandom by default
            -> #str high-entropy key
        """
        keyspace = keyspace if keyspace or not hasattr(cls, 'keyspace') else \
            cls.keyspace
        size = size if size or not hasattr(cls, 'size') else cls.size
        return randkey(size, keyspace, rng=rng)

    def new(self, *args, **kwargs):
        """ Creates a new key and sets the value of the field to the key """
        if not args and not kwargs:
            value = self.generate(self.size, self.keyspace, self.rng)
        else:
            value = self.generate(*args, **kwargs)
        self.__call__(value)

    def copy(self, *args, **kwargs):
        return self._copy(self.size, self.keyspace, self.rng, *args, **kwargs)

    __copy__ = copy


class Email(Text):
    """ =======================================================================
        Field object for PostgreSQL CHAR/TEXT types.

        Validates that a given value looks like an email address before
        inserting it into the DB.

        =======================================================================
        ``Usage Example``
        ..
            email = Email("not_a@real_email")
            email.validate_chars()
        ..
        |False|
    """
    __slots__ = Text.__slots__
    OID = EMAIL

    def __init__(self, maxlen=320, minlen=6, validator=EmailValidator,
                 **kwargs):
        """ `Email`
            :see::meth:Field.__init__
            @minlen: (#int) minimum length of string value
            @maxlen: (#int) minimum length of string value
        """
        super().__init__(minlen=minlen, maxlen=maxlen, validator=validator,
                         **kwargs)

    def __call__(self, value=Field.empty):
        if value is not Field.empty:
            self.value = str(value).lower() if value is not None else value
        return self.value


class Username(Text):
    """ =======================================================================
        Field object for PostgreSQL CHAR/TEXT types.

        Validates that a given value looks like a username and is not
        in :attr:bloom.etc.usernames.reserved_usernames before inserting
        it into the DB.

        =======================================================================
        ``Usage Example``
        ..
            username = Username("admin")
            username.validate()
        ..
        |False|

        ..
            print(username.validator.error)
        ..
        |'This is a reserved username.'|
    """
    __slots__ = ('field_name', 'primary', 'unique', 'index', 'not_null',
                 'value', 'validator', '_alias', 'default', 'minlen', 'maxlen',
                 '_re', 'reserved_usernames', 'table')
    OID = USERNAME

    def __init__(self, maxlen=25, minlen=1,
                 reserved_usernames=usernames.reserved_usernames,
                 re_pattern=None, validator=UsernameValidator, **kwargs):
        """ `Username`
            :see::meth:Field.__init__
            @minlen: (#int) minimum length of string value
            @maxlen: (#int) minimum length of string value
            @reserved_usernames: (#list) lowercase list of usernames to prevent
                from being created
            @re_pattern: (sre_compile) compiled regex pattern to validate
                usernames with. Defautls to :var:string_tools.username_re
        """
        super().__init__(minlen=minlen, maxlen=maxlen, validator=validator,
                         **kwargs)
        self._re = re_pattern or string_tools.username_re
        if reserved_usernames is not None:
            self.reserved_usernames = set(reserved_usernames)

    def add_reserved_username(self, *usernames):
        for username in usernames:
            self.reserved_usernames.add(username.lower())

    @property
    def type_name(self):
        return 'citext'

    @staticmethod
    def register(db):
        try:
            OID, ARRAY_OID = db.get_type_OID('citext')
            return reg_array_type('CITEXTARRAYTYPE',
                                  ARRAY_OID,
                                  psycopg2.STRING)
        except ValueError:
            warnings.warn('Type `citext` was not found in the database.')

    def copy(self, *args, **kwargs):
        return self._copy(maxlen=self.maxlen,
                          minlen=self.minlen,
                          re_pattern=self._re,
                          reserved_usernames=self.reserved_usernames,
                          **kwargs)

    __copy__ = copy

    def __deepcopy__(self, memo):
        cls = self.__class__()
        for k in list(self.__slots__) + list(dir(self)):
            attr = getattr(self, k)
            if k not in {'copy', '_re', 'validator'} and \
               not k.startswith('__') and not callable(attr):
                try:
                    setattr(cls, k, copy.deepcopy(getattr(self, k), memo))
                except AttributeError:
                    pass
                except TypeError:
                    setattr(cls, k, copy.copy(getattr(self, k)))
            elif k == '_re':
                setattr(cls, k, getattr(self, k))
        return cls


class _DurationTemplate(string.Formatter):

    def format_field(self, value, spec):
        ''' "{hours:02d} {mins:(m)} {secs:(sec,secs)}" '''
        sing, plural = None, None
        if '(' in spec:
            spec, cases = spec.split('(')
            sing, *plural = cases.strip(')').split(',')
            plural = "".join(plural)
        value = super(_DurationTemplate, self).format_field(value, spec)
        if sing or plural:
            if value == '1' or value.lstrip('0') == '1' or not plural:
                value = value + sing
            else:
                value = value + plural
        return value


class _DurationDelta(datetime.timedelta):
    _nt = namedtuple('Duration', ('years', 'months', 'days', 'hours', 'mins',
                                  'secs', 'msecs'))

    @property
    def namedtuple(self):
        try:
            dt = self._cache.get(self.total_seconds())
        except AttributeError:
            self._cache = {}
            dt = None
        if dt is not None:
            return dt
        else:
            dt = self
        years, days = divmod(dt.days, 365.242199)
        months, days = divmod(days, 30.416667)
        hours, rem = divmod(dt.seconds, 3600)
        mins, secs = divmod(rem, 60)
        msecs = dt.microseconds
        nt = self._nt(years=int(years),
                      months=int(months),
                      days=int(days),
                      hours=int(hours),
                      mins=int(mins),
                      secs=int(secs),
                      msecs=int(msecs))
        self._cache[self.total_seconds()] = nt
        return nt

    @staticmethod
    def to_db(value):
        return adapt(value.total_seconds())


class Duration(Double):
    __slots__ = Double.__slots__

    def __init__(self, *args, validator=NullValidator, **kwargs):
        """`Duration`
            :see::meth:Field.__init__
        """
        super().__init__(*args, validator=validator, **kwargs)

    def __call__(self, value=Field.empty):
        """ @value: (#int or #float) duration in seconds or
                :class:datetime.timedelta
        """
        if value is not self.empty:
            try:
                value = float(value)
                if value < 1:
                    value = _DurationDelta(microseconds=value * 1000000)
                else:
                    value = _DurationDelta(seconds=value)
            except TypeError as e:
                if value is not None:
                    value = _DurationDelta(seconds=value.total_seconds())
            self.value = value
        return self.value

    @staticmethod
    def register_adapter():
        register_adapter(_DurationDelta, _DurationDelta.to_db)

    _std_fmts = {'years': ('year', 'years'),
                 'months': ('month', 'months'),
                 'days': ('day', 'days'),
                 'hours': ('hour', 'hours'),
                 'mins': ('minute', 'minutes'),
                 'secs': ('second', 'seconds'),
                 'msecs': ('µs', 'µs')}

    @property
    def total_years(self):
        """ -> (#float) """
        return self.total_days / 365.242199

    @property
    def total_months(self):
        """ -> (#float) """
        return self.total_days / 30.416667

    @property
    def total_days(self):
        """ -> (#float) """
        return self.value.total_seconds() / 86400

    @property
    def total_hours(self):
        """ -> (#float) """
        return self.value.total_seconds() / 3600

    @property
    def total_mins(self):
        """ -> (#float) """
        return self.value.total_seconds() / 60

    @property
    def total_secs(self):
        """ -> (#float) """
        return self.value.total_seconds()

    @property
    def total_msecs(self):
        """ -> (#float) """
        return self.value.total_seconds() * 1E6

    @property
    def years(self):
        return self.value.namedtuple.years

    @property
    def months(self):
        return self.value.namedtuple.months

    @property
    def days(self):
        return self.value.namedtuple.days

    @property
    def hours(self):
        return self.value.namedtuple.hours

    @property
    def mins(self):
        return self.value.namedtuple.mins

    @property
    def secs(self):
        return self.value.namedtuple.secs

    @property
    def msecs(self):
        return self.value.namedtuple.msecs

    def to_namedtuple(self):
        return self.value.namedtuple

    def to_dict(self):
        return self.to_namedtuple()._asdict()

    def clock(self):
        """ -> (#str) time delta formatted like |mm:ss|, |hh:mm:ss|, etc.
                depending on how long the time delta is
        """
        dt = self.to_namedtuple()
        started = False
        out = []
        add_out = out.append
        l = len(dt._fields)
        for x, t in enumerate(dt._fields[:-1]):
            val = getattr(dt, t)
            if (val > 0 or started or l - x < 4):
                started = True
                add_out('{:02d}'.format(val))
        return ':'.join(out)

    def _std_format(self, dt, separator=", "):
        fmts = self._std_fmts
        out = []
        add_out = out.append
        for f in dt._fields:
            val = getattr(dt, f)
            if val > 0:
                add_out(string_tools.to_plural(val, *fmts[f]))
        return separator.join(out)

    def format(self, fmt=None):
        """ @fmt: (#str) string for formatting in Python 3 style |str.format|
                with optional singular and plural formats included.
                e.g. |format("{hours:02d} {mins:(m)} {secs:(sec,secs)}")|
                ```Available formats```
                * years
                * months
                * days
                * hours
                * mins
                * secs
                * msecs
            >>> d = Duration()
            >>> d(7253)
            >>> d.format()
            '2 hours, 53 seconds'
            >>> duration.format("{hours:02d}:{mins:02d}:{secs:02d}")
            '02:00:53'
            >>> d.format("{hours:(h)} {mins:(m)} {secs:(sec,secs)}")
            '2h 0m 53secs'
            >>> d.format("{hours:02d(h)} {mins:02(m)} {secs:(s)}")
            '02h 00m 53s'
        """
        dt = self.to_namedtuple()
        if fmt is None:
            return self._std_format(dt)
        return _DurationTemplate().format(fmt, **dt._asdict()).strip()


class PhoneNumber(Field, StringLogic):
    OID = TEXT
    __slots__ = ('field_name', 'primary', 'unique', 'index', 'not_null',
                 'value', 'validator', '_alias', 'default', 'table',
                 'region')
    INTERNATIONAL = phonenumbers.PhoneNumberFormat.INTERNATIONAL
    NATIONAL = phonenumbers.PhoneNumberFormat.NATIONAL
    RFC3966 = phonenumbers.PhoneNumberFormat.RFC3966
    E164 = phonenumbers.PhoneNumberFormat.E164

    def __init__(self, region='US', *args, validator=PhoneNumberValidator,
                 **kwargs):
        """`Phone Number`
            @region: (#str) 2-letter uppercase ISO 3166-1 country
                code (e.g. "GB")
            :see::meth:Field.__init__
        """
        self.region = region
        super().__init__(*args, validator=validator, **kwargs)

    def __call__(self, value):
        """ @value: (#str) phone number-like string or
                :class:phonenumbers.PhoneNumber
        """
        if value is not self.empty:
            if value is not None:
                value = phonenumbers.parse(str(value), self.region)
                value.__str__ = value.__unicode__ = self.to_std
            self.value = value
        return self.value

    def format(self, format=NATIONAL):
        return phonenumbers.format_number(self.value, format)

    def to_html(self):
        return phonenumbers.format_number(self.value, self.RFC3966)

    def to_std(self):
        return phonenumbers.format_number(self.value, self.E164)

    def from_text(self, text):
        for m in phonenumbers.PhoneNumberMatcher(text, self.region):
            return self.__call__(m.raw_string)

    _db_re = re.compile(r"""[\-\s\.]+""")

    @staticmethod
    def register_adapter():
        register_adapter(phonenumbers.phonenumber.PhoneNumber,
                         PhoneNumber.to_db)

    @staticmethod
    def to_db(value):
        return adapt(PhoneNumber._db_re.sub("", phonenumbers.format_number(
            value, PhoneNumber.INTERNATIONAL)).replace('ext', 'x'))
