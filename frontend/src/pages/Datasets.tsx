/**
 * Datasets Page
 * Browse and manage uploaded datasets.
 */

import React from 'react';
import { DatasetList } from '../components/Dataset/DatasetList';
import './Datasets.css';

interface DatasetsProps {
  onEmptyChange?: (isEmpty: boolean) => void;
}

export const Datasets: React.FC<DatasetsProps> = ({ onEmptyChange }) => {
  return (
    <div className="datasets-page">
      <h1>Datasets</h1>
      <p className="page-description">
        Browse your uploaded datasets. Click on any dataset to expand and preview its contents.
      </p>

      <DatasetList onEmptyChange={onEmptyChange} />
    </div>
  );
};
