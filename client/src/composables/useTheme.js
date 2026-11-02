import { ref, computed } from 'vue'

const STORAGE_KEY = 'app-theme'

// Use the saved choice if there is one, otherwise follow the OS setting.
// localStorage can throw in private windows, so treat that as "no choice saved".
const getInitialTheme = () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch (err) {
    // Fall through to the OS preference
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

// Shared theme state (singleton, like useFilters)
const theme = ref(getInitialTheme())

// The theme lives on <html> so the global dark overrides in App.vue can
// outrank component-scoped styles
const applyTheme = (value) => {
  document.documentElement.setAttribute('data-theme', value)
}
applyTheme(theme.value)

export function useTheme() {
  const isDark = computed(() => theme.value === 'dark')

  const toggleTheme = () => {
    theme.value = isDark.value ? 'light' : 'dark'
    applyTheme(theme.value)
    try {
      localStorage.setItem(STORAGE_KEY, theme.value)
    } catch (err) {
      // Theme still applies for this visit; it just won't be remembered
    }
  }

  return {
    theme: computed(() => theme.value),
    isDark,
    toggleTheme
  }
}
