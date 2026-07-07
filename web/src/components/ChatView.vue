<template>
  <div class="chat-view">
    <div v-if="!messages.length" class="empty-state">
      <div class="logo">✦</div>
      <h2>Amor Agent</h2>
      <p>输入任何任务，Agent 自动处理</p>
      <div class="upload-hint">
        <label class="upload-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          上传文档到知识库
          <input type="file" @change="uploadFile" multiple hidden />
        </label>
        <span v-if="knowledgeFiles.length" class="file-count">{{ knowledgeFiles.length }} 个文件已索引</span>
      </div>
    </div>

    <div v-else class="msg-list" ref="msgList">
      <template v-for="(m, i) in messages" :key="i">
        <div v-if="m.role === 'user'" class="msg-row user">
          <div class="bubble user">{{ m.content }}</div>
        </div>
        <div v-else-if="m.role === 'agent'" class="msg-row agent">
          <div class="bubble agent">
            <span v-if="m.thinking" class="dots"><i></i><i></i><i></i></span>
            <div v-else :class="{ content: true, error: m.error }">{{ m.content }}</div>
          </div>
          <div v-if="m.mode === 'multi' && !m.thinking" class="mode-tag">多 Agent</div>
        </div>
      </template>
    </div>

    <div class="input-bar">
      <div class="kb-row" v-if="messages.length">
        <label class="mini-upload">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/></svg>
          知识库
          <input type="file" @change="uploadFile" multiple hidden />
        </label>
        <span v-if="knowledgeFiles.length" class="kb-count">{{ knowledgeFiles.length }} 文件</span>
      </div>
      <div class="input-wrap">
        <input
          v-model="inputText"
          placeholder="输入任务..."
          @keydown.enter="onSend"
          :disabled="loading"
        />
        <button @click="onSend" :disabled="loading">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'

const props = defineProps({ messages: Array, loading: Boolean })
const emit = defineEmits(['send'])

const inputText = ref('')
const msgList = ref(null)
const knowledgeFiles = ref([])

onMounted(async () => {
  try {
    const r = await fetch('/api/knowledge/files').then(r => r.json())
    knowledgeFiles.value = r.files || []
  } catch {}
})

function onSend() {
  const text = inputText.value.trim()
  if (!text || props.loading) return
  emit('send', text)
  inputText.value = ''
}

async function uploadFile(e) {
  const files = e.target.files
  for (const f of files) {
    const form = new FormData()
    form.append('file', f)
    await fetch('/api/knowledge/upload', { method: 'POST', body: form })
  }
  const r = await fetch('/api/knowledge/files').then(r => r.json())
  knowledgeFiles.value = r.files || []
}

watch(() => props.messages?.length, () => {
  nextTick(() => { if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight })
})
</script>

<style scoped>
.chat-view { flex:1; display:flex; flex-direction:column; min-width:0; height:100vh; background:#fff; }
.empty-state { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; color:#9ca3af; }
.logo { font-size:40px; }
.empty-state h2 { font-size:22px; color:#111827; }

.upload-hint { display:flex; flex-direction:column; align-items:center; gap:6px; margin-top:8px; }
.upload-btn {
  display:inline-flex; align-items:center; gap:6px;
  padding:8px 18px; border-radius:20px; border:1px dashed #9ca3af;
  cursor:pointer; font-size:13px; color:#6b7280;
  transition: border-color .2s, color .2s;
}
.upload-btn:hover { border-color:#111827; color:#111827; }
.file-count { font-size:12px; color:#9ca3af; }

.msg-list { flex:1; overflow-y:auto; padding:24px 32px; }
.msg-row { margin-bottom:20px; max-width:80%; }
.msg-row.user { margin-left:auto; }
.msg-row.agent { margin-right:auto; }

.bubble { padding:12px 18px; border-radius:16px; line-height:1.65; font-size:15px; }
.bubble.user { background:#111827; color:#fff; border-radius:16px 16px 4px 16px; }
.bubble.agent { background:#f3f4f6; color:#111827; border-radius:16px 16px 16px 4px; }
.bubble.agent .content { white-space:pre-wrap; word-break:break-word; }
.bubble.agent .content.error { color:#ef4444; }
.bubble.agent .dots { display:flex; gap:4px; padding:6px 0; }
.bubble.agent .dots i { width:6px;height:6px; border-radius:50%; background:#9ca3af; animation:dot 1.4s ease-in-out infinite both; }
.bubble.agent .dots i:nth-child(2){animation-delay:.16s}
.bubble.agent .dots i:nth-child(3){animation-delay:.32s}
@keyframes dot{0%,80%,100%{opacity:.3}40%{opacity:1}}

.mode-tag { font-size:11px; color:#6366f1; margin-top:4px; margin-left:8px; }

.input-bar { padding:16px 32px 20px; }
.kb-row { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
.mini-upload {
  display:inline-flex; align-items:center; gap:4px; cursor:pointer;
  font-size:12px; color:#6b7280; padding:4px 10px; border-radius:12px;
  border:1px solid #e5e7eb; transition: border-color .2s;
}
.mini-upload:hover { border-color:#111827; }
.kb-count { font-size:12px; color:#9ca3af; }

.input-wrap { display:flex; align-items:center; background:#f3f4f6; border-radius:24px; padding:4px 4px 4px 18px; border:1px solid transparent; transition:border-color .2s; }
.input-wrap:focus-within { border-color:#111827; background:#fff; }
.input-wrap input { flex:1; border:none; background:transparent; font-size:15px; padding:10px 0; outline:none; color:#111827; }
.input-wrap input::placeholder { color:#9ca3af; }
.input-wrap button { width:38px;height:38px; border-radius:50%; border:none; background:#111827; color:#fff; cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; transition:background .15s; }
.input-wrap button:hover { background:#374151; }
.input-wrap button:disabled { background:#d1d5db; cursor:default; }
</style>
