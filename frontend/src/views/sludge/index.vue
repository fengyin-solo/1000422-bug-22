<template>
  <section class="page" data-module="sludge">
    <header class="page-head">
      <div>
        <h2>污泥处置管理</h2>
        <p class="page-desc">维护污泥处置单，围绕处置单号、污泥来源、含水率、污泥量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记污泥处置单</button>
        <button class="btn" type="button" @click="exportRows">导出污泥处置清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in inPageStats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <section class="panel">
      <h3>承运单位统计</h3>
      <table class="data-table compact">
        <thead>
          <tr><th>承运单位</th><th>单据数</th><th>待处理</th><th>异常量</th><th>已退回</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in carrierStats" :key="item.carrier">
            <td>{{ item.carrier }}</td>
            <td>{{ item.total }}</td>
            <td>{{ item.pending }}</td>
            <td>{{ item.abnormal }}</td>
            <td>{{ item.returned }}</td>
          </tr>
          <tr v-if="!carrierStats.length">
            <td colspan="5" class="empty-state">暂无承运单位统计数据</td>
          </tr>
        </tbody>
      </table>
    </section>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
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
              v-for="action in availableActions(row)"
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
          <td :colspan="columns.length + 1" class="empty-state">暂无污泥处置数据，可先登记污泥处置单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条污泥处置记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>
type CarrierStat = { carrier: string; total: number; pending: number; abnormal: number; returned: number }
type SludgeSummary = { total: number; pending: number; abnormal: number; returned: number }

const ENDPOINT = '/api/sludge'
const columns = ["处置单号", "污泥来源", "含水率", "污泥量", "处置方式", "外运时间", "承运单位", "处置状态"]
const actions = ["安排外运", "确认接收", "退回污泥"]
const actionsByStatus: Record<string, string[]> = {
  "待外运": ["安排外运"],
  "运输中": ["确认接收", "退回污泥"],
  "已接收": ["退回污泥"],
  "已退回": [],
}

const rows = ref<Row[]>([])
const carrierStats = ref<CarrierStat[]>([])
const summary = ref<SludgeSummary>({ total: 0, pending: 0, abnormal: 0, returned: 0 })
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const inPageStats = computed(() => [
  { label: '全部污泥处置单', value: summary.value.total },
  { label: '待处理', value: summary.value.pending },
  { label: '异常量', value: summary.value.abnormal },
])

function availableActions(row: Row) {
  return actionsByStatus[String(row.status ?? '')] ?? []
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '污泥处置单登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('污泥处置动作未生效，请稍后重试')
    }
    const payload = await response.json()
    if (!payload.ok) {
      throw new Error(payload.message || '污泥处置动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '污泥处置操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}?${query}`),
      request(`${ENDPOINT}/carrier-statistics`),
    ])
    if (!listResponse.ok) {
      throw new Error('污泥处置单列表读取失败')
    }
    if (!statsResponse.ok) {
      throw new Error('承运单位统计读取失败')
    }
    const payload = await listResponse.json()
    const statsPayload = await statsResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    const remoteSummary = statsPayload.summary ?? {}
    summary.value = {
      total: Number(remoteSummary.total ?? 0),
      pending: Number(remoteSummary.pending ?? 0),
      abnormal: Number(remoteSummary.abnormal ?? 0),
      returned: Number(remoteSummary.returned ?? 0),
    }
    carrierStats.value = (statsPayload.items ?? []).map((item: Record<string, unknown>) => ({
      carrier: String(item['承运单位'] ?? '未填写承运单位'),
      total: Number(item.total ?? 0),
      pending: Number(item.pending ?? 0),
      abnormal: Number(item.abnormal ?? 0),
      returned: Number(item.returned ?? 0),
    }))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '污泥处置列表读取失败'
  }
}

onMounted(reload)
</script>
