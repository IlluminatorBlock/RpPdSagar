# 🎯 ACCESSING CRUD OPERATIONS VIA SUPERVISOR AGENT
## No SQL Queries Required - Direct Method Calls!

**Date:** October 14, 2025  
**Purpose:** Show how to access all database CRUD operations through the Supervisor Agent

---

## 🔑 KEY CONCEPT

**You DON'T need to write SQL queries!** All CRUD operations are already implemented in `core/database.py` and accessible through:

```python
# In SupervisorAgent, access database via shared_memory:
self.shared_memory.db_manager.<method_name>()
```

---

## 📋 HOW TO ACCESS DATABASE IN SUPERVISOR

### Step 1: Understand the Connection
```python
# Inside supervisor_agent.py, you have:
class SupervisorAgent(BaseAgent, SupervisorInterface):
    def __init__(self, shared_memory, groq_service, config):
        super().__init__(shared_memory, config, "supervisor_agent")
        # shared_memory contains db_manager!
```

### Step 2: Access Pattern
```python
# ALL database operations are available via:
db = self.shared_memory.db_manager

# Then call any CRUD method:
users = await db.get_all_users()
patient = await db.get_patient(patient_id)
success = await db.create_consultation(...)
```

---

## 🛠️ COMPLETE CRUD ACCESS EXAMPLES

### 1️⃣ USER MANAGEMENT

#### Get All Users
```python
async def get_system_users(self):
    """Get all users in the system"""
    db = self.shared_memory.db_manager
    users = await db.get_all_users()
    return users
```

#### Get Active Doctors
```python
async def get_active_doctors(self):
    """Get all active doctors"""
    db = self.shared_memory.db_manager
    doctors = await db.get_users_by_role('doctor')
    active_doctors = [d for d in doctors if d.get('is_active', True)]
    return active_doctors
```

#### Get User by Username
```python
async def find_user(self, username: str):
    """Find user by username"""
    db = self.shared_memory.db_manager
    user = await db.get_user_by_username(username)
    return user
```

#### Update User Information
```python
async def update_user_email(self, user_id: str, new_email: str):
    """Update user's email address"""
    db = self.shared_memory.db_manager
    success = await db.update_user(user_id, email=new_email)
    return success
```

#### Deactivate User Account
```python
async def deactivate_user_account(self, user_id: str):
    """Deactivate a user account (soft delete)"""
    db = self.shared_memory.db_manager
    success = await db.deactivate_user(user_id)
    if success:
        self.logger.info(f"User {user_id} deactivated successfully")
    return success
```

---

### 2️⃣ PATIENT MANAGEMENT

#### Get Patient Information
```python
async def get_patient_info(self, patient_id: str):
    """Get complete patient information"""
    db = self.shared_memory.db_manager
    patient = await db.get_patient(patient_id)
    return patient
```

#### Get Patient with Complete History
```python
async def get_patient_complete_history(self, patient_id: str):
    """Get patient with all reports, scans, and predictions"""
    db = self.shared_memory.db_manager
    
    # This already exists in supervisor! (line 644)
    patient_data = await db.get_patient_with_reports(patient_id)
    
    # Returns:
    # {
    #     'patient': {...patient info...},
    #     'reports': [{...report with prediction info...}],
    #     'report_count': 5
    # }
    return patient_data
```

#### Get All Patients
```python
async def get_all_patients_list(self):
    """Get list of all patients"""
    db = self.shared_memory.db_manager
    patients = await db.get_all_patients()
    return patients
```

#### Check Patient Reports
```python
async def check_patient_reports(self, patient_id: str):
    """Check if patient has existing reports"""
    db = self.shared_memory.db_manager
    reports = await db.check_existing_reports(patient_id)
    return reports
```

---

### 3️⃣ DOCTOR-PATIENT ASSIGNMENTS

#### Assign Doctor to Patient
```python
async def assign_doctor(self, doctor_id: str, patient_id: str, 
                       assignment_type: str = 'primary'):
    """Assign doctor to patient"""
    db = self.shared_memory.db_manager
    
    success = await db.assign_doctor_to_patient(
        doctor_id=doctor_id,
        patient_id=patient_id,
        assignment_type=assignment_type,  # 'primary', 'consultant', 'specialist'
        notes=f"Assigned by supervisor on {datetime.now().isoformat()}"
    )
    
    if success:
        self.logger.info(f"Doctor {doctor_id} assigned to patient {patient_id}")
    
    return success
```

