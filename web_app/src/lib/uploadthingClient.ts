import { generateReactHelpers } from '@uploadthing/react'
import type { UploadRouter } from '@/uploadthing.server'

export const { useUploadThing } = generateReactHelpers<UploadRouter>({
  url: '/api/uploadthing',
})
