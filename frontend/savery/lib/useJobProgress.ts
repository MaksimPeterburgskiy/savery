/**
 * Hook for tracking background job progress via WebSocket with polling fallback.
 * Supports MATCH, FANOUT, and OPTIMIZE job types.
 */

import NetInfo from '@react-native-community/netinfo';
import { useCallback, useEffect, useRef, useState } from 'react';

// Job status values matching backend JobStatus enum
export type JobStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'CANCELLED';

// Job type for endpoint routing
export type JobType = 'MATCH' | 'FANOUT' | 'OPTIMIZE';

// Job response from the API
export interface JobResponse {
  id: string;
  plan_id: string;
  status: JobStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  progress_current?: number;
  progress_total?: number;
  message?: string;
}

export interface UseJobProgressOptions {
  onComplete?: (job: JobResponse) => void;
  onError?: (message: string) => void;
  onProgress?: (current: number, total: number) => void;
}

export interface UseJobProgressReturn {
  status: JobStatus;
  progress: { current: number; total: number };
  message: string | null;
  error: string | null;
  cancel: () => Promise<void>;
  retry: () => Promise<void>;
  reset: () => void;
  refetch: () => Promise<void>;
}

const TERMINAL_STATUSES: JobStatus[] = ['SUCCESS', 'FAILED', 'CANCELLED'];
const INITIAL_POLL_INTERVAL = 1000;
const MAX_POLL_INTERVAL = 5000;

// Get the job endpoint path based on job type
function getJobEndpoint(routePlanId: string, jobId: string, jobType: JobType): string {
  switch (jobType) {
    case 'MATCH':
      return `/route-plans/${routePlanId}/item-match-jobs/${jobId}`;
    case 'FANOUT':
      return `/route-plans/${routePlanId}/item-fanout-jobs/${jobId}`;
    case 'OPTIMIZE':
      return `/route-plans/${routePlanId}/plan-route-jobs/${jobId}`;
  }
}

