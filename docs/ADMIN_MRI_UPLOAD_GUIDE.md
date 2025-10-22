# Admin MRI Upload & Analysis - Quick Guide

## 🚀 Quick Start

### Method 1: Direct Upload Command

```bash
[ADMIN] > upload "C:\Users\Sagar\Downloads\PPMI_3130_MR_ep2d_RESTING_STATE_br_raw_20130124103642429_210_S180778_I355962 (2).jpg"
```

**What happens:**
1. System validates file exists
2. Prompts for patient information:
   - Enter existing Patient ID, or
   - Press Enter to create new patient
3. Uploads MRI to database
4. Triggers AI analysis automatically
5. Shows results (Positive/Negative, Stage, Confidence)
6. Generates PDF reports automatically
7. **Saves to training dataset** in `data/mri_scans/[diagnosis]/[stage]/`

### Method 2: Interactive Workflow

```bash
[ADMIN] > analyze

# System guides you through:
📁 Enter MRI file path: C:\path\to\scan.jpg
👤 Patient ID (or Enter for new): [Enter]
   Patient Name: John Doe
   Age: 65
   Gender: M
   Contact Info: john@email.com
   
✅ Patient created with ID: PAT001
📤 Uploading MRI scan...
🤖 Starting AI analysis...
⏳ Analyzing MRI scan...
✅ ANALYSIS COMPLETE!
```

---

## 📋 Available Commands for Admin

### MRI Analysis Commands
- `upload "path/to/file.jpg"` - Upload and analyze MRI
- `analyze` - Start guided MRI analysis workflow

### User Management
- `users` - List all users (admin, doctors, patients)
- `doctors` - List all doctors with approval status
- `patients` - List all patients

### System Administration
- `dashboard` - System overview
- `stats` - Detailed statistics
- `logs` - View system logs
- `system` - System admin menu

### Knowledge Base
- `search <query>` - Search medical documents
- `kb <query>` - Query with RAG enhancement

### Natural Language CRUD
- "show all pending doctor approvals"
- "list patients without assigned doctors"
- "get patient details for PAT001"
- "approve doctor DOC123"

### Medical Chat
- "tell me about parkinsons"
- "what are the stages of parkinsons disease"
- "treatment options for stage 2"

---

## 🔍 Example Session

```bash
[ADMIN] > upload "C:\scans\patient_mri.jpg"

🔬 ADMIN MRI UPLOAD & ANALYSIS
======================================================================
📁 File: patient_mri.jpg
📍 Path: C:\scans\patient_mri.jpg

👤 PATIENT INFORMATION
----------------------------------------------------------------------
   Patient ID (or press Enter to create new): 

📝 Creating new patient...
   Patient Name: John Doe
   Age: 65
   Gender: M
   Contact Info (optional): john@email.com

✅ Patient created with ID: PAT001

🔄 Creating analysis session...
📤 Uploading MRI scan...
✅ MRI uploaded successfully (ID: MRI001)

🤖 Starting AI analysis...
⏳ Analyzing MRI scan (this may take a moment)...

✅ ANALYSIS COMPLETE!
======================================================================
   Result: Positive
   Stage: Hoehn & Yahr Stage 2
   Confidence: 87.3%
======================================================================

📄 Generating medical reports...
✅ Reports generated! Check data/reports/ folder

✅ MRI saved to training dataset: PD_POS_S2_PAT001_20251022_180530.jpg
```

---

## 📊 What Gets Created

### 1. Database Records
- ✅ New patient record (if created)
- ✅ Session record
- ✅ MRI scan record
- ✅ Prediction result
- ✅ Medical report

### 2. Files Generated
- ✅ Doctor report PDF: `data/reports/doctor/DR_PAT001_TIMESTAMP.pdf`
- ✅ Patient report PDF: `data/reports/patient/PT_PAT001_TIMESTAMP.pdf`
- ✅ Training dataset image: `data/mri_scans/positive/stage_2/PD_POS_S2_PAT001_TIMESTAMP.jpg`
- ✅ Training dataset metadata: `data/mri_scans/positive/stage_2/PD_POS_S2_PAT001_TIMESTAMP.json`

