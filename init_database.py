#!/usr/bin/env python3
"""
Database Initialization Script
Run this ONCE to set up the database and create embeddings
Separate from main.py to prevent automatic embeddings creation
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import DatabaseManager
from config import Config
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/database_init.log')
    ]
)
logger = logging.getLogger(__name__)

async def initialize_database_with_embeddings():
    """Initialize database and create embeddings - run this once during setup"""
    print("🚀 DATABASE INITIALIZATION WITH EMBEDDINGS")
    print("=" * 60)
    print("⚠️  This will initialize the database and create embeddings")
    print("⚠️  Only run this during initial setup or when rebuilding")
    print()
    
    try:
        # Get configuration
        config = Config()
        
        # Initialize database
        db_config = config.database_config
        db_url = db_config['url']
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
        else:
            db_path = db_url
        
        print(f"📂 Database path: {db_path}")
        
        # Initialize database manager
        database = DatabaseManager(db_path)
        
        # Initialize database (this will create embeddings)
        print("\n🔧 Initializing database tables and embeddings...")
        await database.init_database(initialize_embeddings=True)
        
        # Check embeddings status
        embeddings_manager = database.get_embeddings_manager()
        if embeddings_manager:
            print(f"\n✅ Embeddings manager initialized successfully")
            
            # Load existing or create embeddings from documents
            print("📚 Loading/Creating embeddings from documents...")
            result = await embeddings_manager.load_documents_from_directory()
            
            # Check if we have embeddings
            if hasattr(embeddings_manager, 'id_to_text') and embeddings_manager.id_to_text:
                chunk_count = len(embeddings_manager.id_to_text)
                print(f"📊 Found {chunk_count} existing embeddings")
            else:
                print("📄 No existing embeddings found - will create from documents")
                
                # Load documents
                documents_dir = Path(config.embeddings_config.get('documents_dir', 'data/documents'))
                if documents_dir.exists():
                    pdf_files = list(documents_dir.glob('*.pdf'))
                    txt_files = list(documents_dir.glob('*.txt'))
                    all_files = pdf_files + txt_files
                    
                    if all_files:
                        print(f"📖 Processing {len(all_files)} documents...")
                        success_count = 0
                        
                        for file_path in all_files:
                            print(f"   Processing: {file_path.name}")
                            try:
                                result = await embeddings_manager.load_document(str(file_path))
                                if result:
                                    success_count += 1
                                    print(f"   ✅ Success")
                                else:
                                    print(f"   ⚠️ Failed")
                            except Exception as e:
                                print(f"   ❌ Error: {e}")
                        
                        print(f"\n📊 Successfully processed {success_count}/{len(all_files)} documents")
                        
                        # Save embeddings
                        print("💾 Saving embeddings...")
                        await embeddings_manager.save_embeddings()
                        
                        # Build index
                        print("🔍 Building search index...")
                        await embeddings_manager.build_index()
                        
                        # Final count
                        final_count = len(getattr(embeddings_manager, 'id_to_text', {}))
                        print(f"✅ Total embeddings created: {final_count}")
                    else:
                        print(f"⚠️ No documents found in {documents_dir}")
                        print(f"   Add PDF or TXT files to create embeddings")
                else:
                    print(f"⚠️ Documents directory not found: {documents_dir}")
        else:
            print("❌ Failed to initialize embeddings manager")
        
        print(f"\n🎉 DATABASE INITIALIZATION COMPLETE!")
        print(f"✅ Database tables created")
        print(f"✅ Embeddings manager initialized") 
        print(f"✅ Ready for main.py to run without creating embeddings")
        
    except Exception as e:
        print(f"\n❌ Database initialization failed: {e}")
        logger.error(f"Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def setup_admin_user():
    """Create default admin user using the authentication system"""
    print(f"\n👤 CREATING DEFAULT ADMIN USER")
    print("=" * 40)
    
    try:
        from config import config
        from auth.authentication import AuthenticationManager
        
        db_config = config.database_config
        db_url = db_config['url']
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
        else:
            db_path = db_url
        
        database = DatabaseManager(db_path)
        auth_manager = AuthenticationManager(database)
        
        # Initialize the authentication system (this will create default admin if needed)
        await auth_manager.initialize()
        
        print(f"✅ Admin user created successfully")
        print(f"   Username: admin")
        print(f"   Password: Admin123")
        print(f"   ⚠️  Change password in production!")
            
    except Exception as e:
        print(f"❌ Admin user creation failed: {e}")

if __name__ == "__main__":
    print("🏥 PARKINSON'S MULTIAGENT SYSTEM - DATABASE SETUP")
    print("=" * 80)
    
    # Ask for confirmation
    response = input("\nDo you want to initialize the database and create embeddings? (y/N): ")
    if response.lower() not in ['y', 'yes']:
        print("❌ Database initialization cancelled")
        sys.exit(0)
    
    # Run initialization
    success = asyncio.run(initialize_database_with_embeddings())
    
    if success:
        # Setup admin user
        response = input("\nDo you want to create a default admin user? (y/N): ")
        if response.lower() in ['y', 'yes']:
            asyncio.run(setup_admin_user())
        
        print(f"\n🎯 NEXT STEPS:")
        print(f"   1. ✅ Database is ready")
        print(f"   2. 🚀 Run: python main.py")
        print(f"   3. 🔑 Login with admin credentials")
        print(f"   4. 📊 Test the system functionality")
    else:
        print(f"\n❌ Setup failed - check logs for details")
        sys.exit(1)