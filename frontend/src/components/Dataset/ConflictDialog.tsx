/**
 * Conflict Dialog Component
 * Handles filename conflicts with Replace/Keep Both options per FR-022
 */

import React, { useState } from 'react';
import * as datasetsService from '../../services/datasets';
import type { Dataset } from '../../types';
import './ConflictDialog.css';

interface ConflictDialogProps {
  filename: string;
  file: File;
  onResolve: (dataset: Dataset) => void;
  onCancel: () => void;
}

export const ConflictDialog: React.FC<ConflictDialogProps> = ({
  filename,
  file,
  onResolve,
  onCancel,
}) => {
  const [processing, setProcessing] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  const generateNewFilename = (originalName: string, attempt: number = 1): string => {
    const dotIndex: number = originalName.lastIndexOf('.');
    const name: string = originalName.substring(0, dotIndex);
    const ext: string = originalName.substring(dotIndex);
    return `${name} (${attempt})${ext}`;
  };

  const handleReplace = async (): Promise<void> => {
    setProcessing(true);
    setError('');

    try {
      // First, find and delete the existing dataset
      const datasetList = await datasetsService.list();
      const existingDataset: Dataset | undefined = datasetList.datasets.find(
        (d: Dataset): boolean => d.filename === filename
      );

      if (existingDataset) {
        await datasetsService.deleteDataset(existingDataset.id);
      }

      // Then upload the new file
      const dataset: Dataset = await datasetsService.upload(file);
      onResolve(dataset);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to replace file');
      }
    } finally {
      setProcessing(false);
    }
  };

  const handleKeepBoth = async (): Promise<void> => {
    setProcessing(true);
    setError('');

    try {
      // Try uploading with renamed file
      let attempt: number = 1;
      let success: boolean = false;
      let dataset: Dataset | null = null;

      while (!success && attempt <= 10) {
        const newFilename: string = generateNewFilename(filename, attempt);
        const renamedFile: File = new File([file], newFilename, { type: file.type });

        try {
          dataset = await datasetsService.upload(renamedFile);
          success = true;
        } catch (err: unknown) {
          if (typeof err === 'object' && err !== null && 'status' in err && err.status === 409) {
            // Still conflicting, try next number
            attempt++;
          } else {
            throw err;
          }
        }
      }

      if (success && dataset) {
        onResolve(dataset);
      } else {
        setError('Could not find an available filename');
      }
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to upload file');
      }
    } finally {
      setProcessing(false);
    }
  };

  const handleCancel = (): void => {
    if (!processing) {
      onCancel();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Escape' && !processing) {
      onCancel();
    }
  };

  return (
    <div className="conflict-dialog-overlay" onKeyDown={handleKeyDown}>
      <div className="conflict-dialog" role="dialog" aria-labelledby="dialog-title" aria-modal="true">
        <h3 id="dialog-title">File Already Exists</h3>

        <p className="conflict-message">
          A file named <strong>{filename}</strong> already exists. What would you like to do?
        </p>

        {error && (
          <div className="error-message" role="alert">
            {error}
          </div>
        )}

        <div className="conflict-options">
          <button
            onClick={() => void handleReplace()}
            disabled={processing}
            className="option-button replace-button"
          >
            <div className="option-title">Replace</div>
            <div className="option-description">Delete the old file and upload the new one</div>
          </button>

          <button
            onClick={() => void handleKeepBoth()}
            disabled={processing}
            className="option-button keep-both-button"
          >
            <div className="option-title">Keep Both</div>
            <div className="option-description">
              Upload as &quot;{generateNewFilename(filename)}&quot;
            </div>
          </button>
        </div>

        <div className="dialog-actions">
          <button onClick={handleCancel} disabled={processing} className="dialog-cancel-button">
            Cancel
          </button>
        </div>

        {processing && <div className="processing-overlay">Processing...</div>}
      </div>
    </div>
  );
};
