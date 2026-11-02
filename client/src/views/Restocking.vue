<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="budget-row">
          <label for="budget-slider" class="budget-label">{{ t('restocking.budget') }}</label>
          <div class="budget-input-wrap">
            <span class="budget-prefix">$</span>
            <input
              v-model.number="budget"
              type="number"
              class="budget-input"
              min="0"
              :max="sliderMax"
              step="500"
              :aria-label="t('restocking.budget')"
            />
          </div>
        </div>
        <input
          id="budget-slider"
          v-model.number="budget"
          type="range"
          class="budget-slider"
          min="0"
          :max="sliderMax"
          step="500"
        />
        <div class="slider-scale">
          <span>{{ formatMoney(0) }}</span>
          <span>{{ formatMoney(sliderMax) }}</span>
        </div>
        <p class="budget-hint">{{ t('restocking.budgetHint') }}</p>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.budget') }}</div>
          <div class="stat-value">{{ formatMoney(budget) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.plannedSpend') }}</div>
          <div class="stat-value">{{ formatMoney(recommendation.total_cost) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ formatMoney(recommendation.remaining_budget) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.itemsSelected') }}</div>
          <div class="stat-value">{{ recommendation.items.length }}</div>
        </div>
      </div>

      <div v-if="placedOrder" class="notice success-notice">
        <span>
          {{ t('restocking.orderPlaced', {
            number: placedOrder.order_number,
            total: formatMoney(placedOrder.total_cost),
            date: formatDate(placedOrder.expected_delivery)
          }) }}
        </span>
        <router-link to="/orders" class="notice-link">{{ t('restocking.viewInOrders') }}</router-link>
      </div>
      <div v-if="submitError" class="notice error-notice">
        {{ t('restocking.orderFailed') }}: {{ submitError }}
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }} ({{ recommendation.items.length }})</h3>
          <button
            class="place-order-btn"
            :disabled="submitting || refreshing || placedOrder !== null || recommendation.items.length === 0"
            @click="placeOrder"
          >
            {{ buttonLabel }}
          </button>
        </div>

        <div v-if="recommendation.items.length === 0" class="empty-state">
          {{ t('restocking.noItems') }}
        </div>
        <div v-else :class="['table-container', { refreshing }]">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.item') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th class="num">{{ t('restocking.table.demandGap') }}</th>
                <th class="num">{{ t('restocking.table.quantity') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="num">{{ t('restocking.table.lineTotal') }}</th>
                <th class="num">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommendation.items" :key="item.sku">
                <td>
                  <div class="item-name">{{ translateProductName(item.name) }}</div>
                  <div class="item-sku">{{ item.sku }}</div>
                </td>
                <td><span :class="['badge', item.trend]">{{ t(`trends.${item.trend}`) }}</span></td>
                <td class="num">+{{ item.demand_gap.toLocaleString() }}</td>
                <td class="num">{{ item.quantity.toLocaleString() }}</td>
                <td class="num">{{ formatMoney(item.unit_cost, 2) }}</td>
                <td class="num"><strong>{{ formatMoney(item.line_total) }}</strong></td>
                <td class="num">{{ t('orders.days', { count: item.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, watch, computed, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrencyWithDecimals } from '../utils/currency'

const BUDGET_STEP = 500

export default {
  name: 'Restocking',
  setup() {
    const { t, currentLocale, currentCurrency, translateProductName } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const refreshing = ref(false)
    const submitting = ref(false)
    const submitError = ref(null)
    const placedOrder = ref(null)
    const budget = ref(0)
    const maxBudget = ref(0)
    const recommendation = ref({ items: [], total_cost: 0, remaining_budget: 0 })

    // Round the slider's top end up to a whole step so the full amount is reachable
    const sliderMax = computed(() => Math.ceil(maxBudget.value / BUDGET_STEP) * BUDGET_STEP)

    // Placing an order locks the button until the budget changes, so a second
    // click can't submit the same recommendations twice
    const buttonLabel = computed(() => {
      if (submitting.value) return t('restocking.placing')
      if (placedOrder.value) return t('restocking.orderPlacedShort')
      return t('restocking.placeOrder')
    })

    const formatMoney = (amount, decimals = 0) => {
      return formatCurrencyWithDecimals(amount || 0, currentCurrency.value, decimals)
    }

    const formatDate = (dateString) => {
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return dateString
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return date.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
    }

    // Only the newest request may update the table, so a slow earlier
    // response can't overwrite the result for the current budget
    let latestRequest = 0
    const fetchRecommendations = async () => {
      const requestId = ++latestRequest
      try {
        refreshing.value = true
        const result = await api.getRestockRecommendations(budget.value)
        if (requestId === latestRequest) recommendation.value = result
      } catch (err) {
        if (requestId === latestRequest) error.value = 'Failed to load recommendations: ' + err.message
      } finally {
        if (requestId === latestRequest) refreshing.value = false
      }
    }

    // A budget of 0 is only used to learn the full cost of every eligible
    // item, which sets the slider range. Start the slider halfway along it.
    const loadInitial = async () => {
      try {
        loading.value = true
        const initial = await api.getRestockRecommendations(0)
        maxBudget.value = initial.max_budget
        budget.value = Math.round(initial.max_budget / 2 / BUDGET_STEP) * BUDGET_STEP
        await fetchRecommendations()
      } catch (err) {
        error.value = 'Failed to load recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    // Debounce so dragging the slider doesn't send a request on every step
    let debounceTimer = null
    watch(budget, (value) => {
      if (loading.value) return
      // The number input can hold an empty string or a negative value while typing
      if (typeof value !== 'number' || isNaN(value) || value < 0) return
      placedOrder.value = null
      submitError.value = null
      // Mark the table stale right away so Place Order can't submit the
      // previous budget's items while the debounced fetch is pending
      refreshing.value = true
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(fetchRecommendations, 250)
    })

    const placeOrder = async () => {
      if (submitting.value || placedOrder.value) return
      try {
        submitting.value = true
        submitError.value = null
        const items = recommendation.value.items.map(item => ({ sku: item.sku, quantity: item.quantity }))
        placedOrder.value = await api.createRestockOrder(items)
      } catch (err) {
        submitError.value = err.response?.data?.detail || err.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadInitial)
    onBeforeUnmount(() => clearTimeout(debounceTimer))

    return {
      t,
      translateProductName,
      loading,
      error,
      refreshing,
      submitting,
      submitError,
      placedOrder,
      buttonLabel,
      budget,
      sliderMax,
      recommendation,
      formatMoney,
      formatDate,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  padding: 1.5rem;
}

.budget-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  gap: 1rem;
}

.budget-label {
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-input-wrap {
  display: flex;
  align-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0 0.75rem;
  background: #f8fafc;
}

.budget-prefix {
  color: #64748b;
  font-weight: 600;
}

.budget-input {
  border: none;
  background: transparent;
  padding: 0.5rem 0.25rem;
  width: 120px;
  font-size: 1rem;
  font-weight: 600;
  color: #0f172a;
  text-align: right;
}

.budget-input:focus {
  outline: none;
}

.budget-input-wrap:focus-within {
  border-color: #3b82f6;
}

.budget-slider {
  width: 100%;
  accent-color: #2563eb;
  cursor: pointer;
}

.slider-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.budget-hint {
  margin-top: 0.75rem;
  font-size: 0.875rem;
  color: #64748b;
}

.place-order-btn {
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.625rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.notice {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.875rem 1.25rem;
  border-radius: 10px;
  margin-bottom: 1.25rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.success-notice {
  background: #d1fae5;
  border: 1px solid #a7f3d0;
  color: #065f46;
}

.error-notice {
  background: #fecaca;
  border: 1px solid #fca5a5;
  color: #991b1b;
}

.notice-link {
  color: #065f46;
  font-weight: 700;
  white-space: nowrap;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.table-container.refreshing {
  opacity: 0.6;
  transition: opacity 0.15s ease;
}

.num {
  text-align: right;
}

.item-name {
  font-weight: 500;
  color: #0f172a;
}

.item-sku {
  font-size: 0.75rem;
  color: #64748b;
}
</style>
