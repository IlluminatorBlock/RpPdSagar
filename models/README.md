# Parkinson's Disease Prediction Model

## Required Model File
Place your trained Parkinson's disease prediction model in this directory with the exact filename:
**`parkinsons_model.keras`**

## Model Requirements
- **Format**: Keras model file (.keras extension)
- **Input**: Preprocessed MRI scan features
- **Output**: Binary classification (Parkinson's/No Parkinson's) with confidence scores
- **Architecture**: Should accept features extracted from MRI scans by the MRIProcessor

## Expected Model Interface
The model should be loadable with:
```python
import tensorflow as tf
model = tf.keras.models.load_model('models/parkinsons_model.keras')
```

## Current Status
⚠️ **MODEL NOT FOUND**: The system is currently running in chat-only mode because the model file is missing.

## To Enable MRI Prediction
1. Train or obtain a Parkinson's disease prediction model
2. Save it as `parkinsons_model.keras` in this directory
3. Restart the system - the AI/ML agent will automatically detect and load the model
4. You can then use commands like:
   - `analyze mri "path/to/scan.png"`
   - `get report for "path/to/scan.png"`

## Testing Without a Real Model
The system includes mock prediction functionality for testing. Even without a real model, you can test the workflow by temporarily enabling mock predictions in the AI/ML agent configuration.