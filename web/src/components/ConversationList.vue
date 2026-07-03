<template>
  <aside :class="['conv-sidebar', { collapsed }]">
    <div class="conv-header">
      <el-button type="primary" :icon="Plus" size="small" round @click="$emit('new-conv')">新对话</el-button>
      <el-button :icon="collapsed ? Expand : Fold" text size="small" @click="collapsed = !collapsed" />
    </div>

    <div class="conv-list">
      <div
        v-for="c in conversations"
        :key="c.id"
        :class="['conv-item', { active: c.id === currentId }]"
        @click="$emit('select', c.id)"
      >
        <span class="conv-title">{{ c.title || '新对话' }}</span>
        <el-button :icon="Delete" text size="small" class="delete-btn"
          @click.stop="$emit('delete', c.id)" />
      </div>

      <div v-if="!conversations.length" class="empty">
        暂无对话记录
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref } from 'vue'
import { Plus, Fold, Expand, Delete } from '@element-plus/icons-vue'

defineProps({ conversations: Array, currentId: [Number, null] })
const emit = defineEmits(['select', 'new-conv', 'delete'])
const collapsed = ref(false)
</script>

<style scoped>
.conv-sidebar {
  width: 260px;
  background: #f8f9fa;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width .2s;
}
.conv-sidebar.collapsed { width: 50px; }
.conv-sidebar.collapsed .conv-title,
.conv-sidebar.collapsed .conv-item .delete-btn,
.conv-sidebar.collapsed .empty { display: none; }
.conv-sidebar.collapsed .conv-header { justify-content: center; }

.conv-header {
  padding: 12px;
  display: flex;
  gap: 6px;
  border-bottom: 1px solid #e5e7eb;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conv-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  transition: background .15s;
}
.conv-item:hover { background: #e5e7eb; }
.conv-item.active { background: #dbeafe; }

.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delete-btn { opacity: 0; transition: opacity .15s; }
.conv-item:hover .delete-btn { opacity: .5; }
.conv-item:hover .delete-btn:hover { opacity: 1; }

.empty {
  padding: 24px;
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
}
</style>