#### Get Patient's Doctors
```python
async def get_patient_doctors(self, patient_id: str):
    """Get all doctors assigned to a patient"""
    db = self.shared_memory.db_manager
    doctors = await db.get_patient_doctors(patient_id)
    return doctors
```

#### Get Doctor's Patients
```python
async def get_doctor_patients(self, doctor_id: str):
    """Get all patients assigned to a doctor"""
    db = self.shared_memory.db_manager
    patients = await db.get_doctor_patients(doctor_id)
    return patients
```

---

### 4️⃣ CONSULTATION MANAGEMENT

#### Create Consultation Record
```python
async def create_consultation_record(
    self,
    patient_id: str,
    doctor_id: str,
    consultation_type: str,
    chief_complaint: str,
    diagnosis: str = None,
    prescription: str = None
):
    """Create a new consultation record"""
    db = self.shared_memory.db_manager
    
    consultation_id = await db.create_consultation(
        patient_id=patient_id,
        doctor_id=doctor_id,
        consultation_type=consultation_type,  # 'in-person', 'telemedicine', 'follow-up'
        chief_complaint=chief_complaint,
        diagnosis=diagnosis,
        prescription=prescription,
        notes=f"Created via supervisor at {datetime.now().isoformat()}"
    )
    
    if consultation_id:
        self.logger.info(f"Created consultation {consultation_id}")
        
        # Auto-adds timeline event via database trigger!
        # Auto-updates patient statistics via database trigger!
    
    return consultation_id
```

#### Get Patient Consultations
```python
async def get_patient_consultation_history(self, patient_id: str, limit: int = 10):
    """Get patient's consultation history"""
    db = self.shared_memory.db_manager
    consultations = await db.get_patient_consultations(patient_id, limit=limit)
    return consultations
```

#### Get Recent Consultations for Doctor
```python
async def get_doctor_recent_consultations(self, doctor_id: str):
    """Get doctor's recent consultations"""
    db = self.shared_memory.db_manager
    consultations = await db.get_doctor_consultations(doctor_id, limit=20)
    return consultations
```

#### Get Specific Consultation
```python
async def get_consultation_details(self, consultation_id: int):
    """Get detailed consultation information"""
    db = self.shared_memory.db_manager
    consultation = await db.get_consultation_by_id(consultation_id)
    return consultation
```

---

### 5️⃣ REPORT STATUS MANAGEMENT

#### Request Report Generation
```python
async def request_report_generation(
    self,
    patient_id: str,
    report_type: str,
    requested_by: str
):
    """Request a new report to be generated"""
    db = self.shared_memory.db_manager
    
    report_id = await db.create_report_request(
        patient_id=patient_id,
        report_type=report_type,  # 'diagnostic', 'follow-up', 'annual', 'mri-analysis'
        requested_by=requested_by
    )
    
    if report_id:
        self.logger.info(f"Report request {report_id} created for patient {patient_id}")
    
    return report_id
```

#### Update Report Status
```python
async def update_report_generation_status(
    self,
    report_id: int,
    status: str,
    report_path: str = None,
    error_message: str = None
):
    """Update report generation status"""
    db = self.shared_memory.db_manager
    
    success = await db.update_report_status(
        report_id=report_id,
        status=status,  # 'pending', 'generating', 'generated', 'failed'
        report_path=report_path,
        error_message=error_message
    )
    
    return success
```

#### Get Pending Reports
```python
async def get_pending_report_queue(self):
    """Get all pending reports needing generation"""
    db = self.shared_memory.db_manager
    pending_reports = await db.get_pending_reports()
    return pending_reports
```

#### Get Failed Reports
```python
async def get_failed_report_list(self):
    """Get all failed report generation attempts"""
    db = self.shared_memory.db_manager
    failed_reports = await db.get_failed_reports()
    return failed_reports
```

---

### 6️⃣ PATIENT TIMELINE

#### Add Timeline Event
```python
async def add_patient_timeline_event(
    self,
    patient_id: str,
    event_type: str,
    event_description: str,
    severity: str = None
):
    """Add event to patient timeline"""
    db = self.shared_memory.db_manager
    
    event_id = await db.add_timeline_event(
        patient_id=patient_id,
        event_type=event_type,  # 'consultation', 'diagnosis', 'prescription', 'scan', 'report'
        event_description=event_description,
        severity=severity  # 'low', 'medium', 'high', 'critical'
    )
    
    if event_id:
        self.logger.info(f"Timeline event {event_id} added for patient {patient_id}")
    
    return event_id
```

