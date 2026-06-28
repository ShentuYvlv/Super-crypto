"use client";

import { useEffect, useState } from "react";

import type { ApiEnvelope } from "@/types/api";

export function useApi<T>(path: string, fallback: T) {
  const [data, setData] = useState<T>(fallback);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      try {
        const response = await fetch(path, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`request_failed:${response.status}`);
        }
        const payload = (await response.json()) as ApiEnvelope<T>;
        if (active) {
          setData(payload.payload);
          setError(null);
        }
      } catch (caughtError) {
        if (active) {
          setData(fallback);
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
  }, [fallback, path]);

  return { data, loading, error };
}
