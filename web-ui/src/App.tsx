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

const WAVE_HEIGHTS = [18, 38, 56, 32, 72, 46, 88, 64, 38, 76, 52, 92, 58, 34, 66, 44, 78, 30]

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
    createJob.mutate({ text: text.trim(), language })
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
    <div className="min-h-screen overflow-hidden bg-background text-foreground">
      <div className="noise" aria-hidden="true" />
      <header className="relative z-10 mx-auto flex w-full max-w-[1400px] items-center justify-between px-5 py-6 sm:px-8 lg:px-12">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-full bg-foreground text-background">
            <AudioLines className="size-5" />
          </span>
          <div>
            <p className="text-sm font-extrabold tracking-[-0.03em]">GWEN / VOICE</p>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Studio 01
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-2 text-xs font-semibold">
          <span className="size-2 rounded-full bg-primary shadow-[0_0_0_4px_rgba(215,255,80,0.16)]" />
          Local AI
        </div>
      </header>

      <main className="relative z-10 mx-auto grid w-full max-w-[1400px] gap-10 px-5 pb-12 pt-8 sm:px-8 lg:grid-cols-[0.88fr_1.12fr] lg:gap-16 lg:px-12 lg:pb-16 lg:pt-14">
        <section className="flex flex-col justify-between">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 border-b border-foreground pb-2 text-xs font-bold uppercase tracking-[0.2em]">
              <Sparkles className="size-4" />
              Natural voice synthesis
            </div>
            <h1 className="max-w-3xl font-serif text-[clamp(3.8rem,8vw,7.8rem)] leading-[0.82] tracking-[-0.065em]">
              Words,
              <br />
              <span className="italic text-stroke">heard.</span>
            </h1>
            <p className="mt-8 max-w-lg text-base leading-7 text-muted-foreground sm:text-lg">
              Shape text into expressive speech with Gwen, a voice model tuned for natural
              Vietnamese and ready for ten more languages.
            </p>
          </div>

          <div className="mt-12 rounded-[2rem] bg-foreground p-6 text-background sm:p-8">
            <div className="mb-8 flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-background/55">
                  Signal preview
                </p>
                <p className="mt-2 text-sm text-background/80">
                  One request. One clean MP3.
                </p>
              </div>
              <span className="rounded-full border border-background/20 px-3 py-1 text-xs">
                128 kbps
              </span>
            </div>
            <div className="flex h-28 items-center justify-between gap-1" aria-hidden="true">
              {WAVE_HEIGHTS.map((height, index) => (
                <span
                  key={index}
                  className="wave-bar w-full rounded-full bg-primary"
                  style={{
                    height: `${height}%`,
                    animationDelay: `${index * 70}ms`,
                  }}
                />
              ))}
            </div>
          </div>
        </section>

        <section>
          <Card className="overflow-hidden shadow-[0_30px_90px_rgba(22,25,24,0.12)]">
            <CardHeader className="border-b border-border">
              <div className="flex items-start justify-between gap-5">
                <div>
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-primary-ink">
                    New generation
                  </p>
                  <CardTitle className="text-2xl tracking-[-0.04em] sm:text-3xl">
                    What should Gwen say?
                  </CardTitle>
                </div>
                <span className="grid size-11 shrink-0 place-items-center rounded-full border border-border">
                  <span className="font-mono text-xs font-bold">01</span>
                </span>
              </div>
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

          <p className="mt-4 px-2 text-center text-xs leading-5 text-muted-foreground">
            Powered locally by g-group-ai-lab/gwen-tts-0.6B. The first run downloads the model.
          </p>
        </section>
      </main>
    </div>
  )
}

