/**
 * Dataset Upload Form Component
 * CSV file upload with drag-and-drop and progress tracking per FR-012.
 *
 * Animation phases:
 *   hidden      – no animation shown
 *   uploading   – BeakerProgress (HTTP upload, 0–100%)
 *   processing  – FunnelProgress (ingestion phase)
 *   embedding   – VectorizeProgress (embedding phase)
 *   complete    – CogProgress (shown for COMPLETE_HOLD_MS then fades out)
 *
 * Each phase is shown for at least MIN_PHASE_MS before transitioning.
 * Transitions are cross-fades: fade out → swap content → fade in.
 * Opacity is controlled via inline style so the CSS transition animates it.
 */

import React, { useState, ChangeEvent, DragEvent, useRef, useEffect } from 'react';
import * as datasetsService from '../../services/datasets';
import type { Dataset, UploadProgress } from '../../types';
import { BeakerProgress } from './BeakerProgress';
import { FunnelProgress } from './FunnelProgress';
import { VectorizeProgress } from './VectorizeProgress';
import { CogProgress } from './CogProgress';
import './UploadForm.css';

type AnimPhase = 'hidden' | 'uploading' | 'processing' | 'embedding' | 'complete';

/** Cross-fade duration in ms */
const FADE_MS: number = 350;
/** Minimum time each phase is visible before transitioning away */
const MIN_PHASE_MS: number = 1000;
/** How long to hold the "complete" animation before fading out */
const COMPLETE_HOLD_MS: number = 3000;
/** Seconds of processing before auto-advancing to embedding phase */
const PROCESSING_HOLD_MS: number = 3000;

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
  const processingStartedRef = useRef<boolean>(false);

  /** Cancel all pending phase-transition timers. */
  const clearPhaseTimers = (): void => {
    phaseTimersRef.current.forEach((id: ReturnType<typeof setTimeout>) => clearTimeout(id));
    phaseTimersRef.current = [];
  };

  useEffect(() => {
    return (): void => { clearPhaseTimers(); };
  }, []);

  /**
   * Cross-fade to a new phase, honouring MIN_PHASE_MS for the current phase.
   *
   * Sequence:
   *   1. Wait until current phase has been shown for MIN_PHASE_MS.
   *   2. Fade opacity to 0 (FADE_MS transition).
   *   3. Swap displayPhase to newPhase (React re-renders at opacity 0).
   *   4. One tick later: set opacity to 1 (FADE_MS transition).
   *   5. Call onShown() so callers can schedule follow-up transitions.
   */
  const crossFadeTo = (newPhase: AnimPhase, onShown?: () => void): void => {
    const elapsed: number = Date.now() - phaseStartRef.current;
    const wait: number = Math.max(0, MIN_PHASE_MS - elapsed);

    const tWait: ReturnType<typeof setTimeout> = setTimeout((): void => {
      setAnimOpacity(0);

      const tSwap: ReturnType<typeof setTimeout> = setTimeout((): void => {
        setDisplayPhase(newPhase);
        phaseStartRef.current = Date.now();

        // One tick after React renders the new content at opacity 0, fade in.
        const tFadeIn: ReturnType<typeof setTimeout> = setTimeout((): void => {
          setAnimOpacity(1);
          if (onShown) {
            onShown();
          }
        }, 16);
        phaseTimersRef.current.push(tFadeIn);
      }, FADE_MS);

      phaseTimersRef.current.push(tSwap);
    }, wait);

    phaseTimersRef.current.push(tWait);
  };

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
    if (onUploadStart) {
      onUploadStart();
    }

    // Show uploading phase immediately: render at opacity 0, then fade in after 1 tick.
    setDisplayPhase('uploading');
    phaseStartRef.current = Date.now();
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

          // When HTTP upload completes, cross-fade to processing.
          // After PROCESSING_HOLD_MS of showing processing, cross-fade to embedding.
          // Guard prevents double-scheduling if this callback fires multiple times at 100%.
          if (pct >= 100 && !processingStartedRef.current) {
            processingStartedRef.current = true;
            crossFadeTo('processing', (): void => {
              const tEmbedding: ReturnType<typeof setTimeout> = setTimeout((): void => {
                crossFadeTo('embedding');
              }, PROCESSING_HOLD_MS);
              phaseTimersRef.current.push(tEmbedding);
            });
          }
        }
      );

      // Server responded — cancel any pending phase timers and go to complete.
      clearPhaseTimers();
      processingStartedRef.current = false;
      setProgress(0);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      crossFadeTo('complete', (): void => {
        // After holding complete, fade out and notify parent.
        const tHold: ReturnType<typeof setTimeout> = setTimeout((): void => {
          setAnimOpacity(0);
          const tHide: ReturnType<typeof setTimeout> = setTimeout((): void => {
            setDisplayPhase('hidden');
            onUploadComplete(dataset);
          }, FADE_MS);
          phaseTimersRef.current.push(tHide);
        }, COMPLETE_HOLD_MS);
        phaseTimersRef.current.push(tHold);
      });

    } catch (err: unknown) {
      clearPhaseTimers();
      setAnimOpacity(0);
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
    } finally {
      setUploading(false);
    }
  };

  const handleCancel = (): void => {
    clearPhaseTimers();
    processingStartedRef.current = false;
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
          {displayPhase === 'uploading' && (
            <BeakerProgress progress={progress} />
          )}
          {displayPhase === 'processing' && (
            <FunnelProgress label="Ingesting..." />
          )}
          {displayPhase === 'embedding' && (
            <VectorizeProgress label="Embedding..." />
          )}
          {displayPhase === 'complete' && (
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
