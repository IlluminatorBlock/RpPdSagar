# 🔐 Admin Credentials - Parkinson's Multi-Agent System

## Default Admin Login

### 📋 Admin Account Details

**Username:** `admin`  
**Password:** `Admin123`  
**Email:** `admin@parkinsons.system`  
**Role:** `admin`  
**Full Name:** System Administrator

---

## 🔑 Login Instructions

### For Command Line / Terminal:
```python
from auth.authentication import AuthenticationManager
from core.database import DatabaseManager

# Initialize
db = DatabaseManager("data/parkinsons_system.db")
auth = AuthenticationManager(db)
await auth.initialize()

# Login as admin
success, message, user = await auth.authenticate_admin("admin", "Admin123")

if success:
    print(f"✅ Logged in as: {user.name}")
    print(f"   Role: {user.role.value}")
    print(f"   Email: {user.email}")
```

### For Main System:
When you run `python main.py`, at the first prompt:
1. Select role: **`admin`**
2. Enter username: **`admin`**
3. Enter password: **`Admin123`**

---

## 🛡️ Security Details

### Password Security:
- **Hashing Algorithm:** bcrypt with salt
- **Storage:** Encrypted in `users` table as `password_hash`
- **Verification:** Secure bcrypt comparison

### Auto-Creation:
- The default admin account is **automatically created** on first system initialization
- If deleted, it will be recreated on next startup
- Located in: `auth/authentication.py` and `auth/user_management.py`

---

## 👥 Admin Capabilities

With admin login, you can:

✅ **User Management:**
- Create/update/delete users (admins, doctors, patients)
- Activate/deactivate accounts
- Reset passwords
- View all users

✅ **System Management:**
- Access all patient records
- View all doctor information
- Monitor all consultations
- Access system dashboard
- View audit logs

✅ **Data Access:**
- Full read/write access to all tables
- View all MRI scans
- Access all predictions
- Generate/view all reports
- Manage knowledge base

✅ **CRUD Operations:**
- Doctor-patient assignments
- Consultation records
- Report status management
- Patient timeline
- Patient statistics
- System-wide queries

---

## 🔄 Changing Admin Password

### Option 1: Using Database Manager
```python
from core.database import DatabaseManager
import bcrypt

db = DatabaseManager("data/parkinsons_system.db")

# New password
new_password = "YourNewPassword123"
password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Update in database
async with db.get_connection() as conn:
    await conn.execute("""
        UPDATE users 
        SET password_hash = ?, updated_at = ? 
        WHERE username = 'admin'
    """, (password_hash, datetime.now().isoformat()))
    await conn.commit()
```

### Option 2: Using User Management
```python
from auth.user_management import UserManager

user_mgr = UserManager(db)
await user_mgr.update_user_password("admin", "YourNewPassword123")
```

---

## 📍 Configuration Files

### Default Password Location:
1. **`auth/authentication.py`** (line 58)
   ```python
   self.DEFAULT_ADMIN_PASSWORD = "Admin123"
   ```

2. **`auth/user_management.py`** (line 82)
   ```python
   self.ADMIN_PASSWORD = "Admin123"
   ```

### Database Location:
- **Database File:** `data/parkinsons_system.db`
- **Table:** `users`
- **Admin Record:** WHERE `username = 'admin'` AND `role = 'admin'`

---

## 🚨 Important Security Notes

1. **Change Default Password:** For production use, change the default password immediately
2. **Environment Variables:** Consider storing credentials in environment variables
3. **Access Control:** Admin has full system access - protect credentials carefully
4. **Audit Trail:** All admin actions are logged in `audit_logs` table
5. **Password Policy:** Implement password complexity requirements for production

---

## 🔍 Verifying Admin Account

### Check if Admin Exists:
```python
from core.database import DatabaseManager

db = DatabaseManager("data/parkinsons_system.db")

async with db.get_connection() as conn:
    cursor = await conn.execute("""
        SELECT id, username, email, name, role, is_active, created_at
        FROM users 
        WHERE username = 'admin' AND role = 'admin'
    """)
    admin = await cursor.fetchone()
    
    if admin:
        print("✅ Admin account exists:")
        print(f"   ID: {admin[0]}")
        print(f"   Username: {admin[1]}")
        print(f"   Email: {admin[2]}")
        print(f"   Name: {admin[3]}")
        print(f"   Role: {admin[4]}")
        print(f"   Active: {admin[5]}")
        print(f"   Created: {admin[6]}")
    else:
        print("❌ Admin account not found")
```

---

## 📞 Support

If you have issues logging in:
1. Check if database file exists: `data/parkinsons_system.db`
2. Verify admin account exists (run verification script above)
3. Check if account is active: `is_active = 1`
4. Ensure authentication.py has been initialized
5. Check system logs: `logs/system.log`

---

## 🎯 Quick Reference

| Field | Value |
|-------|-------|
| **Username** | `admin` |
| **Password** | `Admin123` |
| **Email** | `admin@parkinsons.system` |
| **Role** | `admin` |
| **Name** | System Administrator |
| **Status** | Active |
| **Created** | Auto-created on first run |

---

**Last Updated:** October 14, 2025  
**System Version:** Multi-Agent Parkinson's Detection System v1.0
