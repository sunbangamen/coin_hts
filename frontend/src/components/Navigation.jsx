import { Link } from 'react-router-dom'
import './Navigation.css'

export default function Navigation() {
  return (
    <nav className="navbar">
      <header className="navbar-header">
        <h1 className="navbar-title">코인 백테스팅 플랫폼</h1>
      </header>
      <div className="navbar-links">
        <Link to="/" className="nav-link">
          백테스트
        </Link>
        <Link to="/viewer" className="nav-link">
          시그널 뷰어
        </Link>
        <Link to="/data" className="nav-link">
          데이터 관리
        </Link>
        <Link to="/markets" className="nav-link">
          종목 리스트
        </Link>
        <Link to="/screener" className="nav-link">
          조건 검색
        </Link>
      </div>
    </nav>
  )
}
