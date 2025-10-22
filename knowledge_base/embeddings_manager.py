"""
Embeddings Manager for Parkinson's Multiagent System

This module manages text embeddings for the knowledge base,
enabling semantic search and similarity matching for medical information.
"""

import asyncio
import logging
import json
import pickle
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from datetime import datetime
from pathlib import Path
import hashlib
import warnings
import os

# Suppress verbose warnings from ML libraries
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow messages
os.environ['TOKENIZERS_PARALLELISM'] = 'false'  # Suppress tokenizers warning

# Configure logging for this module
logger = logging.getLogger(__name__)

# Suppress verbose output from related libraries
logging.getLogger('sentence_transformers').setLevel(logging.ERROR)
logging.getLogger('transformers').setLevel(logging.ERROR)
logging.getLogger('torch').setLevel(logging.ERROR)
logging.getLogger('tensorflow').setLevel(logging.ERROR)

# Note: In production, these would be real embedding libraries
# For development, we'll use mock implementations
try:
    # Import sentence transformers only when available
    from sentence_transformers import SentenceTransformer   
    SENTENCE_TRANSFORMERS_AVAILABLE = True
    logger.info("✓ Sentence transformers available")
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not available - using mock embeddings")

try:
    import faiss
    FAISS_AVAILABLE = True
    logger.debug("✓ FAISS available")
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS not available - using simple similarity search")


