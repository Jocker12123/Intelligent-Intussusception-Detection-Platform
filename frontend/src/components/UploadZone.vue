<template>
  <div
    class="upload-zone"
    :class="{ 'is-dragover': isDragover, 'has-file': files.length }"
    @click="triggerInput"
    @dragover.prevent="onDragOver"
    @dragleave.prevent="onDragLeave"
    @drop.prevent="onDrop"
  >
    <input
      ref="fileInputRef"
      type="file"
      accept="image/jpeg,image/png,image/bmp,.dcm"
      multiple
      hidden
      @change="onFileChange"
    />

    <template v-if="!files.length">
      <div class="upload-illustration">
        <div class="upload-ring">
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
        </div>
        <div class="upload-dots" />
      </div>
      <p class="upload-text">拖拽超声影像到此处，或点击选择文件</p>
      <p class="upload-hint">支持 JPG / PNG / BMP / DICOM 格式，可一次选择多张，单文件不超过 20MB</p>
      <div class="upload-formats">
        <span class="format-tag">JPG</span>
        <span class="format-tag">PNG</span>
        <span class="format-tag">BMP</span>
        <span class="format-tag">DICOM</span>
      </div>
      <p class="upload-dicom-note">DICOM 文件由算法侧解析用于诊断，浏览器暂不支持在线预览。</p>
    </template>

    <template v-else>
      <div class="file-list">
        <div v-for="(f, idx) in files" :key="f.uid" class="file-item">
          <div class="file-thumb">
            <img v-if="f.previewUrl" :src="f.previewUrl" class="thumb-img" alt="" />
            <el-icon v-else class="thumb-icon"><Document /></el-icon>
          </div>
          <div class="file-meta">
            <div class="file-name">{{ f.name }}</div>
            <div class="file-size">{{ formatSize(f.size) }}</div>
          </div>
          <button class="file-remove" type="button" title="移除" @click.stop="removeFile(idx)">
            <el-icon><Close /></el-icon>
          </button>
        </div>
      </div>
      <div class="file-actions">
        <el-button size="small" @click.stop="clearFiles">
          <el-icon><Refresh /></el-icon>
          清空
        </el-button>
        <span class="file-count">已选 {{ files.length }} 张</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Refresh, Document, Close } from '@element-plus/icons-vue'

const emit = defineEmits(['file-selected'])

const isDragover = ref(false)
const files = ref([])
const fileInputRef = ref(null)

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/bmp', 'application/dicom']
const MAX_SIZE = 20 * 1024 * 1024
let uid = 0

function formatSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

function validateFile(file) {
  const ext = file.name.split('.').pop().toLowerCase()
  if (!ALLOWED_TYPES.includes(file.type) && ext !== 'dcm') {
    ElMessage.error(`不支持的文件类型：${file.name}`)
    return false
  }
  if (file.size > MAX_SIZE) {
    ElMessage.error(`文件超过 20MB 限制：${file.name}`)
    return false
  }
  return true
}

function addFiles(fileList) {
  const arr = Array.from(fileList || [])
  for (const file of arr) {
    if (!validateFile(file)) continue
    // 支持图片预览；DICOM 等无法直接用 img 显示的用占位图标
    const previewUrl = file.type === 'image/jpeg' || file.type === 'image/png' || file.type === 'image/bmp'
      ? URL.createObjectURL(file)
      : ''
    files.value.push({ uid: ++uid, file, name: file.name, size: file.size, previewUrl })
  }
  emit('file-selected', files.value.map((f) => f.file))
}

function removeFile(idx) {
  const f = files.value[idx]
  if (f && f.previewUrl) URL.revokeObjectURL(f.previewUrl)
  files.value.splice(idx, 1)
  emit('file-selected', files.value.map((x) => x.file))
}

function clearFiles() {
  for (const f of files.value) {
    if (f.previewUrl) URL.revokeObjectURL(f.previewUrl)
  }
  files.value = []
  if (fileInputRef.value) fileInputRef.value.value = ''
  emit('file-selected', [])
}

function triggerInput() {
  fileInputRef.value.click()
}

function onFileChange(e) {
  addFiles(e.target.files)
  e.target.value = ''
}

function onDragOver() {
  isDragover.value = true
}

function onDragLeave() {
  isDragover.value = false
}

function onDrop(e) {
  isDragover.value = false
  addFiles(e.dataTransfer.files)
}

onUnmounted(() => {
  for (const f of files.value) {
    if (f.previewUrl) URL.revokeObjectURL(f.previewUrl)
  }
})
</script>

<style scoped>
.upload-zone {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: 36px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  min-height: 240px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--bg-card);
  position: relative;
  overflow: hidden;
}
.upload-zone:hover {
  border-color: var(--primary);
  background: var(--bg-hover);
}
.upload-zone.is-dragover {
  border-color: var(--primary);
  background: var(--primary-glow);
  transform: scale(1.01);
}

.upload-illustration {
  position: relative;
  width: 80px;
  height: 80px;
  margin-bottom: 16px;
}
.upload-ring {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--primary-glow);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
}
.upload-icon {
  font-size: 32px;
  color: var(--primary);
}
.upload-dots {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 24px;
  height: 24px;
  background-image: radial-gradient(circle, var(--border-strong) 1.5px, transparent 1.5px);
  background-size: 8px 8px;
  opacity: 0.5;
}

.upload-text {
  margin: 0 0 6px;
  font-size: 15px;
  color: var(--text-primary);
  font-weight: 600;
}
.upload-hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--text-muted);
}
.upload-dicom-note {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--warning);
}
.upload-formats {
  display: flex;
  gap: 8px;
  justify-content: center;
}
.format-tag {
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  background: var(--bg-page);
  border: 1px solid var(--border-color);
}

/* 多文件列表 */
.file-list {
  width: 100%;
  max-width: 480px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  text-align: left;
}
.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--bg-hover);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
}
.file-thumb {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}
.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb-icon {
  font-size: 22px;
  color: var(--primary);
}
.file-meta {
  flex: 1;
  min-width: 0;
}
.file-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-size {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}
.file-remove {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--text-muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}
.file-remove:hover {
  background: var(--bg-tag-danger);
  color: var(--danger);
}
.file-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  max-width: 480px;
  margin-top: 12px;
}
.file-count {
  font-size: 13px;
  color: var(--text-muted);
}
</style>
