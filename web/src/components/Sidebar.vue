<template>
  <aside class="sidebar">
    <!-- Logo -->
    <div class="logo">
      <span class="logo-dot" />
      <span class="logo-text">Amor</span>
      <el-tag size="small" type="success" effect="light" round>Online</el-tag>
    </div>

    <!-- Model Selector -->
    <div class="section">
      <h4>模型</h4>
      <el-select
        :model-value="currentModel"
        @update:model-value="$emit('update:model', $event)"
        size="large"
        class="w-full"
        popper-class="model-popper"
      >
        <el-option
          v-for="m in models"
          :key="m.id"
          :label="m.name"
          :value="m.id"
        >
          <span style="float:left">{{ m.name }}</span>
          <span style="float:right;color:var(--el-text-color-secondary);font-size:12px">{{ m.provider }}</span>
        </el-option>
      </el-select>
    </div>

    <!-- Agent Roles -->
    <div class="section">
      <h4>
        <el-icon :size="12"><UserFilled /></el-icon>
        Agent 角色
      </h4>
      <div class="tag-row">
        <el-tag
          v-for="a in agents"
          :key="a.id"
          size="default"
          :type="roleType(a.id)"
          effect="plain"
          round
        >
          {{ a.id }}
        </el-tag>
        <span v-if="!agents.length" class="empty">加载中...</span>
      </div>
    </div>

    <!-- Skills -->
    <div class="section">
      <h4>
        <el-icon :size="12"><MagicStick /></el-icon>
        Skill
        <el-button link type="primary" size="small" @click="$emit('reload-skills')" class="reload-btn">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </h4>
      <div class="tag-row">
        <el-tag
          v-for="s in skills"
          :key="s.name"
          size="default"
          effect="plain"
          round
        >
          {{ s.name }}
        </el-tag>
        <span v-if="!skills.length" class="empty">无 Skill 文件</span>
      </div>
    </div>

    <!-- Token Stats -->
    <div class="token-card">
      <div class="stat">
        <span class="stat-label"><el-icon :size="14"><Coin /></el-icon> Token</span>
        <span class="stat-value">{{ tokenStats.total.toLocaleString() }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">模式</span>
        <span class="stat-value">{{ tokenStats.mode }}</span>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { Coin, MagicStick, UserFilled, Refresh } from '@element-plus/icons-vue'

defineProps({
  currentModel: String,
  models: Array,
  skills: Array,
  agents: Array,
  tokenStats: Object,
})

function roleType(id) {
  const map = { researcher: 'primary', executor: 'success', reviewer: 'warning', designer: 'danger' }
  return map[id] || 'info'
}
</script>

<style scoped>
.sidebar {
  width: 272px;
  background: #fff;
  border-right: 1px solid var(--el-border-color-light);
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 22px;
  flex-shrink: 0;
  overflow-y: auto;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 8px;
}
.logo-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: var(--amor-success);
  animation: pulse-dot 2s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: .4; transform: scale(1.5); }
}
.logo-text {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -.3px;
  color: var(--amor-accent);
  flex: 1;
}

.section { display: flex; flex-direction: column; gap: 8px; }
.section h4 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .6px;
  color: var(--el-text-color-secondary);
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 5px;
}
.reload-btn { margin-left: auto; padding: 0; }

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.empty { font-size: 12px; color: var(--el-text-color-placeholder); }

.token-card {
  margin-top: auto;
  background: var(--el-color-primary-light-9);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid var(--el-color-primary-light-7);
}
.stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  padding: 2px 0;
}
.stat-label {
  color: var(--el-text-color-secondary);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.stat-value {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.stat-value.cost { color: var(--amor-brand); font-size: 15px; }

.w-full { width: 100%; }
</style>
