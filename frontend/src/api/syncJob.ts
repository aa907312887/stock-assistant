import http from './http'

export interface SyncJobItem {
  batch_id: string
  job_name: string
  job_mode: string
  status: string
  trade_date: string | null
  started_at: string
  finished_at: string | null
  basic_rows: number
  daily_rows: number
  weekly_rows: number
  monthly_rows: number
  report_rows: number
  failed_stock_count: number
  error_message: string | null
}

export interface SyncJobListResponse {
  items: SyncJobItem[]
  total: number
  page: number
  page_size: number
}

export interface SyncJobDetailResponse extends SyncJobItem {
  stock_total: number | null
  extra_json: Record<string, unknown> | null
}

export function getSyncJobs(params: {
  page?: number
  page_size?: number
  status?: string
  job_mode?: string
  job_name?: string
}) {
  return http.get<SyncJobListResponse>('/admin/sync-jobs', { params })
}

export function getSyncJobDetail(batchId: string) {
  return http.get<SyncJobDetailResponse>(`/admin/sync-jobs/${batchId}`)
}

export interface SyncTaskItem {
  id: number
  trade_date: string
  task_type: string
  trigger_type: string
  status: string
  batch_id: string | null
  rows_affected: number
  error_message: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface SyncTaskListResponse {
  items: SyncTaskItem[]
  total: number
  page: number
  page_size: number
}

export function getSyncTasks(params: {
  page?: number
  page_size?: number
  status?: string
  task_type?: string
  trigger_type?: string
  trade_date_from?: string
  trade_date_to?: string
}) {
  return http.get<SyncTaskListResponse>('/admin/sync-tasks', { params })
}
