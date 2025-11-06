import { useState, useEffect } from 'react'
import '../App.css'
import '../styles/DataManagementPage.css'
import { fetchInventory, uploadFile } from '../services/dataApi'
import SchedulerPanel from '../components/SchedulerPanel'

const TIMEFRAMES = ['1D', '1H', '5M', '1M']

export default function DataManagementPage() {
  const [activeTab, setActiveTab] = useState('inventory')

  // Inventory state
  const [files, setFiles] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [inventoryError, setInventoryError] = useState(null)

  // Filter state
  const [filters, setFilters] = useState({
    symbol: '',
    timeframe: '',
    limit: 50,
    offset: 0
  })

  // Upload state
  const [uploadFile_input, setUploadFile_input] = useState(null)
  const [uploadSymbol, setUploadSymbol] = useState('')
  const [uploadTimeframe, setUploadTimeframe] = useState('1D')
  const [uploadYear, setUploadYear] = useState(new Date().getFullYear())
  const [uploadOverwrite, setUploadOverwrite] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadSuccess, setUploadSuccess] = useState(null)

  // Available symbols (collected from inventory)
  const [availableSymbols, setAvailableSymbols] = useState(new Set())

  /**
   * 인벤토리 조회
   */
  const loadInventory = async () => {
    setLoading(true)
    setInventoryError(null)

    try {
      const params = {
        limit: filters.limit,
        offset: filters.offset
      }

      if (filters.symbol) params.symbol = filters.symbol
      if (filters.timeframe) params.timeframe = filters.timeframe

      const response = await fetchInventory(params)

      setFiles(response.files || [])
      setTotalCount(response.total_count || 0)

      // 가능한 심볼 수집
      const symbols = new Set(response.files.map(f => f.symbol))
      setAvailableSymbols(symbols)
    } catch (error) {
      const errorMessage = error.response?.data?.detail || error.message || '데이터 조회 실패'
      setInventoryError(errorMessage)
      setFiles([])
      setTotalCount(0)
    } finally {
      setLoading(false)
    }
  }

  // 초기 로드
  useEffect(() => {
    loadInventory()
  }, [filters.symbol, filters.timeframe, filters.limit, filters.offset])

  /**
   * 파일 업로드 처리
   */
  const handleUpload = async (e) => {
    e.preventDefault()
    setUploadError(null)
    setUploadSuccess(null)

    if (!uploadFile_input) {
      setUploadError('파일을 선택하세요')
      return
    }

    if (!uploadSymbol.trim()) {
      setUploadError('심볼을 입력하세요')
      return
    }

    setUploading(true)

    try {
      const result = await uploadFile({
        file: uploadFile_input,
        symbol: uploadSymbol.toUpperCase(),
        timeframe: uploadTimeframe.toUpperCase(),
        year: uploadYear,
        overwrite: uploadOverwrite
      })

      if (result.success) {
        setUploadSuccess(`파일이 성공적으로 업로드되었습니다: ${result.file_path}`)
        // 업로드 폼 초기화
        setUploadFile_input(null)
        setUploadSymbol('')
        setUploadTimeframe('1D')
        setUploadYear(new Date().getFullYear())
        setUploadOverwrite(false)

        // 인벤토리 새로고침
        await loadInventory()
      }
    } catch (error) {
      const errorMessage = error.response?.data?.detail || error.message || '파일 업로드 실패'
      setUploadError(errorMessage)
    } finally {
      setUploading(false)
    }
  }

  /**
   * 페이지네이션 처리
   */
  const handlePrevPage = () => {
    setFilters(prev => ({
      ...prev,
      offset: Math.max(0, prev.offset - prev.limit)
    }))
  }

  const handleNextPage = () => {
    if (filters.offset + filters.limit < totalCount) {
      setFilters(prev => ({
        ...prev,
        offset: prev.offset + prev.limit
      }))
    }
  }

  /**
   * 파일 크기 포맷팅
   */
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  /**
   * 날짜 포맷팅
   */
  const formatDate = (isoString) => {
    if (!isoString) return '-'
    const date = new Date(isoString)
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="app">
      <main>
        <div className="form-container">
          <h2>데이터 관리</h2>

          {/* Tab Navigation */}
          <div className="tab-navigation">
            <button
              className={`tab-btn ${activeTab === 'inventory' ? 'active' : ''}`}
              onClick={() => setActiveTab('inventory')}
            >
              📊 데이터 조회
            </button>
            <button
              className={`tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
              onClick={() => setActiveTab('upload')}
            >
              📤 파일 업로드
            </button>
            <button
              className={`tab-btn ${activeTab === 'scheduler' ? 'active' : ''}`}
              onClick={() => setActiveTab('scheduler')}
            >
              ⏰ 자동 수집
            </button>
          </div>

          {/* Inventory Tab */}
          {activeTab === 'inventory' && (
            <div className="inventory-section">
              <h3>데이터 파일 목록</h3>

              {/* Filters */}
              <div className="filters-row">
                <div className="form-group">
                  <label htmlFor="symbol-filter">심볼</label>
                  <select
                    id="symbol-filter"
                    value={filters.symbol}
                    onChange={(e) =>
                      setFilters(prev => ({ ...prev, symbol: e.target.value, offset: 0 }))
                    }
                  >
                    <option value="">모두</option>
                    {Array.from(availableSymbols)
                      .sort()
                      .map(symbol => (
                        <option key={symbol} value={symbol}>
                          {symbol}
                        </option>
                      ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="timeframe-filter">타임프레임</label>
                  <select
                    id="timeframe-filter"
                    value={filters.timeframe}
                    onChange={(e) =>
                      setFilters(prev => ({ ...prev, timeframe: e.target.value, offset: 0 }))
                    }
                  >
                    <option value="">모두</option>
                    {TIMEFRAMES.map(tf => (
                      <option key={tf} value={tf}>
                        {tf}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Error Message */}
              {inventoryError && (
                <div className="error-message" role="alert">
                  ⚠️ {inventoryError}
                </div>
              )}

              {/* Loading Spinner */}
              {loading && (
                <div className="loading-spinner">
                  <div className="spinner"></div>
                  <p>데이터를 조회 중입니다...</p>
                </div>
              )}

              {/* Files Table */}
              {!loading && files.length > 0 && (
                <>
                  <table className="files-table">
                    <thead>
                      <tr>
                        <th>심볼</th>
                        <th>타임프레임</th>
                        <th>연도</th>
                        <th>파일 크기</th>
                        <th>수정일</th>
                      </tr>
                    </thead>
                    <tbody>
                      {files.map((file, idx) => (
                        <tr key={`${file.symbol}-${file.timeframe}-${file.year}-${idx}`}>
                          <td className="symbol-cell">{file.symbol}</td>
                          <td className="timeframe-cell">{file.timeframe}</td>
                          <td className="year-cell">{file.year}</td>
                          <td className="size-cell">{formatFileSize(file.size_bytes)}</td>
                          <td className="date-cell">{formatDate(file.modified_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {/* Pagination */}
                  <div className="pagination">
                    <button
                      className="pagination-btn"
                      onClick={handlePrevPage}
                      disabled={filters.offset === 0}
                    >
                      ← 이전
                    </button>
                    <span className="pagination-info">
                      {filters.offset + 1} - {Math.min(filters.offset + filters.limit, totalCount)} / {totalCount}
                    </span>
                    <button
                      className="pagination-btn"
                      onClick={handleNextPage}
                      disabled={filters.offset + filters.limit >= totalCount}
                    >
                      다음 →
                    </button>
                  </div>
                </>
              )}

              {/* Empty State */}
              {!loading && files.length === 0 && !inventoryError && (
                <div className="empty-state">
                  <p>📭 아직 업로드된 데이터가 없습니다.</p>
                  <p>파일 업로드 탭에서 데이터를 업로드하세요.</p>
                </div>
              )}
            </div>
          )}

          {/* Upload Tab */}
          {activeTab === 'upload' && (
            <div className="upload-section">
              <h3>파일 업로드</h3>

              {/* Success Message */}
              {uploadSuccess && (
                <div className="success-message" role="alert">
                  ✅ {uploadSuccess}
                </div>
              )}

              {/* Error Message */}
              {uploadError && (
                <div className="error-message" role="alert">
                  ⚠️ {uploadError}
                </div>
              )}

              <form onSubmit={handleUpload} className="upload-form">
                {/* File Input */}
                <div className="form-group">
                  <label htmlFor="file-input">파일 선택 * (Parquet 형식)</label>
                  <input
                    id="file-input"
                    type="file"
                    accept=".parquet"
                    onChange={(e) => setUploadFile_input(e.target.files?.[0] || null)}
                    required
                    disabled={uploading}
                  />
                  {uploadFile_input && (
                    <div className="file-info">
                      선택된 파일: {uploadFile_input.name} ({formatFileSize(uploadFile_input.size)})
                    </div>
                  )}
                </div>

                {/* Symbol Input */}
                <div className="form-group">
                  <label htmlFor="symbol-input">심볼 *</label>
                  <input
                    id="symbol-input"
                    type="text"
                    placeholder="예: BTC_KRW"
                    value={uploadSymbol}
                    onChange={(e) => setUploadSymbol(e.target.value)}
                    disabled={uploading}
                    pattern="[A-Za-z0-9_]*"
                    title="대문자, 숫자, 언더스코어만 사용 가능합니다"
                  />
                  <div className="info-text">입력하신 심볼은 자동으로 대문자로 변환됩니다.</div>
                </div>

                {/* Timeframe Select */}
                <div className="form-group">
                  <label htmlFor="timeframe-input">타임프레임 *</label>
                  <select
                    id="timeframe-input"
                    value={uploadTimeframe}
                    onChange={(e) => setUploadTimeframe(e.target.value)}
                    disabled={uploading}
                  >
                    {TIMEFRAMES.map(tf => (
                      <option key={tf} value={tf}>
                        {tf}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Year Input */}
                <div className="form-group">
                  <label htmlFor="year-input">연도 *</label>
                  <input
                    id="year-input"
                    type="number"
                    min="2000"
                    max="2099"
                    value={uploadYear}
                    onChange={(e) => setUploadYear(parseInt(e.target.value))}
                    disabled={uploading}
                  />
                </div>

                {/* Overwrite Checkbox */}
                <div className="form-group checkbox">
                  <label htmlFor="overwrite-check">
                    <input
                      id="overwrite-check"
                      type="checkbox"
                      checked={uploadOverwrite}
                      onChange={(e) => setUploadOverwrite(e.target.checked)}
                      disabled={uploading}
                    />
                    <span>기존 파일 덮어쓰기 허용</span>
                  </label>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  className={`submit-btn ${uploading ? 'loading' : ''}`}
                  disabled={!uploadFile_input || !uploadSymbol.trim() || uploading}
                  aria-busy={uploading}
                >
                  {uploading ? '업로드 중...' : '파일 업로드'}
                </button>
              </form>

              {/* Info Box */}
              <div className="info-box">
                <h4>📋 업로드 가이드</h4>
                <ul>
                  <li>Parquet 형식의 파일만 업로드 가능합니다</li>
                  <li>필수 컬럼: open, high, low, close, volume, timestamp</li>
                  <li>파일 크기: 최대 200MB</li>
                  <li>저장 경로: <code>{`DATA_ROOT/{심볼}/{타임프레임}/{연도}.parquet`}</code></li>
                  <li>심볼과 타임프레임은 자동으로 대문자로 정규화됩니다</li>
                </ul>
              </div>
            </div>
          )}

          {/* Scheduler Tab */}
          {activeTab === 'scheduler' && (
            <SchedulerPanel />
          )}
        </div>
      </main>
    </div>
  )
}
