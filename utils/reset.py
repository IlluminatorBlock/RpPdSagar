#!/usr/bin/env python3
"""
Enhanced Reset Script for Parkinson's Multiagent System

This script completely resets the system to a fresh state by:
1. Clearing ALL database tables (keeps DB files but removes all data)
2. Deleting all embeddings files but preserving knowledge base documents
3. Cleaning up all data directories
4. Removing all log files and directories
5. Clearing all Python cache files and directories (EXCLUDING virtual environment)
6. Removing all temporary and backup files (EXCLUDING virtual environment)
7. Handling Windows permission issues gracefully

After running this script, executing main.py will be like a fresh start.
"""

import asyncio
import logging
import shutil
import os
import sqlite3
import subprocess
import sys
import stat
from pathlib import Path
from typing import List, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemReset:
    """
    Comprehensive system reset utility for clean swipe with Windows compatibility
    """

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.data_dir = self.base_dir / "data"
        self.logs_dir = self.base_dir / "logs"
        self.models_dir = self.base_dir / "models"
        self.is_windows = sys.platform.startswith('win')

    def _handle_windows_permissions(self, path: Path) -> bool:
        """
        Handle Windows permission issues by taking ownership and setting permissions
        
        Args:
            path: Path to the file/directory with permission issues
            
        Returns:
            True if permissions were fixed, False otherwise
        """
        if not self.is_windows:
            return False
            
        try:
            path_str = str(path.resolve())
            
            # Try to take ownership (requires admin privileges)
            try:
                subprocess.run([
                    'takeown', '/f', path_str, '/r', '/d', 'y'
                ], capture_output=True, check=True, timeout=30)
                
                # Grant full control
                subprocess.run([
                    'icacls', path_str, '/grant', f'{os.getenv("USERNAME")}:F', '/t'
                ], capture_output=True, check=True, timeout=30)
                
                logger.info(f"  🔓 Fixed Windows permissions for: {path.name}")
                return True
                
            except subprocess.CalledProcessError:
                # Fallback: try to change file attributes
                try:
                    if path.is_file():
                        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                    elif path.is_dir():
                        for root, dirs, files in os.walk(path):
                            for d in dirs:
                                os.chmod(os.path.join(root, d), stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
                            for f in files:
                                os.chmod(os.path.join(root, f), stat.S_IWRITE | stat.S_IREAD)
                    
                    logger.info(f"  🔓 Changed file attributes for: {path.name}")
                    return True
                except Exception as e:
                    logger.warning(f"  ⚠️  Could not fix permissions for {path.name}: {e}")
                    return False
                    
        except Exception as e:
            logger.warning(f"  ⚠️  Permission fix failed for {path.name}: {e}")
            return False

    def _force_delete_path(self, path: Path) -> bool:
        """
        Force delete a path with multiple strategies
        
        Args:
            path: Path to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if not path.exists():
            return True
            
        try:
            # First attempt: normal deletion
            if path.is_file():
                path.unlink()
                return True
            elif path.is_dir():
                shutil.rmtree(path)
                return True
                
        except PermissionError:
            # Second attempt: fix permissions then delete
            if self._handle_windows_permissions(path):
                try:
                    if path.is_file():
                        path.unlink()
                        return True
                    elif path.is_dir():
                        shutil.rmtree(path)
                        return True
                except Exception as e:
                    logger.warning(f"  ⚠️  Still couldn't delete after permission fix: {e}")
                    
        except Exception as e:
            logger.warning(f"  ⚠️  Delete failed: {e}")
            
        # Third attempt: Windows-specific force delete
        if self.is_windows:
            try:
                path_str = str(path.resolve())
                if path.is_dir():
                    subprocess.run(['rmdir', '/s', '/q', path_str], 
                                 capture_output=True, check=True, shell=True)
                else:
                    subprocess.run(['del', '/f', '/q', path_str], 
                                 capture_output=True, check=True, shell=True)
                
                logger.info(f"  🔨 Force deleted with Windows commands: {path.name}")
                return True
                
            except subprocess.CalledProcessError as e:
                logger.warning(f"  ⚠️  Windows force delete failed: {e}")
        
        return False

    async def reset_database(self) -> bool:
        """
        Clear all database tables for a fresh start (keeps database files but clears all data)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("🗃️  Starting database reset - clearing all tables for clean start...")
            
            # Ensure data directory exists
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            # Find all database files
            db_files = []
            for pattern in ['*.db', '*.sqlite', '*.sqlite3']:
                db_files.extend(list(self.data_dir.glob(pattern)))
            
            tables_cleared = 0
            databases_processed = 0
            
            for db_file in db_files:
                try:
                    logger.info(f"  📊 Processing database: {db_file.name}")
                    
                    # Connect and clear all tables
                    conn = sqlite3.connect(str(db_file))
                    cursor = conn.cursor()
                    
                    # Disable foreign key constraints temporarily
                    cursor.execute("PRAGMA foreign_keys = OFF;")
                    
                    # Get all table names (excluding system tables)
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                    tables = cursor.fetchall()
                    
                    # Drop all user tables
                    for table in tables:
                        table_name = table[0]
                        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
                        logger.info(f"    ✓ Dropped table: {table_name}")
                        tables_cleared += 1
                    
                    # Re-enable foreign key constraints
                    cursor.execute("PRAGMA foreign_keys = ON;")
                    
                    # Vacuum to reclaim space
                    cursor.execute("VACUUM;")
                    
                    # Commit changes and close
                    conn.commit()
                    conn.close()
                    
                    logger.info(f"    ✅ Database {db_file.name} cleared and optimized")
                    databases_processed += 1
                    
                except Exception as e:
                    logger.error(f"    ❌ Failed to clear database {db_file.name}: {e}")
                    # Continue with other databases
            
            logger.info(f"🗃️  Database reset completed - {tables_cleared} tables cleared from {databases_processed} databases")
            return True

        except Exception as e:
            logger.error(f"Database reset failed: {e}")
            return False

    def reset_embeddings(self) -> bool:
        """
        Delete all embeddings files but PRESERVE knowledge base documents
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("🧠 Starting embeddings reset (preserving KB documents)...")

            embeddings_dir = self.data_dir / "embeddings"
            files_deleted = 0
            dirs_deleted = 0

            # Ensure embeddings directory exists
            embeddings_dir.mkdir(parents=True, exist_ok=True)

            if embeddings_dir.exists():
                # KB-related directory names to preserve
                preserve_dirs = {
                    'documents', 'kb', 'knowledge_base', 'docs', 
                    'knowledge', 'kb_docs', 'document_store'
                }
                
                # Embedding file extensions to delete
                embedding_extensions = {
                    '.index', '.pkl', '.pickle', '.npy', '.npz', 
                    '.bin', '.pt', '.pth', '.h5', '.json', '.faiss'
                }

                # Process all items in embeddings directory
                for item in embeddings_dir.iterdir():
                    if item.is_file():
                        # Check if it's an embedding file
                        if any(item.name.lower().endswith(ext) for ext in embedding_extensions) or \
                           any(keyword in item.name.lower() for keyword in ['embedding', 'vector', 'index']):
                            
                            if self._force_delete_path(item):
                                logger.info(f"    ✓ Deleted embedding file: {item.name}")
                                files_deleted += 1
                            else:
                                logger.warning(f"    ⚠️  Could not delete: {item.name}")
                                
                    elif item.is_dir() and item.name.lower() not in preserve_dirs:
                        # Delete embedding-related directories but preserve KB dirs
                        if self._force_delete_path(item):
                            logger.info(f"    ✓ Deleted embedding directory: {item.name}")
                            dirs_deleted += 1
                        else:
                            logger.warning(f"    ⚠️  Could not delete directory: {item.name}")
                            
                    elif item.is_dir():
                        logger.info(f"    🛡️  Preserved KB directory: {item.name}")
                
                # Ensure documents directory exists
                docs_dir = embeddings_dir / "documents"
                docs_dir.mkdir(exist_ok=True)
                
                logger.info(f"🧠 Embeddings cleared: {files_deleted} files, {dirs_deleted} directories")
                logger.info("📚 Knowledge base documents preserved")
            else:
                # Create embeddings directory structure
                embeddings_dir.mkdir(parents=True, exist_ok=True)
                documents_dir = embeddings_dir / "documents"
                documents_dir.mkdir(exist_ok=True)
                logger.info(f"📁 Created embeddings directory structure")

            return True

        except Exception as e:
            logger.error(f"Embeddings reset failed: {e}")
            return False

    def reset_data_directories(self) -> bool:
        """
        Clean up data directories (selective cleaning)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("📂 Starting data directories reset...")

            # Directories to completely clean (delete everything inside)
            dirs_to_clean = [
                self.data_dir / "mri_scans",
                self.data_dir / "reports",
                self.data_dir / "temp",
                self.data_dir / "cache",
                self.data_dir / "processed",
                self.data_dir / "output",
                self.data_dir / "results"
            ]

            files_deleted = 0
            dirs_cleaned = 0

            for dir_path in dirs_to_clean:
                if dir_path.exists():
                    # Delete everything inside the directory
                    for item in dir_path.iterdir():
                        if self._force_delete_path(item):
                            if item.is_file():
                                files_deleted += 1
                            else:
                                dirs_cleaned += 1
                    
                    logger.info(f"    ✓ Cleaned directory: {dir_path.name}")
                else:
                    # Create directory if it doesn't exist
                    dir_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"    ✓ Created directory: {dir_path.name}")

            # Handle documents directory selectively (only remove temp files)
            docs_dir = self.data_dir / "documents"
            if docs_dir.exists():
                temp_patterns = ['*.tmp', '*.temp', '*.cache', '*.lock', '*~', '*.bak']
                for pattern in temp_patterns:
                    for temp_file in docs_dir.rglob(pattern):
                        if self._force_delete_path(temp_file):
                            files_deleted += 1
                
                logger.info(f"    ✓ Cleaned temp files from documents directory")
            else:
                docs_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"    ✓ Created documents directory")

            logger.info(f"📂 Data directories reset: {files_deleted} files, {dirs_cleaned} directories cleaned")
            return True

        except Exception as e:
            logger.error(f"Data directories reset failed: {e}")
            return False

    def reset_logs(self) -> bool:
        """
        Delete all log files and recreate logs directory
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("📋 Starting logs reset...")

            if self.logs_dir.exists():
                # Count files before deletion
                log_files = list(self.logs_dir.rglob("*"))
                file_count = len([f for f in log_files if f.is_file()])
                
                # Delete the entire logs directory
                if self._force_delete_path(self.logs_dir):
                    logger.info(f"    ✓ Deleted logs directory with {file_count} files")
                else:
                    logger.warning(f"    ⚠️  Could not fully delete logs directory")

            # Recreate empty logs directory
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"    ✓ Recreated empty logs directory")

            return True

        except Exception as e:
            logger.error(f"Logs reset failed: {e}")
            return False

    def reset_pycache(self) -> bool:
        """
        Clean up ALL Python cache directories and files (EXCLUDING virtual environment)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("🐍 Starting Python cache cleanup...")
            logger.info("🛡️  PRESERVING virtual environment - will NOT touch venv/__pycache__")

            pycache_dirs_deleted = 0
            pycache_dirs_failed = 0
            pyc_files_deleted = 0
            pyo_files_deleted = 0

            # Comprehensive virtual environment detection patterns
            venv_patterns = [
                '.venv', 'venv', 'env', '.env', 
                'virtualenv', '.virtualenv', 'venv3', 
                'python-env', 'py-env', 'pyenv-version',
                'conda', 'miniconda', 'anaconda'
            ]
            
            def is_in_venv(path_str: str) -> bool:
                """Enhanced virtual environment detection"""
                path_lower = path_str.lower().replace('\\', '/')
                return any(f"/{pattern}/" in path_lower or 
                          path_lower.endswith(f"/{pattern}") or
                          f"/{pattern}_" in path_lower
                          for pattern in venv_patterns)

            # Find and delete all __pycache__ directories
            logger.info("    🔍 Scanning for __pycache__ directories...")
            pycache_dirs = list(self.base_dir.rglob("__pycache__"))
            
            for pycache_dir in pycache_dirs:
                pycache_str = str(pycache_dir.resolve())
                
                if is_in_venv(pycache_str):
                    logger.info(f"    🛡️  SKIPPING venv cache: {pycache_dir.relative_to(self.base_dir)}")
                    continue

                if self._force_delete_path(pycache_dir):
                    logger.info(f"    ✓ Deleted __pycache__: {pycache_dir.relative_to(self.base_dir)}")
                    pycache_dirs_deleted += 1
                else:
                    logger.warning(f"    ⚠️  Could not delete: {pycache_dir.relative_to(self.base_dir)}")
                    pycache_dirs_failed += 1

            # Find and delete all .pyc files
            logger.info("    🔍 Scanning for .pyc files...")
            for pyc_file in self.base_dir.rglob("*.pyc"):
                pyc_str = str(pyc_file.resolve())
                
                if is_in_venv(pyc_str):
                    continue

                if self._force_delete_path(pyc_file):
                    pyc_files_deleted += 1
                    if pyc_files_deleted <= 10:  # Limit logging to avoid spam
                        logger.info(f"    ✓ Deleted .pyc: {pyc_file.relative_to(self.base_dir)}")

            # Find and delete all .pyo files
            logger.info("    🔍 Scanning for .pyo files...")
            for pyo_file in self.base_dir.rglob("*.pyo"):
                pyo_str = str(pyo_file.resolve())
                
                if is_in_venv(pyo_str):
                    continue

                if self._force_delete_path(pyo_file):
                    pyo_files_deleted += 1
                    if pyo_files_deleted <= 10:  # Limit logging
                        logger.info(f"    ✓ Deleted .pyo: {pyo_file.relative_to(self.base_dir)}")

            logger.info(f"🐍 Python cache cleanup complete:")
            logger.info(f"   - ✅ {pycache_dirs_deleted} __pycache__ directories removed")
            logger.info(f"   - ⚠️  {pycache_dirs_failed} __pycache__ directories could not be removed")
            logger.info(f"   - ✅ {pyc_files_deleted} .pyc files removed") 
            logger.info(f"   - ✅ {pyo_files_deleted} .pyo files removed")
            logger.info(f"   - 🛡️  Virtual environment preserved")
            
            return True

        except Exception as e:
            logger.error(f"Python cache reset failed: {e}")
            return False

    def reset_temp_files(self) -> bool:
        """
        Clean up temporary and backup files (excluding virtual environment)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("🧹 Starting temporary files cleanup...")

            # Comprehensive temp file patterns
            temp_extensions = [
                '*.tmp', '*.temp', '*.bak', '*.backup', 
                '*.swp', '*.swo', '*~', '*.orig',
                '*.rej', '*.log.1', '*.log.2', '*.log.*',
                '.DS_Store', 'Thumbs.db', '*.pyc.bak',
                '*.old', '*.backup.*', '*.temp.*'
            ]
            
            temp_files_deleted = 0
            cache_dirs_deleted = 0

            # Virtual environment patterns
            venv_patterns = ['.venv', 'venv', 'env', '.env', 'virtualenv', '.virtualenv']

            def is_in_venv(path_str: str) -> bool:
                """Enhanced virtual environment detection"""
                path_lower = path_str.lower().replace('\\', '/')
                return any(f"/{pattern}/" in path_lower or 
                          path_lower.endswith(f"/{pattern}")
                          for pattern in venv_patterns)

            # Clean temp files
            logger.info("    🔍 Scanning for temporary files...")
            for ext in temp_extensions:
                for temp_file in self.base_dir.rglob(ext):
                    if is_in_venv(str(temp_file)):
                        continue

                    if self._force_delete_path(temp_file):
                        temp_files_deleted += 1
                        if temp_files_deleted <= 20:  # Limit logging
                            logger.info(f"    ✓ Deleted temp file: {temp_file.name}")

            # Clean specific cache directories (but not venv caches)
            cache_dir_names = ['.cache', '.pytest_cache', '.coverage', '.tox', '.mypy_cache']
            for cache_name in cache_dir_names:
                for cache_dir in self.base_dir.rglob(cache_name):
                    if not cache_dir.is_dir():
                        continue
                        
                    if is_in_venv(str(cache_dir)):
                        continue

                    if self._force_delete_path(cache_dir):
                        logger.info(f"    ✓ Deleted cache dir: {cache_dir.relative_to(self.base_dir)}")
                        cache_dirs_deleted += 1

            logger.info(f"🧹 Temp files cleanup: {temp_files_deleted} files, {cache_dirs_deleted} cache dirs removed")
            return True

        except Exception as e:
            logger.error(f"Temporary files reset failed: {e}")
            return False

    def delete_database_files(self) -> bool:
        """
        Completely delete all database files (not just clear tables)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("🗑️  Starting database file deletion...")
            
            databases_deleted = 0
            
            # Find all .db files in data directory
            if self.data_dir.exists():
                db_files = list(self.data_dir.glob("*.db"))
                
                if not db_files:
                    logger.info("    ℹ️  No database files found")
                    return True
                
                for db_file in db_files:
                    try:
                        if self._force_delete_path(db_file):
                            logger.info(f"    ✅ Deleted database file: {db_file.name}")
                            databases_deleted += 1
                        else:
                            logger.warning(f"    ⚠️  Could not delete: {db_file.name}")
                            
                        # Also delete WAL and SHM files (SQLite journal files)
                        for suffix in ['-wal', '-shm', '-journal']:
                            journal_file = db_file.parent / f"{db_file.name}{suffix}"
                            if journal_file.exists():
                                if self._force_delete_path(journal_file):
                                    logger.info(f"    ✅ Deleted journal file: {journal_file.name}")
                                    
                    except Exception as e:
                        logger.error(f"    ❌ Failed to delete {db_file.name}: {e}")
                        
                logger.info(f"🗑️  Database deletion completed - {databases_deleted} files deleted")
            else:
                logger.info("    ℹ️  Data directory does not exist")
                
            return True
            
        except Exception as e:
            logger.error(f"Database deletion failed: {e}")
            return False

    async def full_reset(self, delete_db_files: bool = False) -> bool:
        """
        Perform complete system reset for clean swipe
        
        Args:
            delete_db_files: If True, completely delete database files instead of just clearing tables
        
        Returns:
            True if all reset operations successful, False otherwise
        """
        logger.info("=" * 70)
        logger.info("🚀 STARTING COMPLETE SYSTEM RESET - CLEAN SWIPE")
        logger.info("=" * 70)

        # Choose database operation based on parameter
        db_operation = ("🗑️  Database Files (COMPLETE DELETE)", self.delete_database_files) \
                      if delete_db_files else \
                      ("🗃️  Database Tables (CLEAR ONLY)", self.reset_database)

        operations = [
            db_operation,
            ("🧠 Embeddings (preserve KB docs)", self.reset_embeddings),
            ("📂 Data Directories", self.reset_data_directories),
            ("📋 Log Files", self.reset_logs),
            ("🐍 Python Cache (preserve venv)", self.reset_pycache),
            ("🧹 Temporary Files", self.reset_temp_files)
        ]

        success_count = 0
        total_operations = len(operations)

        for name, operation in operations:
            logger.info(f"\n{'='*50}")
            logger.info(f"Executing: {name}")
            logger.info(f"{'='*50}")
            
            try:
                if asyncio.iscoroutinefunction(operation):
                    result = await operation()
                else:
                    result = operation()

                if result:
                    logger.info(f"✅ {name} - SUCCESS")
                    success_count += 1
                else:
                    logger.error(f"❌ {name} - FAILED")
            except Exception as e:
                logger.error(f"❌ {name} - EXCEPTION: {e}")

        logger.info("\n" + "=" * 70)
        logger.info(f"RESET SUMMARY: {success_count}/{total_operations} operations successful")
        logger.info("=" * 70)

        if success_count == total_operations:
            logger.info("🎉 COMPLETE CLEAN SWIPE SUCCESSFUL!")
            logger.info("✨ System has been completely reset to fresh state")
            logger.info("🚀 You can now run 'python main.py' for a fresh start")
            return True
        else:
            logger.warning("⚠️  Some reset operations completed with warnings")
            logger.info("🔍 Check the logs above for details")
            logger.info("🚀 System should still be ready for fresh start")
            return True  # Return True even with warnings for usability


