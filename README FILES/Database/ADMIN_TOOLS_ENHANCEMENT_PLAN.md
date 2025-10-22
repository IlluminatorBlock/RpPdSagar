# Admin Tools Enhancement Plan

## Current Admin Tools Features

The existing `utils/admin_tools.py` provides:

✅ **User Management:**
- `list-users` - List all users
- `create-user` - Create new user (admin/doctor/patient)
- `update-user` - Update user details
- `deactivate-user` - Deactivate user account
- `reset-password` - Reset user password

---

## 🆕 Proposed Enhancements Using New Tables

### 1. **Patient Management Commands**

#### `list-patients` - List all patients with statistics
```bash
python utils/admin_tools.py list-patients
```
**Shows:**
- Patient ID, Name, Age, Gender
- Total consultations, scans, reports
- Last visit date
- Parkinson's status
- Assigned doctors

#### `view-patient` - View complete patient details
```bash
python utils/admin_tools.py view-patient <patient_id>
```
**Shows:**
- Patient information
- Medical statistics
- Assigned doctors
- Recent activity timeline
- Report status

#### `patient-timeline` - View patient medical timeline
```bash
python utils/admin_tools.py patient-timeline <patient_id>
```
**Shows:**
- Chronological list of all events
- Scans, predictions, reports, consultations
- Date, type, description, severity

---

### 2. **Doctor Management Commands**

#### `list-doctors` - List all doctors
```bash
python utils/admin_tools.py list-doctors
```
**Shows:**
- Doctor ID, Name, Specialization
- License number
- Number of patients
- Recent activity

#### `view-doctor` - View doctor details
```bash
python utils/admin_tools.py view-doctor <doctor_id>
```
**Shows:**
- Doctor information
- Assigned patients
- Recent consultations
- Statistics

#### `assign-doctor` - Assign doctor to patient
```bash
python utils/admin_tools.py assign-doctor <doctor_id> <patient_id>
```
**Options:**
- Primary, Consultant, or Specialist
- Add notes

---

### 3. **Consultation Management Commands**

#### `list-consultations` - List recent consultations
```bash
python utils/admin_tools.py list-consultations --limit 20
```
**Filters:**
- By doctor: `--doctor <doctor_id>`
- By patient: `--patient <patient_id>`
- By date range: `--from YYYY-MM-DD --to YYYY-MM-DD`

#### `create-consultation` - Record a consultation
```bash
python utils/admin_tools.py create-consultation
```
**Interactive input:**
- Patient ID
- Doctor ID
- Consultation type
- Chief complaint
- Diagnosis
- Prescription
- Notes

---

### 4. **Report Management Commands**

#### `list-reports` - List report generation status
```bash
python utils/admin_tools.py list-reports --status pending
```
**Filters:**
- By status: pending, generating, generated, failed
- By patient: `--patient <patient_id>`

#### `report-status` - Check report generation status
```bash
python utils/admin_tools.py report-status <patient_id>
```
**Shows:**
- All reports for patient
- Status, requested date
- Generated date
- Error messages (if failed)

#### `retry-failed-reports` - Retry failed report generation
```bash
python utils/admin_tools.py retry-failed-reports
```

---

### 5. **Statistics & Dashboard Commands**

#### `dashboard` - Admin dashboard overview
```bash
python utils/admin_tools.py dashboard
```
**Shows:**
- Total patients, doctors, users
- Active patients (visited in last 30 days)
- Pending reports
- Recent activity
- System health

#### `patient-stats` - Patient statistics summary
```bash
python utils/admin_tools.py patient-stats
```
**Shows:**
- Total patients
- Patients with Parkinson's
- Average consultations per patient
- Most active patients
- Disease stage distribution

---

### 6. **Bulk Operations Commands**

#### `bulk-update-stats` - Recalculate all patient statistics
```bash
python utils/admin_tools.py bulk-update-stats
```

#### `export-patient-data` - Export patient data to CSV
```bash
python utils/admin_tools.py export-patient-data --output patients.csv
```

#### `export-timeline` - Export patient timeline
```bash
python utils/admin_tools.py export-timeline <patient_id> --output timeline.csv
```

---

## Implementation Plan

### Phase 1: Add New Methods to AdminTools Class

