# Parkinson's Multiagent System

A comprehensive AI-powered multiagent system for Parkinson's disease analysis using MRI scans. This system implements **explicit triggering only** - all prediction and report generation occurs only when explicitly requested, while maintaining robust chat functionality.

## 🎯 Core Features

- **🤖 Multiagent Architecture**: Supervisor, AI/ML, and RAG agents coordinate via shared memory action flags
- **🧠 AI-Powered Analysis**: TensorFlow/Keras model for Parkinson's disease probability assessment from MRI scans
- **📋 Dual Report Generation**: Separate professional doctor reports and patient-friendly reports
- **🖼️ MRI Processing**: Professional medical image processing with feature extraction and quality assessment
- **📚 Medical Knowledge Base**: Semantic search through Parkinson's clinical guidelines and research
- **💬 Interactive Chat**: Full conversational interface without triggering any processing
- **📄 PDF Report Generation**: Professional medical reports with embedded MRI images
- **💾 Complete Data Persistence**: SQLite database with session history, predictions, reports, and binary MRI storage
- **🔍 Health Monitoring**: Real-time system health checks and component status monitoring
- **🔒 Explicit Triggering**: No automatic processing - all analysis requires explicit user requests

## 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Supervisor     │    │    AI/ML Agent   │    │   RAG Agent     │
│     Agent       │    │                  │    │                 │
│                 │    │ • MRI Processing │    │ • Knowledge     │
│ • Chat Handling │    │ • Feature Extract│    │   Base Search   │
│ • Intent        │    │ • ML Prediction  │    │ • Report        │
│   Detection     │    │                  │    │   Generation    │
│ • Flag Creation │    │ Triggers ONLY on │    │ Triggers ONLY on│
│                 │    │ PREDICT_PARKINSONS│    │ GENERATE_REPORT │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────────┐
                    │   Shared Memory     │
                    │                     │
                    │ • Action Flags      │
                    │ • Event Bus         │
                    │ • Session Data      │
                    │ • Database Access   │
                    └─────────────────────┘
```

### Key Design Principles

1. **🔒 Explicit Triggering Only**: Agents process ONLY when action flags are explicitly set by user requests
2. **🚫 No Direct Communication**: Agents communicate exclusively via shared memory action flags
3. **🎯 Supervisor Orchestration**: All user interaction goes through Supervisor Agent for intent detection
4. **🏷️ Flag-Based Workflow**: `PREDICT_PARKINSONS` → `GENERATE_REPORT` → `REPORT_COMPLETE`
5. **💬 Chat Mode Support**: Full conversational capability without triggering any processing workflows

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+**
- **Groq API Key** (get from [Groq Console](https://console.groq.com))
- **4GB+ RAM** (for TensorFlow model loading)
- **Windows/Linux/macOS** (tested on Windows 10/11)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ParkinsonsMultiagentSystem
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your GROQ_API_KEY
   ```

5. **Start the system**
   ```bash
   python main.py
   ```

## 📋 What Happens When You...

### 🤖 Start the System (`python main.py`)

**What happens:**
1. **System Initialization** (15-30 seconds):
   - Loads TensorFlow/Keras Parkinson's prediction model
   - Initializes SQLite database with migration support
   - Starts shared memory event bus
   - Loads Groq service for AI chat/responses
   - Initializes MRI processor for medical imaging
   - Loads sentence transformer embeddings for knowledge base
   - Starts all three agents (Supervisor, AI/ML, RAG)
   - Loads 13+ medical documents into knowledge base

2. **Patient/Doctor Information Collection**:
   ```
   === Patient Information ===
   Patient name: John Doe
   Generated Patient ID: patient_a1b2c3d4

   === Doctor Information ===
   Doctor name (optional): Dr. Smith
   Generated Doctor ID: doctor_e5f6g7h8
   ```

3. **Interactive Mode Ready**:
   ```
   Parkinson's Multiagent System is ready!
   Type 'quit' to exit, 'health' for health check, or enter a message:
   >
   ```

### 💬 Chat with the System

**What happens when you type general questions:**
```
> What are the symptoms of Parkinson's disease?
System: Parkinson's disease symptoms include tremors, rigidity, bradykinesia...
```

