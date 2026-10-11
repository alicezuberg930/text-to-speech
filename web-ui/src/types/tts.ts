export type JobStatus = "queued" | "running" | "succeeded" | "failed"

export type SpeechJob = {
  job_id: string
  status: JobStatus
  progress: number
  text: string
  language: string
  language_label: string
  filename: string
  created_at: string
  updated_at: string
  duration_seconds: number | null
  size: number
  error: string | null
  audio_url: string
}

export type Language = {
  code: string
  label: string
}

export type CreateSpeechInput = {
  text: string
  language: string
}

