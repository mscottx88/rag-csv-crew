/**
 * Upload Page
 * Dedicated CSV file upload interface.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UploadForm } from '../components/Dataset/UploadForm';
import { ConflictDialog } from '../components/Dataset/ConflictDialog';
import type { Dataset } from '../types';
import './Upload.css';

export const Upload: React.FC = () => {
  const navigate = useNavigate();
  const [conflictFile, setConflictFile] = useState<{ filename: string; file: File } | null>(null);

  const handleUploadComplete = (_dataset: Dataset): void => {
    navigate('/datasets');
  };

  const handleConflict = (_filename: string): void => {
    // ConflictDialog handles the UI
  };

  const handleConflictResolve = (_dataset: Dataset): void => {
    setConflictFile(null);
    navigate('/datasets');
  };

  const handleConflictCancel = (): void => {
    setConflictFile(null);
  };

  return (
    <div className="upload-page">
      <h1>Upload Dataset</h1>
      <p className="page-description">
        Upload a CSV file to make it queryable. Once uploaded, you can ask natural language
        questions about your data.
      </p>

      <UploadForm
        onUploadComplete={handleUploadComplete}
        onConflict={handleConflict}
      />

      {conflictFile && (
        <ConflictDialog
          filename={conflictFile.filename}
          file={conflictFile.file}
          onResolve={handleConflictResolve}
          onCancel={handleConflictCancel}
        />
      )}
    </div>
  );
};
