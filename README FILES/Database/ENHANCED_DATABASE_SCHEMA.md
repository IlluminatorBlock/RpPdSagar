# Enhanced Database Schema for Admin CRUD & Patient History

## 🎯 Overview

This document outlines the enhanced database schema to support:
1. **Admin CRUD Operations** - Complete control over all entities
2. **Patient History Tracking** - Full medical journey tracking
3. **Doctor-Patient Relationships** - Multi-doctor tracking
4. **Report Status Tracking** - Generated/pending reports
5. **Visit History** - Complete consultation records
6. **Data Retrieval** - Patient-centric data access

---

## 📊 Current Schema Issues

### ❌ Problems Identified:
1. **No visit/consultation tracking table**
2. **No doctor-patient relationship table** (many-to-many)
3. **No report status tracking** (generated vs pending)
4. **No appointment/visit history**
5. **Sessions table** has denormalized data (patient_name, doctor_name)
6. **No patient medical timeline** consolidation

---

## ✅ Enhanced Schema Design

### 🆕 NEW TABLES TO ADD

#### 1. **doctor_patient_assignments** (Many-to-Many)
Tracks which doctors have treated/are treating which patients.

```sql
CREATE TABLE IF NOT EXISTS doctor_patient_assignments (
    id TEXT PRIMARY KEY,
    doctor_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    assignment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assignment_type TEXT CHECK (assignment_type IN ('primary', 'consultant', 'specialist')),
    is_active BOOLEAN DEFAULT 1,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    UNIQUE(doctor_id, patient_id, assignment_date)
);

CREATE INDEX idx_dpa_doctor ON doctor_patient_assignments(doctor_id);
CREATE INDEX idx_dpa_patient ON doctor_patient_assignments(patient_id);
CREATE INDEX idx_dpa_active ON doctor_patient_assignments(is_active);
```

**Use Cases:**
- Admin: See all doctors treating a patient
- Admin: See all patients under a doctor
- Patient: View all doctors they've consulted
- Doctor: View their patient list

---

#### 2. **consultations** (Visit History)
Tracks every consultation/visit between doctor and patient.

```sql
CREATE TABLE IF NOT EXISTS consultations (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    doctor_id TEXT NOT NULL,
    session_id TEXT,
    consultation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    consultation_type TEXT CHECK (consultation_type IN ('in-person', 'telemedicine', 'follow-up', 'emergency')),
    chief_complaint TEXT,
    diagnosis TEXT,
    prescription TEXT,
    notes TEXT,
    next_visit_date TIMESTAMP,
    status TEXT DEFAULT 'completed' CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no-show')),
    duration_minutes INTEGER,
    fee_charged DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

CREATE INDEX idx_consultations_patient ON consultations(patient_id);
CREATE INDEX idx_consultations_doctor ON consultations(doctor_id);
CREATE INDEX idx_consultations_date ON consultations(consultation_date);
CREATE INDEX idx_consultations_status ON consultations(status);
CREATE INDEX idx_consultations_session ON consultations(session_id);
```

**Use Cases:**
- Admin: View all consultations
- Patient: View their consultation history
- Doctor: View consultations they conducted
- Track: Number of visits per patient

---

#### 3. **report_status** (Report Generation Tracking)
Tracks whether reports are generated, pending, or need regeneration.

```sql
CREATE TABLE IF NOT EXISTS report_status (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    report_id TEXT,  -- NULL if not yet generated
    prediction_id TEXT,
    mri_scan_id TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'generating', 'generated', 'failed', 'archived')),
    requested_by TEXT NOT NULL,  -- user_id who requested
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    generated_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0,
    report_type TEXT,
    metadata JSON,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (report_id) REFERENCES medical_reports(id) ON DELETE SET NULL,
    FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE SET NULL,
    FOREIGN KEY (mri_scan_id) REFERENCES mri_scans(id) ON DELETE SET NULL
);

CREATE INDEX idx_report_status_patient ON report_status(patient_id);
CREATE INDEX idx_report_status_session ON report_status(session_id);
CREATE INDEX idx_report_status_status ON report_status(status);
CREATE INDEX idx_report_status_requested_by ON report_status(requested_by);
```

