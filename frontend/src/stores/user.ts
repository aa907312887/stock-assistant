import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { UserOut } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserOut | null>(null)

  function setLogin(t: string, u: UserOut) {
    token.value = t
    user.value = u
    localStorage.setItem('token', t)
    try {
      localStorage.setItem('user', JSON.stringify(u))
    } catch {
      // ignore
    }
  }

  function setLogout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  function loadUserFromStorage() {
    try {
      const s = localStorage.getItem('user')
      if (s) user.value = JSON.parse(s) as UserOut
    } catch {
      // ignore
    }
  }

  return { token, user, setLogin, setLogout, loadUserFromStorage }
})
