"""

  `Postgres Clients`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   The MIT License (MIT) © 2015 Jared Lunde
   http://github.com/jaredlunde/cargo-orm

"""
try:
    import ujson as json
except ImportError:
    import json

from docr import objects

from collections import defaultdict

import psycopg2
import psycopg2.pool
import psycopg2.extras

from multiprocessing import cpu_count

from vital.cache import DictProperty, local_property
from vital.tools.dicts import merge_dict
from vital.debug import prepr

from cargo.cursors import CNamedTupleCursor, ModelCursor
from cargo.etc.types import reg_array_type, reg_type
from cargo.etc.translator.postgres import OID_map


__all__ = (
    "Postgres",
    "PostgresPool",
    "db",
    "local_client",
    "create_client",
    "create_pool"
)


class BasePostgresClient(object):
    __slots__ = tuple()

    def get_type_OID(self, typname):
        """ -> (#tuple) |(OID, ARRAY_OID)| """
        q = """SELECT t.oid AS OID, t.typname AS name
               FROM pg_catalog.pg_type t
               WHERE t.typname IN(%s, %s)
               ORDER BY name DESC;"""
        conn = self.get()
        cur = conn.cursor(cursor_factory=CNamedTupleCursor)
        cur.execute(q, ('_%s' % typname, typname))
        res = cur.fetchall()
        self.put(conn)
        return tuple(r.oid for r in res)

    def get_type_name(self, OID):
        """ -> (#str) type name for @OID """
        try:
            return OID_map[OID]
        except KeyError:
            q = """SELECT t.oid AS OID, t.typname AS name
                   FROM pg_catalog.pg_type t
                   WHERE t.oid = %s;"""
            cur = self.cursor(cursor_factory=CNamedTupleCursor)
            cur.execute(q, OID)
            res = cur.fetchall()
            return res.oid

    _ext_map = {'hstore': psycopg2.extras.register_hstore,
                'composite': psycopg2.extras.register_composite}

    def register(self, extension, *args, cursor=None, **kwargs):
        """ Shortcut for registering extensions in :prop:_ext_map to the
            local connection or cursor, currently only 'composite' and
            'hstore' are supported.

            @extension: (#str) name of the extension
            @*args: arguments to pass to the extension function
            @cursor: (:class:psycopg2.extensions.cursor) apply to the
                given cursor rather than the local connection
            @**kwargs: keyword arguments to pass ot hte extension function
        """
        conn_or_curs = self.connection if cursor is None else cursor
        return self._ext_map[extension](conn_or_curs, *args, **kwargs)

    def _load_from_str(self, name):
        return objects.Object.import_from(name)

    @DictProperty('_cache', 'cursor_factory', read_only=False)
    def cursor_factory(self):
        if isinstance(self._cursor_factory, str):
            self._cursor_factory = self._load_from_str(self._cursor_factory)
        return self._cursor_factory

    def set_cursor_factory(self, cursor_factory):
        self.cursor_factory = self._load_from_str(cursor_factory)

    @property
    def schema(self):
        """ The default schema to set the cursor search path to """
        opt = self._connection_options
        return opt.get('schema', opt.get('search_path', self._schema))

    def add_search_path(self, *paths):
        """ Adds a schema to the search path in addition to :prop:schema.
        """
        self._search_paths.extend(paths)

    def remove_search_path(self, path):
        """ Removes a schema to the search path in addition to :prop:schema.
        """
        self._search_paths.remove(path)

    def set_schema(self, schema):
        """ Sets the default schema used by the client. """
        self._schema = schema

    @staticmethod
    def apply_schema(cursor, *schemas):
        """ Sets @schemas to the cursor search path.
            @schemas: (#str) one or several schema search paths
        """
        return cursor.execute('SET search_path TO %s' % ", ".join(schemas))

    @staticmethod
    def to_dsn(opt):
        """ Converts @opt to a string if it isn't one already.
            @opt: (#dict) dsn options
        """
        try:
            return " ".join(
                '{}={}'.format(k.replace('database', 'dbname'), v)
                for k, v in opt.items()
                if k in {'dbname', 'database', 'user', 'password',
                         'host', 'port'})
        except AttributeError:
            return opt

    EVENTS = {'COMMIT', 'ROLLBACK', 'CONNECT', 'CLOSE', 'NEW CURSOR'}

    def before(self, event, task):
        """ Creates a hook which fires @task before @event. The task callable
            must accept one argument for this |client| object.

            @event: (#str) name of the event in :prop:_events
            ..
            db.client.before('connect',
                             lambda pg: pg.set_schema('foo'))
            ..
        """
        self._attach_event('BEFORE', event, task)

    def after(self, event, task):
        """ Creates a hook which fires @task after @event. The task callable
            must accept one argument for this |client| object.

            @event: (#str) name of the event in :prop:_events
            ..
                db.client.after('new cursor',
                                lambda pg, cur:
                                    cur.set_client_encoding('latin1'))
            ..
        """
        self._attach_event('AFTER', event, task)

    def _attach_event(self, when, event, task):
        event = event.upper()
        try:
            if task not in self._events[when][event]:
                self._events[when][event].append(task)
        except KeyError:
            self._events[when][event] = []
            self._events[when][event].append(task)

    def _apply_event(self, when, event, *args, **kwargs):
        try:
            event = event.upper()
            for event_cb in self._events[when][event]:
                event_cb(self, *args, **kwargs)
        except KeyError:
            pass

    def _apply_before(self, *args, **kwargs):
        self._apply_event('BEFORE', *args, **kwargs)

    def _apply_after(self, *args, **kwargs):
        self._apply_event('AFTER', *args, **kwargs)