**Use Cases:**
- Admin: See pending report generation requests
- Admin: Track failed report generations
- Patient: Check if their report is ready
- System: Auto-retry failed reports

---

#### 4. **patient_timeline** (Medical Journey)
Consolidated view of all patient events (scans, predictions, reports, consultations).

```sql
CREATE TABLE IF NOT EXISTS patient_timeline (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('scan', 'prediction', 'report', 'consultation', 'diagnosis', 'treatment', 'note')),
    event_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_title TEXT NOT NULL,
    event_description TEXT,
    related_id TEXT,  -- ID of related record (scan_id, report_id, etc.)
    related_table TEXT,  -- Which table the related_id refers to
    doctor_id TEXT,
    session_id TEXT,
    severity TEXT CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

CREATE INDEX idx_timeline_patient ON patient_timeline(patient_id);
CREATE INDEX idx_timeline_event_type ON patient_timeline(event_type);
CREATE INDEX idx_timeline_event_date ON patient_timeline(event_date);
CREATE INDEX idx_timeline_severity ON patient_timeline(severity);
```

**Use Cases:**
- Admin: View complete patient journey
- Patient: See their medical timeline
- Doctor: Review patient history chronologically
- Analytics: Track patient progression

---

#### 5. **patient_statistics** (Aggregated Patient Data)
Pre-computed statistics for quick admin dashboard queries.

```sql
CREATE TABLE IF NOT EXISTS patient_statistics (
    patient_id TEXT PRIMARY KEY,
    total_consultations INTEGER DEFAULT 0,
    total_mri_scans INTEGER DEFAULT 0,
    total_predictions INTEGER DEFAULT 0,
    total_reports INTEGER DEFAULT 0,
    unique_doctors_count INTEGER DEFAULT 0,
    first_visit_date TIMESTAMP,
    last_visit_date TIMESTAMP,
    last_scan_date TIMESTAMP,
    last_report_date TIMESTAMP,
    has_parkinsons BOOLEAN,
    disease_stage TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);

CREATE INDEX idx_patient_stats_last_visit ON patient_statistics(last_visit_date);
CREATE INDEX idx_patient_stats_has_parkinsons ON patient_statistics(has_parkinsons);
CREATE INDEX idx_patient_stats_stage ON patient_statistics(disease_stage);
```

**Use Cases:**
- Admin: Quick dashboard metrics
- Admin: Filter patients by activity
- System: Avoid expensive COUNT queries
- Analytics: Patient engagement tracking

---

### 🔧 TABLES TO MODIFY

#### 1. **sessions** - Remove Denormalized Data
```sql
-- Remove: patient_name, doctor_name (get from JOIN instead)
-- Keep: patient_id, doctor_id (foreign keys)

ALTER TABLE sessions DROP COLUMN patient_name;  -- Will need recreation in SQLite
ALTER TABLE sessions DROP COLUMN doctor_name;
```

#### 2. **medical_reports** - Add Status Tracking
```sql
ALTER TABLE medical_reports ADD COLUMN report_status TEXT DEFAULT 'final';
ALTER TABLE medical_reports ADD COLUMN is_latest BOOLEAN DEFAULT 1;
ALTER TABLE medical_reports ADD COLUMN superseded_by TEXT;  -- ID of newer version
ALTER TABLE medical_reports ADD COLUMN version INTEGER DEFAULT 1;
```

#### 3. **predictions** - Add Patient Reference
```sql
ALTER TABLE predictions ADD COLUMN patient_id TEXT;
ALTER TABLE predictions ADD FOREIGN KEY (patient_id) REFERENCES patients(patient_id);
CREATE INDEX idx_predictions_patient ON predictions(patient_id);
```

