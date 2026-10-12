import { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  ArrowDownToLine,
  AudioLines,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  Sparkles,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Slider } from "@/components/ui/slider"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { api, downloadAudio, subscribeToJob } from "@/lib/api"
import { ttsQueries } from "@/lib/queries/tts"
import type { Language, SpeechJob } from "@/types/tts"

const FALLBACK_LANGUAGES: Language[] = [
  { code: "vn", label: "Vietnamese" },
  { code: "en", label: "English" },
  { code: "zh", label: "Chinese" },
  { code: "ja", label: "Japanese" },
  { code: "ko", label: "Korean" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "it", label: "Italian" },
  { code: "pt", label: "Portuguese" },
  { code: "ru", label: "Russian" },
  { code: "es", label: "Spanish" },
]

function expectedFilename(language: string) {
  const date = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Bangkok",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
    .format(new Date())
    .replaceAll("/", "-")
  return `${date}-${language}.mp3`
}

function formatBytes(size: number) {
  if (!size) return "MP3 · 128 kbps"
  return `${(size / 1024 / 1024).toFixed(2)} MB · MP3`
}

export default function App() {
  const [text, setText] = useState(
    "Xin chào. Công nghệ có thể làm cho mọi ý tưởng trở nên sống động — từng câu, từng nhịp, từng cảm xúc.",
  )
  const [language, setLanguage] = useState("vn")
  const [speed, setSpeed] = useState(1)
  const [job, setJob] = useState<SpeechJob | null>(null)
  const [error, setError] = useState("")
  const [downloading, setDownloading] = useState(false)

  const languagesQuery = useQuery(ttsQueries.languages)
  const languages = languagesQuery.data?.length ? languagesQuery.data : FALLBACK_LANGUAGES

  const createJob = useMutation({
    ...ttsQueries.create,
    onSuccess: (created) => {
      setJob(created)
      setError("")
    },
    onError: (cause) => {
      setError(cause instanceof Error ? cause.message : "Could not start speech generation.")
    },
  })

  useEffect(() => {
    if (!job || job.status === "succeeded" || job.status === "failed") return
    return subscribeToJob(
      job.job_id,
      setJob,
      () => {
        void api
          .getJob(job.job_id)
          .then(setJob)
          .catch(() => setError("Live updates disconnected. Please submit again."))
      },
    )
  }, [job?.job_id, job?.status])

  const selectedLanguage = useMemo(
    () => languages.find((item) => item.code === language),
    [language, languages],
  )
  const isWorking = createJob.isPending || job?.status === "queued" || job?.status === "running"
  const filename = job?.filename || expectedFilename(language)

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!text.trim()) {
      setError("Add some text before generating speech.")
      return
    }
    setJob(null)
    setError("")
    createJob.mutate({ text: text.trim(), language, speed })
  }

  const handleDownload = async () => {
    if (!job) return
    setDownloading(true)
    setError("")
    try {
      await downloadAudio(job)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Download failed.")
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="min-h-screen overflow-hidden p-4">
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border">
          <CardTitle className="text-2xl tracking-[-0.04em] sm:text-3xl">
            New generation
          </CardTitle>
        </CardHeader>

        <CardContent className="pt-6 md:pt-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="speech-text">Your script</Label>
                <span className="font-mono text-xs text-muted-foreground">
                  {text.length} / 4000
                </span>
              </div>
              <Textarea
                id="speech-text"
                value={text}
                onChange={(event) => setText(event.target.value.slice(0, 4000))}
                placeholder="Type or paste the words you want to hear…"
                disabled={isWorking}
              />
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div className="space-y-2.5">
                <Label>Language</Label>
                <Select value={language} onValueChange={setLanguage} disabled={isWorking}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a language" />
                  </SelectTrigger>
                  <SelectContent>
                    {languages.map((item) => (
                      <SelectItem key={item.code} value={item.code}>
                        <span className="flex w-full items-center gap-3">
                          <span className="font-mono text-xs uppercase text-muted-foreground">
                            {item.code}
                          </span>
                          {item.label}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2.5">
                <Label>Output file</Label>
                <div className="flex h-12 items-center rounded-xl border border-dashed border-border bg-muted/60 px-4 font-mono text-xs">
                  {filename}
                </div>
              </div>
              <div className="space-y-2.5 sm:col-span-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="speech-speed">Speed</Label>
                  <span className="rounded-full bg-muted px-2.5 py-1 font-mono text-xs font-semibold">
                    {speed.toFixed(2)}×
                  </span>
                </div>
                <div className="flex h-12 items-center gap-3 rounded-xl border border-input bg-background px-4 shadow-sm">
                  <span className="font-mono text-[10px] text-muted-foreground">0.75×</span>
                  <Slider
                    id="speech-speed"
                    min={0.75}
                    max={1.5}
                    step={0.05}
                    value={[speed]}
                    onValueChange={([value]) => setSpeed(value)}
                    disabled={isWorking}
                    aria-label="Speech speed"
                  />
                  <span className="font-mono text-[10px] text-muted-foreground">1.50×</span>
                </div>
              </div>
            </div>

            <Button type="submit" size="lg" className="w-full" disabled={isWorking}>
              {isWorking ? (
                <>
                  <LoaderCircle className="size-5 animate-spin" />
                  Creating your voice
                </>
              ) : (
                <>
                  <AudioLines className="size-5" />
                  Generate speech
                </>
              )}
            </Button>
          </form>

          <div aria-live="polite" className="mt-6">
            {error && (
              <div className="rounded-2xl border border-destructive/30 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                {error}
              </div>
            )}

            {job && (
              <div className="rounded-2xl border border-border bg-muted/45 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="grid size-10 shrink-0 place-items-center rounded-full bg-foreground text-background">
                      {job.status === "succeeded" ? (
                        <CheckCircle2 className="size-5 text-primary" />
                      ) : job.status === "failed" ? (
                        <span className="text-lg">!</span>
                      ) : (
                        <Clock3 className="size-5" />
                      )}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold">{job.filename}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {job.status === "succeeded"
                          ? `${job.duration_seconds?.toFixed(1) ?? "—"} sec · ${formatBytes(job.size)}`
                          : job.status === "failed"
                            ? job.error || "Generation failed"
                            : `${job.status === "queued" ? "Waiting in queue" : "Synthesizing"} · ${job.progress}%`}
                      </p>
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                        {(job.speed ?? 1).toFixed(2)}× speed
                      </p>
                    </div>
                  </div>
                  <span className="rounded-full border border-border bg-card px-3 py-1 font-mono text-[10px] uppercase">
                    {selectedLanguage?.label ?? job.language_label}
                  </span>
                </div>

                {(job.status === "queued" || job.status === "running") && (
                  <Progress value={job.progress} className="mt-5" />
                )}

                {job.status === "succeeded" && (
                  <div className="mt-5 space-y-4">
                    <audio className="w-full" controls preload="metadata" src={job.audio_url}>
                      Your browser does not support audio playback.
                    </audio>
                    <Button
                      type="button"
                      variant="outline"
                      className="w-full"
                      onClick={handleDownload}
                      disabled={downloading}
                    >
                      {downloading ? (
                        <LoaderCircle className="size-4 animate-spin" />
                      ) : (
                        <ArrowDownToLine className="size-4" />
                      )}
                      Download {job.filename}
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