class Postgres(BasePostgresClient):
    """ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        ``Usage Example``

        Creates a new :class:cargo.Model with a customized
        Postgres instance.
        ..
            from psycopg2.extras import NamedTupleCursor
            from cargo import Model, Postgres

            class MyModel(Model):

                def __init__(self, **model):
                    client = Postgres(cursor_factor=NamedTupleCursor)
                    super().__init__(client=client, **model)
        ..
    """
    __slots__ = ('_dsn', 'autocommit', '_connection', '_connection_options',
                 '_schema', 'encoding', '_cursor_factory', '_cache',
                 '_search_paths', '_events')

    def __init__(self, dsn=None, cursor_factory=CNamedTupleCursor,
                 connection=None, autocommit=False, encoding=None, schema=None,
                 search_paths=None, events=None, **connection_options):
        """ `Postgres Client`

            This is a thin wrapper for the :mod:psycopg2 connection object
            returned by :func:psycopg2.connect, it's purpose being to
            standardize a client object in the event that other SQL backends
            aside from :mod:psycopg2 or Postgres are added in the future.

            @connection: (:mod:psycopg2) connection object returned by
                :func:psycopg2.connect
            @cursor_factory: (:mod:psycopg2 cursor factory) passed to
                :prop:cursor
            @autocommit: (#bool) if True all the commands executed will be
                immediately committed and no rollback is possible
            @encoding: (#str) Sets the client encoding for the current session.
                If None, the default is the encoding defined by the database.
            @schema: (#str) schema to set the postgres search path to
            @search_paths: (#list) additional search paths to set aside
                from the default @schema
            @events: (#dict) |{'[before, after] event_name': action}}|
                available events are: :see::attr:Postgres.EVENTS
                ..
                    from cargo import db
                    db.bind(events={
                        "before": {
                            "commit": do_something
                        },
                        "after": {
                            "new cursor": lambda pg, cur:
                                cur.set_client_encoding('latin1')
                        }
                    })
                ..
            @**connection_options: |key=value| arguments to pass to
                :func:psycopg2.connect
        """
        self._cache = {}

        # Connection options
        self._dsn = dsn
        self._events = events or defaultdict(dict)
        self.autocommit = autocommit
        self._connection = connection
        self._connection_options = connection_options or {}
        self._schema = schema
        try:
            self._search_paths = list(search_paths)
        except TypeError:
            self._search_paths = []
        self.encoding = encoding

        # Cursor options
        self._cursor_factory = cursor_factory

    @prepr('_connection', 'autocommit')
    def __repr__(self): return

    def __enter__(self):
        return self.connection

    def __exit__(self, *exc_info):
        self.close()

    @property
    def closed(self):
        """ -> #bool True if the connection is closed """
        try:
            return self._connection.closed
        except AttributeError:
            return True

    @property
    def connection(self):
        """ Creates a new connection if there isn't one or it is closed.
            -> :mod:psycopg2 connection object
        """
        if not self._connection or self._connection.closed:
            self.connect()
        return self._connection

    def cursor(self, *args, model=None, cursor_factory=None, schema=None,
               **kwargs):
        """ Creates a new cursor object with given options, defaulting to
            configured options.

            @name: (#str) name of the cursor
            @model: (:class:Model|:class:ORM) to bind the cursor to if
                this is a :class:ModelCursor
            @cursor_factory: :mod:psycopg2 cursor factory passed to
                :prop:cursor
            @scrollable: (#bool) specifies if a named cursor is declared
                SCROLL, hence is capable to scroll backwards (using scroll()).
                If True, the cursor can be scrolled backwards, if False it is
                never scrollable. If None (default) the cursor scroll option is
                not specified, usually but not always meaning no backward
                scroll.
            @schema: (#str) search path to set
            @withhold: (#bool) specifies if a named cursor lifetime should
                extend outside of the current transaction, i.e., it is possible
                to fetch from the cursor even after a connection.commit()
                (but not after a connection.rollback()).

            -> :mod:psycopg2 cursor object
        """
        if model is not None and not model._is_naked():
            cursor_factory = ModelCursor
        elif cursor_factory is not None and \
                cursor_factory != self.cursor_factory:
            pass
        elif self.cursor_factory != self.connection.cursor_factory:
            cursor_factory = self.cursor_factory
        self._apply_before("new cursor")
        cursor = self.connection.cursor(*args,
                                        cursor_factory=cursor_factory,
                                        **kwargs)
        self._apply_after("new cursor", cursor)
        try:
            cursor._cargo_model = model
        except AttributeError:
            pass
        schema = schema or self.schema
        if schema:
            paths = [schema]
            paths.extend(self._search_paths)
            self.apply_schema(cursor, *paths)
        return cursor

    def connect(self, dsn=None, **options):
        """ Opens a :mod:psycopg2 connection with @options combined with
            :prop:connection_options

            -> :mod:psycopg2 connection object
        """
        if self._connection is None or self._connection.closed or dsn \
           or options:
            self._apply_before('connect')
            dsn = dsn or self._dsn
            if not dsn:
                dsn = self.to_dsn(self._connection_options)
            self._connection = psycopg2.connect(
                dsn, cursor_factory=self.cursor_factory)
            self._set_conn_options()
            self._apply_after('connect')
        return self._connection

    def _set_conn_options(self, seen=False):
        if not seen:
            if self.autocommit:
                self._connection.set_session(autocommit=self.autocommit)
            if self.encoding:
                self._connection.set_client_encoding(encoding=self.encoding)

    def commit(self):
        """ Commits a transaction """
        self._apply_before('commit')
        self._connection.commit()
        self._apply_after('commit')

    def rollback(self):
        """ Rolls back a transaction """
        self._apply_before('rollback')
        self._connection.rollback()
        self._apply_after('rollback')

    def close(self):
        """ Closes the psycopg2 cursor and connection """
        self._apply_before('close')
        try:
            self._connection.close()
        except AttributeError:
            pass
        self._apply_after('close')

    def get(self, *args, **kwargs):
        """ Dummy method in order to work seamlessly in the ORM with
            :class:PostgresPool
        """
        return self

    def put(self, *args, **kwargs):
        """ Dummy method in order to work seamlessly in the ORM with
            :class:PostgresPool
        """


