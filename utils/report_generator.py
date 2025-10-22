"""
Medical Report Generator for Parkinson's Disease Assessment
===========================================================
One-page professional medical reports for doctors and patients.

Version: 3.0.0 - Concise Edition
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, Color
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors


class MedicalReportGenerator:
    """Generate concise 1-page medical reports"""
    
    # Professional color scheme
    HEADER_BLUE = HexColor('#1E3A8A')
    ACCENT_BLUE = HexColor('#3B82F6')
    TEXT_GRAY = HexColor('#374151')
    
    def __init__(self, embeddings_manager=None):
        self.styles = getSampleStyleSheet()
        self.embeddings_manager = embeddings_manager  # For KB retrieval
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Helper function to add or update style
        def add_or_update_style(name, **kwargs):
            if name in self.styles:
                # Update existing style
                style = self.styles[name]
                for key, value in kwargs.items():
                    setattr(style, key, value)
            else:
                # Add new style
                self.styles.add(ParagraphStyle(name=name, **kwargs))
        
        # Title style
        add_or_update_style(
            'ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=self.HEADER_BLUE,
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        # Subtitle style
        add_or_update_style(
            'ReportSubtitle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.TEXT_GRAY,
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        # Section header
        add_or_update_style(
            'SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=11,
            textColor=self.HEADER_BLUE,
            spaceAfter=4,
            spaceBefore=8,
            fontName='Helvetica-Bold'
        )
        
        # Body text (BodyText already exists in getSampleStyleSheet, so update it)
        add_or_update_style(
            'BodyText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.TEXT_GRAY,
            spaceAfter=4,
            leading=11
        )
    
    async def generate_doctor_report(
        self, 
        patient_id: str,
        patient_name: str,
        age: int,
        gender: str,
        prediction_data: Dict[str, Any],
        mri_path: Optional[str] = None
    ) -> str:
        """
        Generate concise 1-page doctor report
        
        Includes:
        - Patient demographics
        - MRI scan
        - Diagnosis & stage
        - Medications
        - Clinical recommendations
        """
        # Setup PDF
        output_dir = Path("data/reports/doctor")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"DR_{patient_id}_{timestamp}.pdf"
        filepath = output_dir / filename
        
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        story = []
        
        # Header
        story.append(Paragraph("PARKINSON'S DISEASE ASSESSMENT", self.styles['ReportTitle']))
        story.append(Paragraph(
            f"Medical Report - {datetime.now().strftime('%B %d, %Y')}", 
            self.styles['ReportSubtitle']
        ))
        story.append(Spacer(1, 0.1*inch))
        
        # Patient Information
        patient_data = [
            ['Patient ID:', patient_id, 'Date:', datetime.now().strftime('%Y-%m-%d')],
            ['Name:', patient_name, 'Age:', str(age)],
            ['Gender:', gender, 'Report Type:', 'Clinical Assessment']
        ]
        
        patient_table = Table(patient_data, colWidths=[1*inch, 2*inch, 0.8*inch, 1.7*inch])
        patient_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F3F4F6')),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#F3F4F6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), self.TEXT_GRAY),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(patient_table)
        story.append(Spacer(1, 0.15*inch))
        
        # MRI Scan (if available)
        if mri_path and os.path.exists(mri_path):
            try:
                img = Image(mri_path, width=2*inch, height=2*inch)
                story.append(Paragraph("MRI Scan", self.styles['SectionHeader']))
                story.append(img)
                story.append(Spacer(1, 0.1*inch))
            except:
                pass
        
        # Diagnosis & Stage
        story.append(Paragraph("CLINICAL DIAGNOSIS", self.styles['SectionHeader']))
        
        binary_result = prediction_data.get('binary_result', 'Uncertain')
        stage = prediction_data.get('stage_result', 'N/A')
        confidence = prediction_data.get('confidence_score', 0.0)
        
        diagnosis_color = colors.red if binary_result == 'Positive' else colors.green
        
        diagnosis_data = [
            ['Result:', binary_result, 'Confidence:', f"{confidence*100:.1f}%"],
            ['Stage:', f"Hoehn & Yahr Stage {stage}", 'ICD-10:', 'G20']
        ]
        
        diagnosis_table = Table(diagnosis_data, colWidths=[1*inch, 2.5*inch, 1*inch, 1*inch])
        diagnosis_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FEF3C7')),
            ('TEXTCOLOR', (1, 0), (1, 0), diagnosis_color),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(diagnosis_table)
        story.append(Spacer(1, 0.15*inch))
        
        # Recommended Medications
        story.append(Paragraph("RECOMMENDED MEDICATIONS", self.styles['SectionHeader']))
        
        medications = self._get_medications_for_stage(stage, binary_result)
        
        med_data = [['Medication', 'Dosage', 'Frequency']]
        for med in medications:
            med_data.append([med['name'], med['dosage'], med['frequency']])
        
        med_table = Table(med_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
        med_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.HEADER_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')])
        ]))
        story.append(med_table)
        story.append(Spacer(1, 0.15*inch))
        
        # Clinical Recommendations (from KB)
        story.append(Paragraph("CLINICAL RECOMMENDATIONS", self.styles['SectionHeader']))
        recommendations = await self._get_clinical_recommendations(stage, binary_result)
        for rec in recommendations:
            story.append(Paragraph(f"• {rec}", self.styles['BodyText']))
        
        # Footer
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            "<i>This report is AI-assisted. Clinical correlation required. Physician review mandatory.</i>",
            self.styles['BodyText']
        ))
        
        # Build PDF
        doc.build(story)
        
        return str(filepath)
    
    async def generate_patient_report(
        self,
        patient_id: str,
        patient_name: str,
        age: int,
        prediction_data: Dict[str, Any]
    ) -> str:
        """
        Generate concise 1-page patient-friendly report
        
        Includes:
        - Simple diagnosis
        - Disease stage explanation
        - Medications
        - Lifestyle recommendations
        """
        # Setup PDF
        output_dir = Path("data/reports/patient")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"PT_{patient_id}_{timestamp}.pdf"
        filepath = output_dir / filename
        
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        story = []
        
        # Header
        story.append(Paragraph("YOUR HEALTH REPORT", self.styles['ReportTitle']))
        story.append(Paragraph(
            f"Parkinson's Disease Assessment - {datetime.now().strftime('%B %d, %Y')}", 
            self.styles['ReportSubtitle']
        ))
        story.append(Spacer(1, 0.15*inch))
        
        # Patient Info
        story.append(Paragraph(f"<b>Name:</b> {patient_name} | <b>Age:</b> {age} | <b>ID:</b> {patient_id}", self.styles['BodyText']))
        story.append(Spacer(1, 0.15*inch))
        
        # Diagnosis
        story.append(Paragraph("YOUR DIAGNOSIS", self.styles['SectionHeader']))
        
        binary_result = prediction_data.get('binary_result', 'Uncertain')
        stage = prediction_data.get('stage_result', 'N/A')
        
        if binary_result == 'Positive':
            diagnosis_text = f"<b>You have been diagnosed with Parkinson's Disease, Stage {stage}.</b>"
            diagnosis_color = colors.HexColor('#FEE2E2')
        else:
            diagnosis_text = "<b>No signs of Parkinson's Disease detected.</b>"
            diagnosis_color = colors.HexColor('#D1FAE5')
        
        diagnosis_box = Table([[diagnosis_text]], colWidths=[5.5*inch])
        diagnosis_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), diagnosis_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), self.TEXT_GRAY),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(diagnosis_box)
        story.append(Spacer(1, 0.15*inch))
        
        # Stage Explanation (if positive)
        if binary_result == 'Positive':
            story.append(Paragraph("WHAT THIS MEANS", self.styles['SectionHeader']))
            stage_info = await self._get_stage_explanation(stage)
            story.append(Paragraph(stage_info, self.styles['BodyText']))
            story.append(Spacer(1, 0.15*inch))
        
        # Medications
        story.append(Paragraph("YOUR MEDICATIONS", self.styles['SectionHeader']))
        
        if binary_result == 'Positive':
            medications = self._get_medications_for_stage(stage, binary_result)
            for med in medications:
                story.append(Paragraph(
                    f"<b>{med['name']}</b>: {med['dosage']}, {med['frequency']}", 
                    self.styles['BodyText']
                ))
        else:
            story.append(Paragraph("No medications required at this time.", self.styles['BodyText']))
        
        story.append(Spacer(1, 0.15*inch))
        
        # Lifestyle Recommendations
        story.append(Paragraph("LIFESTYLE RECOMMENDATIONS", self.styles['SectionHeader']))
        lifestyle_tips = await self._get_lifestyle_recommendations_from_kb(stage, binary_result)
        for tip in lifestyle_tips:
            story.append(Paragraph(f"✓ {tip}", self.styles['BodyText']))
        
        # Footer
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            "<i>Please discuss this report with your doctor. Follow their guidance for treatment.</i>",
            self.styles['BodyText']
        ))
        
        # Build PDF
        doc.build(story)
        
        return str(filepath)
    
    def _get_medications_for_stage(self, stage: str, result: str) -> list:
        """Get medication recommendations based on stage"""
        if result != 'Positive':
            return []
        
        stage_num = int(stage) if stage.isdigit() else 1
        
        if stage_num <= 1:
            return [
                {'name': 'Carbidopa-Levodopa', 'dosage': '25-100mg', 'frequency': '3 times daily'},
                {'name': 'Rasagiline', 'dosage': '1mg', 'frequency': 'Once daily'}
            ]
        elif stage_num == 2:
            return [
                {'name': 'Carbidopa-Levodopa', 'dosage': '25-100mg', 'frequency': '3-4 times daily'},
                {'name': 'Pramipexole', 'dosage': '0.5mg', 'frequency': '3 times daily'},
                {'name': 'Entacapone', 'dosage': '200mg', 'frequency': 'With each levodopa dose'}
            ]
        else:  # Stage 3+
            return [
                {'name': 'Carbidopa-Levodopa', 'dosage': '25-250mg', 'frequency': '4-5 times daily'},
                {'name': 'Pramipexole ER', 'dosage': '3mg', 'frequency': 'Once daily'},
                {'name': 'Amantadine', 'dosage': '100mg', 'frequency': 'Twice daily'},
                {'name': 'Selegiline', 'dosage': '5mg', 'frequency': 'Twice daily'}
            ]
    
    async def _get_medications_from_kb(self, stage: str, result: str) -> list:
        """Retrieve medication recommendations from knowledge base"""
        if result != 'Positive' or not self.embeddings_manager:
            return self._get_medications_for_stage(stage, result)
        
        try:
            # Search KB for stage-specific medication information
            search_query = f"Parkinson's disease stage {stage} medications treatment levodopa dopamine"
            search_results = await self.embeddings_manager.search_similar(
                query_text=search_query,
                k=3
            )
            
            # If we get good results, use fallback (medications need precise dosing)
            # Keep hardcoded for safety, but log KB findings
            if search_results:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Found {len(search_results)} KB entries for stage {stage} medications")
            
            # Return standard medications (medical safety - don't parse from text)
            return self._get_medications_for_stage(stage, result)
            
        except Exception as e:
            # Fallback to hardcoded if KB search fails
            return self._get_medications_for_stage(stage, result)
    
    async def _get_lifestyle_recommendations_from_kb(self, stage: str, result: str) -> list:
        """Retrieve lifestyle recommendations from knowledge base - NO HARDCODING"""
        if result != 'Positive':
            # For negative results, get general health tips from KB
            if self.embeddings_manager:
                try:
                    search_results = await self.embeddings_manager.search_similar(
                        query_text="healthy lifestyle exercise diet prevention neurological health",
                        k=3
                    )
                    
                    recommendations = []
                    for result_item in search_results:
                        content = result_item.get('text', '')
                        # Extract actionable recommendations from content
                        if content and len(content) > 50:
                            # Simple extraction: look for sentences with key action words
                            sentences = content.split('.')
                            for sentence in sentences[:5]:  # First 5 sentences
                                if any(word in sentence.lower() for word in ['exercise', 'diet', 'sleep', 'healthy', 'should', 'recommended']):
                                    clean_sentence = sentence.strip()
                                    if len(clean_sentence) > 20 and len(clean_sentence) < 150:
                                        recommendations.append(clean_sentence)
                                        if len(recommendations) >= 5:
                                            break
                    
                    if recommendations:
                        return recommendations[:5]
                except:
                    pass
            
            # Fallback for negative results
            return [
                "Exercise regularly (30 minutes daily)",
                "Maintain balanced diet rich in fruits and vegetables",
                "Get adequate sleep (7-8 hours)",
                "Stay socially active and engaged",
                "Manage stress through relaxation techniques"
            ]
        
        # For positive results, get stage-specific lifestyle recommendations from KB
        if not self.embeddings_manager:
            return self._get_lifestyle_recommendations_fallback(stage)
        
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            # Search KB for stage-specific lifestyle and management strategies
            search_query = f"Parkinson's disease stage {stage} lifestyle recommendations exercise diet management daily activities"
            logger.info(f"🔍 Searching KB for lifestyle recommendations: '{search_query}'")
            
            search_results = await self.embeddings_manager.search_similar(
                query_text=search_query,
                k=5  # Get top 5 relevant chunks
            )
            
            logger.info(f"📚 Found {len(search_results)} KB results for stage {stage} lifestyle recommendations")
            
            recommendations = []
            
            # Extract actionable recommendations from KB results
            for result_item in search_results:
                content = result_item.get('text', '')
                similarity = result_item.get('score', 0.0)
                source = result_item.get('metadata', {}).get('source_file', 'Unknown')
                
                logger.info(f"  - Processing result from {source} (similarity: {similarity:.3f})")
                
                if content and similarity > 0.3:  # Only use relevant results
                    # Split into sentences
                    sentences = content.replace('\n', '. ').split('.')
                    
                    for sentence in sentences:
                        sentence = sentence.strip()
                        
                        # Look for actionable lifestyle advice
                        action_keywords = [
                            'exercise', 'physical therapy', 'walk', 'activity', 'movement',
                            'diet', 'nutrition', 'eat', 'food', 'meal',
                            'sleep', 'rest', 'fatigue',
                            'social', 'support', 'group', 'family',
                            'medication', 'therapy', 'treatment',
                            'avoid', 'prevent', 'reduce', 'manage',
                            'daily', 'routine', 'schedule'
                        ]
                        
                        # Check if sentence contains lifestyle advice
                        if any(keyword in sentence.lower() for keyword in action_keywords):
                            # Clean and format the sentence
                            if 20 < len(sentence) < 200:  # Reasonable length
                                # Remove references like [1], (Smith et al.)
                                clean_sentence = sentence
                                import re
                                clean_sentence = re.sub(r'\[\d+\]', '', clean_sentence)
                                clean_sentence = re.sub(r'\([^)]*et al[^)]*\)', '', clean_sentence)
                                clean_sentence = clean_sentence.strip()
                                
                                if clean_sentence and clean_sentence not in recommendations:
                                    recommendations.append(clean_sentence)
                                    logger.info(f"    ✓ Extracted: {clean_sentence[:60]}...")
                        
                        if len(recommendations) >= 10:  # Get enough options
                            break
                
                if len(recommendations) >= 10:
                    break
            
            # If we found good recommendations from KB, return them
            if len(recommendations) >= 5:
                logger.info(f"✅ Using {len(recommendations)} KB-retrieved lifestyle recommendations")
                return recommendations[:9]  # Return top 9
            else:
                logger.warning(f"⚠️ Only found {len(recommendations)} recommendations in KB, using fallback")
                return self._get_lifestyle_recommendations_fallback(stage)
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Error retrieving lifestyle recommendations from KB: {e}")
            return self._get_lifestyle_recommendations_fallback(stage)
    
    def _get_lifestyle_recommendations_fallback(self, stage: str) -> list:
        """Fallback lifestyle recommendations if KB retrieval fails"""
        return [
            "Daily exercise: walking, swimming, or tai chi (30-60 minutes)",
            "Physical therapy sessions 2-3 times per week",
            "High-fiber diet to manage constipation",
            "Stay hydrated (8 glasses of water daily)",
            "Join a Parkinson's support group",
            "Practice voice exercises and facial expressions",
            "Use assistive devices as recommended by therapist",
            "Avoid alcohol and smoking",
            "Get regular sleep on consistent schedule"
        ]
    
    async def _get_clinical_recommendations(self, stage: str, result: str) -> list:
        """Get clinical recommendations from KB for doctor report"""
        if result != 'Positive':
            # For negative results, retrieve general monitoring recommendations from KB
            if self.embeddings_manager:
                try:
                    search_results = await self.embeddings_manager.search_similar(
                        query_text="neurological health monitoring annual assessment preventive care",
                        k=2
                    )
                    
                    recommendations = []
                    for result_item in search_results:
                        content = result_item.get('text', '')
                        if content:
                            sentences = content.split('.')
                            for sentence in sentences[:3]:
                                if any(word in sentence.lower() for word in ['monitor', 'assess', 'follow-up', 'screening']):
                                    clean_sentence = sentence.strip()
                                    if 20 < len(clean_sentence) < 150:
                                        recommendations.append(clean_sentence)
                                        if len(recommendations) >= 3:
                                            break
                    
                    if recommendations:
                        return recommendations[:3]
                except:
                    pass
            
            # Fallback for negative results
            return [
                "Continue routine health monitoring",
                "Annual neurological assessment recommended",
                "Maintain healthy lifestyle and exercise regimen"
            ]
        
        # For positive results, retrieve stage-specific clinical recommendations from KB
        if not self.embeddings_manager:
            return self._get_clinical_recommendations_fallback(stage)
        
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            # Search KB for stage-specific clinical management
            search_query = f"Parkinson's disease stage {stage} Hoehn Yahr clinical management treatment therapy dopaminergic physical therapy"
            logger.info(f"🔍 Searching KB for clinical recommendations: '{search_query}'")
            
            search_results = await self.embeddings_manager.search_similar(
                query_text=search_query,
                k=5
            )
            
            logger.info(f"📚 Found {len(search_results)} KB results for stage {stage} clinical recommendations")
            
            recommendations = []
            
            # Extract clinical recommendations from KB
            for result_item in search_results:
                content = result_item.get('text', '')
                similarity = result_item.get('score', 0.0)
                
                if content and similarity > 0.3:
                    sentences = content.replace('\n', '. ').split('.')
                    
                    for sentence in sentences:
                        sentence = sentence.strip()
                        
                        # Look for clinical action items
                        clinical_keywords = [
                            'therapy', 'treatment', 'medication', 'dopamine', 'levodopa',
                            'physical therapy', 'occupational therapy', 'speech therapy',
                            'follow-up', 'monitor', 'assess', 'refer', 'consider',
                            'initiate', 'optimize', 'adjust', 'manage'
                        ]
                        
                        if any(keyword in sentence.lower() for keyword in clinical_keywords):
                            if 20 < len(sentence) < 200:
                                import re
                                clean_sentence = re.sub(r'\[\d+\]', '', sentence)
                                clean_sentence = re.sub(r'\([^)]*et al[^)]*\)', '', clean_sentence)
                                clean_sentence = clean_sentence.strip()
                                
                                if clean_sentence and clean_sentence not in recommendations:
                                    recommendations.append(clean_sentence)
                                    logger.info(f"    ✓ Clinical rec: {clean_sentence[:60]}...")
                        
                        if len(recommendations) >= 8:
                            break
                
                if len(recommendations) >= 8:
                    break
            
            if len(recommendations) >= 4:
                logger.info(f"✅ Using {len(recommendations)} KB-retrieved clinical recommendations")
                return recommendations[:6]
            else:
                logger.warning(f"⚠️ Only found {len(recommendations)} clinical recommendations in KB, using fallback")
                return self._get_clinical_recommendations_fallback(stage)
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Error retrieving clinical recommendations from KB: {e}")
            return self._get_clinical_recommendations_fallback(stage)
    
    def _get_clinical_recommendations_fallback(self, stage: str) -> list:
        """Fallback clinical recommendations if KB retrieval fails"""
        stage_num = int(stage) if stage.isdigit() else 1
        
        if stage_num <= 1:
            return [
                "Initiate dopaminergic therapy with low-dose Carbidopa-Levodopa",
                "Refer to physical therapy for gait and balance training",
                "Educate patient on disease progression and symptom management",
                "Schedule follow-up in 3 months to assess treatment response"
            ]
        elif stage_num == 2:
            return [
                "Optimize medication regimen; consider adding COMT inhibitor",
                "Intensive physical and occupational therapy recommended",
                "Assess for motor fluctuations and dyskinesias",
                "Consider speech therapy for voice/swallowing issues",
                "Monthly follow-up appointments"
            ]
        else:  # Stage 3+
            return [
                "Consider advanced therapies (DBS, pump therapies)",
                "Multidisciplinary care team: PT, OT, speech therapy",
                "Home safety evaluation and modifications",
                "Caregiver support and respite care resources",
                "Weekly or bi-weekly monitoring"
            ]
    
    async def _get_stage_explanation(self, stage: str) -> str:
        """Get patient-friendly stage explanation from KB"""
        if not self.embeddings_manager:
            return self._get_stage_explanation_fallback(stage)
        
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            # Search KB for stage-specific patient explanation
            search_query = f"Parkinson's disease Hoehn Yahr stage {stage} symptoms progression patient explanation"
            logger.info(f"🔍 Searching KB for stage {stage} explanation")
            
            search_results = await self.embeddings_manager.search_similar(
                query_text=search_query,
                k=3
            )
            
            if search_results and len(search_results) > 0:
                # Extract explanation from top result
                content = search_results[0].get('text', '')
                similarity = search_results[0].get('score', 0.0)
                
                if content and similarity > 0.4:
                    # Look for explanatory sentences
                    sentences = content.replace('\n', '. ').split('.')
                    
                    for sentence in sentences:
                        sentence = sentence.strip()
                        # Look for stage descriptions
                        if any(word in sentence.lower() for word in ['stage', 'symptom', 'balance', 'movement', 'disability']):
                            if 30 < len(sentence) < 250:
                                import re
                                clean_sentence = re.sub(r'\[\d+\]', '', sentence)
                                clean_sentence = re.sub(r'\([^)]*et al[^)]*\)', '', clean_sentence)
                                clean_sentence = clean_sentence.strip()
                                
                                if clean_sentence:
                                    logger.info(f"✅ Using KB explanation for stage {stage}")
                                    return clean_sentence
            
            # If no good KB result, use fallback
            logger.warning(f"⚠️ No suitable KB explanation for stage {stage}, using fallback")
            return self._get_stage_explanation_fallback(stage)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Error retrieving stage explanation from KB: {e}")
            return self._get_stage_explanation_fallback(stage)
    
    def _get_stage_explanation_fallback(self, stage: str) -> str:
        """Fallback patient-friendly stage explanation"""
        explanations = {
            '1': "Early stage - Symptoms are mild and on one side of your body. You can manage daily activities independently.",
            '2': "Moderate stage - Symptoms affect both sides but balance is maintained. You may notice slower movements.",
            '3': "Mid-stage - Balance problems may occur. Some help with daily tasks may be needed.",
            '4': "Advanced stage - Significant disability. Assistance needed for most activities.",
            '5': "Severe stage - Wheelchair or bed-bound. Full-time care required."
        }
        return explanations.get(stage, "Your doctor will explain your specific stage.")
    
    def _get_lifestyle_recommendations(self, stage: str, result: str) -> list:
        """DEPRECATED: Use _get_lifestyle_recommendations_from_kb instead"""
        # This is kept for backward compatibility but should not be used
        return [
            "Daily exercise: walking, swimming, or tai chi (30-60 minutes)",
            "Physical therapy sessions 2-3 times per week",
            "High-fiber diet to manage constipation",
            "Stay hydrated (8 glasses of water daily)",
            "Join a Parkinson's support group",
            "Practice voice exercises and facial expressions",
            "Use assistive devices as recommended by therapist",
            "Avoid alcohol and smoking",
            "Get regular sleep on consistent schedule"
        ]


# Convenience function for backward compatibility
async def generate_concise_reports(
    patient_id: str,
    patient_name: str,
    age: int,
    gender: str,
    prediction_data: Dict[str, Any],
    mri_path: Optional[str] = None
) -> Dict[str, str]:
    """Generate both doctor and patient reports"""
    generator = MedicalReportGenerator()
    
    doctor_report = await generator.generate_doctor_report(
        patient_id, patient_name, age, gender, prediction_data, mri_path
    )
    
    patient_report = await generator.generate_patient_report(
        patient_id, patient_name, age, prediction_data
    )
    
    return {
        'doctor_report': doctor_report,
        'patient_report': patient_report
    }
