#!/usr/bin/env python3
"""
Fix Empty Doctor IDs in Database

This script identifies and fixes doctor records with empty or null doctor_ids.
Run this to clean up database issues caused by earlier registration bugs.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import DatabaseManager
from config import config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def fix_empty_doctor_ids():
    """Find and fix doctors with empty doctor_ids"""
    
    # Initialize database
    db_config = config.database_config
    db_url = db_config['url']
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')
    else:
        db_path = db_url
    
    db_manager = DatabaseManager(db_path)
    await db_manager.init_database()
    
    print("=" * 70)
    print("DOCTOR ID DATABASE CLEANUP")
    print("=" * 70)
    
    try:
        async with db_manager.get_connection() as conn:
            # Find doctors with empty or problematic doctor_ids
            cursor = await conn.execute("""
                SELECT d.doctor_id, d.user_id, u.name, u.email, u.specialization
                FROM doctors d
                JOIN users u ON d.user_id = u.id
                WHERE d.doctor_id IS NULL OR d.doctor_id = '' OR TRIM(d.doctor_id) = ''
            """)
            
            problematic_doctors = await cursor.fetchall()
            
            if not problematic_doctors:
                print("✅ No doctors with empty doctor_ids found.")
                print("   Database is clean!")
                return
            
            print(f"\n⚠️  Found {len(problematic_doctors)} doctor(s) with empty/null doctor_ids:\n")
            
            for idx, doctor in enumerate(problematic_doctors, 1):
                doctor_id, user_id, name, email, specialization = doctor
                print(f"{idx}. Name: {name}")
                print(f"   User ID: {user_id}")
                print(f"   Email: {email}")
                print(f"   Current Doctor ID: '{doctor_id if doctor_id else '(empty)'}'")
                print(f"   Specialization: {specialization or 'Not specified'}")
                print()
            
            print("=" * 70)
            print("OPTIONS:")
            print("1. Auto-generate new doctor IDs for all")
            print("2. Delete these doctor records (keeps user account)")
            print("3. Manually assign doctor IDs")
            print("4. Exit without changes")
            print("=" * 70)
            
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == '1':
                # Auto-generate doctor IDs
                print("\n📝 Auto-generating doctor IDs...")
                for doctor in problematic_doctors:
                    doctor_id, user_id, name, email, specialization = doctor
                    
                    # Generate doctor ID from name
                    name_parts = name.split()
                    if len(name_parts) >= 2:
                        new_doctor_id = f"DR_{name_parts[0][:3].upper()}{name_parts[-1][:3].upper()}"
                    else:
                        new_doctor_id = f"DR_{name[:6].upper()}"
                    
                    # Check if ID already exists
                    check_cursor = await conn.execute("""
                        SELECT doctor_id FROM doctors WHERE doctor_id = ?
                    """, (new_doctor_id,))
                    
                    if await check_cursor.fetchone():
                        # Add user_id suffix to make unique
                        new_doctor_id = f"{new_doctor_id}_{user_id[:4]}"
                    
                    # Update doctor record
                    await conn.execute("""
                        UPDATE doctors SET doctor_id = ? WHERE user_id = ?
                    """, (new_doctor_id, user_id))
                    
                    # Update username in users table
                    await conn.execute("""
                        UPDATE users SET username = ? WHERE id = ?
                    """, (new_doctor_id, user_id))
                    
                    print(f"   ✅ {name}: {doctor_id or '(empty)'} → {new_doctor_id}")
                
                await conn.commit()
                print("\n✅ All doctor IDs updated successfully!")
            
            elif choice == '2':
                # Delete doctor records
                confirm = input("\n⚠️  This will DELETE doctor records. Are you sure? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    for doctor in problematic_doctors:
                        doctor_id, user_id, name, email, specialization = doctor
                        
                        # Delete doctor record (user record remains)
                        await conn.execute("""
                            DELETE FROM doctors WHERE user_id = ?
                        """, (user_id,))
                        
                        # Update user role to remove doctor status
                        await conn.execute("""
                            UPDATE users SET role = 'inactive' WHERE id = ?
                        """, (user_id,))
                        
                        print(f"   🗑️  Deleted doctor record for: {name}")
                    
                    await conn.commit()
                    print("\n✅ Doctor records deleted successfully!")
                else:
                    print("❌ Operation cancelled")
            
            elif choice == '3':
                # Manual assignment
                print("\n📝 Manual doctor ID assignment:")
                for doctor in problematic_doctors:
                    doctor_id, user_id, name, email, specialization = doctor
                    print(f"\nDoctor: {name} (Email: {email})")
                    
                    while True:
                        new_doctor_id = input("  Enter new doctor ID: ").strip()
                        
                        if not new_doctor_id:
                            print("  ❌ Doctor ID cannot be empty")
                            continue
                        
                        # Check if ID already exists
                        check_cursor = await conn.execute("""
                            SELECT doctor_id FROM doctors WHERE doctor_id = ?
                        """, (new_doctor_id,))
                        
                        if await check_cursor.fetchone():
                            print(f"  ❌ Doctor ID '{new_doctor_id}' already exists")
                            continue
                        
                        # Update doctor record
                        await conn.execute("""
                            UPDATE doctors SET doctor_id = ? WHERE user_id = ?
                        """, (new_doctor_id, user_id))
                        
                        # Update username
                        await conn.execute("""
                            UPDATE users SET username = ? WHERE id = ?
                        """, (new_doctor_id, user_id))
                        
                        print(f"  ✅ Updated to: {new_doctor_id}")
                        break
                
                await conn.commit()
                print("\n✅ All doctor IDs updated successfully!")
            
            else:
                print("\n❌ No changes made to database")
    
    except Exception as e:
        logger.error(f"Error fixing doctor IDs: {e}")
        print(f"\n❌ Error: {e}")
    
    finally:
        await db_manager.close()


async def list_all_doctors():
    """List all doctors in the database for verification"""
    
    # Initialize database
    db_config = config.database_config
    db_url = db_config['url']
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')
    else:
        db_path = db_url
    
    db_manager = DatabaseManager(db_path)
    await db_manager.init_database()
    
    print("\n" + "=" * 70)
    print("ALL DOCTORS IN DATABASE")
    print("=" * 70)
    
    try:
        async with db_manager.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT d.doctor_id, u.name, u.email, u.specialization, u.is_active
                FROM doctors d
                JOIN users u ON d.user_id = u.id
                ORDER BY u.name
            """)
            
            doctors = await cursor.fetchall()
            
            if not doctors:
                print("No doctors found in database.")
                return
            
            print(f"\nFound {len(doctors)} doctor(s):\n")
            print(f"{'Doctor ID':<20} {'Name':<25} {'Email':<30} {'Specialization':<20} {'Active'}")
            print("-" * 115)
            
            for doctor in doctors:
                doctor_id, name, email, specialization, is_active = doctor
                active_str = "Yes" if is_active else "No"
                doctor_id_str = doctor_id if doctor_id else "(empty)"
                spec_str = specialization or "Not specified"
                
                print(f"{doctor_id_str:<20} {name:<25} {email:<30} {spec_str:<20} {active_str}")
    
    except Exception as e:
        logger.error(f"Error listing doctors: {e}")
        print(f"\n❌ Error: {e}")
    
    finally:
        await db_manager.close()


async def main():
    """Main entry point"""
    print("\n" + "=" * 70)
    print("PARKINSON'S MULTIAGENT SYSTEM - DATABASE MAINTENANCE")
    print("=" * 70)
    print("\nOptions:")
    print("1. Fix empty/null doctor IDs")
    print("2. List all doctors")
    print("3. Exit")
    print("=" * 70)
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == '1':
        await fix_empty_doctor_ids()
        # Show updated list
        await list_all_doctors()
    elif choice == '2':
        await list_all_doctors()
    else:
        print("Exiting...")


if __name__ == "__main__":
    asyncio.run(main())
