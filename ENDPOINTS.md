# FastAPI Endpoint Map

This file lists FastAPI endpoints recommended for the project. For each file I read in the last scan I include:
- the file path I read
- the endpoints suggested (HTTP method + path)
- the intended purpose, auth/roles, and brief request/response shapes (Pydantic models to create)

Use this as a living document. I'll update it as I read more files.

---

## Files read in this pass

Below are the files scanned and the FastAPI endpoints they suggest.

### File: `main.py`
- Purpose: system orchestration, initialization, health checks, interactive flows

Endpoints:
- GET /health
  - Purpose: overall system health summary (database, shared_memory, groq, agents)
  - Auth: none (or optional admin)
  - Response: { system_status, components: { database, shared_memory, groq_service, supervisor_agent, aiml_agent, rag_agent } }

- POST /initialize
  - Purpose: initialize services (db, shared memory, agents) programmatically
  - Auth: admin
  - Response: { status: "initializing" }

- POST /shutdown
  - Purpose: graceful shutdown
  - Auth: admin
  - Response: { status: "shutting_down" }

- POST /auth/test (or POST /authenticate)
  - Purpose: run authentication-only flow (used by CLI flow in main.py)
  - Auth: none
  - Request: { username?, password?, flow: 'interactive' | 'token' }
  - Response: { success: bool, user: UserOut }

Notes:
- These endpoints map main app lifecycle functions into an HTTP surface. Keep idempotency in mind.

### File: `agents/aiml_agent.py`
- Purpose: MRI processing and Parkinson's prediction (ONNX / TensorFlow / Groq fallbacks)

Endpoints:
- POST /mri/upload
  - Purpose: upload an MRI file (stores via FileManager/Database and creates a session)
  - Auth: doctor/admin/patient (patient can upload their own)
  - Request: multipart/form-data { file: UploadFile, patient_id?: str, metadata?: dict }
  - Response: { session_id, mri_scan_id }

- POST /mri/{session_id}/predict
  - Purpose: trigger prediction for an existing MRI/session (creates PREDICT_PARKINSONS flag)
  - Auth: doctor/admin/patient (RBAC enforced)
  - Request: { priority?: int }
  - Response: { flag_id }

- GET /mri/{session_id}/prediction
  - Purpose: retrieve latest prediction for a session
  - Auth: doctor/admin/patient (patient only their own)
  - Response: PredictionResult (prediction_id, binary_result, stage_result, confidence scores, metadata)

- GET /aiml/health
  - Purpose: agent-level health, model availability (onnx/tf), stats
  - Auth: admin
  - Response: { mri_processor_status, tensorflow_model_status, onnx_status, processing_stats }

Notes:
- Request/response shapes should use Pydantic models reflecting `models.data_models.PredictionResult`.
- Upload should store binary in DB or filesystem via FileManager and call shared_memory.set_action_flag.

### File: `agents/rag_agent.py`
- Purpose: retrieval-augmented generation and report synthesis using Groq + embeddings manager + MedicalReportGenerator

Endpoints:
- POST /reports/generate
  - Purpose: request generation of a medical report for session or patient (creates GENERATE_REPORT flag)
  - Auth: doctor/admin/patient (doctor requires patient_id)
  - Request: { session_id, report_type?: 'comprehensive'|'summary'|'patient_friendly', patient_id?: str }
  - Response: { flag_id }

- GET /reports/{report_id}
  - Purpose: fetch report metadata and content summary stored in DB (not the PDF binary)
  - Auth: doctor/admin/patient (RBAC)
  - Response: MedicalReport metadata (id, session_id, title, confidence, recommendations, pdf paths)

- GET /reports/session/{session_id}
  - Purpose: list reports for a session
  - Auth: role dependent
  - Response: [ MedicalReportOut ]

- GET /reports/{report_id}/download
  - Purpose: download the report PDF (doctor or patient copy)
  - Auth: doctor/admin/patient
  - Response: FileResponse (application/pdf)

