/**
 * Modal overlay component for displaying job progress with cancel and retry support.
 * Used for MATCH, FANOUT, and OPTIMIZE background jobs.
 *
 * Features smooth animations and minimum display time for better UX.
 */

import { Button } from '@/components/ui/button';
import { Text } from '@/components/ui/text';
import {
  JobResponse,
  JobType,
  useJobProgress,
} from '@/lib/useJobProgress';
import { cn } from '@/lib/utils';
import { AlertCircle, Loader2, RefreshCw, X } from 'lucide-react-native';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Modal, Platform, Pressable, View } from 'react-native';
import Animated, {
  Easing,
  FadeIn,
  FadeOut,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSpring,
  withTiming,
} from 'react-native-reanimated';

// Job type to title mapping
const JOB_TITLES: Record<JobType, string> = {
  MATCH: 'Finding product matches...',
  FANOUT: 'Preparing your list...',
  OPTIMIZE: 'Building your route...',
};

// Minimum time (ms) to show the overlay before completing
const MIN_DISPLAY_TIME = 1000;
// Time (ms) to animate to 100% after job completes
const COMPLETION_ANIMATION_TIME = 1000;

export interface JobProgressOverlayProps {
  visible: boolean;
  title?: string;
  routePlanId: string;
  jobId: string | null;
  jobType: JobType;
  onComplete: (job: JobResponse) => void;
  onCancel: () => void;
  onRetry?: () => void;
}

