import http from './http'

export interface UserOut {
  id: number
  username: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserOut
}

export interface LoginForm {
  username: string
  password?: string
}

export function login(data: LoginForm) {
  return http.post<TokenResponse>('/auth/login', data)
}

export function fetchMe() {
  return http.get<UserOut>('/auth/me')
}
