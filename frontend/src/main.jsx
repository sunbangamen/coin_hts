import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navigation from './components/Navigation.jsx'
import BacktestPage from './pages/BacktestPage.jsx'
import DataManagementPage from './pages/DataManagementPage.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Navigation />
      <Routes>
        <Route path="/" element={<BacktestPage />} />
        <Route path="/data" element={<DataManagementPage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
