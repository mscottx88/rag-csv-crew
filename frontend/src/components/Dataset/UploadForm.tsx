/**
 * Dataset Upload Form Component
 * CSV file upload with drag-and-drop and progress tracking per FR-012.
 *
 * Animation phases:
 *   hidden      – no animation shown
 *   uploading   – AssemblyLine3D Station 1: drop hopper (HTTP upload, 0–100%)
 *   processing  – AssemblyLine3D Station 2: shredder (ingestion phase)
 *   embedding   – AssemblyLine3D Station 3: digitizer (embedding phase)
 *   complete    – AssemblyLine3D Station 4: database silo (shown for COMPLETE_HOLD_MS then fades out)
 *
 * Phase transitions within the 3D scene are seamless (lerp-based, no cross-fade).
 * Only the initial appear and final dismiss use CSS opacity fade.
 */

import React, { useState, ChangeEvent, DragEvent, useRef, useEffect } from 'react';
import * as datasetsService from '../../services/datasets';
import type { Dataset, UploadProgress } from '../../types';
import { AssemblyLine3D } from './AssemblyLine3D';
import './UploadForm.css';

type AnimPhase = 'hidden' | 'uploading' | 'processing' | 'embedding' | 'complete';

/** Cross-fade duration in ms */
const FADE_MS: number = 350;
/** Minimum time each animation phase is shown (ms) */
const MIN_PHASE_MS: number = 2000;
/** How long to hold the "complete" animation before fading out */
const COMPLETE_HOLD_MS: number = 2000;

interface UploadFormProps {
  onUploadComplete: (dataset: Dataset) => void;
  onConflict?: (filename: string) => void;
  onUploadStart?: () => void;
}

export const UploadForm: React.FC<UploadFormProps> = ({ onUploadComplete, onConflict, onUploadStart }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);
  const [error, setError] = useState<string>('');
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [displayPhase, setDisplayPhase] = useState<AnimPhase>('hidden');
  const [animOpacity, setAnimOpacity] = useState<number>(0);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const phaseTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const phaseStartRef = useRef<number>(0);
  const uploadDoneRef = useRef<boolean>(false);
  const embeddingReadyRef = useRef<boolean>(false);
  const serverResultRef = useRef<Dataset | null>(null);
  const completeFiredRef = useRef<boolean>(false);

  /** Cancel all pending phase-transition timers. */
  const clearPhaseTimers = (): void => {
    phaseTimersRef.current.forEach((id: ReturnType<typeof setTimeout>) => clearTimeout(id));
    phaseTimersRef.current = [];
  };

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
    uploadDoneRef.current = false;
    embeddingReadyRef.current = false;
    serverResultRef.current = null;
    completeFiredRef.current = false;
    setUploading(true);
    setError('');
    setProgress(0);
    if (onUploadStart) {
      onUploadStart();
    }

    /** Transition to complete phase — called only once, when both
     *  the animation chain has finished AND the server has responded. */
    const goToComplete = (): void => {
      if (completeFiredRef.current) return;
      completeFiredRef.current = true;
      setDisplayPhase('complete');
      const tHold: ReturnType<typeof setTimeout> = setTimeout((): void => {
        setAnimOpacity(0);
        const tHide: ReturnType<typeof setTimeout> = setTimeout((): void => {
          setDisplayPhase('hidden');
          setUploading(false);
          if (serverResultRef.current) {
            onUploadComplete(serverResultRef.current);
          }
        }, FADE_MS);
        phaseTimersRef.current.push(tHide);
      }, COMPLETE_HOLD_MS);
      phaseTimersRef.current.push(tHold);
    };

    // Show uploading phase immediately: render at opacity 0, then fade in after 1 tick.
    phaseStartRef.current = Date.now();
    setDisplayPhase('uploading');
    const tFadeIn: ReturnType<typeof setTimeout> = setTimeout((): void => {
      setAnimOpacity(1);
    }, 16);
    phaseTimersRef.current.push(tFadeIn);

    try {
      const dataset: Dataset = await datasetsService.upload(
        selectedFile,
        (uploadProgress: UploadProgress): void => {
          const pct: number = uploadProgress.percentage;
          setProgress(pct);

          // When HTTP upload completes, start the timed phase chain.
          // Each phase runs for at least MIN_PHASE_MS.
          if (pct >= 100 && !uploadDoneRef.current) {
            uploadDoneRef.current = true;
            const elapsed: number = Date.now() - phaseStartRef.current;
            const remaining: number = Math.max(0, MIN_PHASE_MS - elapsed);

            const t1: ReturnType<typeof setTimeout> = setTimeout((): void => {
              phaseStartRef.current = Date.now();
              setDisplayPhase('processing');

              const t2: ReturnType<typeof setTimeout> = setTimeout((): void => {
                phaseStartRef.current = Date.now();
                setDisplayPhase('embedding');

                const t3: ReturnType<typeof setTimeout> = setTimeout((): void => {
                  embeddingReadyRef.current = true;
                  if (serverResultRef.current) {
                    goToComplete();
                  }
                }, MIN_PHASE_MS);
                phaseTimersRef.current.push(t3);
              }, MIN_PHASE_MS);
              phaseTimersRef.current.push(t2);
            }, remaining);
            phaseTimersRef.current.push(t1);
          }
        }
      );

      // Server responded — store result but don't interrupt the phase chain.
      // The chain will call goToComplete when the animation is ready.
      serverResultRef.current = dataset;
      setProgress(0);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      // If the animation chain already finished waiting, go to complete now.
      if (embeddingReadyRef.current) {
        goToComplete();
      }

    } catch (err: unknown) {
      clearPhaseTimers();
      setAnimOpacity(0);
      setUploading(false);
      const tHide: ReturnType<typeof setTimeout> = setTimeout((): void => {
        setDisplayPhase('hidden');
      }, FADE_MS);
      phaseTimersRef.current.push(tHide);

      if (typeof err === 'object' && err !== null && 'status' in err && err.status === 409) {
        if (onConflict && selectedFile) {
          onConflict(selectedFile.name);
        }
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Upload failed. Please try again.');
      }
    }
  };

  const handleCancel = (): void => {
    clearPhaseTimers();
    uploadDoneRef.current = false;
    embeddingReadyRef.current = false;
    serverResultRef.current = null;
    completeFiredRef.current = false;
    setProgress(0);
    setError('');
    setUploading(false);
    setAnimOpacity(0);
    const tHide: ReturnType<typeof setTimeout> = setTimeout((): void => {
      setDisplayPhase('hidden');
    }, FADE_MS);
    phaseTimersRef.current.push(tHide);
    setSelectedFile(null);

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
        onClick={(): void => { if (!uploading) fileInputRef.current?.click(); }}
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
        <label className="file-label">
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

      {displayPhase !== 'hidden' && (
        <div className="upload-animation" style={{ opacity: animOpacity }}>
          <AssemblyLine3D phase={displayPhase} progress={progress} />
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
