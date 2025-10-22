# Database Normalization & Optimization Plan

## Current Issues Identified

### 1. Normalization Problems

#### A. Sessions Table Denormalization
**Issue**: `sessions` table contains denormalized data:
- `patient_name` (duplicates data from patients table)
- `doctor_name` (duplicates data from users table)

**Solution**: Remove these columns and use JOINs to get names when needed

#### B. Incorrect Foreign Key References
**Issue**: Foreign key constraints reference wrong primary keys:
- `sessions.patient_id` → `patients(id)` should be → `patients(patient_id)`
- `sessions.doctor_id` → `users(id)` is correct but `doctor_id` should reference `doctors(doctor_id)`

**Solution**: Fix foreign key constraints to reference correct primary keys

#### C. Patients Table Redundancy
**Issue**: `patients` table has columns that duplicate `users` table:
- Both have: `name`, `age`, `gender`
- Creates data inconsistency risk

**Solution**: 
- Keep demographic data ONLY in `patients` table
- Remove redundant columns from `users` table
- OR keep in users and remove from patients (depends on design choice)

### 2. SQL Query Optimization Issues

#### A. Missing Indexes
- No composite indexes for common query patterns
- Missing indexes on frequently JOINed columns

#### B. N+1 Query Problems
- Multiple separate queries where JOINs would be better
- Inefficient report retrieval logic

### 3. Recommended Design Choice

**Best Practice**: Separate user authentication from demographic data:
- `users` table: Authentication only (username, email, password_hash, role)
- `patients` table: Patient-specific demographics (name, age, gender, medical history)
- `doctors` table: Doctor-specific data (specialization, license)
- `sessions` table: Session tracking WITHOUT denormalized names

## Detailed Fix Plan

### Phase 1: Schema Normalization

#### Step 1: Fix Sessions Table
```sql
-- Remove denormalized columns
ALTER TABLE sessions DROP COLUMN patient_name;
ALTER TABLE sessions DROP COLUMN doctor_name;

-- Fix foreign key constraints
-- Note: SQLite doesn't support ALTER FOREIGN KEY, so we need to recreate table
```

#### Step 2: Fix Foreign Key References
```sql
-- Recreate sessions table with correct foreign keys
CREATE TABLE sessions_new (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    patient_id TEXT,
    doctor_id TEXT,
    input_type TEXT NOT NULL,
    output_format TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE SET NULL,
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE SET NULL
);
```

#### Step 3: Add Composite Indexes
```sql
-- Sessions queries often filter by user + status
CREATE INDEX idx_sessions_user_status ON sessions(user_id, status);

-- Report queries often join sessions + predictions
CREATE INDEX idx_sessions_patient_created ON sessions(patient_id, created_at DESC);

-- Medical reports often queried by session + type
CREATE INDEX idx_reports_session_type ON medical_reports(session_id, report_type);
```

### Phase 2: Query Optimization

#### Example: Optimized Report Retrieval
**Before** (N+1 queries):
```python
session = await get_session(session_id)
patient = await get_patient(session.patient_id)
doctor = await get_doctor(session.doctor_id)
reports = await get_reports(session_id)
```

**After** (Single JOIN query):
```sql
SELECT 
    s.*,
    p.name as patient_name,
    p.age as patient_age,
    p.gender as patient_gender,
    u.name as doctor_name,
    d.specialization as doctor_specialization,
    mr.id as report_id,
    mr.title as report_title,
    mr.created_at as report_created_at
FROM sessions s
LEFT JOIN patients p ON s.patient_id = p.patient_id
LEFT JOIN doctors d ON s.doctor_id = d.doctor_id
LEFT JOIN users u ON d.user_id = u.id
LEFT JOIN medical_reports mr ON s.id = mr.session_id
WHERE s.id = ?
ORDER BY mr.created_at DESC;
```

### Phase 3: New Report Workflow

#### Patient ID-based Report Retrieval:
1. **Ask for Patient ID**
2. **Retrieve patient info** (name + previous reports)
3. **Display patient name** and report history
4. **Ask: Old report or New report?**
   - **Old Report**: Return existing report as-is
   - **New Report**: 
     - Ask for updated details (use old if empty)
     - **Require MRI scan** for new analysis
     - Generate fresh report

#### Implementation Query:
```sql
-- Get patient with all reports
SELECT 
    p.patient_id,
    p.name,
    p.age,
    p.gender,
    p.medical_history,
    mr.id as report_id,
    mr.title,
    mr.created_at,
    mr.report_type,
    pred.binary_result,
    pred.confidence_score,
    s.id as session_id
FROM patients p
LEFT JOIN sessions s ON p.patient_id = s.patient_id
LEFT JOIN medical_reports mr ON s.id = mr.session_id
LEFT JOIN predictions pred ON mr.prediction_id = pred.id
WHERE p.patient_id = ?
ORDER BY mr.created_at DESC;
```

## Implementation Priority

### HIGH PRIORITY (Do First):
1. ✅ Fix RAGAgent db_manager attribute error
2. ✅ Fix cleanup_expired_sessions method
3. 🔄 Implement intelligent report retrieval workflow
4. 🔄 Remove denormalized columns from sessions

### MEDIUM PRIORITY:
5. Fix foreign key constraints
6. Add composite indexes for common queries
7. Optimize JOIN queries

### LOW PRIORITY:
8. Add query caching layer
9. Implement database connection pooling
10. Add query performance monitoring

## Migration Script

A migration script will be created to:
1. Backup existing database
2. Create new normalized tables
3. Migrate data with proper foreign keys
4. Drop old tables
5. Verify data integrity

## Testing Checklist

- [ ] All foreign keys reference correct tables
- [ ] No denormalized data in sessions table
- [ ] Report retrieval works with patient ID
- [ ] Old report display works
- [ ] New report generation requires MRI
- [ ] All user roles (Admin/Doctor/Patient) work correctly
- [ ] Query performance improved (measure with EXPLAIN QUERY PLAN)

---

**Status**: Plan created - Ready for implementation
**Date**: 2025-10-06
**Priority**: HIGH - Core functionality improvement
