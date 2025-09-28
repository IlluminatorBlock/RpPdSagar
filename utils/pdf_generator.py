"""
PDF Report Generator for Parkinson's Multiagent System

This module handles the generation of professional PDF medical reports
using ReportLab for layout and formatting.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
import logging

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """Generates professional PDF medical reports"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for medical reports"""
        
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Title'],
            fontSize=18,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.darkblue,
            borderWidth=1,
            borderColor=colors.darkblue,
            borderPadding=5
        ))
        
        # Medical text style
        self.styles.add(ParagraphStyle(
            name='MedicalText',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            leftIndent=20
        ))
        
        # Recommendation style
        self.styles.add(ParagraphStyle(
            name='Recommendation',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            leftIndent=30,
            bulletIndent=20,
            bulletFontName='Helvetica-Bold'
        ))
        
        # Disclaimer style
        self.styles.add(ParagraphStyle(
            name='Disclaimer',
            parent=self.styles['Normal'],
            fontSize=9,
            spaceAfter=6,
            textColor=colors.red,
            alignment=TA_JUSTIFY,
            borderWidth=1,
            borderColor=colors.red,
            borderPadding=10
        ))
    
    def generate_medical_report_pdf(self, report_data: Dict[str, Any], output_path: str) -> str:
        """
        Generate a comprehensive PDF medical report
        
        Args:
            report_data: Dictionary containing report information
            output_path: Path where PDF should be saved
            
        Returns:
            Path to generated PDF file
        """
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Create PDF document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Build story (content)
            story = []
            
            # Header
            self._add_header(story, report_data)
            
            # Executive Summary
            self._add_executive_summary(story, report_data)
            
            # Clinical Findings
            self._add_clinical_findings(story, report_data)
            
            # MRI Image Section
            self._add_mri_image(story, report_data)
            
            # Diagnostic Assessment
            self._add_diagnostic_assessment(story, report_data)
            
            # Prediction Results Table
            self._add_prediction_results(story, report_data)
            
            # Recommendations
            self._add_recommendations(story, report_data)
            
            # Knowledge References
            self._add_references(story, report_data)
            
            # Disclaimer
            self._add_disclaimer(story, report_data)
            
            # Footer
            self._add_footer(story, report_data)
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"PDF report generated successfully: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {e}")
            raise
    
    def _add_header(self, story, report_data):
        """Add report header"""
        # Main title
        title = Paragraph("PARKINSON'S DISEASE ANALYSIS REPORT", self.styles['ReportTitle'])
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Report metadata table
        metadata = [
            ['Report ID:', report_data.get('report_id', 'N/A')],
            ['Session ID:', report_data.get('session_id', 'N/A')],
            ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Report Type:', report_data.get('report_type', 'Comprehensive Analysis')]
        ]
        
        metadata_table = Table(metadata, colWidths=[2*inch, 4*inch])
        metadata_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(metadata_table)
        story.append(Spacer(1, 20))
    
    def _add_executive_summary(self, story, report_data):
        """Add executive summary section"""
        story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        
        summary_text = report_data.get('executive_summary', 
            'MRI analysis completed using AI-assisted evaluation. This report provides preliminary findings for clinical review.')
        
        story.append(Paragraph(summary_text, self.styles['MedicalText']))
        story.append(Spacer(1, 15))
    
    def _add_clinical_findings(self, story, report_data):
        """Add clinical findings section"""
        story.append(Paragraph("Clinical Findings", self.styles['SectionHeader']))
        
        findings_text = report_data.get('clinical_findings', 
            'Clinical findings based on AI analysis of MRI data.')
        
        story.append(Paragraph(findings_text, self.styles['MedicalText']))
        story.append(Spacer(1, 15))
    
    def _add_mri_image(self, story, report_data):
        """Add MRI image section"""
        story.append(Paragraph("MRI Scan Analysis", self.styles['SectionHeader']))
        
        # Add MRI information text
        mri_info = report_data.get('mri_info', 'No MRI scan provided')
        story.append(Paragraph(f"**Imaging Information:** {mri_info}", self.styles['MedicalText']))
        story.append(Spacer(1, 10))
        
        # Add MRI image if available
        mri_file_path = report_data.get('mri_file_path')
        if mri_file_path and os.path.exists(mri_file_path):
            try:
                # Create image with proper scaling for PDF
                img = Image(mri_file_path)
                
                # Scale image to fit nicely in the PDF (max width 4 inches, maintain aspect ratio)
                img_width = 4 * inch
                img_height = 3 * inch  # Default height, will be adjusted based on aspect ratio
                
                # Try to get actual image dimensions to maintain aspect ratio
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(mri_file_path) as pil_img:
                        original_width, original_height = pil_img.size
                        aspect_ratio = original_height / original_width
                        img_height = img_width * aspect_ratio
                        
                        # Limit maximum height to prevent very tall images
                        if img_height > 5 * inch:
                            img_height = 5 * inch
                            img_width = img_height / aspect_ratio
                            
                except ImportError:
                    # PIL not available, use default dimensions
                    pass
                except Exception:
                    # Error reading image dimensions, use defaults
                    pass
                
                img.drawWidth = img_width
                img.drawHeight = img_height
                img.hAlign = 'CENTER'
                
                story.append(img)
                story.append(Spacer(1, 10))
                
                # Add image description
                story.append(Paragraph(
                    "**Image Description:** MRI scan used for automated Parkinson's disease analysis. "
                    "The AI system analyzed brain structure and tissue characteristics to provide diagnostic insights.",
                    self.styles['MedicalText']
                ))
                
            except Exception as e:
                logger.warning(f"Could not embed MRI image in PDF: {e}")
                story.append(Paragraph(
                    f"**Note:** MRI image could not be embedded in the report. Original file: {os.path.basename(mri_file_path)}",
                    self.styles['MedicalText']
                ))
        else:
            story.append(Paragraph(
                "**Note:** No MRI scan image available for display in this report.",
                self.styles['MedicalText']
            ))
        
        story.append(Spacer(1, 15))
    
    def _add_diagnostic_assessment(self, story, report_data):
        """Add diagnostic assessment section"""
        story.append(Paragraph("Diagnostic Assessment", self.styles['SectionHeader']))
        
        assessment_text = report_data.get('diagnostic_assessment', 
            'Diagnostic assessment based on clinical guidelines and AI analysis.')
        
        story.append(Paragraph(assessment_text, self.styles['MedicalText']))
        story.append(Spacer(1, 15))
    
    def _add_prediction_results(self, story, report_data):
        """Add prediction results table"""
        story.append(Paragraph("AI Prediction Results", self.styles['SectionHeader']))
        
        # Extract prediction data
        prediction = report_data.get('prediction', {})
        
        results_data = [
            ['Metric', 'Value', 'Interpretation'],
            ['Binary Classification', 
             prediction.get('binary_classification', 'N/A'),
             self._interpret_binary_result(prediction.get('binary_classification'))],
            ['Stage Classification', 
             prediction.get('stage_classification', 'N/A'),
             self._interpret_stage_result(prediction.get('stage_classification'))],
            ['Confidence Score', 
             f"{prediction.get('confidence', 0):.2f}",
             self._interpret_confidence(prediction.get('confidence', 0))],
            ['Processing Time', 
             f"{prediction.get('processing_time', 0):.2f}s",
             'Total analysis duration']
        ]
        
        results_table = Table(results_data, colWidths=[2*inch, 1.5*inch, 2.5*inch])
        results_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(results_table)
        story.append(Spacer(1, 15))
    
    def _add_recommendations(self, story, report_data):
        """Add recommendations section"""
        story.append(Paragraph("Clinical Recommendations", self.styles['SectionHeader']))
        
        recommendations = report_data.get('recommendations', [
            'Follow-up with movement disorder specialist',
            'Consider additional diagnostic imaging',
            'Monitor symptoms for progression',
            'Implement lifestyle modifications'
        ])
        
        for i, rec in enumerate(recommendations, 1):
            story.append(Paragraph(f"{i}. {rec}", self.styles['Recommendation']))
        
        story.append(Spacer(1, 15))
    
    def _add_references(self, story, report_data):
        """Add knowledge base references"""
        story.append(Paragraph("Medical References", self.styles['SectionHeader']))
        
        references = report_data.get('references', [])
        if references:
            for ref in references:
                story.append(Paragraph(f"• {ref}", self.styles['MedicalText']))
        else:
            story.append(Paragraph("References based on current Parkinson's disease clinical guidelines and diagnostic criteria.", self.styles['MedicalText']))
        
        story.append(Spacer(1, 15))
    
    def _add_disclaimer(self, story, report_data):
        """Add medical disclaimer"""
        disclaimer_text = """
        <b>IMPORTANT MEDICAL DISCLAIMER:</b><br/>
        This AI-generated report is for screening and educational purposes only. 
        It does not constitute medical advice, diagnosis, or treatment recommendations. 
        All findings must be reviewed and interpreted by qualified healthcare professionals. 
        Clinical correlation and additional diagnostic testing may be required for definitive diagnosis.
        """
        
        story.append(Paragraph("Medical Disclaimer", self.styles['SectionHeader']))
        story.append(Paragraph(disclaimer_text, self.styles['Disclaimer']))
        story.append(Spacer(1, 15))
    
    def _add_footer(self, story, report_data):
        """Add report footer"""
        footer_text = f"""
        Generated by Parkinson's Multiagent System v1.0<br/>
        Report ID: {report_data.get('report_id', 'N/A')}<br/>
        Generation Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        footer_style = ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        
        story.append(Spacer(1, 30))
        story.append(Paragraph(footer_text, footer_style))
    
    def _interpret_binary_result(self, result):
        """Interpret binary classification result"""
        interpretations = {
            'parkinsons': 'Positive indicators for Parkinson\'s disease',
            'no_parkinsons': 'Negative indicators for Parkinson\'s disease',
            'uncertain': 'Uncertain classification - further evaluation needed'
        }
        return interpretations.get(result, 'Unknown classification')
    
    def _interpret_stage_result(self, stage):
        """Interpret stage classification result"""
        interpretations = {
            '1': 'Stage 1: Unilateral symptoms',
            '2': 'Stage 2: Bilateral symptoms without balance impairment',
            '3': 'Stage 3: Bilateral symptoms with mild postural instability',
            '4': 'Stage 4: Significant disability, limited mobility',
            '5': 'Stage 5: Wheelchair bound or bedridden',
            'uncertain': 'Stage uncertain - clinical assessment needed'
        }
        return interpretations.get(stage, 'Unknown stage')
    
    def _interpret_confidence(self, confidence):
        """Interpret confidence score"""
        if confidence > 0.8:
            return 'High confidence'
        elif confidence > 0.6:
            return 'Moderate confidence'
        elif confidence > 0.4:
            return 'Low confidence'
        else:
            return 'Very low confidence - manual review recommended'


# Service instance
pdf_generator = PDFReportGenerator()