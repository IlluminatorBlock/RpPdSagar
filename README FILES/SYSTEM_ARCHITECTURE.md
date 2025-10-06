# Parkinson's Multi-Agent System Architecture

## System Overview
Clean, modular architecture with 3 distinct LLM agents and clear separation of concerns.

---

## Architecture Components

### 1. **Main.py** - System Gateway
**Role**: Entry point and authentication only

**Responsibilities**:
- System initialization
- User authentication (admin/doctor/patient)
- Route commands to appropriate agents
- NO business logic or data collection

**Key Commands**:
- `new-assessment` → Delegates to RAG Agent
- `assess <patient_id>` → Delegates to RAG Agent  
- `health` → System health check
- `profile` → User profile

---

### 2. **Three Distinct Agents**

#### **Supervisor Agent** - Central Coordinator
**System Prompt**: "You are the central coordinator for a Parkinson's disease assessment system. Your role is to understand user intent, route requests to appropriate agents (AIML for predictions, RAG for knowledge/reports), and orchestrate the overall workflow."

**Responsibilities**:
- Intent detection from user input
- Workflow orchestration
- Agent coordination
- Session management

**Key Methods**:
- `process_user_input()` - Main entry point
- `detect_intent()` - Classify user requests
- `route_to_agent()` - Delegate to AIML or RAG

---

#### **AIML Agent** - Prediction Specialist  
**System Prompt**: "You are an AI/ML specialist focused solely on Parkinson's disease prediction. Analyze MRI scans, process medical images, generate predictions with confidence scores, and provide technical analysis results."

**Responsibilities**:
- MRI scan processing ONLY
- Parkinson's disease prediction
- Confidence score generation
- Technical result presentation

**Key Methods**:
- `classify_parkinsons()` - Main prediction
- `process_mri()` - Image analysis
- Flag monitoring: `PREDICT_PARKINSONS`

**What it does NOT do**:
- Knowledge retrieval
- Report generation
- General medical Q&A

---

#### **RAG Agent** - Knowledge & Reports
**System Prompt**: "You are a medical knowledge specialist and report generator for Parkinson's disease. Retrieve relevant medical information from the knowledge base, answer clinical questions, generate comprehensive medical reports, and handle patient data collection."

**Responsibilities**:
- Knowledge base retrieval (embeddings search)
- Medical question answering
- Report generation (comprehensive PDF reports)
- Patient data collection (admin/doctor workflows)
- Clinical documentation

**Key Methods**:
- `query()` - Knowledge retrieval
- `handle_patient_assessment()` - Complete workflow
- `generate_report()` - PDF creation
- Flag monitoring: `GENERATE_REPORT`

**What it does NOT do**:
- MRI predictions
- AI/ML analysis
- System orchestration

---

### 3. **Report Generator** - Medical Documentation
**Location**: `utils/report_generator.py`

**Role**: Creates professional medical reports

**Key Functions**:
- `collect_admin_patient_data()` - Admin data collection (all optional)
- `collect_doctor_patient_data()` - Doctor data collection (all required)
- `create_comprehensive_pdf_report()` - Generate PDF reports
- Database integration for patient records

**Admin Workflow** (all fields optional):
1. Patient ID (auto-generate if empty)
2. Basic info: name, age, gender, phone
3. Emergency contacts (2)
4. Clinical info: symptoms, allergies
5. Previous testing history
6. Medications, medical history

**Doctor Workflow** (strict requirements):
1. Doctor verification
2. Patient ID (auto-generate or verify existing)
3. Required fields: name, age, gender, phone, emergency contact 1
4. Chief complaint (required)
5. Symptoms list
6. Allergies
7. Previous testing details
8. Medications and history

---

## Data Flow

```
User Input (main.py)
    ↓
Supervisor Agent (intent detection)
    ↓
┌─────────────┬──────────────────┬─────────────┐
│             │                  │             │
AIML Agent    │           RAG Agent           Other
(MRI/Predict) │     (Knowledge/Reports)      (Chat)
    ↓         │              ↓                 ↓
Prediction    │    Knowledge Base          Response
Results       │    + Report Gen            
    ↓         │              ↓                 ↓
Shared Memory │      PDF Report           User
    ↓         │              ↓
Report Flag   └─────→  Complete
```

---

## Patient Assessment Workflow

### **Admin Assessment**:
```
1. admin types: new-assessment
2. main.py → RAG Agent
3. RAG Agent → Report Generator.collect_admin_patient_data()
4. Collect data (all optional)
5. Optional: Add MRI scan
6. Generate PDF report
7. Save to database
8. Display report path
```

### **Doctor Assessment**:
```
1. doctor types: new-assessment  
2. main.py → RAG Agent
3. RAG Agent → Report Generator.collect_doctor_patient_data()
4. Verify doctor credentials
5. Generate/verify patient ID
6. Collect required patient data
7. Optional: Add MRI scan
8. Generate PDF report
9. Save to database
10. Display report path
```

---

## Agent Prompts Summary

| Agent | Primary Prompt Focus | Key Capabilities |
|-------|---------------------|------------------|
| **Supervisor** | "Central coordinator" | Intent, routing, orchestration |
| **AIML** | "Prediction specialist" | MRI analysis, predictions only |
| **RAG** | "Knowledge & reports" | Retrieval, Q&A, documentation |

---

## Key Improvements Made

✅ **Main.py is now minimal** - Just gateway, no bloat
✅ **3 distinct agents** - Each with clear, separate responsibilities  
✅ **Different prompts** - Each agent has unique system prompt
✅ **Clean delegation** - main.py delegates to RAG agent
✅ **Proper data collection** - In report generator, not main.py
✅ **Admin vs Doctor workflows** - Properly separated
✅ **Database integration** - Patient data properly saved
✅ **Report generation** - Comprehensive PDF with all collected data

---

## File Structure

```
ParkinsonsMultiagentSystem/
├── main.py                 # Gateway only
├── agents/
│   ├── supervisor_agent.py  # Central coordinator
│   ├── aiml_agent.py        # Prediction specialist
│   └── rag_agent.py          # Knowledge & reports
├── utils/
│   └── report_generator.py   # Data collection + PDF generation
└── data/
    ├── reports/              # Generated PDFs
    └── parkinsons_system.db  # Patient database
```

---

## Usage Examples

### **Admin Creates Patient**:
```
[ADMIN] > new-assessment
📋 ADMIN PATIENT DATA COLLECTION
(All fields are optional)
Patient ID (press Enter to auto-generate): 
✅ Generated Patient ID: P20251005_A1B2C3D4
...
✅ Report saved: data/reports/P20251005_A1B2C3D4_Report.pdf
```

### **Doctor Creates Patient**:
```
[DOCTOR] > new-assessment
📋 DOCTOR PATIENT DATA COLLECTION
✅ Doctor: Dr. Smith (ID: DOC001)
Patient ID (press Enter to generate new): 
✅ Generated ID: P20251005_X9Y8Z7W6
Patient Full Name (*required*): John Doe
Age (*required*): 65
...
✅ Assessment completed!
```

---

## System Benefits

1. **Modularity**: Each component has single responsibility
2. **Maintainability**: Easy to update individual agents
3. **Scalability**: Can add more agents without affecting others
4. **Clarity**: Clear data flow and responsibilities
5. **Separation**: Business logic separated from gateway
6. **Flexibility**: Easy to modify workflows per role

---

*Last Updated: October 5, 2025*
