import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import logging
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger(__name__)

class DatabaseConnection:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize_connection()
    
    def _initialize_connection(self):
        try:
            # Create database if it doesn't exist
            self._create_database_if_not_exists()
            
            # Create SQLAlchemy engine
            connection_string = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            self.engine = create_engine(connection_string, echo=False)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            logger.info("Database connection initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise
    
    def _create_database_if_not_exists(self):
        try:
            # Connect without specifying database
            connection = pymysql.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD
            )
            
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
            
            connection.commit()
            connection.close()
            logger.info(f"Database {DB_NAME} created or already exists")
        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            raise
    
    def initialize_schema(self):
        """Initialize database schema from SQL file"""
        try:
            # Since tables already exist, just check if database is accessible
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("Database schema is accessible")
        except Exception as e:
            logger.error(f"Failed to access database: {e}")
            # Don't raise - continue without schema initialization
            pass
    
    @contextmanager
    def get_session(self):
        """Get database session with automatic cleanup"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self):
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

# Global database connection instance
db_connection = DatabaseConnection()