"""PostgreSQL connection pool using psycopg2."""

from psycopg2.pool import SimpleConnectionPool

from app.config import settings

_pool: SimpleConnectionPool | None = None


def get_pool() -> SimpleConnectionPool:
    """Return the shared connection pool, creating it on first call.

    Returns
    -------
    SimpleConnectionPool
        A psycopg2 connection pool sized by ``PG_POOL_MIN`` / ``PG_POOL_MAX``.
    """
    # TODO: Create SimpleConnectionPool using settings.pg_* values
    # TODO: Cache in module-level _pool variable
    pass


def get_connection():
    """Get a connection from the pool.

    Returns
    -------
    psycopg2.extensions.connection
        A database connection from the pool.
    """
    # TODO: Call get_pool().getconn()
    pass


def put_connection(conn) -> None:
    """Return a connection back to the pool.

    Parameters
    ----------
    conn : psycopg2.extensions.connection
        The connection to return.
    """
    # TODO: Call get_pool().putconn(conn)
    pass
