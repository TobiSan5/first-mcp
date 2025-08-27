"""
TinyDB database connection management for memory system.
"""

import os
from tinydb import TinyDB
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware


def get_memory_tinydb():
    """Get TinyDB instance for memories."""
    base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
    db_path = os.path.join(base_path, 'tinydb_memories.json')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return TinyDB(db_path, storage=CachingMiddleware(JSONStorage))


def get_tags_tinydb():
    """Get TinyDB instance for tags."""
    base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
    db_path = os.path.join(base_path, 'tinydb_tags.json')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return TinyDB(db_path, storage=CachingMiddleware(JSONStorage))


def get_categories_tinydb():
    """Get TinyDB instance for categories."""
    base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
    db_path = os.path.join(base_path, 'tinydb_categories.json')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return TinyDB(db_path, storage=CachingMiddleware(JSONStorage))


def get_custom_tinydb(db_name: str):
    """Get TinyDB instance for user-specified database."""
    base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
    # Add .json extension if not present
    if not db_name.endswith('.json'):
        db_name = f'{db_name}.json'
    db_path = os.path.join(base_path, db_name)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return TinyDB(db_path, storage=CachingMiddleware(JSONStorage))