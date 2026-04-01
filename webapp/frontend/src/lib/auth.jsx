import { createContext, useContext, useState, useEffect } from 'react'
import { api } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  // null = still loading, object = resolved ({ user, role } or { user: null, role: null })
  const [auth, setAuth] = useState(null)

  useEffect(() => {
    api.authMe()
      .then(setAuth)
      .catch(() => setAuth({ user: null, role: null }))
  }, [])

  const login = async (username, password) => {
    const data = await api.authLogin(username, password)
    setAuth(data)
    return data
  }

  const logout = async () => {
    await api.authLogout()
    setAuth({ user: null, role: null })
  }

  return (
    <AuthContext.Provider value={{ auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
