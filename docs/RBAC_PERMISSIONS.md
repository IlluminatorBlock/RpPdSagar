# Role-Based Access Control (RBAC) System

## 🎯 Overview

The Parkinson's Multiagent System implements a three-tier role-based access control system:

1. **Admin** - Full system access + CRUD operations
2. **Doctor** - Patient management for assigned patients only
3. **Patient** - Personal data access only

---

## 👤 Role Definitions

### 1. **ADMIN** (Highest Privilege)

**Authentication:**
- Pre-created during system initialization
- Username: `admin`
- Password: Set in config
- No approval required

**Permissions:**
- ✅ **Full CRUD operations** on all entities (users, patients, doctors, sessions)
- ✅ **View all data** across the entire system
- ✅ **Upload and analyze MRI scans** for any patient
- ✅ **Create new patients** directly
- ✅ **Approve doctor registrations**
- ✅ **Approve patient-doctor assignments**
- ✅ **System administration** (logs, health, stats)
- ✅ **Knowledge base queries**
- ✅ **Chat with medical AI** (full access)

**Available Commands:**
```
Admin-Specific:
- users              → List all users (patients, doctors, admins)
- doctors            → List all doctors with approval status
- patients           → List all patients
- dashboard          → System overview and statistics
- upload <file>      → Upload MRI scan for analysis
- analyze            → Start MRI analysis workflow
- system             → System administration menu
- stats              → Detailed system statistics
- logs               → View system logs
- search <query>     → Search knowledge base
- kb <query>         → Query knowledge base with RAG

CRUD Commands (Natural Language):
- "show all pending doctor approvals"
- "list patients without doctors"
- "get user details for PATIENT123"
- "create new doctor account"
- "approve doctor DOC456"

Medical Chat:
- Any medical question (e.g., "tell me about parkinsons")
- MRI analysis requests
- Treatment recommendations
```

**Data Access:**
- Can see all patients (regardless of assigned doctor)
- Can see all doctors (pending, approved, inactive)
- Can see all sessions, predictions, reports
- Can view system-wide statistics

---

### 2. **DOCTOR** (Medium Privilege)

**Authentication:**
- Self-registration available
- **Requires admin approval** before full access
- Status: `pending` → `approved` (by admin)

**Permissions:**
- ✅ **View assigned patients** only
- ✅ **Conduct assessments** for assigned patients
- ✅ **Upload MRI scans** for assigned patients
- ✅ **Generate reports** for assigned patients
- ✅ **Chat with medical AI** for medical questions
- ❌ Cannot see other doctors' patients
- ❌ Cannot create/delete patients
- ❌ Cannot approve other doctors
- ❌ Cannot access system administration

**Available Commands:**
```
Doctor-Specific:
- patients               → List YOUR assigned patients only
- new-assessment         → Start new patient assessment
- assess <patient_id>    → Assess existing assigned patient
- reports                → View/manage reports for your patients
- upload <file>          → Upload MRI for your patient

Medical Chat:
- Medical questions (e.g., "treatment for stage 2 parkinsons")
- Patient-specific queries
```

**Data Access:**
- Can ONLY see patients assigned to them
- Can see own profile and assigned patient list
- Can see reports/predictions for assigned patients only
- Cannot see system-wide statistics

**Approval Workflow:**
```
1. Doctor registers → Status: "pending"
2. Admin reviews → Command: "doctors" (shows pending)
3. Admin approves → System updates status to "approved"
4. Doctor can now access full features
```

---

### 3. **PATIENT** (Lowest Privilege)

**Authentication:**
- Self-registration available
- **Requires doctor assignment** for full features
- Approval: Automatic upon doctor assignment

**Permissions:**
- ✅ **View own data** only (reports, predictions)
- ✅ **Upload MRI scans** for self-analysis
- ✅ **Chat with medical AI** for questions
- ✅ **View assigned doctor** information
- ❌ Cannot see other patients
- ❌ Cannot see doctor's other patients
- ❌ Cannot perform CRUD operations
- ❌ Cannot access system administration

