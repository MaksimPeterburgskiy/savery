import {
  getActiveFlow,
  getListId,
  setListId,
  setRoutePlanId,
  FlowState,
} from '@/lib/itemStore';
import { useFocusEffect } from 'expo-router';
import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import ItemInput from './itemInput';

/**
 * App entry point - renders ItemInput directly.
 *
 * Flow state restoration is handled by each screen checking if it needs
 * to forward to the next screen. This builds the navigation stack naturally
 * and enables swipe-back gestures.
 */
export default function Index() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const restoreIds = async () => {
      try {
        const flow = await getActiveFlow();
        if (flow) {
          // Restore IDs to in-memory store for cross-screen access
          restoreSessionIds(flow);
        }
      } catch (e) {
        console.error('[Index] Error restoring flow state:', e);
      } finally {
        setReady(true);
      }
    };

    restoreIds();
  }, []);

  // Re-restore IDs when screen regains focus (handles back navigation)
  useFocusEffect(
    useCallback(() => {
      const ensureIds = async () => {
        // Only restore if IDs are missing (they might have been cleared on remount)
        if (!getListId()) {
          const flow = await getActiveFlow();
          if (flow) {
            restoreSessionIds(flow);
          }
        }
      };
      ensureIds();
    }, [])
  );

  // Wait for IDs to be restored before rendering
  if (!ready) {
    return null;
  }

  // Render ItemInput directly - it will handle forwarding to the right screen
  return <ItemInput />;
}

/**
 * Restore session IDs from flow state to the in-memory store.
 */
function restoreSessionIds(flow: FlowState): void {
  if (flow.listId) {
    setListId(flow.listId);
  }
  if (flow.routePlanId) {
    setRoutePlanId(flow.routePlanId);
  }
}
