/**
 * Main App Component
 * Application routing and layout structure
 */

import React, { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider, ProtectedRoute } from './context/AuthContext';
import { Header } from './components/Layout/Header';
import { Sidebar } from './components/Layout/Sidebar';
import { Login } from './components/Auth/Login';
import { Dashboard } from './pages/Dashboard';
import { Query } from './pages/Query';
import { Datasets } from './pages/Datasets';
import { Upload } from './pages/Upload';
import { DatasetInspector } from './pages/DatasetInspector';
import { History } from './pages/History';
import { NotFound } from './pages/NotFound';
import { CursorSnake } from './components/CursorSnake/CursorSnake';
import { LightningBorder } from './components/LightningBorder/LightningBorder';
import { CircuitBoard } from './components/CircuitBoard/CircuitBoard';
import './App.css';
import './utils/pageTransition.css';

const App: React.FC = () => {
  const [isDatasetsEmpty, setIsDatasetsEmpty] = useState<boolean>(false);

  return (
    <BrowserRouter>
      <AuthProvider>
        <CircuitBoard />
        <LightningBorder />
        <CursorSnake />
        <Routes>
          {/* Public Route: Login */}
          <Route path="/login" element={<Login />} />

          {/* Protected Routes with Layout */}
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <div className="app-layout">
                  <Header />
                  <div className="app-main">
                    <Sidebar isDatasetsEmpty={isDatasetsEmpty} />
                    <main className="app-content">
                      <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/query" element={<Query />} />
                        <Route path="/upload" element={<Upload />} />
                        <Route path="/datasets/:id" element={<DatasetInspector />} />
                        <Route path="/datasets" element={<Datasets onEmptyChange={setIsDatasetsEmpty} />} />
                        <Route path="/history" element={<History />} />
                        <Route path="*" element={<NotFound />} />
                      </Routes>
                    </main>
                  </div>
                </div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
