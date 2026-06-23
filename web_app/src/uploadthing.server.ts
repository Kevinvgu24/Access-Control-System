import { createUploadthing, type FileRouter } from 'uploadthing/server'

const f = createUploadthing()

export const uploadRouter = {
  faceImages: f({ image: { maxFileSize: '4MB', maxFileCount: 6 } })
    .middleware(() => ({ uploader: 'admin' }))
    .onUploadComplete(({ file }) => ({ url: file.ufsUrl ?? file.url })),
} satisfies FileRouter

export type UploadRouter = typeof uploadRouter
