"""
File Manager for Parkinson's System
Handles basic file operations and directory management with role-based report storage.
Supports proper folder structure for admins, doctors, and patients.
"""

import os
import logging
import shutil
import json
from pathlib import Path
from typing import Optional, Union, Dict, Tuple, List
from datetime import datetime
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FileManagerError(Exception):
    """Custom exception for FileManager operations"""
    pass


class FileManager:
    """Robust file manager for organizing patient and doctor files with role-based storage"""
    
    def __init__(self, base_data_dir: str = "data"):
        """Initialize FileManager with base data directory"""
        try:
            self.base_data_dir = Path(base_data_dir).resolve()
            self._ensure_base_structure()
            logger.info(f"FileManager initialized with base directory: {self.base_data_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize FileManager: {e}")
            raise FileManagerError(f"FileManager initialization failed: {e}")
    
    def _ensure_base_structure(self) -> None:
        """Create basic directory structure with proper role-based report folders"""
        directories = [
            'patients', 
            'doctors', 
            'reports',
            'reports/admin/drafts',  # Admin drafts
            'reports/doctor',         # Doctor reports
            'reports/patient',        # Patient reports
            'documents', 
            'mri_scans', 
            'embeddings',
            'logs',
            'backup'
        ]
        
        try:
            for directory in directories:
                dir_path = self.base_data_dir / directory
                dir_path.mkdir(parents=True, exist_ok=True)
            logger.info("Base directory structure created successfully")
        except PermissionError:
            raise FileManagerError("Permission denied: Cannot create base directories")
        except OSError as e:
            raise FileManagerError(f"OS error creating directories: {e}")
    
    def ensure_patient_structure(self, patient_id: str) -> bool:
        """Create directory structure for a patient"""
        if not patient_id or not isinstance(patient_id, str):
            logger.error("Invalid patient_id provided")
            return False
        
        # Sanitize patient_id
        patient_id = self._sanitize_filename(patient_id)
        
        try:
            patient_dirs = [
                self.base_data_dir / "patients" / patient_id,
                self.base_data_dir / "documents" / patient_id,
                self.base_data_dir / "mri_scans" / patient_id
            ]
            
            for directory in patient_dirs:
                directory.mkdir(parents=True, exist_ok=True)
            
            # Create patient info file
            self._create_patient_info(patient_id)
            
            logger.info(f"Patient directory structure created for {patient_id}")
            return True
            
        except PermissionError:
            logger.error(f"Permission denied creating patient structure for {patient_id}")
            return False
        except OSError as e:
            logger.error(f"OS error creating patient structure for {patient_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating patient structure for {patient_id}: {e}")
            return False
    
    def ensure_doctor_structure(self, doctor_id: str) -> bool:
        """Create directory structure for a doctor"""
        if not doctor_id or not isinstance(doctor_id, str):
            logger.error("Invalid doctor_id provided")
            return False
        
        # Sanitize doctor_id
        doctor_id = self._sanitize_filename(doctor_id)
        
        try:
            doctor_dirs = [
                self.base_data_dir / "doctors" / doctor_id
            ]
            
            for directory in doctor_dirs:
                directory.mkdir(parents=True, exist_ok=True)
            
            # Create doctor info file
            self._create_doctor_info(doctor_id)
            
            logger.info(f"Doctor directory structure created for {doctor_id}")
            return True
            
        except PermissionError:
            logger.error(f"Permission denied creating doctor structure for {doctor_id}")
            return False
        except OSError as e:
            logger.error(f"OS error creating doctor structure for {doctor_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating doctor structure for {doctor_id}: {e}")
            return False
    
    def get_report_storage_path(self, user_role: str, user_id: str = None, patient_id: str = None) -> Tuple[Path, str]:
        """
        Get the appropriate storage path based on user role.
        
        Role-based Storage Rules:
        - Admin reports: stored in reports/admin/drafts/draft_{timestamp}.pdf
        - Doctor reports: stored in reports/doctor/{patient_id}_report_{timestamp}.pdf
        - Patient reports: stored in reports/patient/{patient_id}_report_{timestamp}.pdf
        """
        user_role = user_role.lower().strip()
        
        if user_role == "admin":
            path = self.base_data_dir / "reports" / "admin" / "drafts"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"draft_{timestamp}.pdf"
            
        elif user_role == "doctor":
            if not patient_id:
                raise ValueError("Patient ID required for doctor reports")
            patient_id = self._sanitize_filename(patient_id)
            path = self.base_data_dir / "reports" / "doctor"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{patient_id}_report_{timestamp}.pdf"
            
        elif user_role == "patient":
            # Patient reports go into patient folder with their patient_id
            if not patient_id:
                raise ValueError("Patient ID required for patient reports")
            patient_id = self._sanitize_filename(patient_id)
            path = self.base_data_dir / "reports" / "patient"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{patient_id}_report_{timestamp}.pdf"
            
        else:
            raise ValueError(f"Invalid user role: {user_role}")
        
        # Ensure the directory exists
        path.mkdir(parents=True, exist_ok=True)
        return path, filename
    
    def save_report(self, report_content: bytes, user_role: str, user_id: str = None, 
                   patient_id: str = None, custom_filename: str = None) -> Optional[str]:
        """
        Save a report to the appropriate location based on user role.
        
        Args:
            report_content: PDF content as bytes (cleaned of null bytes)
            user_role: 'admin', 'doctor', or 'patient'
            user_id: ID of the user creating the report
            patient_id: Patient ID (for doctor reports)
            custom_filename: Optional custom filename
            
        Returns:
            Full path to saved report or None if failed
        """
        try:
            # Clean content of null bytes and other problematic characters
            if isinstance(report_content, bytes):
                report_content = self._clean_bytes(report_content)
            elif isinstance(report_content, str):
                report_content = self._clean_string(report_content).encode('utf-8')
            
            storage_path, default_filename = self.get_report_storage_path(user_role, user_id, patient_id)
            filename = custom_filename or default_filename
            filename = self._sanitize_filename(filename)
            
            full_path = storage_path / filename
            
            # Write the report with error handling
            with open(full_path, 'wb') as f:
                f.write(report_content)
            
            # Verify the file was written correctly
            if not full_path.exists() or full_path.stat().st_size == 0:
                logger.error("Report file verification failed")
                return None
            
            logger.info(f"Report saved: {full_path}")
            return str(full_path)
            
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            return None
    
    def save_report_legacy(self, patient_id: str, doctor_id: str, report_id: str, 
                          content: bytes, create_doctor_copy: bool = False) -> tuple:
        """
        Legacy compatibility wrapper for the old save_report interface.
        Returns (patient_path, doctor_path) tuple for backward compatibility.
        """
        try:
            # Save patient report
            patient_path = self.save_report(
                report_content=content,
                user_role="patient",
                user_id=patient_id,
                patient_id=patient_id,
                custom_filename=f"{report_id}.pdf"
            )
            
            doctor_path = None
            if create_doctor_copy and doctor_id:
                # Save doctor copy
                doctor_path = self.save_report(
                    report_content=content,
                    user_role="doctor", 
                    user_id=doctor_id,
                    patient_id=patient_id,
                    custom_filename=f"{report_id}_doctor.pdf"
                )
            
            return (patient_path, doctor_path)
            
        except Exception as e:
            logger.error(f"Error in legacy save_report: {e}")
            return (None, None)
    
    def save_file(
        self, 
        content: Union[str, bytes], 
        filename: str, 
        subfolder: str = "", 
        patient_id: Optional[str] = None
    ) -> Optional[str]:
        """Save a file to the appropriate location with improved error handling"""
        
        if not filename:
            logger.error("Filename cannot be empty")
            return None
        
        # Sanitize filename
        filename = self._sanitize_filename(filename)
        
        try:
            # Determine file path
            if patient_id and subfolder:
                patient_id = self._sanitize_filename(patient_id)
                file_path = self.base_data_dir / subfolder / patient_id / filename
            elif subfolder:
                file_path = self.base_data_dir / subfolder / filename
            else:
                file_path = self.base_data_dir / filename
            
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Clean content of problematic characters
            if isinstance(content, bytes):
                content = self._clean_bytes(content)
                mode = 'wb'
                encoding = None
            else:
                content = self._clean_string(content)
                mode = 'w'
                encoding = 'utf-8'
            
            # Write file with backup
            temp_path = file_path.with_suffix(file_path.suffix + '.tmp')
            
            with open(temp_path, mode, encoding=encoding) as f:
                f.write(content)
            
            # Atomic move
            temp_path.replace(file_path)
            
            logger.info(f"File saved successfully: {file_path}")
            return str(file_path)
            
        except PermissionError:
            logger.error(f"Permission denied saving file {filename}")
            return None
        except OSError as e:
            logger.error(f"OS error saving file {filename}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error saving file {filename}: {e}")
            return None
    
    def save_mri_scan(self, source_path: str, patient_id: str, scan_filename: str) -> Optional[str]:
        """Save MRI scan file with validation"""
        
        if not all([source_path, patient_id, scan_filename]):
            logger.error("Missing required parameters for MRI scan save")
            return None
        
        source_file = Path(source_path)
        if not source_file.exists():
            logger.error(f"Source MRI file does not exist: {source_path}")
            return None
        
        if not source_file.is_file():
            logger.error(f"Source path is not a file: {source_path}")
            return None
        
        # Sanitize inputs
        patient_id = self._sanitize_filename(patient_id)
        scan_filename = self._sanitize_filename(scan_filename)
        
        try:
            destination = self.base_data_dir / "mri_scans" / patient_id / scan_filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Check available space (basic check)
            if not self._has_sufficient_space(source_file, destination.parent):
                logger.error("Insufficient disk space for MRI scan")
                return None
            
            # Copy with metadata preservation
            shutil.copy2(source_file, destination)
            
            # Verify copy was successful
            if not destination.exists() or destination.stat().st_size == 0:
                logger.error("MRI scan copy verification failed")
                return None
            
            logger.info(f"MRI scan saved successfully: {destination}")
            return str(destination)
            
        except PermissionError:
            logger.error("Permission denied saving MRI scan")
            return None
        except OSError as e:
            logger.error(f"OS error saving MRI scan: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error saving MRI scan: {e}")
            return None
    
    def read_file(self, file_path: str, binary: bool = False) -> Optional[Union[str, bytes]]:
        """Read file content with error handling"""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"File does not exist: {file_path}")
                return None
            
            mode = 'rb' if binary else 'r'
            encoding = None if binary else 'utf-8'
            
            with open(path, mode, encoding=encoding) as f:
                content = f.read()
            
            # Clean content if it's text
            if not binary and isinstance(content, str):
                content = self._clean_string(content)
            elif binary and isinstance(content, bytes):
                content = self._clean_bytes(content)
            
            logger.info(f"File read successfully: {file_path}")
            return content
            
        except PermissionError:
            logger.error(f"Permission denied reading file: {file_path}")
            return None
        except UnicodeDecodeError:
            logger.error(f"Unicode decode error reading file: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    def delete_file(self, file_path: str) -> bool:
        """Delete file with safety checks"""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"File does not exist for deletion: {file_path}")
                return True  # Already deleted
            
            if not path.is_file():
                logger.error(f"Path is not a file: {file_path}")
                return False
            
            path.unlink()
            logger.info(f"File deleted successfully: {file_path}")
            return True
            
        except PermissionError:
            logger.error(f"Permission denied deleting file: {file_path}")
            return False
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    def list_files(self, directory: str, pattern: str = "*") -> List[str]:
        """List files in directory with pattern matching"""
        try:
            dir_path = Path(directory)
            if not dir_path.exists():
                logger.error(f"Directory does not exist: {directory}")
                return []
            
            if not dir_path.is_dir():
                logger.error(f"Path is not a directory: {directory}")
                return []
            
            files = list(dir_path.glob(pattern))
            return [str(f) for f in files if f.is_file()]
            
        except PermissionError:
            logger.error(f"Permission denied accessing directory: {directory}")
            return []
        except Exception as e:
            logger.error(f"Error listing files in {directory}: {e}")
            return []
    
    def get_user_reports(self, user_role: str, user_id: str) -> List[str]:
        """Get all reports for a specific user based on their role"""
        reports = []
        
        try:
            user_role = user_role.lower().strip()
            
            if user_role == "admin":
                # Admin can see all reports
                draft_path = self.base_data_dir / "reports" / "drafts"
                if draft_path.exists():
                    reports.extend([str(f) for f in draft_path.glob("*.pdf")])
                
                # Also include all doctor and patient reports
                doctors_path = self.base_data_dir / "reports" / "doctors"
                patients_path = self.base_data_dir / "reports" / "patients"
                
                if doctors_path.exists():
                    reports.extend([str(f) for f in doctors_path.rglob("*.pdf")])
                if patients_path.exists():
                    reports.extend([str(f) for f in patients_path.rglob("*.pdf")])
                    
            elif user_role == "doctor":
                # Doctor sees only their own reports
                doctor_reports_path = self.base_data_dir / "reports" / "doctors"
                if doctor_reports_path.exists():
                    for patient_folder in doctor_reports_path.iterdir():
                        if patient_folder.is_dir():
                            reports.extend([str(f) for f in patient_folder.glob("*.pdf")])
                            
            elif user_role == "patient":
                # Patient sees only their own reports
                user_id = self._sanitize_filename(user_id)
                patient_reports_path = self.base_data_dir / "reports" / "patients" / user_id
                if patient_reports_path.exists():
                    reports.extend([str(f) for f in patient_reports_path.glob("*.pdf")])
            
            logger.debug(f"Found {len(reports)} reports for {user_role} {user_id}")
            return reports
            
        except Exception as e:
            logger.error(f"Error getting reports for {user_role} {user_id}: {e}")
            return []
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and invalid characters"""
        if not filename:
            return f"unnamed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Remove null bytes and other problematic characters
        filename = filename.replace('\x00', '').replace('\r', '').replace('\n', '')
        
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove control characters
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
        
        # Remove leading/trailing whitespace and dots
        filename = filename.strip(' .')
        
        # Limit length
        if len(filename) > 255:
            filename = filename[:255]
        
        # Ensure not empty after sanitization
        if not filename:
            filename = f"unnamed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return filename
    
    def _clean_string(self, text: str) -> str:
        """Clean string of null bytes and problematic characters"""
        if not isinstance(text, str):
            return ""
        
        # Remove null bytes and other problematic characters
        text = text.replace('\x00', '')
        
        # Remove other control characters except common ones (tab, newline, carriage return)
        text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        return text
    
    def _clean_bytes(self, data: bytes) -> bytes:
        """Clean bytes of null bytes and problematic characters"""
        if not isinstance(data, bytes):
            return b""
        
        # Remove null bytes
        data = data.replace(b'\x00', b'')
        
        return data
    
    def _has_sufficient_space(self, source_file: Path, destination_dir: Path, buffer_gb: float = 1.0) -> bool:
        """Check if there's sufficient disk space for file operation"""
        try:
            source_size = source_file.stat().st_size
            free_space = shutil.disk_usage(destination_dir).free
            required_space = source_size + (buffer_gb * 1024 * 1024 * 1024)  # Add buffer
            
            return free_space >= required_space
        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")
            return True  # Proceed if we can't check
    
    def _create_patient_info(self, patient_id: str) -> None:
        """Create patient info metadata file"""
        try:
            info = {
                "patient_id": patient_id,
                "created_at": datetime.now().isoformat(),
                "structure_version": "1.0"
            }
            
            info_path = self.base_data_dir / "patients" / patient_id / "patient_info.json"
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.warning(f"Could not create patient info file: {e}")
    
    def _create_doctor_info(self, doctor_id: str) -> None:
        """Create doctor info metadata file"""
        try:
            info = {
                "doctor_id": doctor_id,
                "created_at": datetime.now().isoformat(),
                "structure_version": "1.0"
            }
            
            info_path = self.base_data_dir / "doctors" / doctor_id / "doctor_info.json"
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.warning(f"Could not create doctor info file: {e}")
    
    def get_stats(self) -> Dict[str, Union[str, int, float]]:
        """Get file manager statistics"""
        try:
            stats = {
                "base_directory": str(self.base_data_dir),
                "patients_count": 0,
                "doctors_count": 0,
                "total_size_mb": 0.0
            }
            
            # Count patients and doctors
            patients_dir = self.base_data_dir / "patients"
            if patients_dir.exists():
                stats["patients_count"] = len([d for d in patients_dir.iterdir() if d.is_dir()])
            
            doctors_dir = self.base_data_dir / "doctors"
            if doctors_dir.exists():
                stats["doctors_count"] = len([d for d in doctors_dir.iterdir() if d.is_dir()])
            
            # Calculate total size
            total_size = 0
            for root, dirs, files in os.walk(self.base_data_dir):
                for file in files:
                    try:
                        file_path = Path(root) / file
                        total_size += file_path.stat().st_size
                    except (OSError, FileNotFoundError):
                        continue
            
            stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
            return stats
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}


