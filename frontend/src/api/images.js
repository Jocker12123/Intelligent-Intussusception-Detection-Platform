import api from './index'

export function uploadImage(patientId, file) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('patient_id', patientId)
  return api.post('/images/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getImageUrl(imageId) {
  return `/api/images/${imageId}`
}

export function getImageInfo(imageId) {
  return api.get(`/images/${imageId}/info`)
}

export function deleteImage(imageId) {
  return api.delete(`/images/${imageId}`)
}

export function runDetection(imageId) {
  return api.post(`/images/${imageId}/detect`)
}

// 异步检测任务：提交后返回 task_id，需轮询 progress
export function createDetectionTask(imageId) {
  return api.post(`/detection/tasks/${imageId}`)
}

export function getDetectionTask(taskId) {
  return api.get(`/detection/tasks/${taskId}`)
}

