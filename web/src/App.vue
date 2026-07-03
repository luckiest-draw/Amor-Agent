<template>
  <div class="app-shell">
    <!-- 左侧: 对话历史 -->
    <ConversationList
      :conversations="conversations"
      :current-id="currentConvId"
      @select="onSelectConv"
      @new="onNewConv"
      @delete="onDeleteConv"
    />

    <!-- 中间: 对话区域 -->
    <ChatView
      :messages="messages"
      :loading="loading"
      @send="onSend"
      @new-conv="onNewConv"
    />

    <!-- 右侧: Agent 面板 -->
    <AgentPanel
      :current-model="currentModel"
      :models="models"
      :skills="skills"
      :token-stats="tokenStats"
      @update:model="onModelChange"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import ConversationList from './components/ConversationList.vue'
import ChatView from './components/ChatView.vue'
import AgentPanel from './components/AgentPanel.vue'

const api = axios.create({ baseURL: '/api' })

const currentModel = ref('deepseek/deepseek-chat')
const models = ref([])
const skills = ref([])
const conversations = ref([])
const currentConvId = ref(null)
const messages = ref([])
const loading = ref(false)
const tokenStats = reactive({ total: 0, mode: '—' })

// ── API ────────────────────────────────────
async function loadModels() {
  const { data } = await api.get('/models')
  models.value = data.models
  currentModel.value = data.current
}

async function loadSkills() {
  const { data } = await api.get('/skills')
  skills.value = data.skills || []
}

async function loadConversations() {
  const { data } = await api.get('/conversations')
  conversations.value = data.conversations || []
}

// ── Conversation ──────────────────────────
function onNewConv() {
  currentConvId.value = null
  messages.value = []
  tokenStats.total = 0
  tokenStats.mode = '—'
}

async function onSelectConv(id) {
  currentConvId.value = id
  const { data } = await api.get(`/conversations/${id}/messages`)
  messages.value = (data.messages || []).map(m => ({
    role: m.role, content: m.content, time: Date.now()
  }))
}

async function onDeleteConv(id) {
  conversations.value = conversations.value.filter(c => c.id !== id)
  if (currentConvId.value === id) onNewConv()
}

// ── Send ──────────────────────────────────
async function onSend(text) {
  messages.value.push({ role: 'user', content: text, time: Date.now() })
  const thinkMsg = { role: 'agent', content: '', thinking: true, time: Date.now() }
  messages.value.push(thinkMsg)
  loading.value = true

  try {
    const { data } = await api.post('/chat', {
      message: text,
      model: currentModel.value,
      conversation_id: currentConvId.value,
    })

    if (!currentConvId.value) {
      currentConvId.value = data.conversation_id
      await loadConversations()
    }

    thinkMsg.content = data.content
    thinkMsg.thinking = false
    thinkMsg.mode = data.mode

    tokenStats.total += data.tokens || 0
    tokenStats.mode = data.mode === 'multi' ? '多 Agent 协作' : '—'
  } catch (e) {
    thinkMsg.content = `错误: ${e.response?.data?.detail || e.message}`
    thinkMsg.thinking = false
    thinkMsg.error = true
  } finally {
    loading.value = false
  }
}

function onModelChange(model) {
  currentModel.value = model
  api.put('/models/active', null, { params: { model_id: model } })
}

onMounted(() => {
  loadModels()
  loadSkills()
  loadConversations()
})
</script>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}
</style>