---

## 📝 Admin CRUD Operations

### 1. **View All Patients with Statistics**
```sql
SELECT 
    p.patient_id,
    p.name,
    p.age,
    p.gender,
    ps.total_consultations,
    ps.total_reports,
    ps.unique_doctors_count,
    ps.last_visit_date,
    ps.has_parkinsons,
    ps.disease_stage
FROM patients p
LEFT JOIN patient_statistics ps ON p.patient_id = ps.patient_id
ORDER BY ps.last_visit_date DESC;
```

### 2. **View Patient's Complete Medical History**
```sql
SELECT 
    pt.event_date,
    pt.event_type,
    pt.event_title,
    pt.event_description,
    d.name AS doctor_name,
    pt.severity
FROM patient_timeline pt
LEFT JOIN doctors doc ON pt.doctor_id = doc.doctor_id
LEFT JOIN users d ON doc.user_id = d.id
WHERE pt.patient_id = ?
ORDER BY pt.event_date DESC;
```

### 3. **View All Doctors Treating a Patient**
```sql
SELECT 
    d.doctor_id,
    u.name AS doctor_name,
    d.specialization,
    dpa.assignment_type,
    dpa.assignment_date,
    dpa.is_active,
    COUNT(c.id) AS consultation_count
FROM doctor_patient_assignments dpa
JOIN doctors d ON dpa.doctor_id = d.doctor_id
JOIN users u ON d.user_id = u.id
LEFT JOIN consultations c ON c.doctor_id = d.doctor_id AND c.patient_id = dpa.patient_id
WHERE dpa.patient_id = ?
GROUP BY d.doctor_id
ORDER BY dpa.is_active DESC, consultation_count DESC;
```

### 4. **View Report Generation Status**
```sql
SELECT 
    rs.id,
    p.name AS patient_name,
    rs.status,
    rs.requested_at,
    rs.generated_at,
    rs.report_type,
    u.name AS requested_by_name,
    rs.error_message
FROM report_status rs
JOIN patients p ON rs.patient_id = p.patient_id
JOIN users u ON rs.requested_by = u.id
WHERE rs.status IN ('pending', 'generating', 'failed')
ORDER BY rs.requested_at ASC;
```

### 5. **View Patient Consultation History**
```sql
SELECT 
    c.consultation_date,
    d.name AS doctor_name,
    doc.specialization,
    c.consultation_type,
    c.chief_complaint,
    c.diagnosis,
    c.status,
    c.fee_charged
FROM consultations c
JOIN doctors doc ON c.doctor_id = doc.doctor_id
JOIN users d ON doc.user_id = d.id
WHERE c.patient_id = ?
ORDER BY c.consultation_date DESC;
```

---

## 🔍 Patient Data Retrieval

### What Patients Can Access:

#### 1. **My Medical Timeline**
```sql
SELECT * FROM patient_timeline 
WHERE patient_id = ? 
ORDER BY event_date DESC;
```

#### 2. **My Doctors**
```sql
SELECT 
    u.name,
    d.specialization,
    dpa.assignment_type,
    dpa.assignment_date
FROM doctor_patient_assignments dpa
JOIN doctors d ON dpa.doctor_id = d.doctor_id
JOIN users u ON d.user_id = u.id
WHERE dpa.patient_id = ? AND dpa.is_active = 1;
```

#### 3. **My Reports**
```sql
SELECT 
    mr.id,
    mr.title,
    mr.created_at,
    mr.report_type,
    rs.status AS generation_status
FROM medical_reports mr
LEFT JOIN report_status rs ON mr.id = rs.report_id
JOIN sessions s ON mr.session_id = s.id
WHERE s.patient_id = ?
ORDER BY mr.created_at DESC;
```

