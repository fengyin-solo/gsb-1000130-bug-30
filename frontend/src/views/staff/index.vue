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
        <select v-model="filters['在岗状态']">
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
            <button class="link" type="button" @click="openDetail(row)">查看明细</button>
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
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyHint }}</td>
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
import { useRouter } from 'vue-router'

import { payloadMessage, readPayload, request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/staff'
const columns = ["员工编号", "姓名", "技术职称", "资质证书", "授权项目", "在岗状态", "考核日期", "考核结果"]
const actions = ["安排培训", "确认离岗", "恢复在岗"]
const statuses = ["在岗", "培训中", "离岗", "停岗"]
const stats = [{"label": "在岗人员", "value": 0}, {"label": "培训中人员", "value": 0}, {"label": "离岗人员", "value": 0}]

// 筛选栏字段与接口查询参数的对应关系：页面展示中文字段，发请求时换成接口约定的英文名
const FILTER_PARAMS: Record<string, string> = { "员工编号": "number", "姓名": "name", "技术职称": "title", "在岗状态": "status" }
const filterFields = ["员工编号", "姓名", "技术职称"]

const router = useRouter()
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({ "员工编号": "", "姓名": "", "技术职称": "", "在岗状态": "" })

const hasActiveFilters = computed(() => Object.values(filters.value).some((value) => value.trim() !== ''))
const emptyHint = computed(() => (hasActiveFilters.value
  ? '没有符合条件的检测人员记录，可调整或重置检索条件'
  : '暂无检测人员数据，可先登记检测员'))

function buildQuery(): string {
  const params = new URLSearchParams()
  for (const [field, value] of Object.entries(filters.value)) {
    const trimmed = value.trim()
    if (trimmed) {
      params.set(FILTER_PARAMS[field] ?? field, trimmed)
    }
  }
  return params.toString()
}

function resetFilters() {
  for (const field of Object.keys(filters.value)) {
    filters.value[field] = ''
  }
  void reload()
}

function exportRows() {
  const query = buildQuery()
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
}

function openCreate() {
  errorMessage.value = '检测员登记入口尚未接入审批流'
}

function openDetail(row: Row) {
  void router.push({ name: 'staff-detail', params: { id: String(row.id) } })
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await readPayload(response)
    if (!response.ok || payload?.ok !== true) {
      throw new Error(payloadMessage(payload) ?? '检测人员动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测人员操作失败'
  }
}

// 连续查询或操作时请求会并发，用序号保证只有最后一次响应落地，旧结果不混入列表
let listSeq = 0

async function reload() {
  const seq = ++listSeq
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    const payload = await readPayload(response)
    if (!response.ok) {
      throw new Error(payloadMessage(payload) ?? '检测员列表读取失败')
    }
    if (seq !== listSeq) {
      return
    }
    rows.value = (payload?.items as Row[] | undefined) ?? []
    total.value = typeof payload?.total === 'number' ? payload.total : rows.value.length
  } catch (error) {
    if (seq !== listSeq) {
      return
    }
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof Error ? error.message : '检测人员列表读取失败'
  }
}

onMounted(reload)
</script>
