/**
 * Custom hook for replaying query execution timelines.
 *
 * Schedules progress messages at their original relative timestamps,
 * scaled to cap total duration at ~15 seconds for long-running queries.
 *
 * replayKey increments on every startReplay call so callers can use it
 * as a React key to force a clean remount between replays.
 */

import { useState, useCallback, useRef } from 'react';
import type { TimelineEntry } from '../../types';

export interface ReplayState {
  isReplaying: boolean;
  currentMessage: string | null;
  currentIndex: number;
  /** Increments each time startReplay is called. Use as React key on consumers. */
  replayKey: number;
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
    replayKey: 0,
  });

  const timeoutRefs = useRef<ReturnType<typeof setTimeout>[]>([]);
  /** Monotonic session counter — used to discard stale timeout callbacks. */
  const sessionRef = useRef<number>(0);

  const clearAllTimeouts = useCallback((): void => {
    for (const id of timeoutRefs.current) {
      clearTimeout(id);
    }
    timeoutRefs.current = [];
  }, []);

  const startReplay = useCallback(
    (timeline: TimelineEntry[]): void => {
      if (timeline.length === 0) return;

      clearAllTimeouts();

      // New session — stale callbacks from the previous replay are now ignored
      const session: number = sessionRef.current + 1;
      sessionRef.current = session;

      const firstEntry: TimelineEntry = timeline[0]!;
      const lastEntry: TimelineEntry = timeline[timeline.length - 1]!;
      const totalDuration: number = lastEntry.elapsed_ms;
      const scale: number =
        totalDuration > MAX_REPLAY_DURATION_MS
          ? MAX_REPLAY_DURATION_MS / totalDuration
          : 1;

      // Schedule all timeline entries (skip index 0 — shown immediately via state)
      for (let i = 1; i < timeline.length; i++) {
        const entry: TimelineEntry = timeline[i]!;
        const delay: number = Math.round(entry.elapsed_ms * scale);
        const id: ReturnType<typeof setTimeout> = setTimeout((): void => {
          if (sessionRef.current !== session) return;
          setReplayState(prev => ({
            ...prev,
            currentMessage: entry.message,
            currentIndex: i,
          }));
        }, delay);
        timeoutRefs.current.push(id);
      }

      // Synthetic "html" stage message — backend html-stage messages arrive after
      // status=completed so they're never captured in the timeline. Inject one here
      // so the replay always drives displayStageIdx through all 6 stages.
      const scaledDuration: number = Math.round(totalDuration * scale);
      const syntheticHtmlDelay: number = scaledDuration + 300;
      const htmlId: ReturnType<typeof setTimeout> = setTimeout((): void => {
        if (sessionRef.current !== session) return;
        setReplayState(prev => ({
          ...prev,
          currentMessage: 'Formatting output...',
          currentIndex: timeline.length,
        }));
      }, syntheticHtmlDelay);
      timeoutRefs.current.push(htmlId);

      // End sentinel — fires after the html animation has had time to play (~1500ms MIN_STAGE_MS)
      const endDelay: number = syntheticHtmlDelay + END_PAUSE_MS + 200;
      const endId: ReturnType<typeof setTimeout> = setTimeout((): void => {
        if (sessionRef.current !== session) return;
        setReplayState(prev => ({
          ...prev,
          isReplaying: false,
          currentMessage: null,
          currentIndex: -1,
        }));
        timeoutRefs.current = [];
      }, endDelay);
      timeoutRefs.current.push(endId);

      setReplayState(prev => ({
        isReplaying: true,
        currentMessage: firstEntry.message,
        currentIndex: 0,
        replayKey: prev.replayKey + 1,
      }));
    },
    [clearAllTimeouts],
  );

  const stopReplay = useCallback((): void => {
    clearAllTimeouts();
    setReplayState(prev => ({
      isReplaying: false,
      currentMessage: null,
      currentIndex: -1,
      replayKey: prev.replayKey,
    }));
  }, [clearAllTimeouts]);

  return { replayState, startReplay, stopReplay };
}
