import { ApiError } from '../api/client'

/**
 * True when a request failed because the server could not be reached
 * (no connection, DNS failure, timeout) — NOT when the server answered with an error.
 * This distinction is the heart of offline handling: a 422 means "your data is wrong",
 * status 0 means "try again later".
 */
export const isNetworkError = (e: unknown) => e instanceof ApiError && e.status === 0

export const isOnline = () => typeof navigator === 'undefined' || navigator.onLine
