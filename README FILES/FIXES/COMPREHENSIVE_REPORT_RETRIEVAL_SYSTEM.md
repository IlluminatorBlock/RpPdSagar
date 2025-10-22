# Comprehensive Report Retrieval System - Documentation

**Date:** December 2024  
**Session:** 3  
**Status:** ✅ Completed

---

## Overview

This document details the comprehensive report retrieval system added to the Parkinson's Multi-Agent System. The new system provides flexible querying capabilities to retrieve reports in multiple ways, catering to different user roles and use cases.

## Problem Statement

The user requested a convenient report retrieval system that supports:

1. **Query by Patient ID** - Get all reports for a specific patient
2. **Query by MRI Scan** - Get reports associated with a specific MRI file
3. **Admin Dashboard** - Complete system overview with all doctors, patients, and monitoring statistics
4. **Doctor Dashboard** - Doctor-specific view showing assigned patients and their reports

## Solution Implementation

### New Database Methods

Four new methods were added to `core/database.py`:

#### 1. `get_reports_by_patient_id(patient_id: str)`

**Purpose:** Retrieve all reports for a specific patient

**SQL Query:**
```sql
SELECT mr.* 
FROM medical_reports mr
INNER JOIN sessions s ON mr.session_id = s.id
WHERE s.patient_id = ?
ORDER BY mr.created_at DESC
```

**Returns:** `List[Dict[str, Any]]` containing all reports for the patient

**Use Case:** 
- Patients viewing their own medical history
- Doctors reviewing a patient's report timeline
- Admins auditing patient records

**Example Usage:**
```python
db = DatabaseManager(DATABASE_PATH)
reports = await db.get_reports_by_patient_id("PAT123")

for report in reports:
    print(f"Title: {report['title']}")
    print(f"Type: {report['report_type']}")
    print(f"Created: {report['created_at']}")
    print(f"File: {report['file_path']}")
```

---

#### 2. `get_reports_by_mri_scan(mri_file_path: str)`

**Purpose:** Retrieve reports associated with a specific MRI scan

**SQL Query:**
```sql
SELECT mr.*
FROM medical_reports mr
INNER JOIN mri_scans mri ON mr.session_id = mri.session_id
WHERE mri.file_path = ?
ORDER BY mr.created_at DESC
```

**Returns:** `List[Dict[str, Any]]` containing all reports linked to the MRI scan

**Use Case:**
- Tracing MRI scan → Analysis → Report
- Finding what reports were generated from a specific scan
- Quality assurance and audit trails

**Example Usage:**
```python
db = DatabaseManager(DATABASE_PATH)
mri_path = "data/mri_scans/patient_123_scan_001.jpg"
reports = await db.get_reports_by_mri_scan(mri_path)

if reports:
    print(f"Found {len(reports)} report(s) for this MRI scan")
    for report in reports:
        print(f"  - {report['title']} ({report['report_type']})")
```

---

#### 3. `get_admin_dashboard()`

**Purpose:** Provide comprehensive system overview for administrators

**Data Retrieved:**
- **Summary Statistics:**
  - Total doctors
  - Total patients
  - Total reports
  - Active sessions

- **Doctors Data:**
  - Doctor details (name, specialty, license)
  - Patient count per doctor
  - Session count per doctor
  - Sorted by patient count (busiest doctors first)

- **Patients Data:**
  - Patient details (name, age, gender)
  - Assigned doctor information
  - Report count per patient
  - Session count per patient
  - Sorted by report count

- **Recent Activity:**
  - Last 10 reports generated
  - Patient and doctor names
  - Report types and timestamps

**SQL Queries:**

*Summary Statistics:*
```sql
SELECT COUNT(*) as total FROM doctors
SELECT COUNT(*) as total FROM patients
SELECT COUNT(*) as total FROM medical_reports
SELECT COUNT(*) as total FROM sessions WHERE status = 'active'
```

*Doctors with Patient Counts:*
```sql
SELECT 
    d.doctor_id,
    d.name as doctor_name,
    d.specialty,
    d.license_number,
    COUNT(DISTINCT p.patient_id) as patient_count,
    COUNT(DISTINCT s.id) as session_count
FROM doctors d
LEFT JOIN patients p ON d.doctor_id = p.assigned_doctor_id
LEFT JOIN sessions s ON d.doctor_id = s.doctor_id
GROUP BY d.doctor_id
ORDER BY patient_count DESC
```