```python
# Patient Management
async def list_patients(self, filter_by=None, order_by='last_visit_date')
async def view_patient(self, patient_id)
async def patient_timeline(self, patient_id, limit=None)

# Doctor Management  
async def list_doctors(self)
async def view_doctor(self, doctor_id)
async def assign_doctor(self, doctor_id, patient_id, assignment_type='primary')

# Consultation Management
async def list_consultations(self, doctor_id=None, patient_id=None, limit=20)
async def create_consultation(self)

# Report Management
async def list_reports(self, status=None, patient_id=None)
async def report_status(self, patient_id)
async def retry_failed_reports(self)

# Statistics & Dashboard
async def dashboard(self)
async def patient_stats(self)

# Bulk Operations
async def bulk_update_stats(self)
async def export_patient_data(self, output_file)
async def export_timeline(self, patient_id, output_file)
```

### Phase 2: Add Command-Line Arguments

Update `main()` function to add new subparsers for each command.

### Phase 3: Testing

Test each command with real data:
1. List patients with statistics
2. View patient details
3. Assign doctors
4. Record consultations
5. Check report status

---

## Example: Enhanced Admin Tools Output

### `list-patients` Output:
```
👥 PATIENT LIST (with Statistics)
================================================================================
Found 15 patients:

ID        Name              Age  Consultations  Scans  Reports  Last Visit    Status
--------------------------------------------------------------------------------
P20251... John Doe          45   5              3      3        2025-10-05    Detected
P20251... Jane Smith        38   2              1      1        2025-10-03    Normal
P20251... Bob Johnson       52   8              5      5        2025-10-01    Detected
...
```

### `view-patient P20251006` Output:
```
👤 PATIENT DETAILS
================================================================================

📋 Basic Information:
   Patient ID: P20251006_C331F142
   Name: Safwan
   Age: 21
   Gender: Male
   Phone: 9964499034
   Emergency Contact: 9066885477

📊 Medical Statistics:
   Total Consultations: 0
   Total MRI Scans: 1
   Total Predictions: 1
   Total Reports: 1
   First Visit: 2025-10-06
   Last Visit: 2025-10-06
   Parkinson's Status: Detected
   Disease Stage: Stage 2

👨‍⚕️ Assigned Doctors:
   1. Dr. Sagar Ganiga (Primary) - Assigned: 2025-10-06

📝 Recent Timeline:
   2025-10-06 12:30 - MRI Scan Uploaded (File: test_scan.jpg)
   2025-10-06 12:35 - Parkinson's Analysis Completed (Result: Detected)
   2025-10-06 12:40 - Medical Report Generated (Comprehensive Report)

📄 Reports:
   1. Comprehensive Medical Report - Generated (2025-10-06)
```

### `dashboard` Output:
```
📊 ADMIN DASHBOARD
================================================================================

System Overview:
   Total Users: 25
   ├─ Admins: 2
   ├─ Doctors: 8
   └─ Patients: 15

Patient Activity:
   Active Patients (30 days): 12
   New Patients (7 days): 3
   Patients with Parkinson's: 6 (40%)

Report Generation:
   ✅ Generated: 45
   ⏳ Pending: 2
   🔄 Generating: 1
   ❌ Failed: 0

Recent Activity (Last 24 hours):
   • 3 new MRI scans uploaded
   • 3 predictions completed
   • 2 reports generated
   • 1 new consultation recorded

System Health: ✅ Healthy
Database Size: 15.2 MB
Last Backup: 2025-10-06 08:00
```

---

## Benefits

### For Admins:
✅ **Complete visibility** into all patient data  
✅ **Easy access** to statistics and metrics  
✅ **Quick actions** for common tasks  
✅ **Bulk operations** for efficiency  
✅ **Export capabilities** for reporting  

### For System:
✅ **Leverages new database tables** (doctor_patient_assignments, consultations, report_status, patient_timeline, patient_statistics)  
✅ **Uses pre-computed statistics** for fast queries  
✅ **Consistent command-line interface**  
✅ **Easy to automate** with scripts  

---

## Next Steps

1. ✅ Review current admin_tools.py
2. ⏳ Add new methods to AdminTools class
3. ⏳ Add command-line arguments
4. ⏳ Test with real data
5. ⏳ Create user guide

---

**Ready to implement?** 

I can:
1. Update `admin_tools.py` with all new commands
2. Or create a separate `enhanced_admin_tools.py` file
3. Or add them incrementally one by one

Which would you prefer?
