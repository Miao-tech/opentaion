// web/src/hooks/useUsage.ts
import { useState, useEffect } from "react";
import { fetchUsage } from "../lib/api";
import type { UsageResponse } from "../types/api";

export interface UseUsageResult {
  data: UsageResponse | null;
  isLoading: boolean;
  error: string | null;
}

export function useUsage(): UseUsageResult {
  const [data, setData] = useState<UsageResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchUsage(controller.signal)
      .then((json) => {
        if (!controller.signal.aborted) {
          setData(json);
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, []); // empty deps = fire once on mount, never again

  return { data, isLoading, error };
}
