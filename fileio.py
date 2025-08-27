"""
File I/O module for MCP workspace operations.

This module provides functionality to store and manage text files in a 
configured workspace directory, allowing Claude to persist text content
across sessions in a user-controlled location.
"""

import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class WorkspaceManager:
    """
    Manages file operations in a configured workspace directory.
    
    The workspace location is configured via FIRST_MCP_WORKSPACE_PATH 
    environment variable, falling back to current directory.
    """
    
    def __init__(self):
        """Initialize workspace manager with environment-configured path."""
        # Get workspace directory from environment variable
        self.workspace_path = os.getenv('FIRST_MCP_WORKSPACE_PATH', '.')
        
        # Ensure the workspace directory exists
        if self.workspace_path != '.' and not os.path.exists(self.workspace_path):
            os.makedirs(self.workspace_path, exist_ok=True)
        
        # Create a metadata file to track workspace files
        self.metadata_file = os.path.join(self.workspace_path, '.workspace_metadata.json')
        self._ensure_metadata_file()
    
    def _ensure_metadata_file(self) -> None:
        """Ensure the metadata file exists."""
        if not os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load workspace metadata."""
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save workspace metadata."""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save metadata: {e}")
    
    def _update_file_metadata(self, filename: str, description: str = "", tags: List[str] = None, language: str = "") -> None:
        """Update metadata for a file."""
        metadata = self._load_metadata()
        current_time = datetime.now().isoformat()
        
        if filename not in metadata:
            metadata[filename] = {
                "created_at": current_time,
                "description": description,
                "tags": tags or [],
                "language": language,
                "size_bytes": 0,
                "last_modified": current_time
            }
        else:
            metadata[filename]["last_modified"] = current_time
            if description:
                metadata[filename]["description"] = description
            if tags is not None:
                metadata[filename]["tags"] = tags
            if language:
                metadata[filename]["language"] = language
        
        # Update file size
        file_path = os.path.join(self.workspace_path, filename)
        if os.path.exists(file_path):
            metadata[filename]["size_bytes"] = os.path.getsize(file_path)
        
        self._save_metadata(metadata)
    
    def store_text_file(self, filename: str, content: str, description: str = "", 
                       tags: List[str] = None, language: str = "", overwrite: bool = False) -> Dict[str, Any]:
        """
        Store a text file in the workspace.
        
        Args:
            filename: Name of the file to store
            content: Text content to store
            description: Optional description of the file
            tags: Optional list of tags for categorization
            language: Programming language or file type (e.g., 'python', 'javascript', 'markdown')
            overwrite: Whether to overwrite existing files (default: False)
            
        Returns:
            Dictionary with operation result and file information
        """
        # Validate filename (basic security)
        if not filename or '..' in filename or filename.startswith('/'):
            return {"error": "Invalid filename. Avoid path traversal characters."}
        
        file_path = os.path.join(self.workspace_path, filename)
        
        # Check if file exists and overwrite is not allowed
        if os.path.exists(file_path) and not overwrite:
            return {
                "error": f"File '{filename}' already exists. Use overwrite=True to replace it."
            }
        
        try:
            # Write the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Update metadata
            self._update_file_metadata(filename, description, tags, language)
            
            return {
                "success": True,
                "filename": filename,
                "path": file_path,
                "size_bytes": len(content.encode('utf-8')),
                "description": description,
                "tags": tags or [],
                "language": language,
                "message": f"File '{filename}' stored successfully in workspace"
            }
            
        except Exception as e:
            return {"error": f"Failed to store file: {str(e)}"}
    
    def read_text_file(self, filename: str) -> Dict[str, Any]:
        """
        Read a text file from the workspace.
        
        Args:
            filename: Name of the file to read
            
        Returns:
            Dictionary with file content and metadata
        """
        # Validate filename
        if not filename or '..' in filename or filename.startswith('/'):
            return {"error": "Invalid filename. Avoid path traversal characters."}
        
        file_path = os.path.join(self.workspace_path, filename)
        
        if not os.path.exists(file_path):
            return {"error": f"File '{filename}' not found in workspace"}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metadata = self._load_metadata()
            file_metadata = metadata.get(filename, {})
            
            return {
                "success": True,
                "filename": filename,
                "content": content,
                "size_bytes": len(content.encode('utf-8')),
                "description": file_metadata.get("description", ""),
                "tags": file_metadata.get("tags", []),
                "language": file_metadata.get("language", ""),
                "created_at": file_metadata.get("created_at", ""),
                "last_modified": file_metadata.get("last_modified", "")
            }
            
        except Exception as e:
            return {"error": f"Failed to read file: {str(e)}"}
    
    def list_workspace_files(self, filter_tags: List[str] = None) -> Dict[str, Any]:
        """
        List all files in the workspace with their metadata.
        
        Args:
            filter_tags: Optional list of tags to filter by
            
        Returns:
            Dictionary with list of files and their information
        """
        try:
            metadata = self._load_metadata()
            files = []
            
            for item in os.listdir(self.workspace_path):
                item_path = os.path.join(self.workspace_path, item)
                
                # Skip directories and metadata file
                if os.path.isdir(item_path) or item == '.workspace_metadata.json':
                    continue
                
                file_metadata = metadata.get(item, {})
                file_tags = file_metadata.get("tags", [])
                
                # Apply tag filter if specified
                if filter_tags and not any(tag in file_tags for tag in filter_tags):
                    continue
                
                files.append({
                    "filename": item,
                    "size_bytes": os.path.getsize(item_path),
                    "description": file_metadata.get("description", ""),
                    "tags": file_tags,
                    "language": file_metadata.get("language", ""),
                    "created_at": file_metadata.get("created_at", ""),
                    "last_modified": file_metadata.get("last_modified", "")
                })
            
            # Sort by last modified (newest first)
            files.sort(key=lambda x: x["last_modified"], reverse=True)
            
            return {
                "success": True,
                "workspace_path": self.workspace_path,
                "total_files": len(files),
                "files": files,
                "filter_applied": filter_tags is not None,
                "filter_tags": filter_tags or []
            }
            
        except Exception as e:
            return {"error": f"Failed to list files: {str(e)}"}
    
    def delete_workspace_file(self, filename: str) -> Dict[str, Any]:
        """
        Delete a file from the workspace.
        
        Args:
            filename: Name of the file to delete
            
        Returns:
            Dictionary with operation result
        """
        # Validate filename
        if not filename or '..' in filename or filename.startswith('/'):
            return {"error": "Invalid filename. Avoid path traversal characters."}
        
        if filename == '.workspace_metadata.json':
            return {"error": "Cannot delete workspace metadata file"}
        
        file_path = os.path.join(self.workspace_path, filename)
        
        if not os.path.exists(file_path):
            return {"error": f"File '{filename}' not found in workspace"}
        
        try:
            # Delete the file
            os.remove(file_path)
            
            # Remove from metadata
            metadata = self._load_metadata()
            if filename in metadata:
                del metadata[filename]
                self._save_metadata(metadata)
            
            return {
                "success": True,
                "filename": filename,
                "message": f"File '{filename}' deleted successfully from workspace"
            }
            
        except Exception as e:
            return {"error": f"Failed to delete file: {str(e)}"}
    
    def update_file_metadata(self, filename: str, description: str = None, 
                           tags: List[str] = None, language: str = None) -> Dict[str, Any]:
        """
        Update metadata for an existing file.
        
        Args:
            filename: Name of the file to update
            description: New description (None to keep existing)
            tags: New tags list (None to keep existing)
            language: Programming language or file type (None to keep existing)
            
        Returns:
            Dictionary with operation result
        """
        # Validate filename
        if not filename or '..' in filename or filename.startswith('/'):
            return {"error": "Invalid filename. Avoid path traversal characters."}
        
        file_path = os.path.join(self.workspace_path, filename)
        
        if not os.path.exists(file_path):
            return {"error": f"File '{filename}' not found in workspace"}
        
        try:
            metadata = self._load_metadata()
            current_time = datetime.now().isoformat()
            
            if filename not in metadata:
                metadata[filename] = {
                    "created_at": current_time,
                    "description": "",
                    "tags": [],
                    "language": "",
                    "size_bytes": os.path.getsize(file_path),
                    "last_modified": current_time
                }
            
            # Update fields if provided
            if description is not None:
                metadata[filename]["description"] = description
            if tags is not None:
                metadata[filename]["tags"] = tags
            if language is not None:
                metadata[filename]["language"] = language
            
            metadata[filename]["last_modified"] = current_time
            self._save_metadata(metadata)
            
            return {
                "success": True,
                "filename": filename,
                "updated_description": description is not None,
                "updated_tags": tags is not None,
                "updated_language": language is not None,
                "new_metadata": metadata[filename]
            }
            
        except Exception as e:
            return {"error": f"Failed to update metadata: {str(e)}"}
    
    def get_workspace_info(self) -> Dict[str, Any]:
        """
        Get information about the workspace.
        
        Returns:
            Dictionary with workspace information and statistics
        """
        try:
            metadata = self._load_metadata()
            
            # Count files and calculate total size
            total_files = 0
            total_size = 0
            all_tags = []
            
            for item in os.listdir(self.workspace_path):
                item_path = os.path.join(self.workspace_path, item)
                
                if os.path.isfile(item_path) and item != '.workspace_metadata.json':
                    total_files += 1
                    total_size += os.path.getsize(item_path)
                    
                    file_metadata = metadata.get(item, {})
                    all_tags.extend(file_metadata.get("tags", []))
            
            # Count unique tags
            unique_tags = list(set(all_tags))
            tag_counts = {}
            for tag in all_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            return {
                "success": True,
                "workspace_path": self.workspace_path,
                "workspace_configured": os.getenv('FIRST_MCP_WORKSPACE_PATH') is not None,
                "total_files": total_files,
                "total_size_bytes": total_size,
                "unique_tags": unique_tags,
                "tag_usage": dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)),
                "metadata_file": self.metadata_file
            }
            
        except Exception as e:
            return {"error": f"Failed to get workspace info: {str(e)}"}


