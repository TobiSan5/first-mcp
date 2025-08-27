"""
Generic TinyDB database tools for working with custom databases.
"""

import uuid
import os
import glob
from datetime import datetime
from typing import Dict, Any
from tinydb import Query

from .database import get_custom_tinydb


def tinydb_create_database(db_name: str, description: str = "") -> Dict[str, Any]:
    """
    Create a new TinyDB database file in the data folder.
    
    Perfect for expense tracking, research notes, project data, etc.
    Much faster than LLM-based JSON file updates.
    
    Args:
        db_name: Name of the database (will add .json if needed)
        description: Optional description of the database purpose
        
    Returns:
        Dictionary with database creation confirmation
    """
    try:
        # Create the database (this initializes the file)
        custom_db = get_custom_tinydb(db_name)
        
        # Store metadata about the database
        metadata_table = custom_db.table('_metadata')
        metadata_table.insert({
            "database_name": db_name,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "created_by": "tinydb_create_database"
        })
        
        return {
            "success": True,
            "database_name": db_name,
            "database_file": f"{db_name}.json" if not db_name.endswith('.json') else db_name,
            "description": description,
            "message": "Database created successfully"
        }
        
    except Exception as e:
        return {"error": str(e)}


def tinydb_store_data(db_name: str, table: str, data: Dict[str, Any], record_id: str = "") -> Dict[str, Any]:
    """
    Store data in any TinyDB database in the data folder.
    
    Perfect for expense tracking, research notes, project data, etc.
    Much faster than LLM-based JSON file updates.
    
    Args:
        db_name: Name of the database file
        table: Table name within the database
        data: Data to store (dictionary)
        record_id: Optional specific ID for the record
        
    Returns:
        Dictionary with storage confirmation and record ID
    """
    try:
        custom_db = get_custom_tinydb(db_name)
        try:
            table_db = custom_db.table(table)
            Record = Query()
            
            if record_id:
                # Update existing record or create with specific ID
                existing = table_db.search(Record.id == record_id)
                if existing:
                    table_db.update(data, Record.id == record_id)
                    action = "updated"
                else:
                    data['id'] = record_id
                    table_db.insert(data)
                    action = "created"
            else:
                # Create new record with generated ID
                record_id = str(uuid.uuid4())
                data['id'] = record_id
                table_db.insert(data)
                action = "created"
            
            custom_db.close()
            
            return {
                "success": True,
                "database": db_name,
                "table": table,
                "record_id": record_id,
                "action": action,
                "data": data
            }
            
        except Exception as e:
            custom_db.close()
            raise e
        
    except Exception as e:
        return {"error": str(e)}


def tinydb_query_data(db_name: str, table: str, query_conditions: Dict[str, Any] = {}, 
                     limit: int = 100, sort_by: str = "", reverse_sort: bool = True) -> Dict[str, Any]:
    """
    Query data from any TinyDB database in the data folder.
    
    Args:
        db_name: Name of the database file
        table: Table name to query
        query_conditions: Dictionary of field:value conditions
        limit: Maximum number of results
        sort_by: Field to sort by
        reverse_sort: Sort in descending order (default: True)
        
    Returns:
        Dictionary with query results
    """
    try:
        custom_db = get_custom_tinydb(db_name)
        try:
            table_db = custom_db.table(table)
            Record = Query()
            
            # Build query
            if query_conditions:
                query = None
                for field, value in query_conditions.items():
                    condition = Record[field] == value
                    if query is None:
                        query = condition
                    else:
                        query = query & condition
                        
                results = table_db.search(query)
            else:
                results = table_db.all()
            
            # Sort results if specified
            if sort_by and results:
                results.sort(key=lambda x: x.get(sort_by, ''), reverse=reverse_sort)
            
            # Apply limit
            limited_results = results[:limit]
            
            custom_db.close()
            
            return {
                "success": True,
                "database": db_name,
                "table": table,
                "query_conditions": query_conditions,
                "results": limited_results,
                "total_found": len(results),
                "returned_count": len(limited_results)
            }
            
        except Exception as e:
            custom_db.close()
            raise e
        
    except Exception as e:
        return {"error": str(e)}