# Global file manager instance with error handling
try:
    file_manager = FileManager()
except Exception as e:
    logger.critical(f"Failed to create global FileManager instance: {e}")
    file_manager = None


# Backward compatibility functions with error handling
def ensure_patient_structure(patient_id: str) -> bool:
    """Create patient directory structure"""
    if file_manager is None:
        logger.error("FileManager not available")
        return False
    return file_manager.ensure_patient_structure(patient_id)


def ensure_doctor_structure(doctor_id: str) -> bool:
    """Create doctor directory structure"""
    if file_manager is None:
        logger.error("FileManager not available")
        return False
    return file_manager.ensure_doctor_structure(doctor_id)


def save_report(content: Union[str, bytes], filename: str, patient_id: Optional[str] = None) -> bool:
    """Save a report file"""
    if file_manager is None:
        logger.error("FileManager not available")
        return False
    
    # Convert string content to bytes if needed
    if isinstance(content, str):
        content = content.encode('utf-8')
    
    result = file_manager.save_file(content, filename, "reports", patient_id)
    return result is not None


def save_mri_scan(file_path: str, patient_id: str, scan_filename: str) -> bool:
    """Save an MRI scan file"""
    if file_manager is None:
        logger.error("FileManager not available")
        return False
    
    result = file_manager.save_mri_scan(file_path, patient_id, scan_filename)
    return result is not None


