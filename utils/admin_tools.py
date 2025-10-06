#!/usr/bin/env python3
"""
Admin Tools for Parkinson's Multiagent System
Provides CRUD operations for users, system management, and maintenance
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
import getpass

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import DatabaseManager
from config import config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AdminTools:
    """Administrative tools for user and system management"""
    
    def __init__(self):
        self.config = config
        self.db_manager = None
    
    async def initialize(self):
        """Initialize database connection"""
        try:
            db_config = self.config.database_config
            db_url = db_config['url']
            if db_url.startswith('sqlite:///'):
                db_path = db_url.replace('sqlite:///', '')
            else:
                db_path = db_url
            
            self.db_manager = DatabaseManager(db_path)
            await self.db_manager.init_database()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False
    
    async def list_users(self):
        """List all users in the system"""
        print("👥 USER LIST")
        print("=" * 80)
        
        try:
            users = await self.db_manager.get_all_users()
            
            if not users:
                print("No users found in the system.")
                return
            
            print(f"Found {len(users)} users:\n")
            
            # Headers
            print(f"{'ID':<36} {'Username':<20} {'Role':<10} {'Name':<25} {'Active':<8} {'Created'}")
            print("-" * 110)
            
            for user in users:
                user_id = user.get('id', '')[:8] + '...' if len(user.get('id', '')) > 8 else user.get('id', '')
                username = user.get('username', 'Unknown')
                role = user.get('role', 'unknown')
                name = user.get('name', 'Unknown')
                active = "Yes" if user.get('is_active', True) else "No"
                created = user.get('created_at', 'Unknown')[:10]  # Just date part
                
                print(f"{user_id:<36} {username:<20} {role:<10} {name:<25} {active:<8} {created}")
            
        except Exception as e:
            print(f"❌ Error listing users: {e}")
    
    async def create_user(self):
        """Interactive user creation"""
        print("➕ CREATE NEW USER")
        print("=" * 50)
        
        try:
            # Collect user information
            username = input("Username: ").strip()
            if not username:
                print("❌ Username is required")
                return False
            
            # Check if username exists
            existing_user = await self.db_manager.get_user_by_username(username)
            if existing_user:
                print(f"❌ Username '{username}' already exists")
                return False
            
            email = input("Email: ").strip()
            if not email:
                print("❌ Email is required")
                return False
            
            name = input("Full Name: ").strip()
            if not name:
                print("❌ Name is required")
                return False
            
            print("\nAvailable roles:")
            print("1. admin - Full system access")
            print("2. doctor - Medical professional access")
            print("3. patient - Patient access")
            
            role_choice = input("Select role (1-3): ").strip()
            role_map = {'1': 'admin', '2': 'doctor', '3': 'patient'}
            role = role_map.get(role_choice)
            
            if not role:
                print("❌ Invalid role selection")
                return False
            
            # Get password securely
            password = getpass.getpass("Password: ")
            if not password or len(password) < 6:
                print("❌ Password must be at least 6 characters")
                return False
            
            confirm_password = getpass.getpass("Confirm Password: ")
            if password != confirm_password:
                print("❌ Passwords do not match")
                return False
            
            # Additional fields for doctors
            specialization = None
            license_number = None
            if role == 'doctor':
                specialization = input("Specialization (optional): ").strip() or None
                license_number = input("License Number (optional): ").strip() or None
            
            # Additional fields for patients  
            age = None
            gender = None
            if role == 'patient':
                age_input = input("Age (optional): ").strip()
                if age_input and age_input.isdigit():
                    age = int(age_input)
                gender = input("Gender (optional): ").strip() or None
            
            phone = input("Phone (optional): ").strip() or None
            address = input("Address (optional): ").strip() or None
            
            # Create user data
            user_data = {
                'username': username,
                'email': email,
                'password': password,
                'name': name,
                'role': role,
                'age': age,
                'gender': gender,
                'specialization': specialization,
                'license_number': license_number,
                'phone': phone,
                'address': address,
                'is_active': True
            }
            
            # Create user
            user_id = await self.db_manager.create_user(user_data)
            
            if user_id:
                print(f"\n✅ User created successfully!")
                print(f"   User ID: {user_id}")
                print(f"   Username: {username}")
                print(f"   Role: {role}")
                return True
            else:
                print("❌ Failed to create user")
                return False
                
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            return False
    
    async def update_user(self, username: str):
        """Update an existing user"""
        print(f"✏️  UPDATE USER: {username}")
        print("=" * 50)
        
        try:
            # Get existing user
            user = await self.db_manager.get_user_by_username(username)
            if not user:
                print(f"❌ User '{username}' not found")
                return False
            
            print(f"Current user details:")
            print(f"   Name: {user.get('name', 'Unknown')}")
            print(f"   Email: {user.get('email', 'Unknown')}")
            print(f"   Role: {user.get('role', 'unknown')}")
            print(f"   Active: {'Yes' if user.get('is_active', True) else 'No'}")
            
            # What to update
            print(f"\nWhat would you like to update?")
            print("1. Name")
            print("2. Email") 
            print("3. Role")
            print("4. Active status")
            print("5. Password")
            print("6. Phone")
            print("7. Address")
            
            choice = input("Select option (1-7): ").strip()
            
            update_data = {}
            
            if choice == '1':
                new_name = input(f"New name (current: {user.get('name', 'Unknown')}): ").strip()
                if new_name:
                    update_data['name'] = new_name
            
            elif choice == '2':
                new_email = input(f"New email (current: {user.get('email', 'Unknown')}): ").strip()
                if new_email:
                    update_data['email'] = new_email
            
            elif choice == '3':
                print("Available roles:")
                print("1. admin")
                print("2. doctor") 
                print("3. patient")
                role_choice = input("Select role (1-3): ").strip()
                role_map = {'1': 'admin', '2': 'doctor', '3': 'patient'}
                new_role = role_map.get(role_choice)
                if new_role:
                    update_data['role'] = new_role
            
            elif choice == '4':
                current_active = user.get('is_active', True)
                new_status = input(f"Active status (y/n, current: {'y' if current_active else 'n'}): ").strip().lower()
                if new_status in ['y', 'n']:
                    update_data['is_active'] = new_status == 'y'
            
            elif choice == '5':
                new_password = getpass.getpass("New password: ")
                if new_password and len(new_password) >= 6:
                    confirm = getpass.getpass("Confirm new password: ")
                    if new_password == confirm:
                        update_data['password'] = new_password
                    else:
                        print("❌ Passwords do not match")
                        return False
                else:
                    print("❌ Password must be at least 6 characters")
                    return False
            
            elif choice == '6':
                new_phone = input(f"New phone (current: {user.get('phone', 'None')}): ").strip()
                update_data['phone'] = new_phone if new_phone else None
            
            elif choice == '7':
                new_address = input(f"New address (current: {user.get('address', 'None')}): ").strip()
                update_data['address'] = new_address if new_address else None
            
            else:
                print("❌ Invalid choice")
                return False
            
            if not update_data:
                print("❌ No changes specified")
                return False
            
            # Update user
            success = await self.db_manager.update_user(user['id'], update_data)
            
            if success:
                print(f"✅ User '{username}' updated successfully")
                return True
            else:
                print(f"❌ Failed to update user '{username}'")
                return False
                
        except Exception as e:
            print(f"❌ Error updating user: {e}")
            return False
    
    async def deactivate_user(self, username: str):
        """Deactivate a user account"""
        print(f"🚫 DEACTIVATE USER: {username}")
        print("=" * 50)
        
        try:
            user = await self.db_manager.get_user_by_username(username)
            if not user:
                print(f"❌ User '{username}' not found")
                return False
            
            if not user.get('is_active', True):
                print(f"⚠️ User '{username}' is already deactivated")
                return False
            
            confirm = input(f"Are you sure you want to deactivate '{username}'? (y/N): ").strip().lower()
            if confirm != 'y':
                print("❌ Operation cancelled")
                return False
            
            success = await self.db_manager.update_user(user['id'], {'is_active': False})
            
            if success:
                print(f"✅ User '{username}' deactivated successfully")
                return True
            else:
                print(f"❌ Failed to deactivate user '{username}'")
                return False
                
        except Exception as e:
            print(f"❌ Error deactivating user: {e}")
            return False
    
    async def reset_password(self, username: str):
        """Reset a user's password"""
        print(f"🔑 RESET PASSWORD: {username}")
        print("=" * 50)
        
        try:
            user = await self.db_manager.get_user_by_username(username)
            if not user:
                print(f"❌ User '{username}' not found")
                return False
            
            new_password = getpass.getpass("New password: ")
            if not new_password or len(new_password) < 6:
                print("❌ Password must be at least 6 characters")
                return False
            
            confirm_password = getpass.getpass("Confirm new password: ")
            if new_password != confirm_password:
                print("❌ Passwords do not match")
                return False
            
            success = await self.db_manager.update_user(user['id'], {'password': new_password})
            
            if success:
                print(f"✅ Password reset successfully for '{username}'")
                return True
            else:
                print(f"❌ Failed to reset password for '{username}'")
                return False
                
        except Exception as e:
            print(f"❌ Error resetting password: {e}")
            return False
    
    async def close(self):
        """Close database connection"""
        if self.db_manager:
            await self.db_manager.close()

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Admin Tools for Parkinson\'s Multiagent System')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List users command
    subparsers.add_parser('list-users', help='List all users')
    
    # Create user command  
    subparsers.add_parser('create-user', help='Create a new user')
    
    # Update user command
    update_parser = subparsers.add_parser('update-user', help='Update an existing user')
    update_parser.add_argument('username', help='Username to update')
    
    # Deactivate user command
    deactivate_parser = subparsers.add_parser('deactivate-user', help='Deactivate a user account')
    deactivate_parser.add_argument('username', help='Username to deactivate')
    
    # Reset password command
    reset_parser = subparsers.add_parser('reset-password', help='Reset user password')
    reset_parser.add_argument('username', help='Username for password reset')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize admin tools
    admin_tools = AdminTools()
    
    if not await admin_tools.initialize():
        print("❌ Failed to initialize admin tools")
        return
    
    try:
        # Execute command
        if args.command == 'list-users':
            await admin_tools.list_users()
        
        elif args.command == 'create-user':
            await admin_tools.create_user()
        
        elif args.command == 'update-user':
            await admin_tools.update_user(args.username)
        
        elif args.command == 'deactivate-user':
            await admin_tools.deactivate_user(args.username)
        
        elif args.command == 'reset-password':
            await admin_tools.reset_password(args.username)
        
    finally:
        await admin_tools.close()

if __name__ == "__main__":
    asyncio.run(main())