- GET /rag/health
  - Purpose: RAG agent health and knowledge base status
  - Auth: admin
  - Response: { knowledge_base_status, reports_generated, generation_stats }

Notes:
- `generate_doctor_report` and `generate_patient_report` in `utils/report_generator.py` produce PDF files; endpoints should return DB-stored PDF paths or stream files via FastAPI's FileResponse.

### File: `agents/supervisor_agent.py`
- Purpose: orchestrates workflows, intent detection, smart CRUD admin commands

Endpoints:
- POST /sessions
  - Purpose: create a session (wraps create_session logic used in CLI)
  - Auth: authenticated users
  - Request: { user_id, user_role, patient_id?, doctor_id?, metadata? }
  - Response: { session_id }

- POST /sessions/{session_id}/input
  - Purpose: send user input to SupervisorAgent (chat, prediction request, report request)
  - Auth: user associated with session
  - Request: { message: str, metadata?: dict, mri_file_path?: str }
  - Response: { response: string or structured Response model }

- POST /orchestrate/{session_id}/{workflow_type}
  - Purpose: programmatically start workflows (prediction/report)
  - Auth: admin or orchestrator service
  - Response: { status, flag_id }

- GET /supervisor/agents/status
  - Purpose: aggregated agent statuses
  - Auth: admin

Notes:
- Responses should use a Pydantic `Response` model similar to `models.data_models.Response`.

### File: `services/groq_service.py`
- Purpose: centralized LLM interface; used by Supervisor, AIML, and RAG agents

Endpoints (service admin/diagnostics):
- GET /llm/health
  - Purpose: test Groq connectivity
  - Auth: admin
  - Response: { status, model, response_time }

- POST /llm/explain_prediction
  - Purpose: synchronous wrapper to get an explanation for a prediction (used by AIMLAgent)
  - Auth: internal (service-token) or admin
  - Request: { prediction_result: dict }
  - Response: { explanation: str }

- POST /llm/generate_report
  - Purpose: wrapper for Groq generate_medical_report (used by RAGAgent)
  - Auth: internal
  - Request: { prediction_data: dict, knowledge_entries: list, patient_data?: dict }
  - Response: { title, executive_summary, clinical_findings, diagnostic_assessment, recommendations, confidence_level }

Notes:
- These endpoints implement logic that GroqService already exposes as async methods. For FastAPI, expose admin/internal HTTP wrappers for testing and diagnostics.

### File: `models/agent_interfaces.py`
- Purpose: defines interfaces & base classes for agents; not an HTTP file, but drives required API schemas

Action items for API design:
- Convert data classes from `models/data_models.py` to Pydantic models in `api/schemas.py`:
  - UserIn, UserOut
  - SessionCreate, SessionOut (maps SessionData)
  - MRIUploadIn, MRIScanOut (maps MRIData)
  - PredictionResultOut
  - MedicalReportOut
  - ActionFlagOut

Notes:
- Many agent methods refer to these models; mapping them to Pydantic will make request/response validation simple.

### File: `utils/report_generator.py`
- Purpose: generate concise 1-page PDF reports (doctor + patient), using embeddings manager for KB-driven recommendations

Endpoints (related):
- POST /reports/concise/generate
  - Purpose: convenience endpoint that requests both doctor and patient concise reports for a session/patient
  - Auth: doctor/admin/patient
  - Request: { session_id, patient_id?, report_variant?: 'concise'|'patient'|'doctor' }
  - Response: { doctor_pdf_path, patient_pdf_path }

- GET /reports/concise/{patient_id}/latest
  - Purpose: fetch the most recent concise report file paths
  - Auth: patient/doctor/admin
  - Response: { doctor_pdf_path, patient_pdf_path, generated_at }

Notes:
- Endpoints should stream PDF files when requested and return metadata in DB otherwise.
- Be cautious with heavy synchronous PDF generation; make endpoint call background task (Celery / FastAPI background task) if generation can be slow.

