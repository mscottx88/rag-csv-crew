/**
 * Datasets Page
 * Dataset upload and management interface
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

  const handleUploadComplete = (_dataset: Dataset): void => {
    setRefreshTrigger((prev: number): number => prev + 1); // Trigger list refresh
  };

  const handleConflict = (_filename: string): void => {
    // Store the file for conflict dialog
    // Note: We need to reconstruct the file from state if using ConflictDialog
    // Conflict handling would go here
  };

  const handleConflictResolve = (_dataset: Dataset): void => {
    setConflictFile(null);
    setRefreshTrigger((prev: number): number => prev + 1);
  };

  const handleConflictCancel = (): void => {
    setConflictFile(null);
  };

  return (
    <div className="datasets-page">
      <h1>Datasets</h1>
      <p className="page-description">
        Upload CSV files to make them queryable. Once uploaded, you can ask natural language
        questions about your data.
      </p>

      <div className="datasets-layout">
        <div className="upload-section">
          <UploadForm onUploadComplete={handleUploadComplete} onConflict={handleConflict} />
        </div>

        <div className="list-section">
          <DatasetList refresh={refreshTrigger} />
        </div>
      </div>

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