#### 4. **My Consultations**
```sql
SELECT 
    c.consultation_date,
    u.name AS doctor_name,
    c.chief_complaint,
    c.diagnosis,
    c.next_visit_date
FROM consultations c
JOIN doctors d ON c.doctor_id = d.doctor_id
JOIN users u ON d.user_id = u.id
WHERE c.patient_id = ?
ORDER BY c.consultation_date DESC;
```

#### 5. **My Statistics**
```sql
SELECT * FROM patient_statistics WHERE patient_id = ?;
```

---

## 🚀 Implementation Plan

### Phase 1: Create New Tables
1. Create `doctor_patient_assignments`
2. Create `consultations`
3. Create `report_status`
4. Create `patient_timeline`
5. Create `patient_statistics`

### Phase 2: Migrate Existing Data
1. Populate `doctor_patient_assignments` from existing sessions
2. Create timeline entries from existing scans/predictions/reports
3. Calculate and populate `patient_statistics`

### Phase 3: Add New Columns
1. Modify `medical_reports` table
2. Modify `predictions` table
3. Update foreign key constraints

### Phase 4: Update Application Code
1. Create CRUD methods for new tables
2. Add admin dashboard queries
3. Update patient data retrieval
4. Add automatic timeline updates

---

## 📊 Database Triggers (Auto-Update)

### Auto-update patient_statistics:
```sql
-- Trigger on new consultation
CREATE TRIGGER update_stats_on_consultation
AFTER INSERT ON consultations
FOR EACH ROW
BEGIN
    UPDATE patient_statistics
    SET 
        total_consultations = total_consultations + 1,
        last_visit_date = NEW.consultation_date,
        last_updated = CURRENT_TIMESTAMP
    WHERE patient_id = NEW.patient_id;
END;

-- Trigger on new report
CREATE TRIGGER update_stats_on_report
AFTER INSERT ON medical_reports
FOR EACH ROW
BEGIN
    UPDATE patient_statistics
    SET 
        total_reports = total_reports + 1,
        last_report_date = NEW.created_at,
        last_updated = CURRENT_TIMESTAMP
    WHERE patient_id = (SELECT patient_id FROM sessions WHERE id = NEW.session_id);
END;
```

### Auto-populate patient_timeline:
```sql
-- Trigger on new MRI scan
CREATE TRIGGER timeline_on_scan
AFTER INSERT ON mri_scans
FOR EACH ROW
BEGIN
    INSERT INTO patient_timeline (
        id, patient_id, event_type, event_date, event_title, 
        event_description, related_id, related_table, session_id
    )
    SELECT 
        'timeline_' || NEW.id,
        s.patient_id,
        'scan',
        NEW.upload_timestamp,
        'MRI Scan Uploaded',
        'New MRI scan: ' || NEW.original_filename,
        NEW.id,
        'mri_scans',
        NEW.session_id
    FROM sessions s WHERE s.id = NEW.session_id;
END;
```

---

## ✅ Benefits

### For Admin:
- ✅ Complete visibility into all patient data
- ✅ Track report generation pipeline
- ✅ Monitor doctor-patient relationships
- ✅ Quick access to aggregated statistics
- ✅ Full audit trail of all activities

### For Patients:
- ✅ View complete medical history
- ✅ See all doctors they've consulted
- ✅ Track report generation status
- ✅ Access all their reports
- ✅ View consultation history

### For Doctors:
- ✅ See all their patients
- ✅ Access patient medical timeline
- ✅ Track consultation history
- ✅ View patient progression

### For System:
- ✅ Proper normalization (no redundant data)
- ✅ Fast queries with pre-computed statistics
- ✅ Automatic data consistency with triggers
- ✅ Scalable for large datasets

---

## 📁 Next Steps

1. **Review and approve** this schema design
2. **Create migration script** to add new tables
3. **Implement CRUD methods** in database.py
4. **Update agents** to use new tables
5. **Create admin dashboard** queries
6. **Test with sample data**

---

**Status:** Ready for Implementation  
**Impact:** High - Enables full admin control and patient data access  
**Effort:** Medium - Requires careful migration of existing data
