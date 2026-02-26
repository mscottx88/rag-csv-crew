/**
 * Datasets Page
 * Dataset upload and management interface.
 * Upload area on top (full width), dataset list below (full width).
 * When uploading, the upload area expands to fill the entire space.
 */

import React, { useState } from 'react';
import { UploadForm } from '../components/Dataset/UploadForm';
import { DatasetList } from '../components/Dataset/DatasetList';
import { ConflictDialog } from '../components/Dataset/ConflictDialog';
import type { Dataset } from '../types';
import './Datasets.css';

export const Datasets: React.FC = () => {
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const [conflictFile, setConflictFile] = useState<{ filename: string; file: File } | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);

  const handleUploadComplete = (_dataset: Dataset): void => {
    setIsUploading(false);
    setRefreshTrigger((prev: number): number => prev + 1);
  };

  const handleConflict = (_filename: string): void => {
    setIsUploading(false);
  };

  const handleConflictResolve = (_dataset: Dataset): void => {
    setConflictFile(null);
    setRefreshTrigger((prev: number): number => prev + 1);
  };

  const handleConflictCancel = (): void => {
    setConflictFile(null);
  };

  const handleUploadStart = (): void => {
    setIsUploading(true);
  };

  return (
    <div className={`datasets-page ${isUploading ? 'datasets-uploading' : ''}`}>
      <h1>Datasets</h1>
      <p className="page-description">
        Upload CSV files to make them queryable. Once uploaded, you can ask natural language
        questions about your data.
      </p>

      <UploadForm
        onUploadComplete={handleUploadComplete}
        onConflict={handleConflict}
        onUploadStart={handleUploadStart}
      />

      {!isUploading && (
        <DatasetList refresh={refreshTrigger} />
      )}

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
