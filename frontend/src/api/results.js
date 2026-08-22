import api from './index'

export function getResults(params) {
  return api.get('/results', { params })
}

export function getResultsStats() {
  return api.get('/results/stats')
}

export function getResult(id) {
  return api.get(`/results/${id}`)
}
