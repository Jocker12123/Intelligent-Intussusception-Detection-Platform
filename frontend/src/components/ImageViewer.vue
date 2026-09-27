<template>
  <div class="image-viewer">
    <div v-if="isDicom" class="viewer-dicom">
      <div class="dicom-icon-box">
        <el-icon class="dicom-icon"><Document /></el-icon>
      </div>
      <p class="dicom-title">DICOM 影像</p>
      <p class="dicom-text">该格式由算法侧解析用于诊断，浏览器暂不支持在线预览。</p>
    </div>
    <div v-else-if="!hasError && resolvedSrc" class="viewer-stage">
      <img
        :src="resolvedSrc"
        :alt="alt"
        class="viewer-image"
        @load="onImageLoad"
        @error="hasError = true"
      />
      <!-- 算法只回传了病灶框坐标（没回传标注图）时，在原图上叠加显示 -->
      <div v-if="overlayStyle" class="viewer-box" :style="overlayStyle">
        <span class="viewer-box-tag">AI 标注</span>
      </div>
    </div>
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
import { boxToPercentStyle } from '../utils/imageFit'

const props = defineProps({
  src: { type: String, required: true },
  alt: { type: String, default: '' },
  mediaType: { type: String, default: '' },
  // 病灶框 [x1,y1,x2,y2]（原图像素坐标）；不传则不叠加
  overlayBox: { type: Array, default: null },
})

const hasError = ref(false)
const resolvedSrc = ref('')
const naturalSize = ref({ width: 0, height: 0 })
let objectUrl = null

const isDicom = computed(() => props.mediaType === 'application/dicom')

const overlayStyle = computed(() =>
  boxToPercentStyle(props.overlayBox, naturalSize.value.width, naturalSize.value.height)
)

function onImageLoad(event) {
  const img = event.target
  naturalSize.value = { width: img.naturalWidth, height: img.naturalHeight }
}

const loadImage = async (url) => {
  hasError.value = false
  resolvedSrc.value = ''
  naturalSize.value = { width: 0, height: 0 }

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

/* 图片 + 病灶框叠加层：stage 收缩包裹图片，叠加层用百分比定位 */
.viewer-stage {
  position: relative;
  display: inline-flex;
  max-width: 100%;
}

.viewer-image {
  max-width: 100%;
  max-height: 560px;
  width: auto;
  height: auto;
  display: block;
}

.viewer-box {
  position: absolute;
  box-sizing: border-box;
  border: 2px solid var(--danger, #f56c6c);
  border-radius: 2px;
  pointer-events: none;
}

.viewer-box-tag {
  position: absolute;
  top: 0;
  left: 0;
  padding: 1px 6px;
  font-size: 11px;
  line-height: 16px;
  color: #fff;
  background: var(--danger, #f56c6c);
  border-radius: 0 0 4px 0;
  white-space: nowrap;
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