### Cross-cutting endpoints (recommended)
- POST /auth/login
  - Request: { username, password }
  - Response: { access_token, token_type }

- GET /users/{user_id}
- GET /patients/{patient_id}
- GET /doctors/{doctor_id}
- GET /files/mri/{mri_id} (download or metadata)
- GET /files/reports/{report_id}/download
- POST /kb/search
  - Request: { query: str, k?: int }
  - Response: [ { title, content, source, similarity } ]
- POST /kb/rebuild
  - Purpose: rebuild embeddings/index (admin)

---

## Next steps / Implementation notes
- Create `api/schemas.py` with Pydantic models that mirror `models/data_models.py`.
- Create `api/routes/` modules grouping endpoints: `health.py`, `auth.py`, `sessions.py`, `mri.py`, `predictions.py`, `reports.py`, `kb.py`, `admin.py`.
- Wire the endpoints to services via dependency injection: DatabaseManager, SharedMemoryInterface, FileManager, GroqService, EmbeddingsManager.
- Protect admin/doctor routes with role-based dependency (AuthenticationManager + JWT).
- For long-running jobs (prediction, PDF generation), return a 202 Accepted with flag_id and provide polling endpoints to check completion (/flags/{flag_id}/status).
- Convert agent dataclasses into Pydantic schemas (small effort but increases reliability).

If you want, I can now:
- scaffold the FastAPI project files and create the Pydantic schemas for the top models listed above, or
- continue scanning remaining files and append them to this document.
## FastAPI Endpoint Specification

This document lists the FastAPI endpoints recommended for the ParkinsonsMultiagentSystem
based on the repository files inspected. For each file read, the endpoints that the file
suggests or requires are listed with HTTP method, path, request/response shape, auth role,
and implementation notes (side-effects, flags, DB writes).

---

### Files read
- `core/database.py` (DatabaseManager)
- `core/shared_memory.py` (SharedMemoryInterface + EventBus)
- `models/data_models.py` (Pydantic/dataclass shapes & enums)
- `auth/authentication.py` (AuthenticationManager)
- `auth/user_management.py` (legacy helper flows)
- `utils/file_manager.py` (FileManager helper functions)
- `knowledge_base/embeddings_manager.py` (EmbeddingsManager)
- `services/mri_processor.py` (MRIProcessor)
- `utils/report_generator.py` (MedicalReportGenerator)

---

## Top-level cross-cutting endpoints (system)

- GET /health
  - Purpose: Combined system health (shared memory + DB + embeddings + services)
  - Response: { status, database: {...}, shared_memory: {...}, embeddings: {...} }
  - Auth: none (or api-key for production)
  - Notes: implement by delegating to SharedMemoryInterface.health_check() and DatabaseManager.health_check().

- GET /admin/dashboard
  - Purpose: Admin summary/stats
  - Response: { summary: {...}, doctors: [...], patients: [...], recent_reports: [...] }
  - Auth: Admin
  - Maps to: DatabaseManager.get_admin_dashboard()

---

## Endpoints per file

### core/database.py

- POST /users
  - Purpose: Create user (admin/doctor/patient)
  - Body: UserCreate (email, name, role, password? optional depending on role)
  - Response: { id }
  - Auth: Admin
  - Maps to: DatabaseManager.create_user / authentication flows

- GET /users/{user_id}
  - Purpose: Get user details
  - Response: User model
  - Auth: Admin or owner

- GET /users?role={role}
  - Purpose: List users, filter by role
  - Auth: Admin

- POST /patients
  - Purpose: Create patient
  - Body: PatientCreate (patient_id optional, name, age, gender, assigned_doctor_id)
  - Response: { patient_id }
  - Auth: Admin or Doctor
  - Maps to: DatabaseManager.create_patient()