export function JobProgressOverlay({
  visible,
  title,
  routePlanId,
  jobId,
  jobType,
  onComplete,
  onCancel,
  onRetry,
}: JobProgressOverlayProps) {
  const displayTitle = title ?? JOB_TITLES[jobType];

  // Track when the overlay was shown
  const showTimeRef = useRef<number>(0);
  // Store completed job for delayed callback
  const completedJobRef = useRef<JobResponse | null>(null);
  // Track completion timeout so we can clear it
  const completionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track if we're in the completion delay phase
  const [isCompleting, setIsCompleting] = useState(false);

  // Animated values
  const progressWidth = useSharedValue(0);
  const spinRotation = useSharedValue(0);

  // Start spinner animation when visible
  useEffect(() => {
    if (visible) {
      showTimeRef.current = Date.now();
      progressWidth.value = 0;
      // Continuous rotation for spinner
      spinRotation.value = withRepeat(
        withTiming(360, { duration: 1000, easing: Easing.linear }),
        -1, // infinite
        false
      );
    }
  }, [visible, progressWidth, spinRotation]);

  // Reset state when jobId changes (new job starting)
  useEffect(() => {
    console.log('[JobProgressOverlay] jobId changed, resetting state for new job');
    // Clear any pending timeout from previous job
    if (completionTimeoutRef.current) {
      clearTimeout(completionTimeoutRef.current);
      completionTimeoutRef.current = null;
    }
    // Reset completion tracking
    completedJobRef.current = null;
    setIsCompleting(false);
    // Reset the show time so MIN_DISPLAY_TIME starts fresh for this job
    showTimeRef.current = Date.now();
    // Reset progress bar for the new job
    progressWidth.value = 0;
  }, [jobId, progressWidth]);

  // Handle completion with minimum display time
  const handleComplete = useCallback(
    (job: JobResponse) => {
      console.log('[JobProgressOverlay] handleComplete called:', job.status, job.message, 'already completing:', !!completedJobRef.current);

      // Guard against duplicate calls - if we're already completing, ignore
      if (completedJobRef.current) {
        console.log('[JobProgressOverlay] Ignoring duplicate handleComplete call');
        return;
      }

      completedJobRef.current = job;
      setIsCompleting(true);

      // Animate progress to 100%
      progressWidth.value = withTiming(100, {
        duration: COMPLETION_ANIMATION_TIME,
        easing: Easing.out(Easing.cubic),
      });

      // Calculate remaining time to meet minimum display
      const elapsed = Date.now() - showTimeRef.current;
      const remainingTime = Math.max(0, MIN_DISPLAY_TIME - elapsed);
      const totalDelay = remainingTime + COMPLETION_ANIMATION_TIME;

      console.log('[JobProgressOverlay] Starting completion timeout:', { elapsed, remainingTime, totalDelay });

      // Clear any existing timeout
      if (completionTimeoutRef.current) {
        clearTimeout(completionTimeoutRef.current);
      }

      // Delay the actual completion callback
      completionTimeoutRef.current = setTimeout(() => {
        console.log('[JobProgressOverlay] Completion timeout fired');
        if (completedJobRef.current) {
          onComplete(completedJobRef.current);
          completedJobRef.current = null;
          setIsCompleting(false);
        }
        completionTimeoutRef.current = null;
      }, totalDelay);
    },
    [onComplete, progressWidth]
  );

  const { status, progress, message, error, cancel, reset, refetch } = useJobProgress(
    visible ? routePlanId : null,
    visible ? jobId : null,
    jobType,
    {
      onComplete: handleComplete,
    }
  );

  // Update progress animation when progress changes
  useEffect(() => {
    if (!isCompleting && progress.total > 0) {
      const percent = (progress.current / progress.total) * 100;
      progressWidth.value = withSpring(percent, {
        damping: 15,
        stiffness: 100,
      });
    }
  }, [progress.current, progress.total, isCompleting, progressWidth]);

  // Animated styles
  const progressBarStyle = useAnimatedStyle(() => ({
    width: `${progressWidth.value}%`,
  }));

  const spinnerStyle = useAnimatedStyle(() => ({
    transform: [{ rotate: `${spinRotation.value}deg` }],
  }));

  // Handle cancel button press
  const handleCancel = useCallback(async () => {
    await cancel();
    onCancel();
  }, [cancel, onCancel]);

  // Handle retry button press - resets state immediately then calls parent's onRetry
  const handleRetry = useCallback(async () => {
    // Reset hook state immediately so UI shows loading state right away
    reset();
    // Reset progress bar animation
    progressWidth.value = 0;
    if (onRetry) {
      // Call onRetry (may be async, will complete in background)
      onRetry();
      // Wait for backend to process the request, then refetch
      // (needed when backend reuses same job ID)
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await refetch();
    } else {
    }
  }, [onRetry, reset, progressWidth, refetch]);

  // Determine if we're in an error state (cancelled is not an error)
  const isCancelled = status === 'CANCELLED';
  const isError = (status === 'FAILED' || error !== null) && !isCancelled;
  // Include SUCCESS in isLoading to keep progress bar visible during completion animation
  const isLoading = status === 'PENDING' || status === 'RUNNING' || status === 'SUCCESS' || isCompleting;

  console.log('[JobProgressOverlay] render:', {
    status,
    message,
    progress,
    isLoading,
    isCompleting,
    isError,
    isCancelled,
  });

  // Calculate display percentage
  const displayPercent = progress.total > 0
    ? Math.round((progress.current / progress.total) * 100)
    : 0;

  // Filter out technical error messages from display during loading
  const isErrorMessage = (msg: string | null): boolean => {
    if (!msg) return false;
    const lower = msg.toLowerCase();
    return lower.includes('error') || lower.includes('failed') || lower.includes('exception') || lower.includes('traceback');
  };
  const safeMessage = message && !isErrorMessage(message) ? message : null;

  if (!visible) {
    return null;
  }

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={handleCancel}
    >
      <Pressable
        className="flex-1 items-center justify-center bg-black/50"
        onPress={() => {
          // Don't allow dismissing by tapping outside when loading
        }}
      >
        <Animated.View
          entering={FadeIn.duration(200)}
          exiting={FadeOut.duration(150)}
          className={cn(
            'mx-4 w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl',
            Platform.select({ web: 'max-w-md' })
          )}
        >
          {/* Header */}
          <View className="mb-4 flex-row items-center justify-between">
            <Text className="text-lg font-semibold text-gray-900">
              {isError ? 'Something went wrong' : isCancelled ? 'Cancelled' : displayTitle}
            </Text>
          </View>

          {/* Content */}
          <View className="mb-6">
            {isLoading && (
              <>
                {/* Progress bar */}
                <View className="mb-3">
                  <View className="h-2 overflow-hidden rounded-full bg-gray-200">
                    <Animated.View
                      style={progressBarStyle}
                      className="h-full rounded-full bg-[#4AA8D8]"
                    />
                  </View>
                </View>

                {/* Progress text */}
                <View className="flex-row items-center justify-between">
                  <View className="flex-row items-center">
                    <Animated.View style={spinnerStyle} className="mr-2">
                      <Loader2 size={16} color="#4AA8D8" />
                    </Animated.View>
                    <Text className="text-sm text-gray-600">
                      {isCompleting ? 'Finishing up...' : (safeMessage || 'Processing...')}
                    </Text>
                  </View>
                  {progress.total > 0 && (
                    <Text className="text-sm font-medium text-gray-900">
                      {isCompleting ? '100%' : `${displayPercent}%`}
                    </Text>
                  )}
                </View>
              </>
            )}

            {isError && (
              <View className="flex-row items-start">
                <AlertCircle size={20} color="#EF4444" style={{ marginRight: 8, marginTop: 2 }} />
                <Text className="flex-1 text-sm text-gray-600">
                  {error || 'An unexpected error occurred. Please try again.'}
                </Text>
              </View>
            )}

            {isCancelled && (
              <Text className="text-sm text-gray-600">
                The operation was cancelled.
              </Text>
            )}
          </View>

          {/* Actions */}
          <View className="flex-row justify-end gap-3">
            {isLoading && !isCompleting && (
              <Button
                variant="outline"
                onPress={handleCancel}
                className="flex-row items-center"
              >
                <X size={16} color="#4B5563" style={{ marginRight: 4 }} />
                <Text className="text-sm font-medium text-gray-700">Cancel</Text>
              </Button>
            )}

            {isError && (
              <>
                <Button
                  variant="outline"
                  onPress={onCancel}
                  className="flex-row items-center"
                >
                  <X size={16} color="#4B5563" style={{ marginRight: 4 }} />
                  <Text className="text-sm font-medium text-gray-700">Close</Text>
                </Button>
                <Button
                  variant="continue"
                  onPress={handleRetry}
                  className="flex-row items-center"
                >
                  <RefreshCw size={16} color="#FFFFFF" style={{ marginRight: 4 }} />
                  <Text className="text-sm font-medium text-white">Retry</Text>
                </Button>
              </>
            )}

            {isCancelled && (
              <Button
                variant="outline"
                onPress={onCancel}
                className="flex-row items-center"
              >
                <Text className="text-sm font-medium text-gray-700">Close</Text>
              </Button>
            )}
          </View>
        </Animated.View>
      </Pressable>
    </Modal>
  );
}

export default JobProgressOverlay;
