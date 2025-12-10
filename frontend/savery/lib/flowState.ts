// Flow State Persistence
// AsyncStorage-based flow state management for app restart resilience and back-navigation handling.
// Each shopping list has its own flow state, keyed by listId.

import AsyncStorage from '@react-native-async-storage/async-storage';

// Flow steps represent progression through the shopping optimization flow
export type FlowStep =
  | 'ITEMS_ENTERED'   // itemInput complete, has listId
  | 'STORES_SELECTED' // searchSelect complete, has routePlanId
  | 'MATCHING'        // MATCH job in progress
  | 'MATCHED'         // itemMatch screen ready
  | 'CONFIRMING'      // FANOUT/OPTIMIZE in progress
  | 'OPTIMIZED'       // finalList ready
  | 'COMPLETE';       // All items checked off

export type JobType = 'MATCH' | 'FANOUT' | 'OPTIMIZE';

export interface FlowState {
  listId: string;                        // Primary key - always present
  routePlanId?: string;                  // Set when route plan created (searchSelect)
  currentStep: FlowStep;
  activeJobId?: string;
  activeJobType?: JobType;
  lastUpdated: string;                   // ISO timestamp
}

const FLOW_STATE_PREFIX = 'flowState_';
const ACTIVE_FLOWS_KEY = 'activeFlowListIds';

// Debug logging - set to true to see flow state operations
const DEBUG_FLOW = false;
const log = (...args: any[]) => DEBUG_FLOW && console.log('[FlowState]', ...args);

/**
 * Save current flow state (keyed by listId)
 */
export async function saveFlowState(state: FlowState): Promise<void> {
  const key = `${FLOW_STATE_PREFIX}${state.listId}`;
  const stateToSave: FlowState = {
    ...state,
    lastUpdated: new Date().toISOString(),
  };

  log('saveFlowState:', JSON.stringify(stateToSave, null, 2));
  await AsyncStorage.setItem(key, JSON.stringify(stateToSave));

  // Track this listId in the active flows list
  await addToActiveFlows(state.listId);
  log('Added to active flows, listId:', state.listId);
}

/**
 * Load flow state for a shopping list
 */
export async function loadFlowState(listId: string): Promise<FlowState | null> {
  const key = `${FLOW_STATE_PREFIX}${listId}`;
  log('loadFlowState: loading for listId:', listId, 'key:', key);
  const stored = await AsyncStorage.getItem(key);

  if (!stored) {
    log('loadFlowState: no stored state found');
    return null;
  }

  try {
    const parsed = JSON.parse(stored) as FlowState;
    log('loadFlowState: found state:', JSON.stringify(parsed, null, 2));
    return parsed;
  } catch (e) {
    log('loadFlowState: parse error:', e);
    return null;
  }
}

/**
 * Get the active flow (most recent with in-progress work)
 * Returns the flow state that should be resumed on app restart
 */
export async function getActiveFlow(): Promise<FlowState | null> {
  log('getActiveFlow: starting...');
  const activeListIds = await getActiveFlowListIds();
  log('getActiveFlow: activeListIds:', activeListIds);

  if (activeListIds.length === 0) {
    log('getActiveFlow: no active list IDs found, returning null');
    return null;
  }

  // Load all active flow states
  const flows: FlowState[] = [];
  for (const listId of activeListIds) {
    const flow = await loadFlowState(listId);
    log('getActiveFlow: loaded flow for listId:', listId, '-> step:', flow?.currentStep);
    if (flow && flow.currentStep !== 'COMPLETE') {
      flows.push(flow);
    } else {
      log('getActiveFlow: skipping flow (null or COMPLETE)');
    }
  }

  log('getActiveFlow: found', flows.length, 'non-complete flows');

  if (flows.length === 0) {
    log('getActiveFlow: no active flows found, returning null');
    return null;
  }

  // Prioritize flows with active jobs, then by most recent update
  const flowsWithJobs = flows.filter(f => f.activeJobId);
  if (flowsWithJobs.length > 0) {
    const selected = flowsWithJobs.sort((a, b) =>
      new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime()
    )[0];
    log('getActiveFlow: returning flow with active job:', selected.listId, 'step:', selected.currentStep);
    return selected;
  }

  // Return most recently updated flow
  const selected = flows.sort((a, b) =>
    new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime()
  )[0];
  log('getActiveFlow: returning most recent flow:', selected.listId, 'step:', selected.currentStep);
  return selected;
}

