"use client";

import { useEffect, useRef, useState } from "react";

import type { ApiEnvelope } from "@/types/api";

const CACHE_TTL_MS = 60_000;

type CacheEntry<T> = {
  expiresAt: number;
  payload: T;
};

type ApiRequestState = {
  responseCache: Map<string, CacheEntry<unknown>>;
  inFlightRequests: Map<string, Promise<unknown>>;
};

declare global {
  interface Window {
    __SUPER_CRYPTO_API_REQUEST_STATE__?: ApiRequestState;
  }
}

const moduleRequestState: ApiRequestState = {
  responseCache: new Map<string, CacheEntry<unknown>>(),
  inFlightRequests: new Map<string, Promise<unknown>>()
};

function getRequestState(): ApiRequestState {
  if (typeof window === "undefined") {
    return moduleRequestState;
  }

  window.__SUPER_CRYPTO_API_REQUEST_STATE__ ??= {
    responseCache: new Map<string, CacheEntry<unknown>>(),
    inFlightRequests: new Map<string, Promise<unknown>>()
  };

  return window.__SUPER_CRYPTO_API_REQUEST_STATE__;
}

async function fetchApiPayload<T>(path: string): Promise<T> {
  const { responseCache, inFlightRequests } = getRequestState();
  const now = Date.now();
  const cached = responseCache.get(path);

  if (cached && cached.expiresAt > now) {
    return cached.payload as T;
  }

  const inFlight = inFlightRequests.get(path);
  if (inFlight) {
    return inFlight as Promise<T>;
  }

  const request = fetch(path, { cache: "default" })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`request_failed:${response.status}`);
      }
      const payload = (await response.json()) as ApiEnvelope<T>;
      responseCache.set(path, {
        expiresAt: Date.now() + CACHE_TTL_MS,
        payload: payload.payload
      });
      return payload.payload;
    })
    .finally(() => {
      inFlightRequests.delete(path);
    });

  inFlightRequests.set(path, request);
  return request;
}

export function useApi<T>(path: string, fallback: T) {
  const [data, setData] = useState<T>(fallback);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fallbackRef = useRef(fallback);

  fallbackRef.current = fallback;

  useEffect(() => {
    let active = true;

    async function load() {
      const { responseCache } = getRequestState();
      const cached = responseCache.get(path);
      if (cached && cached.expiresAt > Date.now()) {
        setData(cached.payload as T);
        setError(null);
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const payload = await fetchApiPayload<T>(path);
        if (active) {
          setData(payload);
          setError(null);
        }
      } catch (caughtError) {
        if (active) {
          setData(fallbackRef.current);
          setError(caughtError instanceof Error ? caughtError.message : "request_failed");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [path]);

  return { data, loading, error };
}
