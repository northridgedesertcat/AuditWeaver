import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import config from '../next.config.mjs'

const originalBase = process.env.DJANGO_API_BASE
const originalPort = process.env.DJANGO_PORT

afterEach(() => {
  for (const [key, value] of [['DJANGO_API_BASE', originalBase], ['DJANGO_PORT', originalPort]]) {
    if (value === undefined) delete process.env[key]
    else process.env[key] = value
  }
})

test('proxy defaults to the local Django port', async () => {
  delete process.env.DJANGO_API_BASE
  delete process.env.DJANGO_PORT
  assert.equal((await config.rewrites())[0].destination, 'http://localhost:8000/api/v1/:path*')
})

test('proxy follows a custom local Django port', async () => {
  delete process.env.DJANGO_API_BASE
  process.env.DJANGO_PORT = '8800'
  assert.equal((await config.rewrites())[0].destination, 'http://localhost:8800/api/v1/:path*')
})

test('proxy supports a container service name without a duplicate slash', async () => {
  process.env.DJANGO_API_BASE = 'http://django:8000/'
  assert.equal((await config.rewrites())[0].destination, 'http://django:8000/api/v1/:path*')
})

test('build type checking and streaming-compatible settings stay enabled', () => {
  assert.notEqual(config.typescript?.ignoreBuildErrors, true)
  assert.equal(config.trailingSlash, true)
  assert.equal(config.compress, false)
})