def read_file(file_path: str, binary: bool = False) -> Optional[Union[str, bytes]]:
    """Read file content"""
    if file_manager is None:
        logger.error("FileManager not available")
        return None
    
    return file_manager.read_file(file_path, binary)


def delete_file(file_path: str) -> bool:
    """Delete a file"""
    if file_manager is None:
        logger.error("FileManager not available")
        return False
    
    return file_manager.delete_file(file_path)


# Example usage and testing
if __name__ == "__main__":
    try:
        # Test the file manager
        fm = FileManager("test_data")
        
        # Test patient structure creation
        if fm.ensure_patient_structure("patient_001"):
            print("✓ Patient structure created successfully")
        
        # Test doctor structure creation
        if fm.ensure_doctor_structure("doctor_001"):
            print("✓ Doctor structure created successfully")
        
        # Test file saving
        test_content = "This is a test report for patient 001"
        if fm.save_file(test_content, "test_report.txt", "reports", "patient_001"):
            print("✓ File saved successfully")
        
        # Test file reading
        read_content = fm.read_file("test_data/reports/patient_001/test_report.txt")
        if read_content and read_content.strip() == test_content:
            print("✓ File read successfully")
        
        # Test report saving with role-based storage
        report_data = b"Sample PDF report content"
        report_path = fm.save_report(report_data, "admin", None, None)
        if report_path:
            print("✓ Admin report saved successfully")
        
        # Get stats
        stats = fm.get_stats()
        print(f"✓ Stats: {stats}")
        
        print("All tests passed!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()