/**
 * Clear flow state (on complete or explicit reset)
 */
export async function clearFlowState(listId: string): Promise<void> {
  const key = `${FLOW_STATE_PREFIX}${listId}`;
  await AsyncStorage.removeItem(key);
  await removeFromActiveFlows(listId);
}

/**
 * Determine which screen to navigate to based on state
 */
export function getTargetScreen(state: FlowState): string {
  switch (state.currentStep) {
    case 'OPTIMIZED':
    case 'COMPLETE':
      return '/finalList';
    case 'MATCHED':
    case 'CONFIRMING':
      return '/itemMatch';
    case 'STORES_SELECTED':
    case 'MATCHING':
      return '/searchSelect';
    case 'ITEMS_ENTERED':
    default:
      return '/itemInput';
  }
}

/**
 * Determine which screen to navigate to when there's an active job
 */
export function getTargetScreenForActiveJob(state: FlowState): string {
  switch (state.activeJobType) {
    case 'MATCH':
      return '/searchSelect';
    case 'FANOUT':
    case 'OPTIMIZE':
      return '/itemMatch';
    default:
      return '/itemInput';
  }
}

/**
 * Create initial flow state for a new shopping list
 */
export function createInitialFlowState(listId: string): FlowState {
  return {
    listId,
    currentStep: 'ITEMS_ENTERED',
    lastUpdated: new Date().toISOString(),
  };
}

/**
 * Update flow state with partial changes
 */
export async function updateFlowState(
  listId: string,
  updates: Partial<Omit<FlowState, 'listId'>>
): Promise<FlowState | null> {
  log('updateFlowState: listId:', listId, 'updates:', updates);
  const existing = await loadFlowState(listId);

  if (!existing) {
    log('updateFlowState: no existing state found, returning null');
    return null;
  }

  const updated: FlowState = {
    ...existing,
    ...updates,
    listId, // Ensure listId is never overwritten
    lastUpdated: new Date().toISOString(),
  };

  log('updateFlowState: saving updated state');
  await saveFlowState(updated);
  return updated;
}

// ----- Internal helpers for tracking active flows -----

async function getActiveFlowListIds(): Promise<string[]> {
  const stored = await AsyncStorage.getItem(ACTIVE_FLOWS_KEY);
  log('getActiveFlowListIds: raw stored value:', stored);

  if (!stored) {
    log('getActiveFlowListIds: no stored value, returning []');
    return [];
  }

  try {
    const parsed = JSON.parse(stored) as string[];
    log('getActiveFlowListIds: parsed:', parsed);
    return parsed;
  } catch (e) {
    log('getActiveFlowListIds: parse error:', e);
    return [];
  }
}

async function addToActiveFlows(listId: string): Promise<void> {
  const ids = await getActiveFlowListIds();

  if (!ids.includes(listId)) {
    ids.push(listId);
    log('addToActiveFlows: adding listId:', listId, 'new list:', ids);
    await AsyncStorage.setItem(ACTIVE_FLOWS_KEY, JSON.stringify(ids));
  } else {
    log('addToActiveFlows: listId already in list:', listId);
  }
}

async function removeFromActiveFlows(listId: string): Promise<void> {
  const ids = await getActiveFlowListIds();
  const filtered = ids.filter(id => id !== listId);
  log('removeFromActiveFlows: removing listId:', listId, 'new list:', filtered);
  await AsyncStorage.setItem(ACTIVE_FLOWS_KEY, JSON.stringify(filtered));
}