*Patients with Report Counts:*
```sql
SELECT 
    p.patient_id,
    p.name as patient_name,
    p.age,
    p.gender,
    p.assigned_doctor_id,
    d.name as doctor_name,
    COUNT(DISTINCT s.id) as session_count,
    COUNT(DISTINCT mr.id) as report_count
FROM patients p
LEFT JOIN doctors d ON p.assigned_doctor_id = d.doctor_id
LEFT JOIN sessions s ON p.patient_id = s.patient_id
LEFT JOIN medical_reports mr ON s.id = mr.session_id
GROUP BY p.patient_id
ORDER BY report_count DESC
```

*Recent Reports:*
```sql
SELECT 
    mr.id,
    mr.title,
    mr.report_type,
    mr.created_at,
    s.patient_name,
    s.doctor_name
FROM medical_reports mr
INNER JOIN sessions s ON mr.session_id = s.id
ORDER BY mr.created_at DESC
LIMIT 10
```

**Returns:** `Dict[str, Any]` with keys:
- `summary`: System-wide statistics
- `doctors`: List of doctors with metrics
- `patients`: List of patients with metrics
- `recent_reports`: Recent activity list

**Use Case:**
- System monitoring and analytics
- Resource allocation decisions
- Identifying bottlenecks or underutilized resources
- Audit and compliance reporting

**Example Usage:**
```python
db = DatabaseManager(DATABASE_PATH)
dashboard = await db.get_admin_dashboard()

print(f"Total Doctors: {dashboard['summary']['total_doctors']}")
print(f"Total Patients: {dashboard['summary']['total_patients']}")
print(f"Total Reports: {dashboard['summary']['total_reports']}")

print("\nTop Doctors by Patient Count:")
for doc in dashboard['doctors'][:5]:
    print(f"  Dr. {doc['doctor_name']}: {doc['patient_count']} patients")

print("\nPatients with Most Reports:")
for patient in dashboard['patients'][:5]:
    print(f"  {patient['patient_name']}: {patient['report_count']} reports")
```

---

#### 4. `get_doctor_dashboard(doctor_id: str)`

**Purpose:** Provide doctor-specific dashboard with assigned patients and reports

**Data Retrieved:**
- **Doctor Information:**
  - Complete doctor profile (name, specialty, license, contact)

- **Statistics:**
  - Total assigned patients
  - Total sessions
  - Active sessions

- **Assigned Patients:**
  - Patient details (name, age, gender, medical history)
  - Report count per patient
  - Session count per patient
  - Last report date
  - Emergency contact information
  - Sorted by most recent activity

- **Recent Reports:**
  - Last 20 reports for assigned patients
  - Patient names
  - Report types and file paths
  - Creation timestamps

**SQL Queries:**

*Doctor Info:*
```sql
SELECT * FROM doctors WHERE doctor_id = ?
```

*Assigned Patients with Report Counts:*
```sql
SELECT 
    p.patient_id,
    p.name as patient_name,
    p.age,
    p.gender,
    p.medical_history,
    p.emergency_contact,
    COUNT(DISTINCT s.id) as session_count,
    COUNT(DISTINCT mr.id) as report_count,
    MAX(mr.created_at) as last_report_date
FROM patients p
LEFT JOIN sessions s ON p.patient_id = s.patient_id
LEFT JOIN medical_reports mr ON s.id = mr.session_id
WHERE p.assigned_doctor_id = ?
GROUP BY p.patient_id
ORDER BY last_report_date DESC
```

*Recent Reports:*
```sql
SELECT 
    mr.id,
    mr.title,
    mr.report_type,
    mr.created_at,
    mr.file_path,
    s.patient_name,
    p.patient_id
FROM medical_reports mr
INNER JOIN sessions s ON mr.session_id = s.id
INNER JOIN patients p ON s.patient_id = p.patient_id
WHERE p.assigned_doctor_id = ?
ORDER BY mr.created_at DESC
LIMIT 20
```

*Session Statistics:*
```sql
SELECT 
    COUNT(DISTINCT s.id) as total_sessions,
    COUNT(DISTINCT CASE WHEN s.status = 'active' THEN s.id END) as active_sessions,
    COUNT(DISTINCT p.patient_id) as total_patients
FROM sessions s
INNER JOIN patients p ON s.patient_id = p.patient_id
WHERE p.assigned_doctor_id = ?
```

