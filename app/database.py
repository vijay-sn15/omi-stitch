"""
PostgreSQL database connection module without ORM.
Uses psycopg2 for direct database operations.
"""

import os
from contextlib import contextmanager
from typing import Any, Generator, Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor


class DatabaseConfig:
    """Database configuration from environment variables."""
    
    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "5432"))
        self.database = os.getenv("DB_NAME", "omi_stitch")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "postgres")
        self.min_connections = int(os.getenv("DB_MIN_CONN", "1"))
        self.max_connections = int(os.getenv("DB_MAX_CONN", "10"))
    
    @property
    def dsn(self) -> str:
        """Return database connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class Database:
    """
    Database connection pool manager for PostgreSQL.
    No ORM - uses raw SQL queries with psycopg2.
    """
    
    _instance: Optional["Database"] = None
    _pool: Optional[pool.ThreadedConnectionPool] = None
    
    def __new__(cls) -> "Database":
        """Singleton pattern to ensure single connection pool."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._pool is None:
            self.config = DatabaseConfig()
    
    def initialize_pool(self) -> None:
        """Initialize the connection pool."""
        if self._pool is None:
            try:
                self._pool = pool.ThreadedConnectionPool(
                    minconn=self.config.min_connections,
                    maxconn=self.config.max_connections,
                    host=self.config.host,
                    port=self.config.port,
                    database=self.config.database,
                    user=self.config.user,
                    password=self.config.password,
                )
                print(f"✓ Database pool initialized: {self.config.host}:{self.config.port}/{self.config.database}")
            except psycopg2.Error as e:
                print(f"✗ Failed to initialize database pool: {e}")
                raise
    
    def close_pool(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
            print("✓ Database pool closed")
    
    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Get a connection from the pool."""
        if self._pool is None:
            raise RuntimeError("Database pool not initialized. Call initialize_pool() first.")
        
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, dict_cursor: bool = True) -> Generator[psycopg2.extensions.cursor, None, None]:
        """Get a cursor with automatic connection management."""
        cursor_factory = RealDictCursor if dict_cursor else None
        
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()
    
    def execute(self, query: str, params: tuple = None, fetch: bool = False) -> Optional[list[dict[str, Any]]]:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: Whether to fetch results
            
        Returns:
            List of dictionaries if fetch=True, None otherwise
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()
            return None
    
    def execute_many(self, query: str, params_list: list[tuple]) -> None:
        """Execute a query with multiple parameter sets."""
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)
    
    def fetch_one(self, query: str, params: tuple = None) -> Optional[dict[str, Any]]:
        """Execute a query and fetch one result."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()
    
    def fetch_all(self, query: str, params: tuple = None) -> list[dict[str, Any]]:
        """Execute a query and fetch all results."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


# Global database instance
db = Database()


def get_db() -> Database:
    """Dependency injection helper for FastAPI."""
    return db
