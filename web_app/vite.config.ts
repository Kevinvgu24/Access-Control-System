import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import compression from 'vite-plugin-compression'
import type { ViteDevServer } from 'vite'
import type { IncomingMessage, ServerResponse } from 'http'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [
      react(),
      // UploadThing dev server route
      {
        name: 'uploadthing-dev',
        apply: 'serve',
        async configureServer(server: ViteDevServer) {
          const token = env.UPLOADTHING_TOKEN
          if (!token) {
            console.warn('[uploadthing] UPLOADTHING_TOKEN not set — file uploads will fail.')
            return
          }
          try {
            const { createRouteHandler }  = await import('uploadthing/server')
            const { uploadRouter }        = await import('./src/uploadthing.server')
            const handler = createRouteHandler({ router: uploadRouter, config: { token } })

            server.middlewares.use(
              '/api/uploadthing',
              async (req: IncomingMessage, res: ServerResponse) => {
                const url = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`)
                const headers = new Headers()
                for (const [k, v] of Object.entries(req.headers)) {
                  if (v) headers.set(k, Array.isArray(v) ? v[0] : v)
                }
                const chunks: Buffer[] = []
                for await (const chunk of req) chunks.push(chunk as Buffer)
                const body = chunks.length > 0 ? Buffer.concat(chunks) : undefined

                const webReq  = new Request(url, { method: req.method ?? 'GET', headers, body })
                const webRes  = await handler(webReq)

                res.writeHead(webRes.status, Object.fromEntries(webRes.headers.entries()))
                res.end(Buffer.from(await webRes.arrayBuffer()))
              }
            )
          } catch (e) {
            console.error('[uploadthing] Failed to set up dev middleware:', e)
          }
        },
      },
      compression({ algorithm: 'gzip',          ext: '.gz' }),
      compression({ algorithm: 'brotliCompress', ext: '.br' }),
    ],
    resolve: {
      alias: { '@': path.resolve(__dirname, './src') },
    },
    server: { port: 5175 },
    build: {
      target: 'es2020',
      sourcemap: false,
      cssCodeSplit: false,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules/react') || id.includes('node_modules/react-dom') || id.includes('node_modules/react-router')) {
              return 'vendor'
            }
            if (id.includes('node_modules/zustand'))  return 'state'
            if (id.includes('node_modules/firebase')) return 'firebase'
          },
        },
      },
    },
  }
})
