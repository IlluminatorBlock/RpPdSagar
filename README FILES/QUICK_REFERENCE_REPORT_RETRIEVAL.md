# Quick Reference - Report Retrieval System

## How to Use the New Report Retrieval Methods

### 1. Get Reports by Patient ID

```python
from core.database import DatabaseManager
from config import DATABASE_PATH

db = DatabaseManager(DATABASE_PATH)

# Get all reports for a patient
reports = await db.get_reports_by_patient_id("PAT123")

# Display results
for report in reports:
    print(f"{report['title']} - {report['created_at']}")
```

**Use Cases:**
- Patient viewing their medical history
- Doctor reviewing patient's report timeline
- Admin auditing patient records

---

### 2. Get Reports by MRI Scan

```python
# Get reports associated with an MRI scan
mri_path = "data/mri_scans/patient_scan_001.jpg"
reports = await db.get_reports_by_mri_scan(mri_path)

# Trace MRI → Report
print(f"Found {len(reports)} reports from this scan")
```

**Use Cases:**
- Tracing scan to report
- Quality assurance
- Audit trails

---

### 3. Admin Dashboard

```python
# Get comprehensive system overview
dashboard = await db.get_admin_dashboard()

# Access summary statistics
print(f"Doctors: {dashboard['summary']['total_doctors']}")
print(f"Patients: {dashboard['summary']['total_patients']}")
print(f"Reports: {dashboard['summary']['total_reports']}")

# Access doctors data
for doc in dashboard['doctors']:
    print(f"Dr. {doc['doctor_name']}: {doc['patient_count']} patients")

# Access patients data
for patient in dashboard['patients']:
    print(f"{patient['patient_name']}: {patient['report_count']} reports")

# Access recent activity
for report in dashboard['recent_reports']:
    print(f"{report['title']} - {report['patient_name']}")
```

**Use Cases:**
- System monitoring
- Resource allocation
- Compliance reporting
- Performance metrics

---

### 4. Doctor Dashboard

```python
# Get doctor-specific dashboard
dashboard = await db.get_doctor_dashboard("DOC123")

# Access doctor info
print(f"Dr. {dashboard['doctor_info']['name']}")
print(f"Specialty: {dashboard['doctor_info']['specialty']}")

# Access statistics
print(f"Patients: {dashboard['statistics']['total_patients']}")
print(f"Sessions: {dashboard['statistics']['total_sessions']}")

# Access assigned patients
for patient in dashboard['patients']:
    print(f"{patient['patient_name']}: {patient['report_count']} reports")
    print(f"Last report: {patient['last_report_date']}")

# Access recent reports
for report in dashboard['recent_reports']:
    print(f"{report['title']} - {report['patient_name']}")
```

**Use Cases:**
- Daily workflow dashboard
- Patient management
- Report tracking
- Follow-up scheduling

---

## Testing

Run the test suite:

```bash
python test_report_queries.py
```

This will:
1. Test patient report retrieval
2. Test MRI scan report retrieval
3. Test admin dashboard
4. Test doctor dashboard

---

## Security Pattern

Always implement role-based access control:

```python
async def secure_get_reports(user_id, user_role, patient_id):
    db = DatabaseManager(DATABASE_PATH)
    
    if user_role == 'admin':
        return await db.get_reports_by_patient_id(patient_id)
    
    elif user_role == 'doctor':
        patient = await db.get_patient(patient_id)
        if patient['assigned_doctor_id'] == user_id:
            return await db.get_reports_by_patient_id(patient_id)
        raise PermissionError("Not your patient")
    
    elif user_role == 'patient':
        if user_id == patient_id:
            return await db.get_reports_by_patient_id(patient_id)
        raise PermissionError("Cannot access other patients")
```

---

## Files Added/Modified

### Modified:
- `core/database.py` (lines 910-1080)
  - Added `get_reports_by_patient_id()`
  - Added `get_reports_by_mri_scan()`
  - Added `get_admin_dashboard()`
  - Added `get_doctor_dashboard()`

### Created:
- `test_report_queries.py` - Comprehensive test suite
- `COMPREHENSIVE_REPORT_RETRIEVAL_SYSTEM.md` - Full documentation
- `QUICK_REFERENCE_REPORT_RETRIEVAL.md` - This file

---

## Need Help?

See full documentation: `COMPREHENSIVE_REPORT_RETRIEVAL_SYSTEM.md`
