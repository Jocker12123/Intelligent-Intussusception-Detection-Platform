import api from './index'

export function getAuditLogs(params) {
  return api.get('/audit', { params })
}

export function exportAuditLogs(params) {
  return api.get('/audit/export', { params, responseType: 'blob' })
}