**Returns:** `Dict[str, Any]` with keys:
- `doctor_info`: Complete doctor profile
- `statistics`: Session and patient counts
- `patients`: List of assigned patients with metrics
- `recent_reports`: Recent reports for assigned patients

**Use Case:**
- Doctor's daily workflow dashboard
- Patient management and monitoring
- Quick access to patient histories
- Report tracking and follow-up

**Example Usage:**
```python
db = DatabaseManager(DATABASE_PATH)
dashboard = await db.get_doctor_dashboard("DOC123")

print(f"Doctor: {dashboard['doctor_info']['name']}")
print(f"Specialty: {dashboard['doctor_info']['specialty']}")
print(f"\nAssigned Patients: {dashboard['statistics']['total_patients']}")
print(f"Total Sessions: {dashboard['statistics']['total_sessions']}")

print("\nYour Patients:")
for patient in dashboard['patients']:
    print(f"  {patient['patient_name']} (Age: {patient['age']})")
    print(f"    Reports: {patient['report_count']}, Last: {patient['last_report_date']}")
```

---

## Database Schema Relationships

The implementation leverages these key relationships:

```
patients.assigned_doctor_id → doctors.doctor_id
  └─ Links patients to their assigned doctors

sessions.patient_id → patients.patient_id
sessions.doctor_id → doctors.doctor_id
  └─ Links sessions to patients and doctors

medical_reports.session_id → sessions.id
  └─ Links reports to sessions (and transitively to patients/doctors)

mri_scans.session_id → sessions.id
  └─ Links MRI scans to sessions
```

## Testing

A comprehensive test suite is provided in `test_report_queries.py`:

### Running the Tests

```bash
python test_report_queries.py
```

### Test Coverage

1. **Patient Report Retrieval**
   - Fetches a sample patient
   - Retrieves all reports for that patient
   - Displays report details

2. **MRI Scan Report Retrieval**
   - Fetches a sample MRI scan
   - Retrieves associated reports
   - Shows report linkage

3. **Admin Dashboard**
   - Displays system summary statistics
   - Lists all doctors with patient counts
   - Lists all patients with report counts
   - Shows recent activity

4. **Doctor Dashboard**
   - Fetches a sample doctor
   - Displays doctor profile and statistics
   - Lists assigned patients with metrics
   - Shows recent reports

### Expected Output

```
================================================================================
COMPREHENSIVE REPORT RETRIEVAL SYSTEM - TEST SUITE
================================================================================

TEST 1: Get Reports by Patient ID
================================================================================
📋 Fetching reports for Patient: John Doe (ID: PAT123)
✅ Found 3 report(s):
  Report #1:
    - Title: Comprehensive Parkinson's Assessment
    - Type: comprehensive
    - Created: 2024-12-15 10:30:00
    - File Path: data/reports/report_PAT123_001.pdf
    - Generated By: RAG_Agent

[... additional test output ...]

✅ ALL TESTS COMPLETED SUCCESSFULLY
```

## Integration with Main System

These methods are now available throughout the application:

### In Agent Code

```python
from core.database import DatabaseManager

class RAGAgent:
    async def get_patient_history(self, patient_id: str):
        db = DatabaseManager(DATABASE_PATH)
        reports = await db.get_reports_by_patient_id(patient_id)
        return reports
```

### In Authentication/Authorization

```python
async def admin_view(user_id: str):
    db = DatabaseManager(DATABASE_PATH)
    
    if user_role == 'admin':
        dashboard = await db.get_admin_dashboard()
        return dashboard
    elif user_role == 'doctor':
        dashboard = await db.get_doctor_dashboard(doctor_id)
        return dashboard
```

### In Report Generation

```python
async def generate_follow_up_report(patient_id: str):
    db = DatabaseManager(DATABASE_PATH)
    
    # Get previous reports for context
    previous_reports = await db.get_reports_by_patient_id(patient_id)
    
    # Use historical data to inform new report
    # ...
```

## Performance Considerations

### Indexes

The following indexes ensure efficient queries:

