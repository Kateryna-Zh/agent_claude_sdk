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
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn=settings.pg_pool_min,
            maxconn=settings.pg_pool_max,
            host=settings.pg_host,
            port=settings.pg_port,
            dbname=settings.pg_database,
            user=settings.pg_user,
            password=settings.pg_password,
        )
    return _pool


def get_connection():
    """Get a connection from the pool.

    Returns
    -------
    psycopg2.extensions.connection
        A database connection from the pool.
    """
    return get_pool().getconn()


def put_connection(conn) -> None:
    """Return a connection back to the pool.

    Parameters
    ----------
    conn : psycopg2.extensions.connection
        The connection to return.
    """
    get_pool().putconn(conn)
