/**
 * Custom hook for replaying query execution timelines.
 *
 * Schedules progress messages at their original relative timestamps,
 * scaled to cap total duration at ~15 seconds for long-running queries.
 */

import { useState, useCallback, useRef } from 'react';
import type { TimelineEntry } from '../../types';

export interface ReplayState {
  isReplaying: boolean;
  currentMessage: string | null;
  currentIndex: number;
}

interface UseQueryReplayReturn {
  replayState: ReplayState;
  startReplay: (timeline: TimelineEntry[]) => void;
  stopReplay: () => void;
}

const MAX_REPLAY_DURATION_MS: number = 15000;
const END_PAUSE_MS: number = 1500;

export function useQueryReplay(): UseQueryReplayReturn {
  const [replayState, setReplayState] = useState<ReplayState>({
    isReplaying: false,
    currentMessage: null,
    currentIndex: -1,
  });

  const timeoutRefs = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearAllTimeouts = useCallback((): void => {
    for (const id of timeoutRefs.current) {
      clearTimeout(id);
    }
    timeoutRefs.current = [];
  }, []);

  const stopReplay = useCallback((): void => {
    clearAllTimeouts();
    setReplayState({
      isReplaying: false,
      currentMessage: null,
      currentIndex: -1,
    });
  }, [clearAllTimeouts]);

  const startReplay = useCallback(
    (timeline: TimelineEntry[]): void => {
      if (timeline.length === 0) return;

      // Clear any previous replay
      clearAllTimeouts();

      const firstEntry: TimelineEntry = timeline[0]!;
      setReplayState({
        isReplaying: true,
        currentMessage: firstEntry.message,
        currentIndex: 0,
      });

      // Calculate time scale factor — cap replay at MAX_REPLAY_DURATION_MS
      const lastEntry: TimelineEntry = timeline[timeline.length - 1]!;
      const totalDuration: number = lastEntry.elapsed_ms;
      const scale: number =
        totalDuration > MAX_REPLAY_DURATION_MS
          ? MAX_REPLAY_DURATION_MS / totalDuration
          : 1;

      // Schedule each entry at its scaled elapsed time
      // (skip index 0 since we set it immediately above)
      for (let i = 1; i < timeline.length; i++) {
        const entry: TimelineEntry = timeline[i]!;
        const delay: number = Math.round(entry.elapsed_ms * scale);
        const idx: number = i;

        const id: ReturnType<typeof setTimeout> = setTimeout((): void => {
          setReplayState({
            isReplaying: true,
            currentMessage: entry.message,
            currentIndex: idx,
          });
        }, delay);

        timeoutRefs.current.push(id);
      }

      // Schedule end of replay after the last entry + pause
      const lastDelay: number = Math.round(totalDuration * scale) + END_PAUSE_MS;
      const endId: ReturnType<typeof setTimeout> = setTimeout((): void => {
        setReplayState({
          isReplaying: false,
          currentMessage: null,
          currentIndex: -1,
        });
        timeoutRefs.current = [];
      }, lastDelay);

      timeoutRefs.current.push(endId);
    },
    [clearAllTimeouts]
  );

  return { replayState, startReplay, stopReplay };
}