- GET /patients/{patient_id}
  - Purpose: Get patient record with optional reports
  - Response: Patient or patient-with-reports
  - Auth: Doctor (if assigned) or Patient owner or Admin
  - Maps to: DatabaseManager.get_patient(), get_patient_with_reports()

- GET /patients (paginated)
  - Purpose: List patients (optionally by doctor)
  - Auth: Admin/Doctor

- POST /sessions
  - Purpose: Create a new interaction session
  - Body: SessionCreate (input_type, output_format, user_id, optional patient_id)
  - Response: { session_id }
  - Auth: Any authenticated user
  - Maps to: DatabaseManager.create_session(); SharedMemoryInterface.create_session() wrapper

- GET /sessions/{session_id}
  - Purpose: Get session summary (mri scans, predictions, reports)
  - Response: { session, mri_scans, predictions, reports, action_flags }
  - Auth: Session owner / Admin / Doctor assigned
  - Maps to: DatabaseManager.get_session_summary()

- POST /mri_scans
  - Purpose: Upload MRI scan (multipart/form-data or provide server path)
  - Body: multipart with file, session_id, original_filename, file_type
  - Response: { scan_id, file_path }
  - Auth: Authenticated user
  - Side effects: calls DatabaseManager.store_mri_scan(), FileManager.save_mri_scan(), publishes event via SharedMemoryInterface.event_bus

- GET /mri_scans/session/{session_id}
  - Purpose: List MRI scans for session
  - Response: [mri scan metadata]
  - Auth: Owner / Doctor / Admin

- GET /mri_scans/{scan_id}/binary
  - Purpose: Download MRI binary (if stored in DB or file system)
  - Response: application/octet-stream
  - Auth: Owner / Doctor / Admin
  - Maps to: DatabaseManager.get_mri_binary_data() or FileManager.read_file()

- POST /predictions/trigger
  - Purpose: Ask system to run prediction on a session or specific MRI
  - Body: { session_id, mri_scan_id (optional), priority (optional) }
  - Response: { flag_id, status: 'scheduled' }
  - Auth: Owner / Doctor / Admin
  - Side effects: creates ActionFlag ActionFlagType.PREDICT_PARKINSONS via SharedMemoryInterface.set_action_flag()

- GET /predictions/session/{session_id}/latest
  - Purpose: Get latest prediction for session
  - Response: PredictionResult
  - Auth: Owner / Doctor / Admin
  - Maps to: SharedMemoryInterface.get_latest_prediction()/DatabaseManager.get_latest_prediction()

- GET /predictions/session/{session_id}
  - Purpose: List all predictions for session
  - Response: [PredictionResult]
  - Auth: Owner / Doctor / Admin

- POST /reports/generate
  - Purpose: Request a report generation for a session/patient
  - Body: { session_id, patient_id?, report_type: 'full'|'summary'|'patient_friendly', requested_by }
  - Response: { report_request_id }
  - Auth: Doctor / Admin / Patient (depending on flow)
  - Side effects: creates ActionFlag ActionFlagType.GENERATE_REPORT via SharedMemoryInterface.set_action_flag(); DatabaseManager.create_report_request()

- GET /reports/session/{session_id}
  - Purpose: List reports generated for a session
  - Response: [medical_reports rows]
  - Auth: Owner / Doctor assigned / Admin
  - Maps to: DatabaseManager.get_reports_by_session()

- GET /reports/{report_id}/download
  - Purpose: Download report PDF or text
  - Response: file stream
  - Auth: Owner / Doctor assigned / Admin
  - Maps to: FileManager.read_file(report.file_path)

### Notes (database)
- Many DB helper endpoints map to admin dashboards and CRUD for doctors, consultations, timelines, and report_status as implemented in DatabaseManager. Implement pagination, rate-limits and role checks.

---

### core/shared_memory.py

