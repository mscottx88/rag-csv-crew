/**
 * Dataset Upload Form Component
 * CSV file upload with drag-and-drop and progress tracking per FR-012.
 *
 * Animation phases:
 *   hidden      – no animation shown
 *   uploading   – BeakerProgress (HTTP upload, 0–99%)
 *   processing  – FunnelProgress (upload hit 100%, first ~3 s of server work)
 *   embedding   – VectorizeProgress (3 s+ of server work; embedding phase)
 *   complete    – CogProgress (response received, shown for 3.5 s)
 *   fading      – CogProgress fading out over 1.5 s
 */

import React, { useState, ChangeEvent, DragEvent, useRef, useEffect } from 'react';
import * as datasetsService from '../../services/datasets';
import type { Dataset, UploadProgress } from '../../types';
import { BeakerProgress } from './BeakerProgress';
import { FunnelProgress } from './FunnelProgress';
import { VectorizeProgress } from './VectorizeProgress';
import { CogProgress } from './CogProgress';
import './UploadForm.css';

type AnimPhase = 'hidden' | 'uploading' | 'processing' | 'embedding' | 'complete' | 'fading';

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
  const [animPhase, setAnimPhase] = useState<AnimPhase>('hidden');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const phaseTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  // Guards against setting up the processing→embedding timer more than once
  const processingStartedRef = useRef<boolean>(false);

  /** Cancel any pending phase-transition timers */
  const clearPhaseTimers = (): void => {
    phaseTimersRef.current.forEach((id: ReturnType<typeof setTimeout>) => clearTimeout(id));
    phaseTimersRef.current = [];
  };

  // Clean up timers on unmount
  useEffect(() => {
    return (): void => { clearPhaseTimers(); };
  }, []);

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

    clearPhaseTimers();
    processingStartedRef.current = false;
    setUploading(true);
    setError('');
    setProgress(0);
    setAnimPhase('uploading');

    try {
      const dataset: Dataset = await datasetsService.upload(
        selectedFile,
        (uploadProgress: UploadProgress): void => {
          const pct: number = uploadProgress.percentage;
          setProgress(pct);

          // When HTTP upload finishes, switch to funnel (ingestion) phase.
          // After 3 s of waiting, switch to vectorize (embedding) phase.
          // Guard prevents multiple timers if the callback fires > once at 100%.
          if (pct >= 100 && !processingStartedRef.current) {
            processingStartedRef.current = true;
            setAnimPhase('processing');

            const t0: ReturnType<typeof setTimeout> = setTimeout((): void => {
              // Only advance if we haven't already moved to 'complete'
              setAnimPhase((prev: AnimPhase): AnimPhase =>
                prev === 'processing' ? 'embedding' : prev
              );
            }, 3000);
            phaseTimersRef.current.push(t0);
          }
        }
      );

      // Server responded — all phases done
      clearPhaseTimers();
      setSelectedFile(null);
      setProgress(0);
      setAnimPhase('complete');

      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      // Show cog for 3.5 s, then 1.5 s fade-out, then notify parent
      const t1: ReturnType<typeof setTimeout> = setTimeout((): void => {
        setAnimPhase('fading');
        const t2: ReturnType<typeof setTimeout> = setTimeout((): void => {
          setAnimPhase('hidden');
          onUploadComplete(dataset);
        }, 1500);
        phaseTimersRef.current.push(t2);
      }, 3500);
      phaseTimersRef.current.push(t1);

    } catch (err: unknown) {
      clearPhaseTimers();
      setAnimPhase('hidden');

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
    clearPhaseTimers();
    processingStartedRef.current = false;
    setSelectedFile(null);
    setProgress(0);
    setError('');
    setUploading(false);
    setAnimPhase('hidden');

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const showAnimation: boolean = animPhase !== 'hidden';
  const isFading: boolean = animPhase === 'fading';

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

      {showAnimation && (
        <div className={`upload-animation ${isFading ? 'fading-out' : ''}`}>
          {animPhase === 'uploading' && (
            <BeakerProgress progress={progress} />
          )}
          {animPhase === 'processing' && (
            <FunnelProgress label="Ingesting..." />
          )}
          {animPhase === 'embedding' && (
            <VectorizeProgress label="Embedding..." />
          )}
          {(animPhase === 'complete' || animPhase === 'fading') && (
            <CogProgress label="Complete!" />
          )}
        </div>
      )}

      <div className="button-group">
        <button
          onClick={() => void handleUpload()}
          disabled={!selectedFile || uploading}
          className="upload-button"
        >
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