class EmbeddingsManager:
    """
    Professional embeddings manager for medical knowledge base.
    Handles text embedding generation, storage, and similarity search.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Embedding model configuration
        self.model_name = config.get('embedding_model', 'all-MiniLM-L6-v2')
        self.embedding_dimension = config.get('embedding_dimension', 384)
        self.max_sequence_length = config.get('max_sequence_length', 512)
        
        # Storage configuration
        self.embeddings_dir = Path(config.get('embeddings_dir', 'data/embeddings'))
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache configuration
        self.cache_size = config.get('cache_size', 1000)
        self.enable_caching = config.get('enable_caching', True)
        
        # Search configuration
        self.similarity_threshold = config.get('similarity_threshold', 0.7)
        self.max_search_results = config.get('max_search_results', 10)
        
        # Initialize storage
        self.embeddings_cache = {}
        self.text_to_id = {}
        self.id_to_text = {}
        self.id_to_metadata = {}
        self.next_id = 0
        
        # Initialize model (mock for development)
        self.model = None
        self.index = None
        
        # Document loading capabilities
        self.documents_dir = Path(config.get('documents_dir', 'data/documents'))
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        
        # Supported document types
        self.supported_extensions = {'.pdf', '.txt', '.md', '.json'}
        
        # Chunking configuration
        self.chunk_size = config.get('chunk_size', 500)
        self.chunk_overlap = config.get('chunk_overlap', 50)
        
        logger.info(f"Embeddings Manager initialized with model: {self.model_name}")
    
    async def initialize(self):
        """Initialize the embeddings model and index"""
        try:
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                logger.info(f"Loading model: {self.model_name}")
                # Import and load the actual model - this may take some time
                try:
                    self.model = SentenceTransformer(self.model_name)
                    logger.info("✓ Model loaded")
                    self.using_real_embeddings = True
                except Exception as e:
                    logger.warning(f"Failed to load model: {e}")
                    self.model = None
                    self.using_real_embeddings = False
            else:
                logger.warning("Using mock embeddings")
                self.model = None
                self.using_real_embeddings = False
            
            # Initialize search index
            await self._initialize_search_index()
            
            # Load existing embeddings if available
            await self._load_existing_embeddings()
            
            logger.info("✓ Embeddings manager ready")
            
        except Exception as e:
            logger.error(f"Failed to initialize embeddings manager: {e}")
            raise
    
    async def load_documents_from_directory(self, directory_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load all medical documents from a directory into the knowledge base.
        
        Args:
            directory_path: Path to documents directory (uses default if None)
            
        Returns:
            Dictionary with loading statistics
        """
        try:
            doc_dir = Path(directory_path) if directory_path else self.documents_dir
            
            if not doc_dir.exists():
                logger.warning(f"Documents directory not found: {doc_dir}")
                # Create default medical documents
                await self._create_default_medical_documents()
                return await self.load_documents_from_directory(str(self.documents_dir))
            
            logger.info(f"Loading documents from: {doc_dir}")
            
            stats = {
                'total_files': 0,
                'loaded_files': 0,
                'failed_files': 0,
                'total_chunks': 0,
                'file_types': {},
                'errors': []
            }
            
            # Find all supported documents
            for ext in self.supported_extensions:
                files = list(doc_dir.glob(f"**/*{ext}"))
                stats['file_types'][ext] = len(files)
                stats['total_files'] += len(files)
                
                for file_path in files:
                    try:
                        logger.info(f"Loading document: {file_path.name}")
                        chunks = await self._load_and_chunk_document(file_path)
                        
                        if chunks:
                            # Add chunks to embeddings
                            added_ids = await self.batch_add_texts(
                                texts=[chunk['text'] for chunk in chunks],
                                metadata_list=[chunk['metadata'] for chunk in chunks]
                            )
                            
                            stats['loaded_files'] += 1
                            stats['total_chunks'] += len(chunks)
                            logger.info(f"Added {len(chunks)} chunks from {file_path.name}")
                        else:
                            stats['failed_files'] += 1
                            logger.warning(f"No content extracted from {file_path.name}")
                            
                    except Exception as e:
                        stats['failed_files'] += 1
                        error_msg = f"Failed to load {file_path.name}: {str(e)}"
                        stats['errors'].append(error_msg)
                        logger.error(error_msg)
            
            logger.info(f"Document loading completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to load documents: {e}")
            raise
    
    async def _load_and_chunk_document(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load and chunk a document into smaller pieces for embedding"""
        try:
            # Extract text based on file type
            if file_path.suffix == '.pdf':
                text = await self._extract_text_from_pdf(file_path)
            elif file_path.suffix in ['.txt', '.md']:
                text = await self._extract_text_from_text_file(file_path)
            elif file_path.suffix == '.json':
                text = await self._extract_text_from_json(file_path)
            else:
                logger.warning(f"Unsupported file type: {file_path.suffix}")
                return []
            
            if not text or len(text.strip()) < 50:
                logger.warning(f"Insufficient text content in {file_path.name}")
                return []
            
            # Chunk the text
            chunks = self._chunk_text(text)
            
            # Create metadata for each chunk
            base_metadata = {
                'source_file': str(file_path.name),
                'file_type': file_path.suffix,
                'source_path': str(file_path),
                'loaded_at': datetime.now().isoformat(),
                'document_category': self._categorize_document(file_path.name, text)
            }
            
            # Prepare chunks with metadata
            chunked_docs = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = base_metadata.copy()
                chunk_metadata.update({
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'chunk_length': len(chunk)
                })
                
                chunked_docs.append({
                    'text': chunk,
                    'metadata': chunk_metadata
                })
            
            return chunked_docs
            
        except Exception as e:
            logger.error(f"Failed to load and chunk document {file_path}: {e}")
            return []
    
    async def _extract_text_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file using PyPDF2"""
        try:
            import PyPDF2
            logger.debug(f"Extracting text from PDF: {file_path.name}")

            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""

                # Extract text from all pages
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

                # Clean up the extracted text
                text = text.strip()
                if len(text) < 100:
                    logger.warning(f"Very little text extracted from {file_path.name}: {len(text)} characters")
                else:
                    logger.info(f"Extracted {len(text)} characters from {file_path.name}")

                return text

        except ImportError:
            logger.error("PyPDF2 not available for PDF extraction")
            return ""
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {file_path.name}: {e}")
            return ""
                
        except Exception as e:
            logger.error(f"Failed to extract PDF text: {e}")
            return ""
    
    async def _extract_text_from_text_file(self, file_path: Path) -> str:
        """Extract text from text/markdown file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read text file: {e}")
            return ""
    
    async def _extract_text_from_json(self, file_path: Path) -> str:
        """Extract text from JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract text fields from JSON
            text_parts = []
            self._extract_text_from_dict(data, text_parts)
            return '\n'.join(text_parts)
            
        except Exception as e:
            logger.error(f"Failed to read JSON file: {e}")
            return ""
    
    def _extract_text_from_dict(self, obj, text_parts: List[str]):
        """Recursively extract text from dictionary/list structures"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and len(value) > 10:
                    text_parts.append(f"{key}: {value}")
                elif isinstance(value, (dict, list)):
                    self._extract_text_from_dict(value, text_parts)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_text_from_dict(item, text_parts)
    
    def _chunk_text(self, text: str) -> List[str]:
        """Chunk text into smaller pieces with overlap"""
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings near the chunk boundary
                for i in range(min(50, len(text) - end)):
                    if text[end + i] in '.!?':
                        end = end + i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = end - self.chunk_overlap
            if start >= len(text):
                break
        
        return chunks
    
    def _categorize_document(self, filename: str, text: str) -> str:
        """Categorize document based on content"""
        filename_lower = filename.lower()
        text_lower = text.lower()
        
        if any(term in filename_lower or term in text_lower for term in 
               ['parkinson', 'parkinsons', 'pd', 'movement disorder']):
            return 'parkinsons_disease'
        elif any(term in filename_lower or term in text_lower for term in 
                ['neurology', 'neurological', 'brain', 'neurodegenerative']):
            return 'neurology'
        elif any(term in filename_lower or term in text_lower for term in 
                ['mri', 'imaging', 'radiology', 'scan']):
            return 'medical_imaging'
        elif any(term in filename_lower or term in text_lower for term in 
                ['treatment', 'therapy', 'medication', 'drug']):
            return 'treatment'
        elif any(term in filename_lower or term in text_lower for term in 
                ['diagnosis', 'diagnostic', 'clinical', 'assessment']):
            return 'diagnosis'
        else:
            return 'general_medical'
    
    async def _create_default_medical_documents(self):
        """Create default medical documents for testing"""
        try:
            logger.info("Creating default medical documents...")
            
            # Create comprehensive Parkinson's document
            parkinsons_content = """
# Parkinson's Disease: Comprehensive Medical Reference

## Overview
Parkinson's disease (PD) is a progressive neurodegenerative disorder affecting movement control. It is the second most common neurodegenerative disease after Alzheimer's disease, affecting approximately 1% of individuals over 60 years of age.

## Pathophysiology
The primary pathological process involves the selective loss of dopaminergic neurons in the substantia nigra pars compacta. This neuronal loss leads to:

1. **Reduced dopamine production**: Critical for normal movement control
2. **α-synuclein aggregation**: Formation of Lewy bodies and Lewy neurites
3. **Neuroinflammation**: Activated microglia and reactive astrocytes
4. **Oxidative stress**: Mitochondrial dysfunction and increased reactive oxygen species

## Clinical Manifestations

### Motor Symptoms (Cardinal Features)
1. **Tremor**: Rest tremor (4-6 Hz), typically unilateral onset
2. **Rigidity**: Increased muscle tone, cogwheel or lead-pipe rigidity
3. **Bradykinesia**: Slowness of movement, decreased amplitude of movements
4. **Postural Instability**: Balance problems, increased fall risk (late feature)

### Non-Motor Symptoms
1. **Cognitive**: Executive dysfunction, dementia (30-40% develop PD dementia)
2. **Psychiatric**: Depression (50%), anxiety, apathy, hallucinations
3. **Sleep disorders**: REM sleep behavior disorder, insomnia, excessive daytime sleepiness
4. **Autonomic**: Constipation, orthostatic hypotension, urinary dysfunction
5. **Sensory**: Hyposmia, pain, restless leg syndrome

## Diagnostic Criteria

### UK PD Society Brain Bank Criteria
**Inclusion criteria (Parkinsonism):**
- Bradykinesia AND at least one of: tremor, rigidity, postural instability

**Exclusion criteria:**
- History of strokes, head injury, antipsychotic medication
- More than one affected relative
- Sustained remission
- Strictly unilateral features after 3 years
- Supranuclear gaze palsy
- Cerebellar signs
- Early severe autonomic involvement
- Early severe dementia
- Babinski sign
- Presence of cerebral tumor or hydrocephalus on CT scan
- Negative response to large doses of levodopa

**Supportive criteria:**
- Unilateral onset
- Rest tremor present
- Progressive disorder
- Persistent asymmetry
- Excellent response to levodopa (70-100%)
- Severe levodopa-induced chorea
- Levodopa response for 5 years or more
- Clinical course of 10 years or more

## Staging Systems

### Hoehn and Yahr Scale
- **Stage 1**: Unilateral involvement only
- **Stage 1.5**: Unilateral and axial involvement
- **Stage 2**: Bilateral involvement without impairment of balance
- **Stage 2.5**: Mild bilateral disease with recovery on pull test
- **Stage 3**: Bilateral disease; mild to moderate disability; some postural instability
- **Stage 4**: Severely disabling disease; still able to walk or stand unassisted
- **Stage 5**: Wheelchair bound or bedridden unless aided

### MDS-UPDRS (Movement Disorder Society-Unified Parkinson's Disease Rating Scale)
- **Part I**: Non-motor experiences of daily living (13 items)
- **Part II**: Motor experiences of daily living (13 items)
- **Part III**: Motor examination (33 items)
- **Part IV**: Motor complications (6 items)

## Treatment Strategies

### Pharmacological Management

#### First-line therapy:
1. **Levodopa/Carbidopa**: Gold standard, most effective
   - Start with 25/100 mg TID
   - Titrate based on response and side effects
   - Consider controlled-release formulations for wearing-off

2. **Dopamine Agonists**: 
   - Pramipexole: Start 0.125 mg TID, max 1.5 mg TID
   - Ropinirole: Start 0.25 mg TID, max 8 mg TID
   - Rotigotine patch: Start 2 mg/24h, max 8 mg/24h

3. **MAO-B Inhibitors**:
   - Selegiline: 5 mg BID
   - Rasagiline: 1 mg daily
   - Safinamide: 50-100 mg daily

#### Advanced therapies:
1. **Deep Brain Stimulation (DBS)**:
   - Subthalamic nucleus (STN-DBS)
   - Globus pallidus interna (GPi-DBS)
   - Indications: Motor fluctuations, dyskinesias, tremor

2. **Continuous therapies**:
   - Levodopa-carbidopa intestinal gel (LCIG)
   - Subcutaneous apomorphine infusion

### Non-Pharmacological Management
1. **Physical therapy**: Gait training, balance exercises, flexibility
2. **Occupational therapy**: Activities of daily living, home safety
3. **Speech therapy**: Voice amplification, swallowing assessment
4. **Exercise**: Aerobic exercise, resistance training, tai chi, dancing
5. **Nutrition**: Mediterranean diet, adequate protein spacing

## Prognosis and Disease Progression
- Variable progression rate
- Mean time from diagnosis to Hoehn & Yahr stage 3: 7-8 years
- Mortality rate 1.5-3 times higher than general population
- Quality of life significantly impacts with motor fluctuations and non-motor symptoms

## Recent Research and Future Directions
1. **Biomarkers**: α-synuclein seeding assays, imaging biomarkers
2. **Neuroprotective trials**: GLP-1 agonists, urate, genetic therapies
3. **Precision medicine**: Genetic subtyping, personalized treatment
4. **Digital health**: Wearable devices, remote monitoring

## References
- Movement Disorder Society Clinical Diagnostic Criteria for Parkinson's Disease
- International Parkinson and Movement Disorder Society Evidence-Based Medicine Reviews
- NICE Guidelines: Parkinson's Disease in Adults (NG71)
"""

            mri_imaging_content = """
# MRI Imaging in Parkinson's Disease

## Introduction
Magnetic Resonance Imaging (MRI) plays an increasingly important role in the evaluation of Parkinson's disease, particularly in differential diagnosis and research applications.

## Conventional MRI Findings

### T1-weighted imaging:
- Usually normal in idiopathic PD
- May show mild cerebral atrophy in advanced cases
- Helps exclude secondary causes (strokes, tumors)

### T2-weighted imaging:
- Normal signal intensity in substantia nigra in most cases
- Absence of "swallow tail" sign may suggest PD

### FLAIR imaging:
- Helps identify white matter lesions
- Excludes vascular parkinsonism

## Advanced MRI Techniques

### Diffusion Tensor Imaging (DTI):
- Reduced fractional anisotropy in substantia nigra
- Correlates with disease severity
- Useful for early detection research

### Susceptibility-Weighted Imaging (SWI):
- Loss of substantia nigra hyperintensity
- "Swallow tail" sign absence
- Increased iron deposition visualization

### Neuromelanin-sensitive MRI:
- Direct visualization of substantia nigra neuromelanin
- Correlates with dopaminergic neuron loss
- Promising for early diagnosis

## Differential Diagnosis

### Multiple System Atrophy (MSA):
- Hot cross bun sign in pons
- Putaminal rim sign
- Cerebellar and pontine atrophy

### Progressive Supranuclear Palsy (PSP):
- Midbrain atrophy (hummingbird sign)
- Superior cerebellar peduncle atrophy
- Third ventricle dilatation

### Corticobasal Degeneration (CBD):
- Asymmetric cortical atrophy
- Corpus callosum thinning
- Ventricular enlargement

## Quantitative Analysis
- Substantia nigra volume measurements
- Iron content quantification
- Cortical thickness analysis
- Connectivity pattern analysis

## Clinical Applications
1. **Differential diagnosis**: Distinguishing PD from atypical parkinsonism
2. **Disease monitoring**: Tracking progression in research studies
3. **Treatment response**: Evaluating neuroprotective interventions
4. **Genetic studies**: Correlating imaging with genetic variants

## Limitations
- Normal conventional MRI in early PD
- Overlap between PD and atypical syndromes
- Need for specialized sequences and analysis
- Limited availability of advanced techniques

## Future Directions
- Machine learning applications
- Multimodal imaging approaches
- Longitudinal studies
- Integration with clinical biomarkers
"""

            # Save documents
            parkinsons_file = self.documents_dir / "parkinsons_disease_comprehensive.md"
            mri_file = self.documents_dir / "mri_imaging_parkinsons.md"
            
            with open(parkinsons_file, 'w', encoding='utf-8') as f:
                f.write(parkinsons_content)
            
            with open(mri_file, 'w', encoding='utf-8') as f:
                f.write(mri_imaging_content)
            
            logger.info(f"Created default medical documents in {self.documents_dir}")
            
        except Exception as e:
            logger.error(f"Failed to create default documents: {e}")
            raise
            
        except Exception as e:
            logger.error(f"Failed to initialize embeddings manager: {e}")
            raise
    
    async def generate_embedding(self, text: str, text_id: Optional[str] = None) -> np.ndarray:
        """
        Generate embedding for a piece of text.
        
        Args:
            text: Input text to embed
            text_id: Optional identifier for the text
            
        Returns:
            Numpy array containing the embedding vector
        """
        try:
            # Check cache first
            text_hash = self._hash_text(text)
            if self.enable_caching and text_hash in self.embeddings_cache:
                logger.debug(f"Using cached embedding for text_id: {text_id}")
                return self.embeddings_cache[text_hash]
            
            # Preprocess text
            processed_text = await self._preprocess_text(text)
            
            # Generate embedding
            embedding = await self._generate_embedding(processed_text)
            
            # Cache the embedding
            if self.enable_caching:
                self._cache_embedding(text_hash, embedding)
            
            logger.debug(f"Generated embedding for text (length: {len(text)})")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    async def add_text(self, 
                      text: str, 
                      metadata: Optional[Dict[str, Any]] = None,
                      text_id: Optional[str] = None) -> str:
        """
        Add text to the embeddings index.
        
        Args:
            text: Text to add
            metadata: Optional metadata associated with the text
            text_id: Optional custom ID for the text
            
        Returns:
            String ID of the added text
        """
        try:
            # Generate or use provided ID
            if text_id is None:
                text_id = self._generate_text_id()
            
            # Generate embedding
            embedding = await self.generate_embedding(text, text_id)
            
            # Store text and metadata
            self.id_to_text[text_id] = text
            self.text_to_id[text] = text_id
            self.id_to_metadata[text_id] = metadata or {}
            
            # Add to search index
            await self._add_to_index(text_id, embedding)
            
            # Save to persistent storage
            await self._save_embedding(text_id, embedding, text, metadata)
            
            logger.debug(f"Added text to index with ID: {text_id}")
            return text_id
            
        except Exception as e:
            logger.error(f"Failed to add text to index: {e}")
            raise
    
    async def search_similar(self, 
                           query_text: str, 
                           k: Optional[int] = None,
                           similarity_threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Search for similar texts in the index.
        
        Args:
            query_text: Text to search for
            k: Number of results to return (default: max_search_results)
            similarity_threshold: Minimum similarity score (default: configured threshold)
            
        Returns:
            List of dictionaries containing search results
        """
        try:
            start_time = datetime.now()
            
            # Set defaults
            k = k or self.max_search_results
            similarity_threshold = similarity_threshold or self.similarity_threshold
            
            # Generate query embedding
            query_embedding = await self.generate_embedding(query_text)
            
            # Perform similarity search
            results = await self._search_index(query_embedding, k, similarity_threshold)
            
            # Enrich results with metadata
            enriched_results = []
            for result in results:
                text_id = result['id']
                enriched_result = {
                    'id': text_id,
                    'text': self.id_to_text.get(text_id, ''),
                    'similarity': result['similarity'],
                    'metadata': self.id_to_metadata.get(text_id, {})
                }
                enriched_results.append(enriched_result)
            
            search_time = (datetime.now() - start_time).total_seconds()
            logger.debug(f"Found {len(enriched_results)} similar texts in {search_time:.3f}s")
            
            return enriched_results
            
        except Exception as e:
            logger.error(f"Failed to search similar texts: {e}")
            raise
    
    async def get_text_by_id(self, text_id: str) -> Optional[Dict[str, Any]]:
        """Get text and metadata by ID"""
        if text_id in self.id_to_text:
            return {
                'id': text_id,
                'text': self.id_to_text[text_id],
                'metadata': self.id_to_metadata.get(text_id, {})
            }
        return None
    
    async def update_text(self, 
                         text_id: str, 
                         new_text: Optional[str] = None,
                         new_metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update existing text and/or metadata"""
        try:
            if text_id not in self.id_to_text:
                logger.warning(f"Text ID not found: {text_id}")
                return False
            
            # Update text if provided
            if new_text is not None:
                old_text = self.id_to_text[text_id]
                
                # Remove old text mapping
                if old_text in self.text_to_id:
                    del self.text_to_id[old_text]
                
                # Update text
                self.id_to_text[text_id] = new_text
                self.text_to_id[new_text] = text_id
                
                # Regenerate embedding
                new_embedding = await self.generate_embedding(new_text, text_id)
                await self._update_index(text_id, new_embedding)
                
                # Save updated embedding
                await self._save_embedding(text_id, new_embedding, new_text, 
                                         self.id_to_metadata.get(text_id, {}))
            
            # Update metadata if provided
            if new_metadata is not None:
                self.id_to_metadata[text_id] = new_metadata
            
            logger.debug(f"Updated text with ID: {text_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update text: {e}")
            return False
    
    async def remove_text(self, text_id: str) -> bool:
        """Remove text from the index"""
        try:
            if text_id not in self.id_to_text:
                logger.warning(f"Text ID not found: {text_id}")
                return False
            
            # Remove from mappings
            text = self.id_to_text[text_id]
            if text in self.text_to_id:
                del self.text_to_id[text]
            
            del self.id_to_text[text_id]
            if text_id in self.id_to_metadata:
                del self.id_to_metadata[text_id]
            
            # Remove from index
            await self._remove_from_index(text_id)
            
            # Remove from persistent storage
            await self._remove_saved_embedding(text_id)
            
            logger.debug(f"Removed text with ID: {text_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove text: {e}")
            return False
    
    async def batch_add_texts(self, 
                            texts: List[str], 
                            metadata_list: Optional[List[Dict[str, Any]]] = None,
                            text_ids: Optional[List[str]] = None) -> List[str]:
        """Add multiple texts to the index in batch"""
        try:
            start_time = datetime.now()
            
            # Prepare metadata and IDs
            if metadata_list is None:
                metadata_list = [{}] * len(texts)
            if text_ids is None:
                text_ids = [self._generate_text_id() for _ in texts]
            
            # Validate input lengths
            if not (len(texts) == len(metadata_list) == len(text_ids)):
                raise ValueError("Texts, metadata, and IDs lists must have the same length")
            
            # Generate embeddings for all texts
            embeddings = []
            for i, text in enumerate(texts):
                embedding = await self.generate_embedding(text, text_ids[i])
                embeddings.append(embedding)
            
            # Add all to storage
            added_ids = []
            for i, (text, embedding, metadata, text_id) in enumerate(
                zip(texts, embeddings, metadata_list, text_ids)
            ):
                # Store text and metadata
                self.id_to_text[text_id] = text
                self.text_to_id[text] = text_id
                self.id_to_metadata[text_id] = metadata
                
                # Add to index
                await self._add_to_index(text_id, embedding)
                
                # Save to persistent storage
                await self._save_embedding(text_id, embedding, text, metadata)
                
                added_ids.append(text_id)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Batch added {len(texts)} texts in {processing_time:.2f}s")
            
            return added_ids
            
        except Exception as e:
            logger.error(f"Failed to batch add texts: {e}")
            raise
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the embeddings index"""
        return {
            'total_texts': len(self.id_to_text),
            'embedding_dimension': self.embedding_dimension,
            'cache_size': len(self.embeddings_cache),
            'model_name': self.model_name,
            'similarity_threshold': self.similarity_threshold,
            'storage_path': str(self.embeddings_dir),
            'next_id': self.next_id
        }
    
    def _hash_text(self, text: str) -> str:
        """Generate hash for text caching"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _cache_embedding(self, text_hash: str, embedding: np.ndarray):
        """Cache embedding with size limit"""
        if len(self.embeddings_cache) >= self.cache_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self.embeddings_cache))
            del self.embeddings_cache[oldest_key]
        
        self.embeddings_cache[text_hash] = embedding
    
    def _generate_text_id(self) -> str:
        """Generate unique text ID"""
        text_id = f"txt_{self.next_id:06d}"
        self.next_id += 1
        return text_id
    
    async def _preprocess_text(self, text: str) -> str:
        """Preprocess text before embedding generation"""
        # Basic preprocessing
        processed = text.strip()
        
        # Truncate if too long
        if len(processed) > self.max_sequence_length:
            processed = processed[:self.max_sequence_length]
            logger.debug(f"Truncated text to {self.max_sequence_length} characters")
        
        return processed
    
    async def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text using sentence transformer or fallback to mock"""
        if self.model is not None and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Use real sentence transformer model
                embedding = self.model.encode(text, convert_to_numpy=True)
                # Ensure it's float32 for FAISS compatibility
                embedding = embedding.astype(np.float32)
                # Normalize to unit vector for cosine similarity
                embedding = embedding / np.linalg.norm(embedding)
                return embedding
            except Exception as e:
                logger.warning(f"Failed to generate real embedding, falling back to mock: {e}")
                return await self._generate_mock_embedding(text)
        else:
            # Fallback to mock embeddings
            return await self._generate_mock_embedding(text)
    
    async def _generate_mock_embedding(self, text: str) -> np.ndarray:
        """Generate mock embedding for development purposes"""
        await asyncio.sleep(0.1)  # Simulate embedding generation time
        
        # Create deterministic embedding based on text
        text_hash = self._hash_text(text)
        np.random.seed(int(text_hash[:8], 16))
        embedding = np.random.normal(0, 1, self.embedding_dimension).astype(np.float32)
        
        # Normalize to unit vector
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    async def _initialize_search_index(self):
        """Initialize the search index for similarity search"""
        if FAISS_AVAILABLE:
            logger.info("Initializing FAISS index for vector search")
            self.index = faiss.IndexFlatIP(self.embedding_dimension)  # Inner product for cosine similarity
            self.id_to_index = {}
            self.index_to_id = {}
            self.next_index_id = 0
            logger.info("FAISS index initialized successfully")
        else:
            # Use simple in-memory storage as fallback
            self.index = {}
            logger.warning("FAISS not available - using simple in-memory index")
    
    async def _add_to_index(self, text_id: str, embedding: np.ndarray):
        """Add embedding to the search index"""
        if hasattr(self.index, 'add'):  # FAISS index
            # FAISS doesn't support text IDs directly, so we maintain a mapping
            if text_id not in self.id_to_index:
                # Add new vector to FAISS
                self.index.add(embedding.reshape(1, -1))
                self.id_to_index[text_id] = self.next_index_id
                self.index_to_id[self.next_index_id] = text_id
                self.next_index_id += 1
        else:
            # Fallback to simple in-memory storage
            self.index[text_id] = embedding
    
    async def _update_index(self, text_id: str, embedding: np.ndarray):
        """Update embedding in the search index"""
        if isinstance(self.index, dict):
            self.index[text_id] = embedding
        else:
            # Would handle FAISS update in production
            pass
    
    async def _remove_from_index(self, text_id: str):
        """Remove embedding from the search index"""
        if isinstance(self.index, dict) and text_id in self.index:
            del self.index[text_id]
    
    async def _search_index(self, 
                          query_embedding: np.ndarray, 
                          k: int, 
                          similarity_threshold: float) -> List[Dict[str, Any]]:
        """Search the index for similar embeddings"""
        results = []
        
        if isinstance(self.index, dict):
            # Dictionary-based cosine similarity search
            similarities = []
            
            # Normalize query embedding
            query_norm = np.linalg.norm(query_embedding)
            if query_norm == 0:
                logger.warning("Query embedding has zero norm")
                return results
                
            query_normalized = query_embedding / query_norm
            
            for text_id, embedding in self.index.items():
                try:
                    # Normalize stored embedding
                    embedding_norm = np.linalg.norm(embedding)
                    if embedding_norm == 0:
                        continue
                        
                    embedding_normalized = embedding / embedding_norm
                    
                    # Calculate cosine similarity (dot product of normalized vectors)
                    similarity = np.dot(query_normalized, embedding_normalized)
                    
                    # Apply threshold (cosine similarity ranges from -1 to 1)
                    if similarity >= similarity_threshold:
                        similarities.append((text_id, similarity))
                        
                except Exception as e:
                    logger.warning(f"Error calculating similarity for {text_id}: {e}")
                    continue
            
            # Sort by similarity and take top k
            similarities.sort(key=lambda x: x[1], reverse=True)
            for text_id, similarity in similarities[:k]:
                results.append({
                    'id': text_id,
                    'similarity': float(similarity)
                })
        
        elif hasattr(self.index, 'search'):
            # FAISS-based search
            try:
                import faiss
                logger.debug(f"Using FAISS search with query shape: {query_embedding.shape}")
                
                # FAISS expects 2D array
                query_vector = query_embedding.reshape(1, -1).astype(np.float32)
                
                # Search FAISS index
                scores, indices = self.index.search(query_vector, k)
                
                # Convert results
                for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                    if idx >= 0:  # Valid index
                        # Convert FAISS inner product score to similarity
                        # For normalized vectors, inner product = cosine similarity
                        similarity = float(score)
                        
                        # Apply threshold
                        if similarity >= similarity_threshold:
                            # Get text_id from index mapping
                            text_id = self.index_to_id.get(idx) if hasattr(self, 'index_to_id') else f"idx_{idx}"
                            
                            results.append({
                                'id': text_id,
                                'similarity': similarity
                            })
                            
                logger.info(f"FAISS search returned {len(results)} results above threshold {similarity_threshold}")
                
            except Exception as e:
                logger.error(f"FAISS search failed: {e}")
                # Fallback to no results
                pass
        
        else:
            logger.warning(f"Unknown index type: {type(self.index)}")
        
        return results
    
    async def _save_embedding(self, 
                            text_id: str, 
                            embedding: np.ndarray, 
                            text: str, 
                            metadata: Dict[str, Any]):
        """Save embedding to persistent storage"""
        try:
            embedding_file = self.embeddings_dir / f"{text_id}.pkl"
            
            data = {
                'id': text_id,
                'text': text,
                'embedding': embedding,
                'metadata': metadata,
                'created_at': datetime.now().isoformat(),
                'model_name': self.model_name
            }
            
            with open(embedding_file, 'wb') as f:
                pickle.dump(data, f)
                
        except Exception as e:
            logger.error(f"Failed to save embedding for {text_id}: {e}")
    
    async def _load_existing_embeddings(self):
        """Load existing embeddings from persistent storage"""
        try:
            embedding_files = list(self.embeddings_dir.glob("*.pkl"))
            
            for embedding_file in embedding_files:
                try:
                    with open(embedding_file, 'rb') as f:
                        data = pickle.load(f)
                    
                    text_id = data['id']
                    text = data['text']
                    embedding = data['embedding']
                    metadata = data.get('metadata', {})
                    
                    # Restore mappings
                    self.id_to_text[text_id] = text
                    self.text_to_id[text] = text_id
                    self.id_to_metadata[text_id] = metadata
                    
                    # Add to index
                    await self._add_to_index(text_id, embedding)
                    
                    # Update next_id counter
                    if text_id.startswith('txt_'):
                        try:
                            id_num = int(text_id.split('_')[1])
                            self.next_id = max(self.next_id, id_num + 1)
                        except ValueError:
                            pass
                            
                except Exception as e:
                    logger.error(f"Failed to load embedding from {embedding_file}: {e}")
            
            logger.info(f"Loaded {len(self.id_to_text)} existing embeddings")
            
        except Exception as e:
            logger.error(f"Failed to load existing embeddings: {e}")
    
    async def _remove_saved_embedding(self, text_id: str):
        """Remove saved embedding file"""
        try:
            embedding_file = self.embeddings_dir / f"{text_id}.pkl"
            if embedding_file.exists():
                embedding_file.unlink()
        except Exception as e:
            logger.error(f"Failed to remove saved embedding for {text_id}: {e}")
    
    async def clear_cache(self):
        """Clear the embeddings cache"""
        self.embeddings_cache.clear()
        logger.info("Embeddings cache cleared")
    
    async def rebuild_index(self):
        """Rebuild the search index from stored embeddings"""
        try:
            logger.info("Rebuilding search index...")
            
            # Clear current index
            await self._initialize_search_index()
            
            # Reload all embeddings
            for text_id in list(self.id_to_text.keys()):
                embedding_file = self.embeddings_dir / f"{text_id}.pkl"
                if embedding_file.exists():
                    with open(embedding_file, 'rb') as f:
                        data = pickle.load(f)
                    await self._add_to_index(text_id, data['embedding'])
            
            logger.info("Search index rebuilt successfully")
            
        except Exception as e:
            logger.error(f"Failed to rebuild index: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on embeddings manager"""
        return {
            'status': 'healthy',
            'model_name': self.model_name,
            'embedding_dimension': self.embedding_dimension,
            'total_texts': len(self.id_to_text),
            'cache_size': len(self.embeddings_cache),
            'dependencies': {
                'sentence_transformers': SENTENCE_TRANSFORMERS_AVAILABLE,
                'faiss': FAISS_AVAILABLE,
                'numpy': True
            },
            'storage': {
                'embeddings_dir': str(self.embeddings_dir),
                'files_count': len(list(self.embeddings_dir.glob("*.pkl")))
            }
        }