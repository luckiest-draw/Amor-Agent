<template>
  <aside :class="['agent-panel', { collapsed }]">
    <div class="panel-header">
      <span v-if="!collapsed">Agent</span>
      <el-button :icon="collapsed ? Expand : Fold" text size="small" @click="collapsed = !collapsed" />
    </div>

    <template v-if="!collapsed">
      <div class="section">
        <h4>模型</h4>
        <el-select :model-value="currentModel" @update:model-value="$emit('update:model', $event)" size="small" class="w-full">
          <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </div>

      <div class="section">
        <h4>Skill</h4>
        <div class="tags">
          <el-tag v-for="s in skills" :key="s.name" size="small" effect="plain" round>{{ s.name }}</el-tag>
          <span v-if="!skills.length" class="empty">无</span>
        </div>
      </div>

      <div class="token-card">
        <div class="stat">
          <span>Token</span>
          <span class="val">{{ tokenStats.total.toLocaleString() }}</span>
        </div>
        <div class="stat">
          <span>模式</span>
          <span class="val">{{ tokenStats.mode }}</span>
        </div>
      </div>
    </template>
  </aside>
</template>

<script setup>
import { ref } from 'vue'
import { Fold, Expand } from '@element-plus/icons-vue'

defineProps({ currentModel: String, models: Array, skills: Array, tokenStats: Object })
const collapsed = ref(false)
</script>

<style scoped>
.agent-panel {
  width: 240px;
  background: #f8f9fa;
  border-left: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width .2s;
  padding: 16px;
  gap: 18px;
}
.agent-panel.collapsed { width: 50px; padding: 12px 8px; }
.agent-panel.collapsed .section,
.agent-panel.collapsed .token-card { display: none; }

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 15px;
  font-weight: 600;
}

.section { display: flex; flex-direction: column; gap: 6px; }
.section h4 { font-size: 11px; text-transform: uppercase; color: #6b7280; letter-spacing: .5px; }

.tags { display: flex; flex-wrap: wrap; gap: 4px; }
.empty { font-size: 12px; color: #9ca3af; }
.w-full { width: 100%; }

.token-card {
  margin-top: auto;
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  border: 1px solid #e5e7eb;
}
.stat { display: flex; justify-content: space-between; font-size: 13px; padding: 2px 0; }
.stat .val { font-weight: 600; font-variant-numeric: tabular-nums; }
</style>
