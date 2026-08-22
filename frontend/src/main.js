import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus, { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as Icons from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './styles/theme.css'
import { initTheme } from './utils/theme'

initTheme()

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
for (const [k, v] of Object.entries(Icons)) app.component(k, v)

// 全局错误边界：捕获未处理的渲染/钩子错误，避免页面静默挂掉
app.config.errorHandler = (err, instance, info) => {
  // eslint-disable-next-line no-console
  console.error('Unhandled app error:', err, info)
  ElMessage.error('页面出现异常，请刷新或稍后重试')
}

app.mount('#app')
