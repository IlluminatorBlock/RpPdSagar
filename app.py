"""
Streamlit Web Application for Parkinson's Multiagent System
Professional Medical Interface with Chat, File Upload, and Monitoring
"""

import streamlit as st
import asyncio
import logging
import json
import uuid
import time
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import your main system
from main import ParkinsonsMultiagentSystem

# Configure page
st.set_page_config(
    page_title="Parkinson's Multiagent System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for medical interface
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        text-align: center;
    }
    
    .patient-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    .status-indicator {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
    }
    
    .status-healthy { background-color: #28a745; }
    .status-warning { background-color: #ffc107; }
    .status-error { background-color: #dc3545; }
    
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 10px;
        border-left: 4px solid #007bff;
        background: #f8f9fa;
    }
    
    .system-message {
        border-left-color: #28a745;
        background: #d4edda;
    }
    
    .error-message {
        border-left-color: #dc3545;
        background: #f8d7da;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


class StreamlitApp:
    def __init__(self):
        self.system: Optional[ParkinsonsMultiagentSystem] = None
        self.initialize_session_state()
    
    def initialize_session_state(self):
        """Initialize Streamlit session state variables"""
        if 'system_initialized' not in st.session_state:
            st.session_state.system_initialized = False
        
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        
        if 'patient_info' not in st.session_state:
            st.session_state.patient_info = {}
        
        if 'doctor_info' not in st.session_state:
            st.session_state.doctor_info = {}
        
        if 'session_id' not in st.session_state:
            st.session_state.session_id = f"session_{uuid.uuid4().hex[:8]}"
        
        if 'health_data' not in st.session_state:
            st.session_state.health_data = []
        
        if 'system_metrics' not in st.session_state:
            st.session_state.system_metrics = {
                'total_queries': 0,
                'successful_responses': 0,
                'error_count': 0,
                'avg_response_time': 0
            }
    
    async def initialize_system(self):
        """Initialize the Parkinson's Multiagent System"""
        if not st.session_state.system_initialized:
            try:
                with st.spinner("Initializing Parkinson's Multiagent System..."):
                    self.system = ParkinsonsMultiagentSystem()
                    await self.system.start()
                    st.session_state.system_initialized = True
                    st.success("✅ System initialized successfully!")
                    
                    # Add initialization message to chat
                    st.session_state.chat_history.append({
                        'timestamp': datetime.now(),
                        'type': 'system',
                        'message': 'Parkinson\'s Multiagent System is now ready to assist you.',
                        'metadata': {}
                    })
                    
            except Exception as e:
                st.error(f"❌ Failed to initialize system: {str(e)}")
                st.session_state.system_initialized = False
    
    def render_header(self):
        """Render the main header"""
        st.markdown("""
        <div class="main-header">
            <h1>🧠 Parkinson's Multiagent System</h1>
            <p>Advanced AI-Powered Medical Analysis and Consultation Platform</p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_sidebar(self):
        """Render the sidebar with patient/doctor info and system controls"""
        with st.sidebar:
            st.header("🏥 Session Information")
            
            # Patient Information
            st.subheader("👤 Patient Information")
            patient_name = st.text_input(
                "Patient Name", 
                value=st.session_state.patient_info.get('patient_name', ''),
                key="patient_name_input"
            )
            
            if patient_name and patient_name != st.session_state.patient_info.get('patient_name', ''):
                st.session_state.patient_info = {
                    'patient_id': f"patient_{uuid.uuid4().hex[:8]}",
                    'patient_name': patient_name
                }
                st.success(f"Patient ID: {st.session_state.patient_info['patient_id']}")
            
            # Doctor Information
            st.subheader("👨‍⚕️ Doctor Information")
            doctor_name = st.text_input(
                "Doctor Name", 
                value=st.session_state.doctor_info.get('doctor_name', ''),
                key="doctor_name_input"
            )
            
            if doctor_name and doctor_name != st.session_state.doctor_info.get('doctor_name', ''):
                st.session_state.doctor_info = {
                    'doctor_id': f"doctor_{uuid.uuid4().hex[:8]}",
                    'doctor_name': doctor_name
                }
                st.success(f"Doctor ID: {st.session_state.doctor_info['doctor_id']}")
            
            st.divider()
            
            # System Status
            st.subheader("🔧 System Status")
            if st.session_state.system_initialized:
                st.markdown('<span class="status-indicator status-healthy"></span>System Online', 
                           unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-indicator status-error"></span>System Offline', 
                           unsafe_allow_html=True)
            
            # System Metrics
            st.subheader("📊 Session Metrics")
            metrics = st.session_state.system_metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Queries", metrics['total_queries'])
                st.metric("Success Rate", f"{(metrics['successful_responses']/max(metrics['total_queries'], 1)*100):.1f}%")
            with col2:
                st.metric("Errors", metrics['error_count'])
                st.metric("Avg Response", f"{metrics['avg_response_time']:.2f}s")
            
            st.divider()
            
            # System Controls
            st.subheader("⚙️ System Controls")
            if st.button("🔄 Reset Chat"):
                st.session_state.chat_history = []
                st.rerun()
            
            if st.button("🆕 New Session"):
                st.session_state.session_id = f"session_{uuid.uuid4().hex[:8]}"
                st.session_state.chat_history = []
                st.success("New session started!")
                st.rerun()
    
    def render_chat_interface(self):
        """Render the main chat interface"""
        st.header("💬 Medical Consultation Chat")
        
        # Chat history container
        chat_container = st.container()
        
        with chat_container:
            for message in st.session_state.chat_history:
                self.render_chat_message(message)
        
        # Chat input
        with st.form("chat_form", clear_on_submit=True):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                user_input = st.text_area(
                    "Enter your message:",
                    placeholder="Describe symptoms, ask questions, or request analysis...",
                    height=100,
                    key="chat_input"
                )
            
            with col2:
                st.write("")  # Spacing
                st.write("")  # Spacing
                submitted = st.form_submit_button("Send 📤", use_container_width=True)
                
                # File upload
                uploaded_file = st.file_uploader(
                    "Upload MRI/Image",
                    type=['png', 'jpg', 'jpeg', 'dcm', 'nii'],
                    key="file_upload"
                )
        
        # Process message
        if submitted and user_input.strip():
            self.process_user_message(user_input, uploaded_file)
        
        # Auto-scroll to bottom
        if st.session_state.chat_history:
            st.empty()
    
    def render_chat_message(self, message):
        """Render a single chat message"""
        timestamp = message['timestamp'].strftime("%H:%M:%S")
        msg_type = message['type']
        content = message['message']
        
        if msg_type == 'user':
            st.markdown(f"""
            <div class="chat-message">
                <strong>👤 You</strong> <small>({timestamp})</small><br>
                {content}
            </div>
            """, unsafe_allow_html=True)
            
        elif msg_type == 'system':
            st.markdown(f"""
            <div class="chat-message system-message">
                <strong>🤖 System</strong> <small>({timestamp})</small><br>
                {content}
            </div>
            """, unsafe_allow_html=True)
            
        elif msg_type == 'error':
            st.markdown(f"""
            <div class="chat-message error-message">
                <strong>❌ Error</strong> <small>({timestamp})</small><br>
                {content}
            </div>
            """, unsafe_allow_html=True)
    
    async def process_user_message(self, message: str, uploaded_file=None):
        """Process user message through the system"""
        if not st.session_state.system_initialized:
            st.error("System not initialized. Please wait for initialization to complete.")
            return
        
        # Add user message to chat
        st.session_state.chat_history.append({
            'timestamp': datetime.now(),
            'type': 'user',
            'message': message,
            'metadata': {'file_uploaded': uploaded_file is not None if uploaded_file else False}
        })
        
        # Update metrics
        st.session_state.system_metrics['total_queries'] += 1
        
        try:
            start_time = time.time()
            
            # Prepare metadata
            metadata = {
                'session_id': st.session_state.session_id,
                'user_id': 'streamlit_user',
                **st.session_state.patient_info,
                **st.session_state.doctor_info
            }
            
            # Handle file upload
            if uploaded_file:
                # Save uploaded file temporarily
                file_path = f"temp_{uploaded_file.name}"
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                metadata['uploaded_file'] = file_path
                message = f"{message}\n[File uploaded: {uploaded_file.name}]"
            
            # Process through system
            with st.spinner("Processing your request..."):
                response = await self.system.process_user_input(message, metadata)
            
            # Calculate response time
            response_time = time.time() - start_time
            st.session_state.system_metrics['avg_response_time'] = (
                (st.session_state.system_metrics['avg_response_time'] * 
                 (st.session_state.system_metrics['total_queries'] - 1) + response_time) /
                st.session_state.system_metrics['total_queries']
            )
            
            # Extract response content
            if hasattr(response, 'content'):
                response_content = response.content
            else:
                response_content = response.get('message', 'No response received')
            
            # Add system response to chat
            st.session_state.chat_history.append({
                'timestamp': datetime.now(),
                'type': 'system',
                'message': response_content,
                'metadata': {'response_time': response_time}
            })
            
            st.session_state.system_metrics['successful_responses'] += 1
            
        except Exception as e:
            # Add error message to chat
            st.session_state.chat_history.append({
                'timestamp': datetime.now(),
                'type': 'error',
                'message': f"Error processing request: {str(e)}",
                'metadata': {}
            })
            
            st.session_state.system_metrics['error_count'] += 1
            st.error(f"Error: {str(e)}")
        
        finally:
            st.rerun()
    
    def render_monitoring_dashboard(self):
        """Render system monitoring dashboard"""
        st.header("📊 System Monitoring Dashboard")
        
        # System health check
        if st.button("🔍 Check System Health"):
            if self.system:
                try:
                    with st.spinner("Checking system health..."):
                        health_data = self.system.health_check()
                    
                    # Store health data
                    health_data['timestamp'] = datetime.now()
                    st.session_state.health_data.append(health_data)
                    
                    # Display current health
                    self.display_health_status(health_data)
                    
                except Exception as e:
                    st.error(f"Health check failed: {str(e)}")
        
        # Health history chart
        if st.session_state.health_data:
            self.render_health_charts()
    
    def display_health_status(self, health_data):
        """Display current system health status"""
        st.subheader("Current System Health")
        
        # Overall status
        overall_status = health_data.get('system_status', 'unknown')
        status_color = {
            'healthy': '🟢',
            'warning': '🟡', 
            'error': '🔴',
            'stopped': '⚫'
        }.get(overall_status, '⚪')
        
        st.markdown(f"**Overall Status:** {status_color} {overall_status.title()}")
        
        # Component status
        components = health_data.get('components', {})
        if components:
            st.subheader("Component Status")
            
            cols = st.columns(3)
            for i, (component, status) in enumerate(components.items()):
                with cols[i % 3]:
                    component_status = status.get('status', 'unknown') if isinstance(status, dict) else 'unknown'
                    status_emoji = {
                        'healthy': '✅',
                        'warning': '⚠️',
                        'error': '❌',
                        'unknown': '❓'
                    }.get(component_status, '❓')
                    
                    st.metric(
                        label=component.replace('_', ' ').title(),
                        value=status_emoji,
                        delta=component_status.title()
                    )
    
    def render_health_charts(self):
        """Render health monitoring charts"""
        if len(st.session_state.health_data) < 2:
            return
        
        st.subheader("Health Trends")
        
        # Prepare data for charts
        df_health = pd.DataFrame(st.session_state.health_data)
        df_health['timestamp'] = pd.to_datetime(df_health['timestamp'])
        
        # System status over time
        fig_status = go.Figure()
        status_map = {'healthy': 1, 'warning': 0.5, 'error': 0, 'stopped': -1}
        
        fig_status.add_trace(go.Scatter(
            x=df_health['timestamp'],
            y=[status_map.get(status, 0) for status in df_health['system_status']],
            mode='lines+markers',
            name='System Status',
            line=dict(color='blue')
        ))
        
        fig_status.update_layout(
            title="System Status Over Time",
            xaxis_title="Time",
            yaxis_title="Status Level",
            yaxis=dict(tickvals=[1, 0.5, 0, -1], ticktext=['Healthy', 'Warning', 'Error', 'Stopped'])
        )
        
        st.plotly_chart(fig_status, use_container_width=True)


async def main():
    """Main application function"""
    app = StreamlitApp()
    
    # Render header
    app.render_header()
    
    # Initialize system
    await app.initialize_system()
    
    # Create main layout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Main tabs
        tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Monitoring", "📋 Analytics"])
        
        with tab1:
            app.render_chat_interface()
        
        with tab2:
            app.render_monitoring_dashboard()
        
        with tab3:
            st.header("📈 Analytics Dashboard")
            
            # Session analytics
            if st.session_state.chat_history:
                # Message count over time
                messages_df = pd.DataFrame(st.session_state.chat_history)
                messages_df['timestamp'] = pd.to_datetime(messages_df['timestamp'])
                
                fig_messages = px.histogram(
                    messages_df, 
                    x='timestamp', 
                    color='type',
                    title="Message Activity Over Time"
                )
                st.plotly_chart(fig_messages, use_container_width=True)
                
                # Message type distribution
                type_counts = messages_df['type'].value_counts()
                fig_pie = px.pie(
                    values=type_counts.values,
                    names=type_counts.index,
                    title="Message Type Distribution"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No chat data available yet. Start a conversation to see analytics.")
    
    with col2:
        app.render_sidebar()


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())