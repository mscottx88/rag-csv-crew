/**
 * Dataset Upload Form Component
 * CSV file upload with drag-and-drop and progress tracking per FR-012
 */

import React, { useState, ChangeEvent, DragEvent, useRef } from 'react';
import * as datasetsService from '../../services/datasets';
import type { Dataset, UploadProgress } from '../../types';
import './UploadForm.css';

interface UploadFormProps {
  onUploadComplete: (dataset: Dataset) => void;
  onConflict?: (filename: string) => void;
}

export const UploadForm: React.FC<UploadFormProps> = ({ onUploadComplete, onConflict }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);
  const [error, setError] = useState<string>('');
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>): void => {
    const file: File | null = e.target.files?.[0] || null;
    setSelectedFile(file);
    setError('');
    setProgress(0);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setIsDragging(false);

    const file: File | null = e.dataTransfer.files?.[0] || null;
    if (file && file.name.toLowerCase().endsWith('.csv')) {
      setSelectedFile(file);
      setError('');
      setProgress(0);
    } else {
      setError('Please select a valid CSV file');
    }
  };

  const handleUpload = async (): Promise<void> => {
    if (!selectedFile) {
      setError('Please select a file');
      return;
    }

    setUploading(true);
    setError('');
    setProgress(0);

    try {
      const dataset: Dataset = await datasetsService.upload(
        selectedFile,
        (uploadProgress: UploadProgress): void => {
          setProgress(uploadProgress.percentage);
        }
      );

      setSelectedFile(null);
      setProgress(0);
      onUploadComplete(dataset);

      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err: unknown) {
      // Check for conflict error (409)
      if (typeof err === 'object' && err !== null && 'status' in err && err.status === 409) {
        if (onConflict && selectedFile) {
          onConflict(selectedFile.name);
        }
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Upload failed. Please try again.');
      }
    } finally {
      setUploading(false);
    }
  };

  const handleCancel = (): void => {
    setSelectedFile(null);
    setProgress(0);
    setError('');
    setUploading(false);

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="upload-form">
      <h2>Upload CSV Dataset</h2>

      <div
        className={`drop-zone ${isDragging ? 'dragging' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={handleFileSelect}
          disabled={uploading}
          className="file-input"
          id="file-input"
        />
        <label htmlFor="file-input" className="file-label">
          {selectedFile ? (
            <span>{selectedFile.name}</span>
          ) : (
            <span>Drag and drop a CSV file here, or click to select</span>
          )}
        </label>
      </div>

      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}

      {uploading && (
        <div className="progress-container">
          <div className="progress-bar" style={{ width: `${progress}%` }} />
          <span className="progress-text">{progress}%</span>
        </div>
      )}

      <div className="button-group">
        <button onClick={handleUpload} disabled={!selectedFile || uploading} className="upload-button">
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
        {selectedFile && !uploading && (
          <button onClick={handleCancel} className="cancel-button">
            Cancel
          </button>
        )}
      </div>
    </div>
  );
};