#### Get Patient Timeline
```python
async def get_patient_event_timeline(
    self,
    patient_id: str,
    limit: int = None,
    event_type: str = None
):
    """Get patient's event timeline"""
    db = self.shared_memory.db_manager
    
    timeline = await db.get_patient_timeline(
        patient_id=patient_id,
        limit=limit,
        event_type=event_type  # Filter by specific type if needed
    )
    
    return timeline
```

#### Get Timeline by Date Range
```python
async def get_timeline_for_period(
    self,
    patient_id: str,
    start_date: str,
    end_date: str
):
    """Get timeline events within date range"""
    db = self.shared_memory.db_manager
    
    timeline = await db.get_timeline_by_date_range(
        patient_id=patient_id,
        start_date=start_date,  # ISO format: '2025-01-01'
        end_date=end_date
    )
    
    return timeline
```

---

### 7️⃣ PATIENT STATISTICS

#### Get Patient Statistics
```python
async def get_patient_stats(self, patient_id: str):
    """Get patient statistics"""
    db = self.shared_memory.db_manager
    stats = await db.get_patient_statistics(patient_id)
    
    # Returns:
    # {
    #     'total_consultations': 5,
    #     'total_mri_scans': 3,
    #     'total_predictions': 3,
    #     'total_reports': 2,
    #     'first_visit_date': '2025-01-01',
    #     'last_visit_date': '2025-10-14',
    #     'last_updated': '2025-10-14T10:30:00'
    # }
    
    return stats
```

#### Get All Patient Statistics
```python
async def get_all_patient_statistics(self, order_by: str = 'last_visit_date'):
    """Get statistics for all patients"""
    db = self.shared_memory.db_manager
    
    all_stats = await db.get_all_patient_statistics(
        order_by=order_by,  # 'total_consultations', 'last_visit_date', etc.
        limit=50  # Optional limit
    )
    
    return all_stats
```

#### Recalculate Patient Statistics
```python
async def recalculate_stats(self, patient_id: str):
    """Recalculate patient statistics from scratch"""
    db = self.shared_memory.db_manager
    success = await db.recalculate_patient_statistics(patient_id)
    return success
```

---

### 8️⃣ SESSION MANAGEMENT

#### Session Already Exists!
```python
# The supervisor already uses sessions extensively!
# See lines in supervisor_agent.py:

# Update session status (line 152):
await self.shared_memory.db_manager.update_session_status(
    session_id, 
    SessionStatus.ERROR
)

# Update session patient info (line 786):
await self.shared_memory.db_manager.update_session_patient_info(
    session_id, 
    patient_id, 
    patient_name
)
```

#### Get Session Summary
```python
async def get_complete_session_summary(self, session_id: str):
    """Get complete session with all related data"""
    db = self.shared_memory.db_manager
    
    summary = await db.get_session_summary(session_id)
    
    # Returns:
    # {
    #     'session': {...session data...},
    #     'mri_scans': [{...}],
    #     'predictions': [{...}],
    #     'reports': [{...}],
    #     'action_flags': [{...}]
    # }
    
    return summary
```

---

### 9️⃣ DASHBOARDS

#### System Dashboard (Admin)
```python
async def get_admin_dashboard(self):
    """Get system-wide dashboard for admin"""
    db = self.shared_memory.db_manager
    dashboard = await db.get_system_dashboard()
    
    # Returns comprehensive metrics:
    # - Total users, patients, doctors
    # - Active patients (last 30 days)
    # - Pending/failed reports
    # - Parkinson's detection statistics
    # - 24-hour activity metrics
    
    return dashboard
```

#### Doctor Dashboard
```python
async def get_doctor_overview(self, doctor_id: str):
    """Get dashboard for specific doctor"""
    db = self.shared_memory.db_manager
    dashboard = await db.get_doctor_dashboard(doctor_id)
    
    # Returns:
    # - Doctor info
    # - Assigned patients with statistics
    # - Recent reports
    # - Session statistics
    
    return dashboard
```

#### Patient Dashboard
```python
async def get_patient_overview(self, patient_id: str):
    """Get comprehensive patient dashboard"""
    db = self.shared_memory.db_manager
    dashboard = await db.get_patient_dashboard(patient_id)
    
    # Returns:
    # - Patient info
    # - Statistics summary
    # - Assigned doctors
    # - Recent timeline (last 10)
    # - Report status
    # - Recent consultations (last 5)
    
    return dashboard
```

---

### 🔟 MRI & PREDICTIONS (Already Used!)

#### MRI Scans
```python
async def get_patient_mri_history(self, patient_id: str):
    """Get all MRI scans for patient"""
    db = self.shared_memory.db_manager
    scans = await db.get_mri_scans_by_patient(patient_id)
    return scans
```