def test_workspace_manager():
    """Test the workspace manager functionality."""
    print("Testing Workspace Manager...")
    
    # Use a test directory
    test_dir = "test_workspace"
    os.environ['FIRST_MCP_WORKSPACE_PATH'] = test_dir
    
    try:
        workspace = WorkspaceManager()
        
        # Test storing files
        print("Storing test files...")
        result1 = workspace.store_text_file(
            "notes.txt", 
            "These are my test notes.\nLine 2 of notes.",
            description="Test notes file",
            tags=["notes", "testing"]
        )
        print(f"Store result: {result1.get('message', result1.get('error'))}")
        
        result2 = workspace.store_text_file(
            "code.py",
            "print('Hello World')\n# This is a test script",
            description="Python test script",
            tags=["code", "python", "testing"],
            language="python"
        )
        print(f"Store result: {result2.get('message', result2.get('error'))}")
        
        # Test listing files
        print("\nListing all files:")
        file_list = workspace.list_workspace_files()
        if file_list["success"]:
            for file_info in file_list["files"]:
                print(f"- {file_info['filename']}: {file_info['description']} "
                      f"(tags: {file_info['tags']}, language: {file_info['language']})")
        
        # Test reading a file
        print("\nReading notes.txt:")
        read_result = workspace.read_text_file("notes.txt")
        if read_result["success"]:
            print(f"Content: {read_result['content'][:50]}...")
        
        # Test workspace info
        print("\nWorkspace info:")
        info = workspace.get_workspace_info()
        if info["success"]:
            print(f"Total files: {info['total_files']}")
            print(f"Unique tags: {info['unique_tags']}")
        
    finally:
        # Clean up test directory
        import shutil
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        print(f"\nCleaned up test directory: {test_dir}")


if __name__ == "__main__":
    test_workspace_manager()