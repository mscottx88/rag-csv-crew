/**
 * Application Entry Point
 * Bootstraps the React application
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

/* Disable browser right-click context menu globally */
document.addEventListener('contextmenu', (e: MouseEvent): void => { e.preventDefault(); });

const root: HTMLElement | null = document.getElementById('root');

if (!root) {
  throw new Error('Root element not found');
}

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