**Internally:**
- Supervisor Agent detects **no processing keywords**
- Routes to Groq API for conversational response
- **No action flags set** - pure chat mode
- Response generated via Llama 3.8B model

### 🔬 Request MRI Analysis

**What happens when you type:**
```
> generate report on "C:\path\to\mri_scan.jpg"
```

**Complete workflow triggered:**
1. **Intent Detection**: Supervisor detects MRI file + "generate report"
2. **Session Creation**: New session with patient/doctor metadata
3. **MRI Storage**: Binary MRI data stored in database
4. **Flag Creation**: `PREDICT_PARKINSONS` flag set
5. **AI/ML Processing**:
   - MRI preprocessing (skull stripping, normalization)
   - Feature extraction (anatomical, intensity, texture)
   - TensorFlow model prediction (57.25% Parkinson's probability)
   - Results stored in database
6. **Prediction Complete**: `PREDICTION_COMPLETE` flag set
7. **Report Generation Triggered**: `GENERATE_REPORT` flag set
8. **RAG Processing**:
   - Retrieves prediction data from shared memory
   - Searches knowledge base for relevant medical info
   - Generates dual reports via Groq API
   - Creates PDF reports with embedded MRI images
9. **Completion**: `REPORT_COMPLETE` flag set

**Output:**
- Doctor PDF: `doctor_report_session_xyz_20250920_011913.pdf`
- Patient PDF: `patient_report_session_xyz_20250920_011913.pdf`
- Both stored in `data/reports/` directory

### 🏥 Health Check

**What happens when you type:**
```
> health
```

**System response:**
```json
{
  "system_status": "healthy",
  "initialization_complete": true,
  "components": {
    "database": {"status": "healthy", "connections": 5},
    "shared_memory": {"status": "healthy", "cache_size": 42},
    "groq_service": {"status": "healthy", "api_responsive": true},
    "supervisor_agent": {"status": "healthy", "active_sessions": 3},
    "aiml_agent": {"status": "healthy", "model_loaded": true},
    "rag_agent": {"status": "healthy", "knowledge_entries": 113}
  }
}
```

### 🛑 System Shutdown

**What happens when you type:**
```
> quit
```

**Graceful shutdown sequence:**
1. Stops all agent monitoring loops
2. Closes database connections
3. Shuts down shared memory event bus
4. Closes Groq API connections
5. Saves any pending data
6. Logs final system state

## 📊 Detailed Workflow Breakdown

### 1. **Chat-Only Mode** (No Processing)
- **Trigger**: General questions, conversation
- **Processing**: Supervisor → Groq API → Response
- **Flags Set**: None
- **Data Stored**: None
- **Example**: "What is Parkinson's disease?"

### 2. **MRI Analysis Only**
- **Trigger**: "analyze mri [file]" or "predict [file]"
- **Processing**: Supervisor → AI/ML Agent → MRI Processing → Prediction
- **Flags**: `PREDICT_PARKINSONS` → `PREDICTION_COMPLETE`
- **Output**: Prediction results displayed
- **Data Stored**: MRI binary data, prediction results

### 3. **Report Generation Only**
- **Trigger**: "generate report" (with existing prediction data)
- **Processing**: Supervisor → RAG Agent → Knowledge Search → Report Generation
- **Flags**: `GENERATE_REPORT` → `REPORT_COMPLETE`
- **Output**: PDF reports generated
- **Data Stored**: Medical reports

### 4. **Combined MRI + Report Workflow**
- **Trigger**: "generate report on [MRI file]"
- **Processing**: Full pipeline (analysis + report)
- **Flags**: `PREDICT_PARKINSONS` → `PREDICTION_COMPLETE` → `GENERATE_REPORT` → `REPORT_COMPLETE`
- **Output**: Prediction results + PDF reports
- **Data Stored**: Everything (MRI, prediction, reports)

### 5. **Error Handling**
- **Invalid MRI**: Graceful error, cleanup flags
- **API Failures**: Retry with exponential backoff
- **Model Errors**: Fallback responses, flag cleanup
- **Database Issues**: Connection retry, data integrity checks

## 🔧 Configuration

### Environment Variables (`.env`)

```bash
# Required: Groq API Configuration
GROQ_API_KEY=your_api_key_here
GROQ_MODEL_CHAT=llama3-8b-8192
GROQ_MODEL_ANALYSIS=llama3-70b-8192
GROQ_MODEL_REPORT=llama3-70b-8192

# Optional: Database Configuration
DATABASE_URL=sqlite:///./data/parkinsons_system.db
DATABASE_ECHO=false
DATABASE_POOL_SIZE=10

# Optional: Model Configuration
PARKINSON_MODEL_PATH=models/parkinsons_model.keras
ENABLE_MOCK_PREDICTIONS=false

# Optional: Logging
LOG_LEVEL=INFO
DEBUG_MODE=false
```

### System Configuration (`config.py`)

**MRI Processing:**
- Target dimensions: (256, 256, 128)
- Supported formats: DICOM, PNG, JPEG, NIfTI
- Quality thresholds: 0.6 minimum score

**AI/ML Agent:**
- Processing timeout: 120 seconds
- Model confidence threshold: 0.7
- Feature validation: 0.6 minimum

**RAG Agent:**
- Knowledge search limit: 5 results
- Relevance threshold: 0.7
- Generation timeout: 60 seconds

**Shared Memory:**
- Cache size: 1000 items
- TTL: 3600 seconds (1 hour)
- Cleanup interval: 300 seconds (5 minutes)

## 📁 Project Structure & File Purposes

```
ParkinsonsMultiagentSystem/
├── main.py                    # 🚀 System entry point & interactive CLI
├── config.py                  # ⚙️ Configuration management
├── requirements.txt           # 📦 Python dependencies
├── README.md                  # 📖 This documentation
│
├── agents/                    # 🤖 Agent implementations
│   ├── supervisor_agent.py    # 🎯 Main orchestrator - intent detection & chat
│   ├── aiml_agent.py         # 🧠 MRI processing & ML predictions
│   └── rag_agent.py          # 📚 Report generation & knowledge search
│
├── core/                     # 🔧 Core system components
│   ├── database.py           # 💾 SQLite database operations
│   └── shared_memory.py      # 📡 Inter-agent communication
│
├── models/                   # 📋 Data structures
│   ├── data_models.py        # 🏗️ Core data classes (User, Session, MRI, etc.)
│   └── agent_interfaces.py   # 🔌 Base agent classes & interfaces
│
├── services/                 # 🔗 External integrations
│   ├── groq_service.py       # 🤖 Groq API (Llama models)
│   └── mri_processor.py      # 🖼️ Medical image processing
│
├── knowledge_base/           # 📚 Medical knowledge
│   └── embeddings_manager.py # 🔍 Text embeddings & semantic search
│
├── utils/                    # 🛠️ Utilities
│   ├── pdf_generator.py      # 📄 PDF report creation
│   └── report_generator.py   # 📝 Report formatting
│
├── data/                     # 💽 Data storage
│   ├── parkinsons_system.db  # 🗄️ SQLite database
│   ├── mri_scans/           # 🖼️ MRI scan storage
│   ├── reports/             # 📄 Generated PDF reports
│   └── embeddings/          # 🔍 Knowledge base vectors
│
└── logs/                     # 📊 System logs
    └── system.log           # 📝 Application logging
```

## 🧪 Testing & Validation

### Available Test Commands

```bash
# Health check (built-in)
python main.py
> health

# Simple validation test
python -c "
import asyncio
from main import ParkinsonsMultiagentSystem
async def test():
    system = ParkinsonsMultiagentSystem()
    await system.initialize()
    health = await system.health_check()
    print('System healthy:', health['system_status'] == 'healthy')
asyncio.run(test())
"
```

### Test Coverage Areas

- ✅ **Explicit Triggering**: Verifies no automatic processing occurs
- ✅ **Chat Functionality**: Confirms conversational responses work
- ✅ **MRI Processing**: Validates image preprocessing and feature extraction
- ✅ **Model Prediction**: Tests TensorFlow model loading and inference
- ✅ **Report Generation**: Validates PDF creation and content accuracy
- ✅ **Database Operations**: Tests data persistence and retrieval
- ✅ **Error Handling**: Validates graceful failure handling

## 📊 Data Storage & Privacy

### Database Schema

**Core Tables:**
- `users` - Patient/doctor information
- `patients` - Extended patient medical data
- `sessions` - User interaction sessions
- `mri_scans` - Binary MRI data storage
- `predictions` - AI model prediction results
- `medical_reports` - Generated report content
- `action_flags` - Inter-agent communication flags

**Security Features:**
- Binary MRI data encryption-ready
- Session-based access control
- Audit logging for all operations
- Automatic cleanup of expired sessions

### Data Flow

1. **Input**: User provides patient info, MRI file, analysis request
2. **Processing**: MRI → preprocessing → feature extraction → AI prediction
3. **Storage**: All data persisted with session tracking
4. **Output**: Dual PDF reports with embedded images
5. **Cleanup**: Automatic removal of expired sessions (24h default)

## 🔍 Monitoring & Troubleshooting

### Log Files

**Main Log**: `logs/system.log`
```
2025-09-20 01:18:13,144 [INFO] parkinsons_system.main: Starting Parkinson's Multiagent System initialization...
2025-09-20 01:18:19,943 [INFO] agents.aiml_agent: [AUDIT] ✅ Model loaded successfully
2025-09-20 01:18:21,479 [INFO] parkinsons_system.main: System initialization completed successfully!
```

### Common Issues & Solutions

**❌ "Model loading failed"**
- Check TensorFlow installation: `pip install tensorflow`
- Verify model file exists: `models/parkinsons_model.keras`
- Check RAM: Minimum 4GB required

**❌ "Groq API error"**
- Verify API key in `.env`: `GROQ_API_KEY=your_key_here`
- Check internet connection
- Confirm API quota/limits

**❌ "Database locked"**
- Close other instances of the application
- Check file permissions on `data/parkinsons_system.db`
- Wait for automatic cleanup (5 minutes)

**❌ "MRI processing failed"**
- Verify image format (PNG/JPG/DICOM supported)
- Check file path validity
- Ensure sufficient disk space

### Performance Metrics

**Initialization Time**: 15-30 seconds
**MRI Processing**: 3-5 seconds per scan
**Prediction Time**: 5-10 seconds
**Report Generation**: 10-20 seconds
**Memory Usage**: 2-4GB RAM during operation

## 🛠️ Development & Extension

### Adding New Features

1. **New Agent**: Extend `BaseAgent` class in `models/agent_interfaces.py`
2. **New Action Flag**: Add to `ActionFlagType` enum in `models/data_models.py`
3. **New Data Model**: Add to `models/data_models.py` with database schema
4. **New Service**: Implement service interface and integrate in `main.py`

### Code Quality Standards

- **Type Hints**: All functions use proper type annotations
- **Async/Await**: All I/O operations are asynchronous
- **Error Handling**: Comprehensive try/catch with logging
- **Documentation**: Docstrings for all classes and methods
- **Logging**: Structured logging with appropriate levels

## 🤝 Usage Guidelines

### Medical Disclaimer

⚠️ **IMPORTANT**: This system is designed for research and educational purposes. All generated reports include explicit disclaimers that results require professional medical interpretation. The system should never be used as a substitute for qualified medical diagnosis or treatment.

### Ethical Considerations

- **No Auto-Diagnosis**: System requires explicit user requests for analysis
- **Clear Disclaimers**: All outputs include medical disclaimers
- **Data Privacy**: Patient data handled according to privacy principles
- **Professional Oversight**: Designed to augment, not replace, medical professionals

## 📞 Support & Contributing

### Getting Help

1. **Check Health Status**: Type `health` in interactive mode
2. **Review Logs**: Check `logs/system.log` for detailed information
3. **Validate Setup**: Ensure all dependencies are installed correctly
4. **Test Components**: Use built-in health checks to isolate issues

### Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Make changes with comprehensive testing
4. Update documentation as needed
5. Submit pull request with detailed description

---

**🎯 Key Reminder**: This system implements **explicit triggering only**. No MRI processing, prediction, or report generation occurs automatically - all analysis must be explicitly requested by users through specific commands like "generate report on [MRI file]".

**🔬 Research Focus**: Designed for Parkinson's disease analysis research, with comprehensive data collection and analysis capabilities for medical AI development.

### Prerequisites

- Python 3.9+
- Groq API key (get from [Groq Console](https://console.groq.com))

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ParkinsonsMultiagentSystem
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your GROQ_API_KEY
   ```

4. **Run tests**
   ```bash
   # Using the simple test runner
   python tests/run_tests.py
   
   # Or using pytest if installed
   pytest tests/test_explicit_triggering.py -v
   ```

5. **Start the system**
   ```bash
   python main.py
   ```

## 📋 Usage Examples

### Chat Mode (No Processing Triggered)

```
> Hello, what can you help me with?
System: I'm here to help with Parkinson's disease analysis...

> What are the symptoms of Parkinson's disease?
System: Parkinson's disease symptoms include tremors, rigidity...

> Can you explain how MRI scans work?
System: MRI (Magnetic Resonance Imaging) uses magnetic fields...
```

**✅ No action flags set - pure conversational mode**

### Explicit MRI Analysis

```
> Please analyze this MRI scan for Parkinson's: /path/to/scan.dcm
System: I'll analyze the MRI scan for Parkinson's disease indicators...

[System sets PREDICT_PARKINSONS flag]
[AI/ML Agent processes the scan]
[Analysis results stored in shared memory]

System: Analysis complete. Parkinson's probability: 75%
```

**✅ PREDICT_PARKINSONS flag explicitly set and processed**

### Explicit Report Generation

```
> Please generate a comprehensive medical report
System: I'll generate a detailed medical report based on the analysis...

[System sets GENERATE_REPORT flag]
[RAG Agent generates report using knowledge base]
[Report stored in shared memory]

System: Medical report generated successfully.
```

**✅ GENERATE_REPORT flag explicitly set and processed**

### Combined Workflow

```
> Hi, I need to analyze an MRI scan
System: Hello! I can help you analyze MRI scans for Parkinson's disease.

> Please analyze /data/patient_123.dcm for Parkinson's disease
System: Analyzing MRI scan... [PREDICT_PARKINSONS flag set]
System: Analysis complete. Results show 82% probability of Parkinson's.

> Now generate a detailed medical report please
System: Generating comprehensive report... [GENERATE_REPORT flag set]
System: Medical report generated with findings and recommendations.

> Thank you! What should the patient do next?
System: Based on the high probability result, I recommend...
```

## 🔧 Configuration

### Environment Variables

```bash
# Required: Groq API Configuration
GROQ_API_KEY=your_api_key_here
GROQ_MODEL_CHAT=llama3-8b-8192
GROQ_MODEL_ANALYSIS=llama3-70b-8192
GROQ_MODEL_REPORT=llama3-70b-8192

# Optional: Database Configuration  
DATABASE_URL=sqlite:///./data/parkinsons_system.db
DATABASE_ECHO=false

# Optional: Logging
LOG_LEVEL=INFO
DEBUG_MODE=false
```

### System Configuration

Key configuration options in `config.py`:

- **MRI Processing**: Image dimensions, preprocessing pipeline, quality thresholds
- **Agent Timeouts**: Response timeouts, retry limits, confidence thresholds  
- **Embeddings**: Model selection, cache settings, similarity thresholds
- **Database**: Connection pooling, cleanup intervals, session management

## 📊 Workflow Details

### 1. Chat-Only Workflow
- User asks general questions
- Supervisor Agent responds via Groq
- **No action flags set**
- No other agents activated

### 2. Explicit MRI Prediction Workflow
1. User explicitly requests MRI analysis
2. Supervisor Agent sets `PREDICT_PARKINSONS` flag
3. AI/ML Agent claims flag and processes:
   - MRI preprocessing and feature extraction
   - ML model prediction
   - Results stored in shared memory
4. Flag marked complete
5. Supervisor responds with results

### 3. Explicit Report Generation Workflow
1. User explicitly requests report generation
2. Supervisor Agent sets `GENERATE_REPORT` flag  
3. RAG Agent claims flag and processes:
   - Retrieves prediction data from shared memory
   - Searches knowledge base for relevant information
   - Generates comprehensive report via Groq
   - Stores report in shared memory
4. Flag marked complete
5. Supervisor responds with report access

### 4. Error Handling
- Invalid MRI files: Graceful error messages, flag cleanup
- Missing predictions: Reports indicate missing data
- API failures: Retry logic with exponential backoff
- Agent timeouts: Automatic flag cleanup and user notification

## 🧪 Testing

### Test Coverage

- **Explicit Triggering**: Verifies no automatic processing occurs
- **Chat-Only Mode**: Confirms chat works without setting flags
- **Flag-Based Communication**: Tests agent isolation and shared memory communication
- **Combined Workflows**: Validates full analysis and report generation sequences
- **Error Handling**: Tests graceful failure handling

### Running Tests

```bash
# Simple test runner (no dependencies)
python tests/run_tests.py

# Full pytest suite (requires pytest)
pytest tests/ -v

# Specific test categories
pytest tests/test_explicit_triggering.py::TestChatOnlyWorkflow -v
pytest tests/test_explicit_triggering.py::TestExplicitMRIPredictionWorkflow -v
pytest tests/test_explicit_triggering.py::TestExplicitReportGenerationWorkflow -v
```

## 📁 Project Structure

```
ParkinsonsMultiagentSystem/
├── agents/                    # Agent implementations
│   ├── __init__.py
│   ├── supervisor_agent.py    # Main orchestrator agent
│   ├── aiml_agent.py         # MRI processing and ML prediction
│   └── rag_agent.py          # Report generation and knowledge retrieval
├── core/                     # Core system components
│   ├── __init__.py
│   ├── database.py           # Database operations
│   └── shared_memory.py      # Inter-agent communication
├── knowledge_base/           # Knowledge management
│   ├── __init__.py
│   └── embeddings_manager.py # Text embeddings and similarity search
├── models/                   # Data models and interfaces
│   ├── __init__.py
│   ├── agent_interfaces.py   # Base agent classes
│   └── data_models.py        # Core data structures
├── services/                 # External service integrations
│   ├── __init__.py
│   ├── groq_service.py       # Groq API integration
│   └── mri_processor.py      # MRI image processing
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── run_tests.py          # Simple test runner
│   └── test_explicit_triggering.py  # Comprehensive tests
├── utils/                    # Utility modules
│   ├── __init__.py
│   └── report_generator.py   # Report formatting and generation
├── config.py                 # Configuration management
├── main.py                   # Application entry point
├── requirements.txt          # Python dependencies
├── .env.example             # Environment configuration template
└── README.md                # This file
```

## 🔍 Monitoring and Health Checks

### System Health Check

```python
# Programmatic health check
health_status = await system.health_check()

# Interactive health check
> health
Health Status: {
  'system_status': 'healthy',
  'components': {
    'database': {'status': 'healthy', 'connections': 5},
    'shared_memory': {'status': 'healthy', 'cache_size': 42},
    'groq_service': {'status': 'healthy', 'api_responsive': True},
    'supervisor_agent': {'status': 'healthy', 'active_sessions': 3}
  }
}
```

### Logs and Debugging

- **Console Logging**: INFO level for general operation
- **File Logging**: DEBUG level in `logs/system.log`
- **Agent Logging**: Individual agent operation tracking
- **Flag Monitoring**: Action flag lifecycle logging

## 🛠️ Development

### Adding New Functionality

1. **New Agent**: Extend `BaseAgent` class
2. **New Flag Type**: Add to `ActionFlag` enum and implement handling
3. **New Data Model**: Add to `data_models.py` with validation
4. **New Service**: Implement service interface and integrate

### Best Practices

- All agent communication via shared memory action flags
- Explicit triggering only - no automatic processing
- Comprehensive error handling and logging
- Async/await for all I/O operations
- Type hints and docstrings for all functions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Run test suite: `python tests/run_tests.py`
5. Commit changes: `git commit -am 'Add new feature'`
6. Push to branch: `git push origin feature/new-feature`
7. Submit a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For questions, issues, or contributions:

1. Check the test suite: `python tests/run_tests.py`
2. Review the logs: `logs/system.log`
3. Check health status: Type `health` in interactive mode
4. Create an issue with system health output and relevant logs

---

**Key Reminder**: This system implements **explicit triggering only**. No MRI processing or report generation occurs automatically - all analysis must be explicitly requested by users. Chat functionality works independently without triggering any processing workflows.