class PostgresPoolConnection(Postgres):
    __slots__ = ('pool', '_connection')

    def __init__(self, pool, connection):
        self.pool = pool
        self._connection = connection
        self._set_conn_options()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.pool.put(self)

    def __getattr__(self, name):
        try:
            return self.__getattribute__(name)
        except AttributeError:
            return self.pool.__getattribute__(name)

    def put(self, *args, **kwargs):
        """ Returns the connection to the pool """
        self.pool.putconn(self._connection, *args, **kwargs)


class PostgresPool(BasePostgresClient):
    __slots__ = ('_dsn', 'autocommit',  '_connection_options', '_schema',
                 'encoding', '_cursor_factory', 'minconn', 'maxconn', '_pool',
                 '_cache', '_search_paths', '_events')

    def __init__(self, minconn=1, maxconn=1, dsn=None,
                 cursor_factory=CNamedTupleCursor, pool=None,
                 autocommit=False, encoding=None, schema=None,
                 search_paths=None, events=None, **connection_options):
        """ :see::class:Postgres
            @minconn: (#int) minimum number of connections to establish
                within the pool
            @maxconn: (#int) maximum number of connections to establish
                within the pool
            @pool: (:class:psycopg2.pool.ThreadedConnectionPool) initialized
                pyscopg2 connection pool object
        """
        self._cache = {}
        # Connection options
        self._dsn = dsn
        self.autocommit = autocommit
        self._events = events or defaultdict(dict)
        self._connection_options = connection_options or {}
        self._schema = schema
        self._search_paths = search_paths or []
        self.encoding = encoding
        self._pool = pool
        self.minconn = minconn
        self.maxconn = maxconn

        # Cursor options
        self._cursor_factory = cursor_factory

    @prepr('_pool', 'autocommit')
    def __repr__(self): return

    def __enter__(self):
        """ Gets a connection from the pool """
        self.connect()
        return self

    def __exit__(self, *exc_info):
        """ Puts away the active connection in the pool """
        self.close()

    @property
    def closed(self):
        """ -> #bool True if the connection is closed """
        try:
            return self._pool.closed
        except (ValueError, AttributeError):
            return True

    def connect(self, dsn=None, **options):
        """ Opens a :mod:psycopg2 connection with @options combined with
            :prop:connection_options

            -> :mod:psycopg2 connection object
        """
        if not self._pool or self._pool.closed or dsn or options:
            dsn = dsn or self._dsn
            opt = merge_dict(self._connection_options, options)
            if not dsn:
                dsn = self.to_dsn(opt)
            minconn = opt.get('minconn', self.minconn)
            maxconn = opt.get('maxconn', self.maxconn)
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn, maxconn, dsn)
        return self._pool

    @property
    def pool(self):
        return self.connect()

    def get(self, *args, **kwargs):
        return PostgresPoolConnection(pool=self,
                                      connection=self.pool.getconn())

    def put(self, poolconn, *args, **kwargs):
        """ Returns the connection to the pool
            @poolcon: (:class:PostgresPoolConnection) object
        """
        try:
            poolconn = poolconn._connection
        except AttributeError:
            pass
        self.pool.putconn(poolconn, *args, **kwargs)

    def close(self):
        """ Closes all the psycopg2 cursors and connections """
        try:
            self.pool.closeall()
        except AttributeError:
            pass


