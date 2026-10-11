import type { CreateSpeechInput, Language, SpeechJob } from "@/types/tts"

export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8011").replace(/\/$/, "")

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : Array.isArray(payload?.detail)
          ? payload.detail[0]?.msg
          : null
    throw new Error(detail || `Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  languages: () => request<Language[]>("/languages"),
  createJob: (input: CreateSpeechInput) =>
    request<SpeechJob>("/jobs", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  getJob: (jobId: string) => request<SpeechJob>(`/jobs/${encodeURIComponent(jobId)}`),
}

export function subscribeToJob(
  jobId: string,
  onUpdate: (job: SpeechJob) => void,
  onError: () => void,
) {
  const source = new EventSource(`${API_URL}/jobs/${encodeURIComponent(jobId)}/events`, {
    withCredentials: true,
  })
  source.onmessage = ({ data }) => {
    const job = JSON.parse(data) as SpeechJob
    onUpdate(job)
    if (job.status === "succeeded" || job.status === "failed") {
      source.close()
    }
  }
  source.onerror = () => {
    source.close()
    onError()
  }
  return () => source.close()
}

export async function downloadAudio(job: SpeechJob) {
  const response = await fetch(job.audio_url, { credentials: "include" })
  if (!response.ok) throw new Error("The audio file could not be downloaded.")
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = job.filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