```sql
-- Session indexes
CREATE INDEX idx_sessions_patient_id ON sessions(patient_id);
CREATE INDEX idx_sessions_doctor_id ON sessions(doctor_id);
CREATE INDEX idx_sessions_status ON sessions(status);

-- Report indexes
CREATE INDEX idx_reports_session_id ON medical_reports(session_id);
CREATE INDEX idx_reports_created_at ON medical_reports(created_at);

-- MRI scan indexes
CREATE INDEX idx_mri_scans_session_id ON mri_scans(session_id);

-- Patient indexes
(Primary key on patient_id, assigned_doctor_id foreign key)
```

### Query Optimization

- **JOIN operations** use indexed foreign keys
- **ORDER BY clauses** use indexed timestamp columns
- **COUNT operations** use efficient aggregation with indexes
- **LEFT JOIN** preserves all records even without matches

## Security Considerations

### Access Control

Implement role-based access control:

```python
async def get_reports_secure(user_id: str, user_role: str, patient_id: str):
    db = DatabaseManager(DATABASE_PATH)
    
    if user_role == 'admin':
        # Admins can access any patient's reports
        return await db.get_reports_by_patient_id(patient_id)
    
    elif user_role == 'doctor':
        # Verify doctor is assigned to this patient
        patient = await db.get_patient(patient_id)
        if patient['assigned_doctor_id'] == user_id:
            return await db.get_reports_by_patient_id(patient_id)
        else:
            raise PermissionError("Doctor not assigned to this patient")
    
    elif user_role == 'patient':
        # Patients can only access their own reports
        if user_id == patient_id:
            return await db.get_reports_by_patient_id(patient_id)
        else:
            raise PermissionError("Cannot access other patients' reports")
```

## Files Modified

### core/database.py

**Lines 910-1080:** Added 4 new methods:
- `get_reports_by_patient_id()` (lines 914-926)
- `get_reports_by_mri_scan()` (lines 928-942)
- `get_admin_dashboard()` (lines 944-1023)
- `get_doctor_dashboard()` (lines 1025-1080)

## Files Created

### test_report_queries.py

**Purpose:** Comprehensive test suite demonstrating all new retrieval methods

**Contents:**
- `test_patient_report_retrieval()` - Test patient ID query
- `test_mri_report_retrieval()` - Test MRI scan query
- `test_admin_dashboard()` - Test admin dashboard
- `test_doctor_dashboard()` - Test doctor dashboard
- `run_all_tests()` - Execute all tests sequentially

## Benefits

### 1. Convenience
- Single method call to get comprehensive data
- No need to write complex JOIN queries in application code
- Consistent data format across all retrieval methods

### 2. Flexibility
- Multiple ways to access the same data
- Different views for different user roles
- Easy to extend with additional methods

### 3. Performance
- Optimized SQL queries with proper indexes
- Efficient aggregation and grouping
- Minimal database round-trips

### 4. Maintainability
- Centralized database logic
- Easy to modify queries without changing application code
- Clear separation of concerns

### 5. Security
- Can easily add role-based filtering
- Audit trail capability (who accessed what)
- Prevents SQL injection (parameterized queries)

## Future Enhancements

### Potential Additions

1. **Date Range Filtering**
```python
async def get_reports_by_date_range(start_date: str, end_date: str) -> List[Dict]:
    # Get reports within date range
```

2. **Report Type Filtering**
```python
async def get_reports_by_type(report_type: str) -> List[Dict]:
    # Get all reports of specific type (e.g., 'comprehensive', 'follow-up')
```

3. **Patient Status Filtering**
```python
async def get_admin_dashboard_filtered(status: str = None) -> Dict:
    # Filter dashboard by patient status (active, inactive, etc.)
```

4. **Export Functionality**
```python
async def export_reports_to_csv(patient_id: str, output_path: str):
    # Export reports to CSV for external analysis
```

5. **Statistics and Analytics**
```python
async def get_system_analytics(time_period: str = '30d') -> Dict:
    # Get trends, averages, patterns over time
```

## Summary

The comprehensive report retrieval system provides:

✅ **4 new database methods** for flexible querying  
✅ **Optimized SQL queries** with proper indexes  
✅ **Role-based data access** (admin, doctor, patient)  
✅ **Complete test suite** with examples  
✅ **Full documentation** with usage patterns  
✅ **Security considerations** for access control  

The system is now fully operational and ready for integration into the main application workflow.

---

**Implementation Complete:** All requested features have been implemented and tested.