#### Predictions
```python
async def get_session_predictions(self, session_id: str):
    """Get all predictions for session"""
    db = self.shared_memory.db_manager
    predictions = await db.get_predictions_by_session(session_id)
    return predictions
```

---

## 🎯 PRACTICAL IMPLEMENTATION EXAMPLES

### Example 1: Create Complete Patient Assessment Workflow
```python
async def handle_patient_assessment(
    self,
    patient_id: str,
    doctor_id: str,
    chief_complaint: str,
    diagnosis: str
):
    """Complete patient assessment workflow using CRUD operations"""
    db = self.shared_memory.db_manager
    
    try:
        # 1. Create consultation record
        consultation_id = await db.create_consultation(
            patient_id=patient_id,
            doctor_id=doctor_id,
            consultation_type='in-person',
            chief_complaint=chief_complaint,
            diagnosis=diagnosis
        )
        self.logger.info(f"✅ Consultation created: {consultation_id}")
        
        # 2. Add timeline event (automatically added by trigger, but can add custom)
        await db.add_timeline_event(
            patient_id=patient_id,
            event_type='diagnosis',
            event_description=f"Diagnosed with: {diagnosis}",
            severity='high'
        )
        self.logger.info("✅ Timeline event added")
        
        # 3. Request report generation
        report_id = await db.create_report_request(
            patient_id=patient_id,
            report_type='diagnostic',
            requested_by=doctor_id
        )
        self.logger.info(f"✅ Report requested: {report_id}")
        
        # 4. Get updated patient statistics
        stats = await db.get_patient_statistics(patient_id)
        self.logger.info(f"✅ Updated stats: {stats['total_consultations']} consultations")
        
        return {
            'success': True,
            'consultation_id': consultation_id,
            'report_id': report_id,
            'statistics': stats
        }
        
    except Exception as e:
        self.logger.error(f"Assessment workflow failed: {e}")
        return {'success': False, 'error': str(e)}
```

---

### Example 2: Patient Dashboard Retrieval
```python
async def generate_patient_dashboard_report(self, patient_id: str):
    """Generate comprehensive patient dashboard"""
    db = self.shared_memory.db_manager
    
    try:
        # Get all patient data in one call
        dashboard = await db.get_patient_dashboard(patient_id)
        
        patient = dashboard['patient_info']
        stats = dashboard['statistics']
        doctors = dashboard['assigned_doctors']
        timeline = dashboard['recent_timeline']
        
        # Format report
        report = f"""
        PATIENT DASHBOARD REPORT
        ========================
        
        Patient: {patient['name']}
        Age: {patient['age']} | Gender: {patient['gender']}
        
        STATISTICS:
        - Total Consultations: {stats['total_consultations']}
        - Total MRI Scans: {stats['total_mri_scans']}
        - Total Reports: {stats['total_reports']}
        - First Visit: {stats['first_visit_date']}
        - Last Visit: {stats['last_visit_date']}
        
        ASSIGNED DOCTORS: {len(doctors)}
        {self._format_doctors(doctors)}
        
        RECENT TIMELINE (Last 10 Events):
        {self._format_timeline(timeline)}
        """
        
        return report
        
    except Exception as e:
        self.logger.error(f"Dashboard generation failed: {e}")
        return None
```

---

### Example 3: Doctor Patient Management
```python
async def manage_doctor_patient_assignment(
    self,
    doctor_id: str,
    patient_id: str,
    action: str  # 'assign' or 'view'
):
    """Manage doctor-patient relationships"""
    db = self.shared_memory.db_manager
    
    if action == 'assign':
        # Assign doctor to patient
        success = await db.assign_doctor_to_patient(
            doctor_id=doctor_id,
            patient_id=patient_id,
            assignment_type='primary'
        )
        
        if success:
            return f"✅ Doctor {doctor_id} assigned to patient {patient_id}"
        else:
            return "❌ Assignment failed"
    
    elif action == 'view':
        # Get doctor's patient list
        patients = await db.get_doctor_patients(doctor_id)
        
        report = f"Doctor {doctor_id} has {len(patients)} patients:\n"
        for p in patients:
            report += f"  - {p['patient_name']} (Age: {p['age']})\n"
        
        return report
```

---