### 3. Reports Include
**Doctor Report (1 page):**
- MRI scan image
- Patient demographics
- Diagnosis & stage
- Medications to prescribe
- Clinical recommendations

**Patient Report (1 page):**
- Simple diagnosis explanation
- Disease stage meaning
- Medications prescribed
- **Lifestyle recommendations from knowledge base**
- Support resources

---

## ⚠️ Troubleshooting

### "File not found" Error
```bash
❌ File not found: C:\path\to\scan.jpg
💡 Make sure the file path is correct
```

**Solutions:**
1. Check file path is correct
2. Use quotes around paths with spaces
3. Use full absolute path
4. Check file extension (.jpg, .jpeg, .png)

### "Patient not found" Error
```bash
❌ Patient not found: PAT999
💡 Use 'patients' command to see all patients
```

**Solutions:**
1. List all patients: `patients`
2. Press Enter to create new patient
3. Verify patient ID spelling

### "Analysis timeout" Error
```bash
⚠️ Analysis timeout - check 'logs' for details
```

**Solutions:**
1. Check system logs: `logs`
2. Verify AIML agent is running
3. Check MRI file is valid image
4. Restart system if needed

---

## 🎯 Best Practices

### 1. **Always Use Full Paths**
```bash
✅ Good: upload "C:\Users\Sagar\Downloads\scan.jpg"
❌ Bad:  upload scan.jpg
```

### 2. **Create Patients Before Bulk Uploads**
```bash
# Method 1: Create patient first
[ADMIN] > create patient name="John Doe" age=65 gender=M

# Method 2: Let upload create patient
[ADMIN] > upload "scan.jpg"
# Press Enter when asked for Patient ID
```

### 3. **Verify Results**
```bash
# After upload, check:
[ADMIN] > patients          # Verify patient created
[ADMIN] > dashboard         # See prediction count
[ADMIN] > stats             # Detailed statistics
```

### 4. **Monitor Training Dataset Growth**
```bash
# Check saved scans
dir data\mri_scans\positive\stage_2
# Should show: PD_POS_S2_*.jpg and PD_POS_S2_*.json files
```

---

## 🔄 Complete Workflow

### For New Patient
```bash
1. [ADMIN] > upload "path/to/scan.jpg"
2. Press Enter (create new patient)
3. Enter patient details (name, age, gender, contact)
4. Wait for analysis (~10-30 seconds)
5. View results and reports
6. Check data/reports/ for PDF files
7. Check data/mri_scans/ for training dataset
```

### For Existing Patient
```bash
1. [ADMIN] > patients                    # Get patient ID
2. [ADMIN] > upload "path/to/scan.jpg"
3. Enter patient ID (e.g., PAT001)
4. Wait for analysis
5. View results
```

---

## 📈 After Analysis

### View Generated Reports
```bash
# Doctor report
Open: data/reports/doctor/DR_PAT001_TIMESTAMP.pdf

# Patient report  
Open: data/reports/patient/PT_PAT001_TIMESTAMP.pdf
```

### Check Training Dataset
```bash
# Navigate to saved MRI
cd data\mri_scans\positive\stage_2

# View files
dir
# Shows:
# PD_POS_S2_PAT001_20251022_180530.jpg
# PD_POS_S2_PAT001_20251022_180530.json

# Read metadata
type PD_POS_S2_PAT001_20251022_180530.json
```

### Verify in Database
```bash
[ADMIN] > patients          # See new patient
[ADMIN] > dashboard         # See stats updated
[ADMIN] > stats             # Detailed breakdown
```

---

## 💡 Tips

1. **Quote paths with spaces:** `upload "C:\My Folder\scan.jpg"`
2. **Use Tab completion** if your terminal supports it
3. **Check logs** if something fails: `logs`
4. **Health check** before uploading: `health`
5. **Clear screen** when cluttered: `clear` or `cls`

---

## 🆘 Need Help?

```bash
[ADMIN] > help              # Show all commands
[ADMIN] > dashboard         # System overview
[ADMIN] > system            # System administration
[ADMIN] > logs              # Check for errors
```

---

*For detailed permissions, see `docs/RBAC_PERMISSIONS.md`*  
*For training dataset info, see `data/mri_scans/README.md`*