#: Storage for connection clients/pools
#  local_client = local_property()
local_client = {}


class _db(object):
    """ Thread-local ORM session """
    engine = None

    def __init__(self):
        self.engine = local_property()

    def __getattr__(self, name):
        if name != 'engine':
            try:
                return self.engine.__getattribute__(name)
            except AttributeError:
                pass
        return self.__getattribute__(name)

    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def __delattr__(self, name):
        return self.engine.__detattr__(name)

    def __repr__(self):
        try:
            return self.engine.__repr__()
        except RuntimeError:
            return "<_db:{}>".format(hex(id(self)))

    def __get__(self):
        if self.engine:
            return self.engine
        return self

    def bind(self, *opt, client=None, **opts):
        """ Creates a thread-local, global :class:ORM object with the
            given options.

            @*opt and **opts are passed to :class:Postgres
        """
        from cargo.orm import ORM
        if not client:
            client = create_client(*opt, **opts)
        self.engine = ORM(client=client)
        return self

    open = bind

    def close(self):
        try:
            self.engine.db.close()
        except AttributeError:
            pass


db = _db()


def create_client(*opt, name='db', **opts):
    """ Creates a connection client in the :attr:local_client thread which
        will be used as the default client in the ORM.

        @name: (#str) name in the :attr:local_client thread dictionary to cache
            the client within

        See also: :class:Postgres
    """
    local_client[name] = Postgres(*opt, **opts)
    return local_client[name]


def create_pool(minconn=None, maxconn=None, name='db', *args, **kwargs):
    """ Creates a connection pool in the :attr:local_client thread which
        will be used as the default client in the ORM.

        @name: (#str) name in the :attr:local_client thread dictionary to cache
            the pool within

        See also: :class:PostgresPool
    """
    minconn = minconn or cpu_count()
    maxconn = maxconn or (cpu_count() * 2)
    local_client[name] = PostgresPool(minconn, maxconn, *args, **kwargs)
    return local_client[name]