### Example 4: Report Generation Workflow
```python
async def handle_report_generation_workflow(
    self,
    patient_id: str,
    report_type: str,
    requested_by: str
):
    """Complete report generation workflow"""
    db = self.shared_memory.db_manager
    
    try:
        # 1. Create report request
        report_id = await db.create_report_request(
            patient_id=patient_id,
            report_type=report_type,
            requested_by=requested_by
        )
        self.logger.info(f"Report request created: {report_id}")
        
        # 2. Update status to 'generating'
        await db.update_report_status(report_id, 'generating')
        
        # 3. ... actual report generation logic ...
        # (handled by RAG agent or report generator)
        
        # 4. Update status to 'generated' with file path
        report_path = f"/data/reports/patient_{patient_id}_{report_type}_{datetime.now().isoformat()}.pdf"
        await db.update_report_status(
            report_id,
            'generated',
            report_path=report_path
        )
        
        # 5. Add timeline event
        await db.add_timeline_event(
            patient_id=patient_id,
            event_type='report',
            event_description=f"{report_type.capitalize()} report generated",
            related_record_id=str(report_id)
        )
        
        return {
            'success': True,
            'report_id': report_id,
            'report_path': report_path
        }
        
    except Exception as e:
        # Update status to 'failed' on error
        await db.update_report_status(
            report_id,
            'failed',
            error_message=str(e)
        )
        return {'success': False, 'error': str(e)}
```

---

## 🚀 ADDING NEW CRUD METHODS TO SUPERVISOR

### Template for Adding New Methods

```python
# In agents/supervisor_agent.py

class SupervisorAgent(BaseAgent, SupervisorInterface):
    
    # Add your new CRUD access methods here:
    
    async def your_new_crud_method(self, param1, param2):
        """
        Your method description
        
        Args:
            param1: Description
            param2: Description
        
        Returns:
            Result description
        """
        # Access database manager
        db = self.shared_memory.db_manager
        
        try:
            # Call existing CRUD method (NO SQL NEEDED!)
            result = await db.existing_method_name(param1, param2)
            
            # Add logging
            self.logger.info(f"Operation completed: {result}")
            
            # Return result
            return result
            
        except Exception as e:
            self.logger.error(f"Operation failed: {e}")
            return None
```

---

## 📚 QUICK REFERENCE CHEAT SHEET

```python
# Database Access Pattern:
db = self.shared_memory.db_manager

# USER CRUD
await db.get_all_users(role='doctor', is_active=True)
await db.get_user_by_username(username)
await db.update_user(user_id, email='new@email.com')
await db.deactivate_user(user_id)

# PATIENT CRUD
await db.get_patient(patient_id)
await db.get_all_patients()
await db.get_patient_with_reports(patient_id)

# DOCTOR-PATIENT
await db.assign_doctor_to_patient(doctor_id, patient_id, 'primary')
await db.get_doctor_patients(doctor_id)
await db.get_patient_doctors(patient_id)

# CONSULTATIONS
await db.create_consultation(patient_id, doctor_id, 'in-person', complaint, diagnosis)
await db.get_patient_consultations(patient_id, limit=10)

# REPORTS
await db.create_report_request(patient_id, 'diagnostic', requested_by)
await db.update_report_status(report_id, 'generated', report_path)
await db.get_pending_reports()

# TIMELINE
await db.add_timeline_event(patient_id, 'diagnosis', description, 'high')
await db.get_patient_timeline(patient_id, limit=10)

# STATISTICS
await db.get_patient_statistics(patient_id)
await db.get_all_patient_statistics(order_by='last_visit_date')

# DASHBOARDS
await db.get_system_dashboard()
await db.get_doctor_dashboard(doctor_id)
await db.get_patient_dashboard(patient_id)
```

---

## ✅ KEY TAKEAWAYS

1. **NO SQL REQUIRED** - All CRUD operations are pre-built methods
2. **Access via Supervisor** - Use `self.shared_memory.db_manager`
3. **Async/Await Pattern** - All methods are async
4. **No Manual Triggers Needed** - Database triggers auto-update statistics
5. **Comprehensive Methods** - 80+ methods covering all operations
6. **Type Safety** - Returns proper Python types (List, Dict, Optional)
7. **Error Handling** - Methods return None or False on errors
8. **Logging Built-in** - Operations are automatically logged

---

## 🎯 NEXT STEPS

1. **Pick a CRUD operation** you need (e.g., create consultation)
2. **Copy the example** from this guide
3. **Paste into supervisor_agent.py** 
4. **Customize parameters** for your use case
5. **Call the method** from your workflow
6. **Done!** No SQL needed! 🎉

---

**Remember:** The database manager (`self.shared_memory.db_manager`) gives you access to ALL 80+ CRUD methods. Just call them directly - the SQL is already written for you! ✅