**Available Commands:**
```
Patient-Specific:
- reports           → View YOUR medical reports
- doctor            → View assigned doctor info
- symptoms          → Report symptoms or ask questions
- upload <file>     → Upload MRI scan for analysis
- history           → View your medical history

Medical Chat:
- Symptom descriptions (e.g., "I have tremors")
- Questions about diagnosis
- Lifestyle recommendations
```

**Data Access:**
- Can ONLY see own patient record
- Can ONLY see own reports, predictions, sessions
- Can see assigned doctor's name and contact
- Cannot see any other patient data

**Doctor Assignment:**
```
1. Patient registers → No doctor assigned
2. Doctor/Admin assigns patient to doctor
3. Patient can now see assigned doctor info
4. Doctor can now see patient in their patient list
```

---

## 🔐 Database Access Control

### User Table Queries

**Admin:**
```sql
-- Can query ALL users
SELECT * FROM users;
SELECT * FROM doctors WHERE status = 'pending';
SELECT * FROM patients;
```

**Doctor:**
```sql
-- Can only query assigned patients
SELECT * FROM patients 
WHERE patient_id IN (
  SELECT patient_id FROM doctor_patient_assignments 
  WHERE doctor_id = <current_doctor_id>
);
```

**Patient:**
```sql
-- Can only query own record
SELECT * FROM patients WHERE patient_id = <current_patient_id>;
```

### Session/Prediction Queries

**Admin:**
```sql
-- Can see ALL sessions
SELECT * FROM sessions;
SELECT * FROM predictions;
```

**Doctor:**
```sql
-- Can only see sessions for assigned patients
SELECT s.* FROM sessions s
JOIN patients p ON s.patient_id = p.patient_id
JOIN doctor_patient_assignments dpa ON p.patient_id = dpa.patient_id
WHERE dpa.doctor_id = <current_doctor_id>;
```

**Patient:**
```sql
-- Can only see own sessions
SELECT * FROM sessions WHERE patient_id = <current_patient_id>;
```

---

## 🔄 Permission Matrix

| Feature | Admin | Doctor | Patient |
|---------|-------|--------|---------|
| **View all patients** | ✅ | ❌ | ❌ |
| **View assigned patients** | ✅ | ✅ | ❌ |
| **View own data** | ✅ | ✅ | ✅ |
| **Create patients** | ✅ | ❌ | ❌ |
| **Upload MRI (any patient)** | ✅ | ❌ | ❌ |
| **Upload MRI (assigned)** | ✅ | ✅ | ❌ |
| **Upload MRI (self)** | ✅ | ✅ | ✅ |
| **Approve doctors** | ✅ | ❌ | ❌ |
| **Assign patients to doctors** | ✅ | ✅ | ❌ |
| **View system logs** | ✅ | ❌ | ❌ |
| **System administration** | ✅ | ❌ | ❌ |
| **Medical AI chat** | ✅ | ✅ | ✅ |
| **Knowledge base queries** | ✅ | ✅ | ✅ |
| **View reports (any)** | ✅ | ❌ | ❌ |
| **View reports (assigned)** | ✅ | ✅ | ❌ |
| **View reports (own)** | ✅ | ✅ | ✅ |

---

## 🚦 Workflow Examples

### Admin Creates Patient & Analyzes MRI

```bash
[ADMIN] > upload "C:\scans\patient_mri.jpg"

# System prompts:
Patient ID (or press Enter to create new): [Enter]
Patient Name: John Doe
Age: 65
Gender: M
Contact Info (optional): john@email.com

# System:
✅ Patient created with ID: PAT001
📤 Uploading MRI scan...
🤖 Starting AI analysis...
✅ ANALYSIS COMPLETE!
   Result: Positive
   Stage: Hoehn & Yahr Stage 2
   Confidence: 87.3%
📄 Generating medical reports...
✅ Reports generated! Check data/reports/ folder
```

### Doctor Assesses Assigned Patient

```bash
[DOCTOR] > patients
# Shows only patients assigned to this doctor

[DOCTOR] > assess PAT001
# Can only assess if PAT001 is assigned to this doctor
# If not assigned: "❌ Patient not in your assigned list"
```

### Patient Views Own Reports

```bash
[PATIENT] > reports
# Shows only this patient's reports

[PATIENT] > upload "my_mri.jpg"
# Uploads MRI for this patient only
```

