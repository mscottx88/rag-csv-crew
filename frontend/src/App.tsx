/**
 * Main App Component
 * Application routing and layout structure
 */

import React from 'react';
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
import './App.css';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
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
                    <Sidebar />
                    <main className="app-content">
                      <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/query" element={<Query />} />
                        <Route path="/upload" element={<Upload />} />
                        <Route path="/datasets/:id" element={<DatasetInspector />} />
                        <Route path="/datasets" element={<Datasets />} />
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
