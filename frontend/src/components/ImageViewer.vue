<template>
  <div class="image-viewer">
    <div v-if="isDicom" class="viewer-dicom">
      <div class="dicom-icon-box">
        <el-icon class="dicom-icon"><Document /></el-icon>
      </div>
      <p class="dicom-title">DICOM 影像</p>
      <p class="dicom-text">该格式由算法侧解析用于诊断，浏览器暂不支持在线预览。</p>
    </div>
    <img
      v-else-if="!hasError && resolvedSrc"
      :src="resolvedSrc"
      :alt="alt"
      class="viewer-image"
      @error="hasError = true"
    />
    <div v-else-if="hasError" class="viewer-error">
      <el-icon class="error-icon"><PictureFilled /></el-icon>
      <p class="error-text">图片加载失败</p>
    </div>
    <div v-else class="viewer-loading">
      <el-icon class="loading-icon is-loading"><Loading /></el-icon>
      <p class="loading-text">加载中...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { PictureFilled, Loading, Document } from '@element-plus/icons-vue'
import api from '../api/index'

const props = defineProps({
  src: { type: String, required: true },
  alt: { type: String, default: '' },
  mediaType: { type: String, default: '' },
})

const hasError = ref(false)
const resolvedSrc = ref('')
let objectUrl = null

const isDicom = computed(() => props.mediaType === 'application/dicom')

const loadImage = async (url) => {
  hasError.value = false
  resolvedSrc.value = ''

  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = null
  }

  if (!url) return

  if (url.startsWith('/api/')) {
    try {
      const requestUrl = url.replace(/^\/api/, '')
      const response = await api.get(requestUrl, { responseType: 'blob' })
      objectUrl = URL.createObjectURL(response.data)
      resolvedSrc.value = objectUrl
    } catch (e) {
      hasError.value = true
    }
  } else {
    resolvedSrc.value = url
  }
}

watch(() => props.src, (newVal) => {
  loadImage(newVal)
}, { immediate: true })

onUnmounted(() => {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
  }
})
</script>

<style scoped>
.image-viewer {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 360px;
  background: var(--bg-detail-item);
  overflow: hidden;
  width: 100%;
  height: 100%;
}

.viewer-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  max-width: 100%;
  max-height: 560px;
  display: block;
}

.viewer-error, .viewer-loading, .viewer-dicom {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: var(--text-muted);
  padding: 60px 0;
}

.viewer-dicom {
  gap: 4px;
}
.dicom-icon-box {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}
.dicom-icon {
  font-size: 36px;
  color: var(--primary);
}
.dicom-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.dicom-text {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-muted);
  max-width: 240px;
  text-align: center;
  line-height: 1.6;
}

.error-icon, .loading-icon {
  font-size: 64px;
  margin-bottom: 12px;
}

.error-text, .loading-text {
  margin: 0;
  font-size: 15px;
  font-family: var(--font-sans);
}
</style>