---

## 🛡️ Security Implementation

### 1. **Session-Based Authentication**

```python
# Each user session stores role
system.current_user = {
    'id': 'USER123',
    'role': 'doctor',  # or 'admin', 'patient'
    'name': 'Dr. Smith',
    'approved': True
}
```

### 2. **Role Checks Before Operations**

```python
# Example: Before showing all patients
if user_role == 'admin':
    patients = await db.get_all_patients()
elif user_role == 'doctor':
    patients = await db.get_patients_for_doctor(doctor_id)
elif user_role == 'patient':
    patients = [await db.get_patient(patient_id)]
```

### 3. **Database-Level Filters**

```python
# All database queries include role-based filtering
async def get_sessions(user_role, user_id):
    if user_role == 'admin':
        return await db.query("SELECT * FROM sessions")
    elif user_role == 'doctor':
        return await db.query("""
            SELECT s.* FROM sessions s
            JOIN doctor_patient_assignments dpa 
            ON s.patient_id = dpa.patient_id
            WHERE dpa.doctor_id = ?
        """, [user_id])
    else:  # patient
        return await db.query("""
            SELECT * FROM sessions 
            WHERE patient_id = ?
        """, [user_id])
```

---

## ✅ Approval Workflows

### Doctor Approval (by Admin)

```bash
# Step 1: Doctor registers
[SYSTEM] > Doctor registration successful (pending approval)

# Step 2: Admin reviews
[ADMIN] > doctors
👨‍⚕️ DOCTORS (1 pending, 3 approved)
   ⏳ Dr. Smith (DOC123) - pending - smith@hospital.com

# Step 3: Admin approves
[ADMIN] > approve doctor DOC123
✅ Dr. Smith approved! They can now access the system.

# Alternative: Natural language
[ADMIN] > approve dr smith
🤖 Processing admin command...
✅ Doctor DOC123 (Dr. Smith) approved successfully!
```

### Patient-Doctor Assignment

```bash
# Admin or Doctor can assign
[ADMIN] > assign patient PAT001 to doctor DOC123
✅ Patient PAT001 assigned to Dr. Smith (DOC123)

# Or natural language:
[ADMIN] > assign john doe to dr smith
🤖 Processing admin command...
✅ Patient PAT001 (John Doe) assigned to DOC123 (Dr. Smith)
```

---

## 📋 Command Summary by Role

### Admin Commands
✅ All CRUD operations (natural language)  
✅ `users`, `doctors`, `patients`, `dashboard`  
✅ `upload <file>`, `analyze`  
✅ `system`, `stats`, `logs`  
✅ `search`, `kb`  
✅ Medical chat  

### Doctor Commands
✅ `patients` (assigned only)  
✅ `new-assessment`, `assess <id>`  
✅ `reports`  
✅ `upload <file>` (for assigned patients)  
✅ Medical chat  

### Patient Commands
✅ `reports` (own only)  
✅ `doctor`, `symptoms`, `history`  
✅ `upload <file>` (self only)  
✅ Medical chat  

---

## 🔧 Database Schema Notes

### Users Table
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    role TEXT CHECK(role IN ('admin', 'doctor', 'patient')),
    status TEXT CHECK(status IN ('active', 'pending', 'inactive')),
    approved BOOLEAN DEFAULT 0,
    created_at TEXT,
    approved_by TEXT,  -- Admin who approved
    approved_at TEXT
);
```

### Doctor-Patient Assignments
```sql
CREATE TABLE doctor_patient_assignments (
    assignment_id TEXT PRIMARY KEY,
    doctor_id TEXT,
    patient_id TEXT,
    assigned_at TEXT,
    assigned_by TEXT,  -- Admin or auto-assigned
    status TEXT DEFAULT 'active',
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);
```

---

## 📞 Support

**For permission issues:**
- Check user role: `profile` command
- Check approval status: Admin uses `doctors` or `users`
- Check patient assignment: Doctor uses `patients`

**For access denied errors:**
- Verify you're logged in with correct role
- Verify doctor approval status
- Verify patient-doctor assignment

---

*Last Updated: October 22, 2025*  
*System Version: 3.0.0*
