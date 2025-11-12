import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import './App.css'
import './styles/charts.css'
import Navigation from './components/Navigation'
import BacktestPage from './pages/BacktestPage'
import SignalViewerPage from './pages/SignalViewerPage'
import DataManagementPage from './pages/DataManagementPage'
import MarketListPage from './pages/MarketListPage'
import MarketScreenerPage from './pages/MarketScreenerPage'

export default function App() {
  return (
    <Router>
      <Navigation />
      <Routes>
        <Route path="/" element={<BacktestPage />} />
        <Route path="/viewer" element={<SignalViewerPage />} />
        <Route path="/data" element={<DataManagementPage />} />
        <Route path="/markets" element={<MarketListPage />} />
        <Route path="/screener" element={<MarketScreenerPage />} />
      </Routes>
    </Router>
  )
}
