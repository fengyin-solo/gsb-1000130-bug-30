<template>
  <section class="page" data-module="staff">
    <header class="page-head">
      <div>
        <h2>检测人员管理</h2>
        <p class="page-desc">维护检测员，围绕员工编号、姓名、技术职称、资质证书做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记检测员</button>
        <button class="btn" type="button" @click="exportRows">导出检测人员清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>在岗状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            {{ hasCriteria ? '没有符合条件的检测人员记录，可调整或重置条件' : '暂无检测人员数据，可先登记检测员' }}
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条检测人员记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/staff'
const columns = ["员工编号", "姓名", "技术职称", "资质证书", "授权项目", "在岗状态", "考核日期", "考核结果"]
const actions = ["安排培训", "确认离岗", "恢复在岗"]
const statuses = ["在岗", "培训中", "离岗", "停岗"]
const stats = [{"label": "在岗人员", "value": 0}, {"label": "培训中人员", "value": 0}, {"label": "离岗人员", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const statusFilter = ref('')
const filterFields = columns.slice(0, 3)

// 只认最后一次查询的响应：连续操作时慢一拍的旧响应不许覆盖新结果
let requestSeq = 0

const hasCriteria = computed(
  () => Boolean(statusFilter.value) || filterFields.some((field) => (filters.value[field] ?? '').trim()),
)

function buildQuery(): string {
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = (filters.value[field] ?? '').trim()
    if (value) {
      params.set(field, value)
    }
  }
  if (statusFilter.value) {
    params.set('status', statusFilter.value)
  }
  return params.toString()
}

async function readDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json()
    if (typeof payload?.detail === 'string') {
      return payload.detail
    }
  } catch {
    // 响应体不是 JSON 时退回默认说明
  }
  return fallback
}

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  const query = buildQuery()
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
}

function openCreate() {
  errorMessage.value = '检测员登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error(await readDetail(response, '检测人员动作未生效，请稍后重试'))
    }
    // 按当前筛选条件刷新，定位保持在原结果集，不回到开头
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测人员操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const seq = ++requestSeq
  const query = buildQuery()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error(await readDetail(response, '检测员列表读取失败'))
    }
    const payload = await response.json()
    if (seq !== requestSeq) {
      return
    }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    if (seq !== requestSeq) {
      return
    }
    // 读取失败时保留当前列表与条件，明细不丢，只提示原因
    errorMessage.value = error instanceof Error ? error.message : '检测人员列表读取失败'
  }
}

onMounted(reload)
</script>
