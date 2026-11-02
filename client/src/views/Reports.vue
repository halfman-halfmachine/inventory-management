<template>
  <div class="reports">
    <div class="page-header">
      <h2>{{ t('reports.title') }}</h2>
      <p>{{ t('reports.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="monthlyData.length === 0" class="card empty-state">{{ t('reports.noData') }}</div>
    <div v-else>
      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('reports.totalRevenueYTD') }}</div>
          <div class="stat-value">{{ formatMoney(summary.totalRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.avgMonthlyRevenue') }}</div>
          <div class="stat-value">{{ formatMoney(summary.avgMonthlyRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.totalOrdersYTD') }}</div>
          <div class="stat-value">{{ summary.totalOrders.toLocaleString() }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('reports.bestQuarter') }}</div>
          <div class="stat-value">{{ summary.bestQuarter || '-' }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.quarterlyPerformance') }}</h3>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('reports.table.quarter') }}</th>
                <th class="num">{{ t('reports.table.totalOrders') }}</th>
                <th class="num">{{ t('reports.table.totalRevenue') }}</th>
                <th class="num">{{ t('reports.table.avgOrderValue') }}</th>
                <th class="num">{{ t('reports.table.fulfillmentRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in quarterlyData" :key="q.quarter">
                <td><strong>{{ q.quarter }}</strong></td>
                <td class="num">{{ q.total_orders.toLocaleString() }}</td>
                <td class="num">{{ formatMoney(q.total_revenue) }}</td>
                <td class="num">{{ formatMoney(q.avg_order_value) }}</td>
                <td class="num">
                  <span :class="['badge', getFulfillmentClass(q.fulfillment_rate)]">
                    {{ q.fulfillment_rate }}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthlyRevenueTrend') }}</h3>
        </div>
        <div class="chart-container">
          <div class="bar-chart">
            <div v-for="row in monthRows" :key="row.month" class="bar-wrapper">
              <div class="bar-container">
                <div
                  class="bar"
                  :style="{ height: row.barHeight + 'px' }"
                  :title="`${row.label}: ${formatMoney(row.revenue)}`"
                ></div>
              </div>
              <div class="bar-label">{{ row.label }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthOverMonth') }}</h3>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('reports.table.month') }}</th>
                <th class="num">{{ t('reports.table.orders') }}</th>
                <th class="num">{{ t('reports.table.revenue') }}</th>
                <th class="num">{{ t('reports.table.change') }}</th>
                <th class="num">{{ t('reports.table.growthRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in monthRows" :key="row.month">
                <td><strong>{{ row.label }}</strong></td>
                <td class="num">{{ row.order_count.toLocaleString() }}</td>
                <td class="num">{{ formatMoney(row.revenue) }}</td>
                <td class="num">
                  <span v-if="row.change !== null" :class="getChangeClass(row.change)">
                    {{ formatChange(row.change) }}
                  </span>
                  <span v-else>-</span>
                </td>
                <td class="num">
                  <span v-if="row.change !== null" :class="getChangeClass(row.change)">
                    {{ formatGrowth(row.growthRate) }}
                  </span>
                  <span v-else>-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrencyWithDecimals } from '../utils/currency'

const MAX_BAR_HEIGHT = 200

export default {
  name: 'Reports',
  setup() {
    const { t, currentLocale, currentCurrency } = useI18n()
    const {
      selectedPeriod,
      selectedLocation,
      selectedCategory,
      selectedStatus,
      getCurrentFilters
    } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const quarterlyData = ref([])
    const monthlyData = ref([])

    // Only the newest request may update the page, so quickly changing
    // filters can't leave an older, slower response on screen
    let latestRequest = 0
    const loadData = async () => {
      const requestId = ++latestRequest
      try {
        loading.value = true
        error.value = null
        const filters = getCurrentFilters()
        const [quarterly, monthly] = await Promise.all([
          api.getQuarterlyReport(filters),
          api.getMonthlyTrends(filters)
        ])
        if (requestId !== latestRequest) return
        quarterlyData.value = quarterly
        monthlyData.value = monthly
      } catch (err) {
        if (requestId !== latestRequest) return
        console.error('Failed to load reports:', err)
        error.value = `${t('reports.loadFailed')}: ${err.message}`
      } finally {
        if (requestId === latestRequest) loading.value = false
      }
    }

    const summary = computed(() => {
      const totalRevenue = monthlyData.value.reduce((sum, m) => sum + m.revenue, 0)
      const totalOrders = monthlyData.value.reduce((sum, m) => sum + m.order_count, 0)
      const best = quarterlyData.value.reduce(
        (top, q) => (!top || q.total_revenue > top.total_revenue ? q : top),
        null
      )
      return {
        totalRevenue,
        totalOrders,
        avgMonthlyRevenue: monthlyData.value.length ? totalRevenue / monthlyData.value.length : 0,
        bestQuarter: best ? best.quarter : ''
      }
    })

    // Format "YYYY-MM" for the current language; fall back to the raw value
    // if the string isn't a valid month
    const formatMonth = (monthStr) => {
      const [year, month] = (monthStr || '').split('-').map(Number)
      const date = new Date(year, month - 1, 1)
      if (!year || !month || isNaN(date.getTime())) return monthStr
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return date.toLocaleDateString(locale, { year: 'numeric', month: 'short' })
    }

    // Precompute everything each month row and chart bar needs once per data
    // change, instead of re-scanning the list for every bar on every render
    const monthRows = computed(() => {
      const maxRevenue = Math.max(0, ...monthlyData.value.map(m => m.revenue))
      return monthlyData.value.map((m, i) => {
        const previous = i > 0 ? monthlyData.value[i - 1].revenue : null
        return {
          ...m,
          label: formatMonth(m.month),
          barHeight: maxRevenue > 0 ? (m.revenue / maxRevenue) * MAX_BAR_HEIGHT : 0,
          change: previous === null ? null : m.revenue - previous,
          growthRate: previous ? ((m.revenue - previous) / previous) * 100 : null
        }
      })
    })

    const formatMoney = (amount) => formatCurrencyWithDecimals(amount || 0, currentCurrency.value, 0)

    const formatChange = (change) => {
      if (change === 0) return formatMoney(0)
      return (change > 0 ? '+' : '-') + formatMoney(Math.abs(change))
    }

    const formatGrowth = (rate) => {
      if (rate === null) return 'N/A'
      return (rate > 0 ? '+' : '') + rate.toFixed(1) + '%'
    }

    const getChangeClass = (change) => {
      if (change > 0) return 'positive-change'
      if (change < 0) return 'negative-change'
      return ''
    }

    const getFulfillmentClass = (rate) => {
      if (rate >= 90) return 'success'
      if (rate >= 75) return 'warning'
      return 'danger'
    }

    watch([selectedPeriod, selectedLocation, selectedCategory, selectedStatus], loadData)
    onMounted(loadData)

    return {
      t,
      loading,
      error,
      quarterlyData,
      monthlyData,
      summary,
      monthRows,
      formatMoney,
      formatChange,
      formatGrowth,
      getChangeClass,
      getFulfillmentClass
    }
  }
}
</script>

<style scoped>
/* Cards, tables, stat cards and badges use the shared styles in App.vue */
.num {
  text-align: right;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.chart-container {
  padding: 1rem 1rem 2rem;
}

.bar-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 250px;
  gap: 0.5rem;
}

.bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  max-width: 80px;
}

.bar-container {
  height: 200px;
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.bar {
  width: 100%;
  background: linear-gradient(to top, #3b82f6, #60a5fa);
  border-radius: 4px 4px 0 0;
  transition: height 0.3s ease;
  cursor: pointer;
}

.bar:hover {
  background: linear-gradient(to top, #2563eb, #3b82f6);
}

.bar-label {
  margin-top: 1.5rem;
  font-size: 0.75rem;
  color: #64748b;
  text-align: center;
  transform: rotate(-45deg);
  white-space: nowrap;
}

.positive-change {
  color: #16a34a;
  font-weight: 600;
}

.negative-change {
  color: #dc2626;
  font-weight: 600;
}
</style>
