# Quick Reference: Agent Architecture
## Parkinson's Multi-Agent System

---

## 🎯 Three Agents - Three Responsibilities

### 🧠 **SUPERVISOR AGENT**
**File**: `agents/supervisor_agent.py`  
**Role**: Central orchestrator - NEVER does ML or retrieval

```
┌─────────────────────────────────────┐
│    What Supervisor DOES:           │
├─────────────────────────────────────┤
│ ✓ Detect user intent                │
│ ✓ Set action flags:                 │
│   • PREDICT_PARKINSONS → AIML      │
│   • GENERATE_REPORT → RAG          │
│ ✓ Wait for completion flags         │
│ ✓ Compile final reports             │
│ ✓ Handle errors                     │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│    What Supervisor NEVER does:     │
├─────────────────────────────────────┤
│ ✗ Load ML models                    │
│ ✗ Run predictions                   │
│ ✗ Search knowledge base             │
│ ✗ Generate reports                  │
└─────────────────────────────────────┘
```

---

### 📚 **RAG AGENT**
**File**: `agents/rag_agent.py`  
**Role**: Knowledge retrieval + Report generation

```
┌─────────────────────────────────────┐
│    What RAG DOES:                   │
├─────────────────────────────────────┤
│ ✓ Monitor GENERATE_REPORT flag      │
│ ✓ Search embeddings/knowledge base  │
│ ✓ Generate PDF reports              │
│ ✓ Save to role folders:             │
│   • admin/drafts/                   │
│   • doctor/                         │
│   • patient/                        │
│ ✓ Set REPORT_COMPLETE flag          │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│    What RAG NEVER does:             │
├─────────────────────────────────────┤
│ ✗ Process MRI scans                 │
│ ✗ Run ML predictions                │
│ ✗ Handle user input                 │
└─────────────────────────────────────┘
```

---

### 🤖 **AIML AGENT**
**File**: `agents/aiml_agent.py`  
**Role**: ML model execution ONLY

```
┌─────────────────────────────────────┐
│    What AIML DOES:                  │
├─────────────────────────────────────┤
│ ✓ Monitor PREDICT_PARKINSONS flag   │
│ ✓ Load MRI scans                    │
│ ✓ Preprocess images                 │
│ ✓ Load Keras model                  │
│ ✓ Run predictions                   │
│ ✓ Return structured results         │
│ ✓ Set PREDICTION_COMPLETE flag      │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│    What AIML NEVER does:            │
├─────────────────────────────────────┤
│ ✗ Generate reports                  │
│ ✗ Search knowledge base             │
│ ✗ Handle user input                 │
└─────────────────────────────────────┘
```

---

## 🔄 Complete Workflow Example

```
USER: "Analyze MRI scan at C:/scans/patient.png and generate report"
  ↓
┌──────────────────────────────────────────────────────────┐
│ SUPERVISOR: Intent = "combined" (prediction + report)   │
│ → Set PREDICT_PARKINSONS flag                            │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ AIML: Detected PREDICT_PARKINSONS flag                   │
│ 1. Load MRI: patient.png                                 │
│ 2. Preprocess: 224x224, normalize                        │
│ 3. Load model: parkinsons_model.keras                    │
│ 4. Predict: 87.3% Positive, Stage II                     │
│ 5. Store in shared_memory.predictions                    │
│ → Set PREDICTION_COMPLETE flag                           │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ SUPERVISOR: Detected PREDICTION_COMPLETE                 │
│ → Set GENERATE_REPORT flag                               │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ RAG: Detected GENERATE_REPORT flag                       │
│ 1. Get prediction from shared_memory                     │
│ 2. Search knowledge base: "Parkinson's Stage II"         │
│ 3. Get patient data from database                        │
│ 4. Generate PDF: MedicalReportGenerator                  │
│ 5. Save: data/reports/doctor/patient_Report.pdf          │
│ → Set REPORT_COMPLETE flag                               │
└──────────────────────────────────────────────────────────┘
  ↓
┌──────────────────────────────────────────────────────────┐
│ SUPERVISOR: Detected REPORT_COMPLETE                     │
│ → Return: "Report generated at data/reports/..."         │
└──────────────────────────────────────────────────────────┘
  ↓
USER: Receives report path and status
```

---

## 🚩 Flag System

### Action Flags:
```python
PREDICT_PARKINSONS      # Set by: Supervisor → Monitored by: AIML
GENERATE_REPORT         # Set by: Supervisor → Monitored by: RAG
PREDICTION_COMPLETE     # Set by: AIML → Monitored by: Supervisor
REPORT_COMPLETE         # Set by: RAG → Monitored by: Supervisor
```

### Flag Lifecycle:
```
1. Supervisor: set_action_flag(PREDICT_PARKINSONS)
2. AIML: detect flag → claim → process → complete
3. AIML: set_action_flag(PREDICTION_COMPLETE)
4. Supervisor: detect completion → proceed
```

---

## 📁 Report Folders

```
data/reports/
├── admin/
│   └── drafts/      ← Admin creates drafts here
├── doctor/          ← Doctor clinical reports here
└── patient/         ← Patient-facing reports here
```

**Routing Logic** (`utils/file_manager.py`):
```python
if user_role == 'admin':
    save_to: data/reports/admin/drafts/
elif user_role == 'doctor':
    save_to: data/reports/doctor/
elif user_role == 'patient':
    save_to: data/reports/patient/
```

---

## 🗄️ Data Storage

### Database (`data/parkinsons_system.db`):
- Users, Patients, MRI Scans, Predictions, Reports
- Knowledge entries, Embeddings

### Shared Memory (In-Memory):
- Active sessions, Prediction cache, Report cache
- MRI data buffer, Action flags, Event bus

---

## ⚡ Embeddings

### Created Once:
```bash
python init_database.py  # initialize_embeddings=True
```

### Loaded Every Startup:
```python
# main.py
embeddings_manager = database.get_embeddings_manager()
```

**Rule**: ✅ Create once | ✅ Load many times

---

## 📊 Code Stats

- **Report Generator**: 2,335 lines (was 2,561)
- **Removed**: 226 lines dead code
- **Agents**: Supervisor (949), RAG (1,548), AIML (921)
- **Total System**: ~15,000 lines

---

## 🎯 Quick Troubleshooting

### Issue: Agent not responding
```
Check: Is flag set correctly?
→ Supervisor: await shared_memory.set_action_flag(...)
→ Agent: Subscribed to correct flag event?
```

### Issue: Report not generating
```
Check: Did prediction complete?
→ Verify PREDICTION_COMPLETE flag set
→ Check shared_memory.predictions has data
→ Verify RAG agent received GENERATE_REPORT flag
```

### Issue: MRI not processing
```
Check: File path correct?
→ Verify file exists: os.path.exists(mri_path)
→ Check PREDICT_PARKINSONS flag set
→ Verify AIML agent monitoring started
```

---

## ✅ System Status Indicators

```
Initialization:
[✓] Database connected
[✓] Shared memory initialized
[✓] Embeddings loaded
[✓] Agents initialized
[✓] Event bus started

Runtime:
[✓] Supervisor monitoring
[✓] AIML monitoring PREDICT_PARKINSONS
[✓] RAG monitoring GENERATE_REPORT
[✓] Flags working
[✓] Reports saving correctly
```

---

**Quick Reference Card** | **Parkinson's Multi-Agent System**  
**Version**: 1.0 | **Date**: October 5, 2025
