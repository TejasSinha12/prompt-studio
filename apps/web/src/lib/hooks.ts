"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "./api";

export interface Resource<T> {
  data: T | undefined;
  error: string | null;
  loading: boolean;
  reload: () => Promise<void>;
  setData: (d: T | undefined | ((prev: T | undefined) => T | undefined)) => void;
}

/** Fetch a GET endpoint; refetches when `path` changes. `null` path = skip. */
export function useResource<T>(path: string | null): Resource<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(path !== null);
  const ctrl = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    if (path === null) return;
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setLoading(true);
    try {
      const d = await api.get<T>(path, c.signal);
      if (!c.signal.aborted) {
        setData(d);
        setError(null);
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) setError(errorMessage(e));
    } finally {
      if (!c.signal.aborted) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    void load();
    return () => ctrl.current?.abort();
  }, [load]);

  return { data, error, loading, reload: load, setData };
}

/** Wrap an async action with busy state; prevents duplicate submissions. */
export function useAction<A extends unknown[], R>(fn: (...args: A) => Promise<R>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const running = useRef(false);
  const run = useCallback(
    async (...args: A): Promise<R | undefined> => {
      if (running.current) return undefined;
      running.current = true;
      setBusy(true);
      setError(null);
      try {
        return await fn(...args);
      } catch (e) {
        setError(errorMessage(e));
        throw e;
      } finally {
        running.current = false;
        setBusy(false);
      }
    },
    [fn],
  );
  return { run, busy, error, setError };
}

export function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function useLocalStorage<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(initial);
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(key);
      if (raw !== null) setValue(JSON.parse(raw) as T);
    } catch {
      /* storage unavailable */
    }
  }, [key]);
  const set = useCallback(
    (v: T) => {
      setValue(v);
      try {
        window.localStorage.setItem(key, JSON.stringify(v));
      } catch {
        /* storage unavailable */
      }
    },
    [key],
  );
  return [value, set];
}
