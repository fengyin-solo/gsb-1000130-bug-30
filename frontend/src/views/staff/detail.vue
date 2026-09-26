<template>
  <section class="page" data-module="staff-detail">
    <header class="page-head">
      <div>
        <h2>检测员明细</h2>
        <p class="page-desc">与列表页定位同一条检测人员记录，核对技术职称、资质证书与在岗状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="load">刷新明细</button>
        <RouterLink class="btn ghost" to="/staff">返回列表</RouterLink>
      </div>
    </header>

    <p v-if="notFound" class="empty-state">{{ notFoundHint }}</p>

    <template v-else>
      <table v-if="entry" class="data-table">
        <tbody>
          <tr v-for="field in detailFields" :key="field">
            <th>{{ field }}</th>
            <td>{{ entry[field] ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty-state">明细加载中…</p>

      <div v-if="entry" class="page-actions">
        <button
          v-for="action in actions"
          :key="action"
          class="btn"
          type="button"
          @click="runAction(action)"
        >
          {{ action }}
        </button>
      </div>
    </template>

    <footer class="page-foot">
      <span v-if="entry">当前定位：{{ entry['员工编号'] }} · {{ entry['姓名'] }}</span>
      <span v-else>未定位到检测员记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { payloadMessage, readPayload, request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/staff'
const detailFields = ["员工编号", "姓名", "技术职称", "资质证书", "授权项目", "在岗状态", "考核日期", "考核结果"]
const actions = ["安排培训", "确认离岗", "恢复在岗"]

const route = useRoute()
const entry = ref<Row | null>(null)
const notFound = ref(false)
const notFoundHint = ref('')
const errorMessage = ref('')

const entryId = computed(() => Number(route.params.id))

// 与列表页同一条根因修复：连续切换记录或重复刷新时，只有最后一次响应能落地
let detailSeq = 0

async function load() {
  const seq = ++detailSeq
  errorMessage.value = ''
  notFound.value = false
  if (!Number.isInteger(entryId.value) || entryId.value <= 0) {
    entry.value = null
    notFound.value = true
    notFoundHint.value = '明细地址中的检测员编号无效，请从列表页重新进入'
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${entryId.value}`)
    const payload = await readPayload(response)
    if (response.status === 404) {
      if (seq !== detailSeq) {
        return
      }
      entry.value = null
      notFound.value = true
      notFoundHint.value = payloadMessage(payload) ?? `检测员 ${entryId.value} 不存在或已归档，可返回列表重新定位`
      return
    }
    if (!response.ok) {
      throw new Error(payloadMessage(payload) ?? '检测员明细读取失败')
    }
    if (seq !== detailSeq) {
      return
    }
    entry.value = payload as Row
  } catch (error) {
    if (seq !== detailSeq) {
      return
    }
    // 接口异常时保留已加载的明细，只提示错误，不让明细丢失
    errorMessage.value = error instanceof Error ? error.message : '检测员明细读取失败'
  }
}

async function runAction(action: string) {
  if (!entry.value) {
    return
  }
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId.value}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await readPayload(response)
    if (!response.ok || payload?.ok !== true) {
      throw new Error(payloadMessage(payload) ?? '检测人员动作未生效，请稍后重试')
    }
    // 动作生效后重新拉取同一条记录，保证详情与列表读到同一状态
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测人员操作失败'
  }
}

watch(
  () => route.params.id,
  () => {
    entry.value = null
    void load()
  },
  { immediate: true },
)
</script>