- POST /flags
  - Purpose: Create an action flag (used internally by supervisor or external API)
  - Body: { session_id, flag_type, data, priority, expires_in_minutes }
  - Response: { flag_id }
  - Auth: internal system / Agent API key
  - Maps to: SharedMemoryInterface.set_action_flag()

- GET /flags/pending?flag_type={flag_type}
  - Purpose: List pending flags (agents poll this)
  - Response: [ActionFlag]
  - Auth: Agent / System
  - Maps to: SharedMemoryInterface.get_pending_flags()

- POST /flags/{flag_id}/claim
  - Purpose: Agent claims a flag
  - Body: { agent_id }
  - Response: { success }
  - Auth: Agent credentials
  - Maps to: SharedMemoryInterface.claim_action_flag()

- POST /flags/{flag_id}/complete
  - Purpose: Mark flag completed
  - Response: success
  - Auth: Agent
  - Maps to: SharedMemoryInterface.complete_action_flag()

- GET /events/subscribe (websocket)
  - Purpose: Real-time event subscriptions for UIs/agents
  - Auth: Agent / Web UI with auth token
  - Notes: Implements EventBus websocket or Server-Sent Events to stream messages like flag_created, prediction_stored, report_stored.

---

### models/data_models.py

This file defines data shapes. Implement corresponding Pydantic models for all request/response bodies. Examples:

- Pydantic models to create: SessionCreate, MRIUploadResponse, PredictionResponse, MedicalReportOut, UserCreate, PatientCreate, ActionFlagCreate.

Use enums from this module (InputType, OutputFormat, ActionFlagType, etc.) in FastAPI parameter types.

---

### auth/authentication.py and auth/user_management.py

- POST /auth/login
  - Purpose: Login flow (admin/doctor/patient)
  - Body: { role: 'admin'|'doctor'|'patient', credentials }
  - Response: { success, token, user }
  - Notes: Admin uses password, doctor uses doctor_id+password, patients may be passwordless. Return JWT or session token.

- POST /auth/register/doctor
  - Purpose: Register doctor (admin-only in many flows)
  - Body: { doctor_id, name, password, license_number, specialization, email }
  - Response: { success, doctor_id }
  - Auth: Admin

- POST /auth/register/patient
  - Purpose: Register patient (doctor or admin can register)
  - Body: { patient_id optional, name, age, gender, assigned_doctor_id }
  - Response: { success, patient_id }
  - Auth: Doctor or Admin

- GET /auth/me
  - Purpose: Return current user profile from token
  - Auth: Any

### Notes (auth)
- Implement JWT tokens with role claims. Use AuthenticationManager.check_permissions for RBAC decisions server-side.

---

### utils/file_manager.py

- POST /files/reports (upload)
  - Purpose: Upload/store a report file (used rarely; reports are produced server-side)
  - Body: multipart file, role, user_id, patient_id
  - Response: { path }
  - Auth: Admin/Doctor/Patient

- GET /files/reports/user/{user_role}/{user_id}
  - Purpose: List saved reports for user
  - Response: [ file paths ]
  - Auth: Owner/Doctor/Admin

- POST /files/mri/upload
  - Purpose: Save MRI file into repository (legacy or admin upload)
  - Body: multipart file, patient_id, session_id
  - Response: { saved_path }
  - Auth: Admin/Doctor/Patient

---

### knowledge_base/embeddings_manager.py

- POST /kb/documents/load
  - Purpose: Load documents from disk into embeddings (admin/setup)
  - Body: { directory_path optional }
  - Response: { total_files, loaded_files, total_chunks }
  - Auth: Admin
  - Maps to: EmbeddingsManager.load_documents_from_directory()

- POST /kb/texts/add
  - Purpose: Add a single text chunk to embeddings
  - Body: { text, metadata (optional), text_id (optional) }
  - Response: { text_id }
  - Auth: Admin

- POST /kb/search
  - Purpose: Semantic search
  - Body: { query_text, k (optional) }
  - Response: [ { id, text, similarity, metadata } ]
  - Auth: Doctor / Admin / System
  - Maps to: EmbeddingsManager.search_similar()

