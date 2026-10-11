import { mutationOptions, queryOptions } from "@tanstack/react-query"

import { api } from "@/lib/api"

export const ttsQueries = {
  languages: queryOptions({
    queryKey: ["languages"],
    queryFn: api.languages,
    staleTime: Number.POSITIVE_INFINITY,
  }),
  job: (jobId: string) =>
    queryOptions({
      queryKey: ["speech-job", jobId],
      queryFn: () => api.getJob(jobId),
      enabled: Boolean(jobId),
    }),
  create: mutationOptions({
    mutationKey: ["speech-job", "create"],
    mutationFn: api.createJob,
  }),
}