def tinydb_update_data(db_name: str, table: str, record_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update specific fields in an existing record in any TinyDB database.
    
    Args:
        db_name: Name of the database file
        table: Table name
        record_id: ID of the record to update
        updates: Dictionary of field:value updates
        
    Returns:
        Dictionary with update confirmation
    """
    try:
        custom_db = get_custom_tinydb(db_name)
        try:
            table_db = custom_db.table(table)
            Record = Query()
            
            # Perform update
            updated = table_db.update(updates, Record.id == record_id)
            
            if updated:
                # Get updated record
                updated_record = table_db.search(Record.id == record_id)[0]
                custom_db.close()
                return {
                    "success": True,
                    "database": db_name,
                    "table": table,
                    "record_id": record_id,
                    "updated_fields": list(updates.keys()),
                    "updated_record": updated_record
                }
            else:
                custom_db.close()
                return {"error": f"No record found with ID {record_id} in table {table}"}
                
        except Exception as e:
            custom_db.close()
            raise e
            
    except Exception as e:
        return {"error": str(e)}


def tinydb_delete_data(db_name: str, table: str, record_id: str = "", query_conditions: Dict[str, Any] = {}) -> Dict[str, Any]:
    """
    Delete records from any TinyDB database in the data folder.
    
    Args:
        db_name: Name of the database file
        table: Table name
        record_id: ID of specific record to delete (optional)
        query_conditions: Conditions for bulk deletion (optional)
        
    Returns:
        Dictionary with deletion confirmation
    """
    try:
        custom_db = get_custom_tinydb(db_name)
        try:
            table_db = custom_db.table(table)
            Record = Query()
            
            if record_id:
                # Delete specific record by ID
                deleted_count = len(table_db.remove(Record.id == record_id))
                operation_type = "single_record"
            elif query_conditions:
                # Delete records matching conditions
                query = None
                for field, value in query_conditions.items():
                    condition = Record[field] == value
                    if query is None:
                        query = condition
                    else:
                        query = query & condition
                
                deleted_count = len(table_db.remove(query))
                operation_type = "bulk_deletion"
            else:
                custom_db.close()
                return {"error": "Must provide either record_id or query_conditions"}
            
            custom_db.close()
            
            return {
                "success": True,
                "database": db_name,
                "table": table,
                "operation_type": operation_type,
                "deleted_count": deleted_count
            }
            
        except Exception as e:
            custom_db.close()
            raise e
        
    except Exception as e:
        return {"error": str(e)}


def tinydb_list_databases() -> Dict[str, Any]:
    """
    List all TinyDB databases in the data folder.
    
    Shows dedicated databases (memories, tags, categories) and user-created databases.
    
    Returns:
        Dictionary with all available databases and their information
    """
    try:
        base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
        
        # Find all JSON files in data path
        json_pattern = os.path.join(base_path, '*.json')
        json_files = glob.glob(json_pattern)
        
        databases = []
        for json_file in json_files:
            filename = os.path.basename(json_file)
            
            # Skip legacy files and workspace metadata
            if filename.startswith('memory_') or filename == '.workspace_metadata.json':
                continue
                
            db_info = {
                "database_name": filename.replace('.json', ''),
                "database_file": filename,
                "file_size": os.path.getsize(json_file),
                "modified_time": os.path.getmtime(json_file)
            }
            
            # Add type classification
            if filename in ['tinydb_memories.json', 'tinydb_tags.json', 'tinydb_categories.json']:
                db_info["type"] = "dedicated_memory_system"
            elif filename == 'mcp_database.json':
                db_info["type"] = "legacy_generic_database"
            else:
                db_info["type"] = "user_created_database"
                
            # Try to get table count
            try:
                temp_db = get_custom_tinydb(filename.replace('.json', ''))
                db_info["table_count"] = len(temp_db.tables())
                temp_db.close()
            except:
                db_info["table_count"] = 0
                
            databases.append(db_info)
        
        # Sort by type and name
        databases.sort(key=lambda x: (x["type"], x["database_name"]))
        
        return {
            "success": True,
            "databases": databases,
            "total_databases": len(databases),
            "data_path": base_path
        }
        
    except Exception as e:
        return {"error": str(e)}


def tinydb_get_database_info(db_name: str) -> Dict[str, Any]:
    """
    Get comprehensive information about a specific TinyDB database.
    
    Args:
        db_name: Name of the database to inspect
        
    Returns:
        Dictionary with detailed database information
    """
    try:
        custom_db = get_custom_tinydb(db_name)
        
        # Get basic database info
        base_path = os.getenv('FIRST_MCP_DATA_PATH', os.getcwd())
        db_file = f"{db_name}.json" if not db_name.endswith('.json') else db_name
        db_path = os.path.join(base_path, db_file)
        
        info = {
            "database_name": db_name,
            "database_file": db_file,
            "database_path": db_path,
            "file_exists": os.path.exists(db_path)
        }
        
        if info["file_exists"]:
            info["file_size"] = os.path.getsize(db_path)
            info["file_size_mb"] = round(info["file_size"] / (1024 * 1024), 2)
            info["modified_time"] = datetime.fromtimestamp(os.path.getmtime(db_path)).isoformat()
        
        # Get table information
        tables = []
        total_records = 0
        
        for table_name in custom_db.tables():
            table_db = custom_db.table(table_name)
            record_count = len(table_db.all())
            total_records += record_count
            
            table_info = {
                "table_name": table_name,
                "record_count": record_count
            }
            
            # Get sample record if available
            if record_count > 0:
                sample_record = table_db.all()[0]
                # Remove large values for preview
                sample_preview = {}
                for key, value in sample_record.items():
                    if isinstance(value, str) and len(value) > 100:
                        sample_preview[key] = value[:97] + "..."
                    else:
                        sample_preview[key] = value
                table_info["sample_record"] = sample_preview
                
            tables.append(table_info)
        
        custom_db.close()
        
        info.update({
            "tables": tables,
            "table_count": len(tables),
            "total_records": total_records
        })
        
        return {
            "success": True,
            **info
        }
        
    except Exception as e:
        return {"error": str(e)}