- POST /kb/rebuild-index
  - Purpose: Rebuild index from saved embeddings
  - Auth: Admin
  - Maps to: EmbeddingsManager.rebuild_index()

---

### services/mri_processor.py

- POST /mri/process
  - Purpose: Preprocess MRI and extract features
  - Body: { file_path OR upload file, session_id }
  - Response: { processing_result: { quality_metrics, processed_dimensions, status } }
  - Auth: System/Agent/Doctor
  - Maps to: MRIProcessor.preprocess_mri() and extract_features()

- POST /mri/features/validate
  - Purpose: Validate extracted features
  - Body: { features }
  - Response: { is_valid, quality_score, warnings, errors }
  - Auth: Agent/System
  - Maps to: MRIProcessor.validate_features()

- POST /mri/save-training
  - Purpose: Save MRI for training dataset (preserve training dataset on reset)
  - Body: { source_file_path, patient_id, diagnosis, stage, session_id, metadata }
  - Response: { image_path, metadata_path }
  - Auth: Admin/Doctor/System
  - Maps to: MRIProcessor.save_mri_for_training()

---

### utils/report_generator.py (MedicalReportGenerator)

- POST /reports/generate/doctor
  - Purpose: Generate doctor PDF report immediately
  - Body: { session_id, patient_id, patient_name, age, gender, prediction_data, mri_path (optional) }
  - Response: { file_path }
  - Auth: Doctor / Admin
  - Maps to: MedicalReportGenerator.generate_doctor_report(); should also call SharedMemoryInterface.store_report() to persist metadata

- POST /reports/generate/patient
  - Purpose: Generate patient-friendly PDF report
  - Body: { session_id, patient_id, patient_name, age, prediction_data }
  - Response: { file_path }
  - Auth: Doctor / Patient / Admin
  - Maps to: MedicalReportGenerator.generate_patient_report()

- GET /reports/kb/recommendations
  - Purpose: Return KB-driven clinical / lifestyle recommendations given stage/result
  - Query: ?stage=2&result=Positive
  - Response: [recommendations]
  - Auth: Doctor / Admin
  - Notes: This endpoint should call embeddings_manager.search_similar() then run report-generator parsing logic.

---

## Implementation notes and priorities

- Priority 1 (must-have):
  - /mri upload, /predictions/trigger, /reports/generate, /reports/{id}/download, /auth/login, /sessions create/get, health endpoint.

- Priority 2 (nice to have):
  - KB search endpoints, embeddings management, admin dashboards, doctor/patient CRUD endpoints.

- Security & Auth:
  - Use JWT with role claims. Enforce role-based checks server-side for each endpoint.
  - Protect agent endpoints (flag creation/claim/complete) with an internal API key or mutual TLS.

- Data shapes:
  - Implement Pydantic models that mirror classes in `models/data_models.py`.
  - Ensure file uploads stream to FileManager then DB (store path and optionally binary in DB).

- Background processing:
  - Prediction and report generation should be scheduled via action flags (SharedMemoryInterface) and handled by agents (AIMLAgent, RAGAgent) workers. Endpoints only create flags and return immediate ack.

---

## Next steps (implementation checklist)

1. Create Pydantic models for request/response based on `models/data_models.py`.
2. Implement auth (JWT) wrappers and dependency to extract current user and role.
3. Implement core endpoints (sessions, mri upload, prediction trigger, report request, report download).
4. Implement agent-facing endpoints for flags (internal only) and a websocket/events stream for real-time notifications.
5. Implement KB search endpoints and admin endpoints to load/rebuild embeddings.
6. Add unit tests for happy paths: MRI upload → prediction flag → prediction stored → report request → report file generated and persisted.

If you want, I can scaffold a FastAPI app with these endpoints and Pydantic models next. Tell me which endpoints you want implemented first and I'll generate the code and tests.