export function useJobProgress(
  routePlanId: string | null,
  jobId: string | null,
  jobType: JobType,
  options: UseJobProgressOptions = {}
): UseJobProgressReturn {
  const { onComplete, onError, onProgress } = options;

  const [status, setStatus] = useState<JobStatus>('PENDING');
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Refs for cleanup
  const wsRef = useRef<WebSocket | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollIntervalRef = useRef(INITIAL_POLL_INTERVAL);
  const mountedRef = useRef(true);
  const lastJobRef = useRef<JobResponse | null>(null);
  const prevJobIdRef = useRef<string | null>(null);

  // API base URL
  const apiBase = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api';
  const wsBase = apiBase.replace(/^http/, 'ws').replace(/\/api$/, '');

  // Handle job update from WebSocket or polling
  const handleJobUpdate = useCallback(
    (job: JobResponse) => {
      if (!mountedRef.current) return;

      console.log('[useJobProgress] handleJobUpdate called:', {
        status: job.status,
        message: job.message,
        progress_current: job.progress_current,
        progress_total: job.progress_total,
      });

      lastJobRef.current = job;
      setStatus(job.status);
      setMessage(job.message ?? null);

      // Only update progress if values are provided, or if not in terminal state
      // This prevents the progress bar from disappearing when SUCCESS message
      // arrives without progress fields (the previous RUNNING message had them)
      const isTerminal = TERMINAL_STATUSES.includes(job.status);
      if (job.progress_current !== undefined || job.progress_total !== undefined || !isTerminal) {
        const current = job.progress_current ?? 0;
        const total = job.progress_total ?? 0;
        setProgress({ current, total });

        if (total > 0) {
          onProgress?.(current, total);
        }
      }

      if (TERMINAL_STATUSES.includes(job.status)) {
        if (job.status === 'SUCCESS') {
          onComplete?.(job);
        } else if (job.status === 'FAILED') {
          const genericError = 'Task failed. Please try again.';
          setError(genericError);
          onError?.(genericError);
        } else if (job.status === 'CANCELLED') {
          setError('Task was cancelled');
        }
      }
    },
    [onComplete, onError, onProgress]
  );

  // Fetch job status via HTTP polling
  const fetchJobStatus = useCallback(async () => {
    if (!routePlanId || !jobId || !mountedRef.current) return null;

    try {
      const endpoint = getJobEndpoint(routePlanId, jobId, jobType);
      const res = await fetch(`${apiBase}${endpoint}`, {
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        throw new Error(`Failed to fetch job status: ${res.status}`);
      }

      const job: JobResponse = await res.json();
      return job;
    } catch (err) {
      const genericError = 'Unable to check task status. Please try again.';
      if (mountedRef.current) {
        setError(genericError);
        onError?.(genericError);
      }
      return null;
    }
  }, [routePlanId, jobId, jobType, apiBase, onError]);

  // Start polling fallback
  const startPolling = useCallback(() => {
    const poll = async () => {
      if (!mountedRef.current) return;

      const job = await fetchJobStatus();
      if (job) {
        console.log('[useJobProgress] Poll result:', job.status, job.message);
        handleJobUpdate(job);

        // Stop polling if terminal status reached
        if (TERMINAL_STATUSES.includes(job.status)) {
          return;
        }

        // Reset poll interval on successful update
        pollIntervalRef.current = INITIAL_POLL_INTERVAL;
      } else {
        // Backoff on failure
        pollIntervalRef.current = Math.min(pollIntervalRef.current * 2, MAX_POLL_INTERVAL);
      }

      // Schedule next poll
      if (mountedRef.current) {
        pollTimerRef.current = setTimeout(poll, pollIntervalRef.current);
      }
    };

    poll();
  }, [fetchJobStatus, handleJobUpdate]);

  // Connect WebSocket
  const connectWebSocket = useCallback(() => {
    if (!routePlanId || !jobId) return;

    const wsUrl = `${wsBase}/ws/jobs/${jobId}?plan_id=${routePlanId}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        // Reset poll interval on successful connection
        pollIntervalRef.current = INITIAL_POLL_INTERVAL;
      };

      ws.onmessage = (event) => {
        try {
          const job: JobResponse = JSON.parse(event.data);
          console.log('[useJobProgress] WebSocket message received:', job.status, job.message);
          handleJobUpdate(job);

          // Close WebSocket if terminal status reached
          if (TERMINAL_STATUSES.includes(job.status)) {
            ws.close();
          }
        } catch {
          // Ignore parse errors
        }
      };

      ws.onerror = () => {
        // Fall back to polling on WebSocket error
        ws.close();
      };

      ws.onclose = () => {
        // Only handle if this is still the active WebSocket (not an old one being cleaned up)
        if (wsRef.current !== ws) return;

        wsRef.current = null;

        // Start polling if not in terminal state
        // If lastJobRef.current is null, we never got a message, so we need to poll
        const lastStatus = lastJobRef.current?.status;
        const isTerminal = lastStatus && TERMINAL_STATUSES.includes(lastStatus);
        if (mountedRef.current && !isTerminal) {
          startPolling();
        }
      };
    } catch {
      // Fall back to polling if WebSocket connection fails
      startPolling();
    }
  }, [routePlanId, jobId, wsBase, handleJobUpdate, startPolling]);

  // Cancel job
  const cancel = useCallback(async () => {
    if (!routePlanId || !jobId) return;

    try {
      const endpoint = getJobEndpoint(routePlanId, jobId, jobType);
      const res = await fetch(`${apiBase}${endpoint}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        throw new Error(`Failed to cancel job: ${res.status}`);
      }

      const job: JobResponse = await res.json();
      handleJobUpdate(job);
    } catch (err) {
      const genericError = 'Unable to cancel task. Please try again.';
      setError(genericError);
      onError?.(genericError);
    }
  }, [routePlanId, jobId, jobType, apiBase, handleJobUpdate, onError]);

  // Retry by re-fetching current status
  const retry = useCallback(async () => {
    setError(null);
    const job = await fetchJobStatus();
    if (job) {
      handleJobUpdate(job);

      // Restart WebSocket connection if not in terminal state
      if (!TERMINAL_STATUSES.includes(job.status)) {
        connectWebSocket();
      }
    }
  }, [fetchJobStatus, handleJobUpdate, connectWebSocket]);

  // Reset state to initial values (used when starting a new job via retry)
  const reset = useCallback(() => {
    setStatus('PENDING');
    setProgress({ current: 0, total: 0 });
    setMessage(null);
    setError(null);
    lastJobRef.current = null;
    pollIntervalRef.current = INITIAL_POLL_INTERVAL;
  }, []);

  // Force refetch current job status (used when jobId stays the same but job was restarted)
  const refetch = useCallback(async () => {
    const job = await fetchJobStatus();
    if (job && mountedRef.current) {
      handleJobUpdate(job);
      // If not terminal, start polling/websocket
      if (!TERMINAL_STATUSES.includes(job.status)) {
        startPolling();
      }
    }
  }, [fetchJobStatus, handleJobUpdate, startPolling]);

  // Separate effect to reset state when jobId changes
  // This ensures the UI updates immediately when a new job starts (e.g., on retry)
  useEffect(() => {
    if (jobId && jobId !== prevJobIdRef.current) {
      // New job ID detected - reset all state immediately
      setStatus('PENDING');
      setProgress({ current: 0, total: 0 });
      setMessage(null);
      setError(null);
      lastJobRef.current = null;
      pollIntervalRef.current = INITIAL_POLL_INTERVAL;
    }
    prevJobIdRef.current = jobId;
  }, [jobId]);

  // Main effect: connect when jobId changes
  useEffect(() => {
    mountedRef.current = true;

    if (!routePlanId || !jobId) {
      return;
    }

    // Check network connectivity and decide connection strategy
    const initConnection = async () => {
      const netState = await NetInfo.fetch();

      if (netState.isConnected && netState.isInternetReachable !== false) {
        // Try WebSocket first
        connectWebSocket();
      } else {
        // Fall back to polling immediately if no network
        startPolling();
      }
    };

    initConnection();

    // Do an immediate fetch to get current status right away
    const doInitialFetch = async () => {
      const job = await fetchJobStatus();
      if (job && mountedRef.current) {
        console.log('[useJobProgress] Initial fetch result:', job.status, job.message);
        handleJobUpdate(job);
      }
    };
    doInitialFetch();

    // Also do a fallback fetch after 2 seconds in case WebSocket missed updates
    const fallbackTimer = setTimeout(async () => {
      if (!mountedRef.current) return;
      const job = await fetchJobStatus();
      if (job && mountedRef.current) {
        console.log('[useJobProgress] Fallback fetch result:', job.status, job.message);
        handleJobUpdate(job);
      }
    }, 2000);

    // Cleanup
    return () => {
      mountedRef.current = false;
      clearTimeout(fallbackTimer);

      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [routePlanId, jobId, connectWebSocket, startPolling, fetchJobStatus, handleJobUpdate]);

  return {
    status,
    progress,
    message,
    error,
    cancel,
    retry,
    reset,
    refetch,
  };
}

export default useJobProgress;
