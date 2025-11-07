import React, { useState, useEffect } from 'react'
import {
  getPresets,
  savePreset,
  updatePreset,
  deletePreset
} from '../services/strategyApi'

/**
 * StrategyPresetModal - 전략 프리셋 관리 모달
 *
 * Props:
 *   - isOpen (bool): 모달 열림 여부
 *   - onClose (func): 모달 닫기 핸들러
 *   - onPresetSelect (func): 프리셋 선택 핸들러 (name, preset 전달)
 *   - currentStrategy (string): 현재 선택된 전략
 *   - currentParams (Object): 현재 파라미터
 */
export default function StrategyPresetModal({
  isOpen,
  onClose,
  onPresetSelect,
  currentStrategy,
  currentParams
}) {
  const [presets, setPresets] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('list') // 'list' or 'save'
  const [presetName, setPresetName] = useState('')
  const [presetDescription, setPresetDescription] = useState('')
  const [selectedPreset, setSelectedPreset] = useState(null)

  // 모달이 열릴 때 프리셋 목록 로드
  useEffect(() => {
    if (isOpen) {
      loadPresets()
    }
  }, [isOpen])

  // 프리셋 목록 로드
  const loadPresets = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getPresets()
      setPresets(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message || '프리셋 목록을 로드할 수 없습니다')
    } finally {
      setLoading(false)
    }
  }

  // 프리셋 적용
  const handleSelectPreset = (preset) => {
    setSelectedPreset(preset)
    // 부모 컴포넌트에 알림
    if (onPresetSelect) {
      onPresetSelect(preset.name, {
        strategy: preset.strategy,
        params: preset.params
      })
    }
  }

  // 프리셋 저장
  const handleSavePreset = async () => {
    if (!presetName.trim()) {
      setError('프리셋 이름을 입력하세요')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const preset = {
        name: presetName,
        strategy: currentStrategy,
        params: currentParams,
        description: presetDescription
      }

      await savePreset(preset)

      // 프리셋 목록 새로고침
      await loadPresets()

      // 폼 초기화
      setPresetName('')
      setPresetDescription('')
      setActiveTab('list')
    } catch (err) {
      setError(err.message || '프리셋 저장에 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  // 프리셋 삭제
  const handleDeletePreset = async (name) => {
    if (!window.confirm(`"${name}" 프리셋을 삭제하시겠습니까?`)) {
      return
    }

    setLoading(true)
    setError(null)
    try {
      await deletePreset(name)
      // 프리셋 목록 새로고침
      await loadPresets()
    } catch (err) {
      setError(err.message || '프리셋 삭제에 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content preset-modal" onClick={(e) => e.stopPropagation()}>
        {/* 헤더 */}
        <div className="modal-header">
          <h2>전략 프리셋 관리</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {/* 탭 */}
        <div className="preset-tabs">
          <button
            className={`tab-btn ${activeTab === 'list' ? 'active' : ''}`}
            onClick={() => setActiveTab('list')}
          >
            📋 프리셋 목록
          </button>
          <button
            className={`tab-btn ${activeTab === 'save' ? 'active' : ''}`}
            onClick={() => setActiveTab('save')}
          >
            💾 현재 설정 저장
          </button>
        </div>

        {/* 에러 메시지 */}
        {error && (
          <div className="error-message">
            <strong>오류:</strong> {error}
          </div>
        )}

        {/* 탭 컨텐츠 */}
        <div className="modal-body">
          {activeTab === 'list' ? (
            <div className="preset-list-tab">
              {loading && <p className="loading">프리셋을 로드 중입니다...</p>}
              {!loading && presets.length === 0 && (
                <p className="no-data">저장된 프리셋이 없습니다.</p>
              )}
              {!loading && presets.length > 0 && (
                <div className="preset-list">
                  {presets.map((preset) => (
                    <div
                      key={preset.name}
                      className={`preset-item ${
                        selectedPreset?.name === preset.name ? 'selected' : ''
                      }`}
                    >
                      <div className="preset-info">
                        <div className="preset-name">{preset.name}</div>
                        <div className="preset-strategy">{preset.strategy}</div>
                        {preset.description && (
                          <div className="preset-description">
                            {preset.description}
                          </div>
                        )}
                        <div className="preset-meta">
                          생성: {new Date(preset.created_at).toLocaleDateString()}
                        </div>
                      </div>
                      <div className="preset-actions">
                        <button
                          className="action-btn apply-btn"
                          onClick={() => handleSelectPreset(preset)}
                        >
                          ✓ 적용
                        </button>
                        <button
                          className="action-btn delete-btn"
                          onClick={() => handleDeletePreset(preset.name)}
                          disabled={loading}
                        >
                          🗑️ 삭제
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="preset-save-tab">
              <div className="form-group">
                <label htmlFor="preset-name">프리셋 이름 *</label>
                <input
                  id="preset-name"
                  type="text"
                  value={presetName}
                  onChange={(e) => setPresetName(e.target.value)}
                  placeholder="예: 보수적 전략"
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label htmlFor="preset-description">설명 (선택사항)</label>
                <textarea
                  id="preset-description"
                  value={presetDescription}
                  onChange={(e) => setPresetDescription(e.target.value)}
                  placeholder="프리셋에 대한 설명을 입력하세요"
                  disabled={loading}
                  rows={3}
                />
              </div>

              <div className="preset-preview">
                <h4>저장할 설정</h4>
                <div className="preview-item">
                  <span className="label">전략:</span>
                  <span className="value">{currentStrategy}</span>
                </div>
                <div className="preview-params">
                  <span className="label">파라미터:</span>
                  <div className="params-list">
                    {Object.entries(currentParams).map(([key, value]) => (
                      <div key={key} className="param-item">
                        <span className="param-name">{key}:</span>
                        <span className="param-value">
                          {typeof value === 'number' ? value.toFixed(4) : String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 푸터 */}
        <div className="modal-footer">
          {activeTab === 'save' && (
            <button
              className="primary-btn"
              onClick={handleSavePreset}
              disabled={loading || !presetName.trim()}
            >
              {loading ? '저장 중...' : '프리셋 저장'}
            </button>
          )}
          <button className="secondary-btn" onClick={onClose} disabled={loading}>
            닫기
          </button>
        </div>
      </div>

      {/* 모달 스타일 */}
      <style jsx>{`
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background-color: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .modal-content.preset-modal {
          background: white;
          border-radius: 8px;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
          width: 90%;
          max-width: 600px;
          max-height: 80vh;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px;
          border-bottom: 1px solid #e0e0e0;
        }

        .modal-header h2 {
          margin: 0;
          font-size: 1.5rem;
        }

        .modal-close {
          background: none;
          border: none;
          font-size: 2rem;
          cursor: pointer;
          color: #666;
          padding: 0;
          width: 30px;
          height: 30px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .modal-close:hover {
          color: #000;
        }

        .preset-tabs {
          display: flex;
          border-bottom: 1px solid #e0e0e0;
          background: #f5f5f5;
        }

        .tab-btn {
          flex: 1;
          padding: 12px 20px;
          border: none;
          background: none;
          cursor: pointer;
          font-size: 0.95rem;
          border-bottom: 3px solid transparent;
          color: #666;
          transition: all 0.3s;
        }

        .tab-btn.active {
          color: #2c3e50;
          border-bottom-color: #3498db;
          background: white;
        }

        .modal-body {
          flex: 1;
          overflow-y: auto;
          padding: 20px;
        }

        .error-message {
          background: #fee;
          color: #c33;
          padding: 12px;
          border-radius: 4px;
          margin-bottom: 20px;
        }

        .loading {
          text-align: center;
          color: #999;
          padding: 40px 20px;
        }

        .no-data {
          text-align: center;
          color: #999;
          padding: 40px 20px;
        }

        .preset-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .preset-item {
          border: 1px solid #e0e0e0;
          border-radius: 6px;
          padding: 12px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          transition: all 0.3s;
        }

        .preset-item:hover {
          background: #f9f9f9;
          border-color: #ccc;
        }

        .preset-item.selected {
          background: #eff8ff;
          border-color: #3498db;
        }

        .preset-info {
          flex: 1;
          min-width: 0;
        }

        .preset-name {
          font-weight: 600;
          margin-bottom: 4px;
        }

        .preset-strategy {
          font-size: 0.85rem;
          color: #666;
          margin-bottom: 4px;
        }

        .preset-description {
          font-size: 0.85rem;
          color: #999;
          margin-bottom: 4px;
        }

        .preset-meta {
          font-size: 0.75rem;
          color: #aaa;
        }

        .preset-actions {
          display: flex;
          gap: 8px;
          margin-left: 12px;
        }

        .action-btn {
          padding: 6px 12px;
          border: 1px solid #ddd;
          border-radius: 4px;
          background: white;
          cursor: pointer;
          font-size: 0.85rem;
          transition: all 0.3s;
          white-space: nowrap;
        }

        .apply-btn:hover {
          background: #3498db;
          color: white;
          border-color: #3498db;
        }

        .delete-btn:hover {
          background: #e74c3c;
          color: white;
          border-color: #e74c3c;
        }

        .delete-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .preset-save-tab {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .form-group label {
          font-weight: 500;
          font-size: 0.95rem;
        }

        .form-group input,
        .form-group textarea {
          padding: 10px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 0.95rem;
          font-family: inherit;
        }

        .form-group input:disabled,
        .form-group textarea:disabled {
          background: #f5f5f5;
          cursor: not-allowed;
        }

        .preset-preview {
          background: #f5f5f5;
          padding: 12px;
          border-radius: 4px;
        }

        .preset-preview h4 {
          margin: 0 0 12px 0;
          font-size: 0.95rem;
        }

        .preview-item {
          display: flex;
          justify-content: space-between;
          margin-bottom: 8px;
          font-size: 0.9rem;
        }

        .preview-item .label {
          font-weight: 500;
          color: #666;
        }

        .preview-item .value {
          color: #333;
        }

        .preview-params {
          margin-top: 12px;
        }

        .preview-params .label {
          display: block;
          font-weight: 500;
          color: #666;
          margin-bottom: 8px;
          font-size: 0.9rem;
        }

        .params-list {
          display: flex;
          flex-direction: column;
          gap: 4px;
          padding-left: 12px;
        }

        .param-item {
          display: flex;
          justify-content: space-between;
          font-size: 0.85rem;
        }

        .param-name {
          color: #666;
        }

        .param-value {
          color: #333;
          font-weight: 500;
        }

        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          padding: 20px;
          border-top: 1px solid #e0e0e0;
          background: #f5f5f5;
        }

        .primary-btn,
        .secondary-btn {
          padding: 10px 20px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 0.95rem;
          font-weight: 500;
          transition: all 0.3s;
        }

        .primary-btn {
          background: #3498db;
          color: white;
        }

        .primary-btn:hover:not(:disabled) {
          background: #2980b9;
        }

        .primary-btn:disabled {
          background: #bdc3c7;
          cursor: not-allowed;
        }

        .secondary-btn {
          background: white;
          color: #333;
          border: 1px solid #ddd;
        }

        .secondary-btn:hover:not(:disabled) {
          background: #f9f9f9;
          border-color: #999;
        }

        .secondary-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  )
}
