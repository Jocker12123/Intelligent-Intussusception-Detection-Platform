import api from './index'

export function getResults(params) {
  return api.get('/results', { params })
}

export function getResultsStats() {
  return api.get('/results/stats')
}

export function exportResults(params) {
  return api.get('/results/export', { params, responseType: 'blob' })
}

export function getResult(id) {
  return api.get(`/results/${id}`)
}

// 算法回传的带病灶框标注图（由 ImageViewer 带鉴权拉取，故返回站内路径）
export function getResultImageUrl(id) {
  return `/api/results/${id}/image`
}