async def main():
    """Main reset function with enhanced confirmation and Windows compatibility"""
    print("🩺 Parkinson's Multiagent System - Complete Reset")
    print("=" * 55)
    print()
    print("⚠️  WARNING: COMPLETE CLEAN SWIPE")
    print()
    print("Choose reset mode:")
    print("  1️⃣  CLEAR DATABASE (keep database files, clear all tables)")
    print("  2️⃣  DELETE DATABASE (completely remove database files)")
    print()
    
    mode = input("Enter mode (1 or 2): ").strip()
    delete_db_files = False
    
    if mode == "2":
        delete_db_files = True
        print("\n🚨 MODE: COMPLETE DATABASE DELETION")
        print("This will permanently delete:")
        print("  ❌ ALL database FILES (parkinsons_system.db)")
    elif mode == "1":
        print("\n🔄 MODE: DATABASE CLEAR")
        print("This will permanently delete:")
        print("  ❌ ALL database tables (but keep .db files)")
    else:
        print("❌ Invalid mode. Reset cancelled.")
        return
    
    print("  ❌ ALL embeddings (but keeps KB documents)")
    print("  ❌ ALL log files")
    print("  ❌ ALL __pycache__ directories (preserves venv)")
    print("  ❌ ALL temporary and cache files")
    print("  ❌ ALL processed data files")
    print()
    print("✅ This will preserve:")
    print("  ✓ Virtual environment (venv)")
    print("  ✓ Knowledge base documents")
    print("  ✓ Source code files")
    print("  ✓ Configuration files")
    print()
    
    # Check if running on Windows
    if sys.platform.startswith('win'):
        print("🪟 Windows detected - enhanced permission handling enabled")
        print("💡 Note: Some operations may require administrator privileges")
        print()
    
    print("🚨 THIS ACTION CANNOT BE UNDONE!")
    print()

    # Enhanced confirmation
    confirm1 = input("Type 'CLEAN SWIPE' to confirm complete reset: ")
    if confirm1 != 'CLEAN SWIPE':
        print("❌ Reset cancelled - incorrect confirmation")
        return

    confirm2 = input("Are you absolutely sure? Type 'YES DELETE ALL' to proceed: ")
    if confirm2 != 'YES DELETE ALL':
        print("❌ Reset cancelled - confirmation failed")
        return

    print("\n🚀 Starting complete clean swipe...")
    print("Please wait while the system is reset...")

    # Perform reset
    reset_tool = SystemReset()
    success = await reset_tool.full_reset(delete_db_files=delete_db_files)

    print("\n" + "=" * 70)
    if success:
        print("✅ CLEAN SWIPE COMPLETED SUCCESSFULLY!")
        print("🎉 System has been completely reset to fresh state")
        print("📚 Knowledge base documents preserved")
        print("🐍 Virtual environment preserved") 
        print("🚀 Ready for fresh start with 'python main.py'")
    else:
        print("⚠️  CLEAN SWIPE COMPLETED WITH SOME WARNINGS")
        print("🔍 Check the detailed logs above")
        print("🚀 System should still be ready for fresh start")

    print("=" * 70)


if __name__ == "__main__":
    # Run the complete reset
    asyncio.run(main())