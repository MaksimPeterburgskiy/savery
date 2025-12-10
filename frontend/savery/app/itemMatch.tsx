import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Text } from '@/components/ui/text';
import { JobProgressOverlay } from '@/components/JobProgressOverlay';
import {
  getListId,
  getRoutePlanId,
  setListId,
  setRoutePlanId,
  getActiveFlow,
  loadFlowState,
  updateFlowState,
} from '@/lib/itemStore';
import { CardStyle } from '@/lib/theme';
import { useFocusEffect, useRouter } from 'expo-router';
import { ArrowRight } from 'lucide-react-native';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Image, ListRenderItem, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

// ===== TYPES =====

/** List item response from the API */
interface ListItemResponse {
  id: string;
  raw_text_qty: string | null;
  raw_text_item: string | null;
  item_name: string | null;
  qty_value: number | null;
  qty_unit: string | null;
  position: number;
}

/** Candidate response from the API */
interface CandidateResponse {
  id: string;
  list_item: ListItemResponse;
  product: {
    id: string;
    brand: string;
    name: string;
    size_text: string;
    image_url?: string;
  };
  score: number;
  rejected_by_user: boolean;
}

/** Group candidates by list_item.id */
type CandidatesByItem = Record<string, CandidateResponse[]>;

// ===== COMPONENTS =====

interface ItemCandidateCardProps {
  rawText: string;
  candidates: CandidateResponse[];
  selections: Record<string, boolean>;
  onToggle: (candidateId: string, selected: boolean) => void;
}

const ItemCandidateCard: React.FC<ItemCandidateCardProps> = ({
  rawText,
  candidates,
  selections,
  onToggle,
}) => {
  const selectedCount = candidates.filter((c) => selections[c.id]).length;

  return (
    <Card style={CardStyle.card}>
      <CardContent className="w-full p-0">
        <View style={CardStyle.headerSpaceBetween}>
          <Text style={CardStyle.mainText}>{rawText}</Text>
          <Text style={CardStyle.subText}>
            {selectedCount} of {candidates.length} selected
          </Text>
        </View>
      </CardContent>

      {/* Candidate rows */}
      <View style={{ gap: 2 }}>
        {candidates.map((candidate) => (
          <View key={candidate.id} style={CardStyle.itemRow}>
            {/* Product image or placeholder */}
            {candidate.product.image_url ? (
              <Image
                source={{ uri: candidate.product.image_url }}
                style={{ width: 48, height: 48, borderRadius: 8, marginRight: 12 }}
              />
            ) : (
              <View style={CardStyle.imagePlaceholder} />
            )}

            <View style={CardStyle.itemInfo}>
              <Text style={CardStyle.mainText}>
                {candidate.product.brand} {candidate.product.name}
              </Text>
              <Text style={CardStyle.subText}>
                {candidate.product.size_text} • Score: {Math.round(candidate.score)}%
              </Text>
            </View>

            <Checkbox
              style={CardStyle.checkContainer}
              accessibilityLabel={`Select ${candidate.product.name}`}
              checked={selections[candidate.id] ?? false}
              onCheckedChange={(checked: boolean) => onToggle(candidate.id, checked)}
            />
          </View>
        ))}
      </View>
    </Card>
  );
};

/** Card for items without any matches */
interface UnmatchedItemCardProps {
  item: ListItemResponse;
}

const UnmatchedItemCard: React.FC<UnmatchedItemCardProps> = ({ item }) => {
  return (
    <Card style={CardStyle.card}>
      <CardContent className="w-full p-0">
        <View style={CardStyle.headerSpaceBetween}>
          <Text style={CardStyle.mainText}>{item.raw_text_item ?? 'Unknown Item'}</Text>
          <Text style={[CardStyle.subText, { color: '#ef4444' }]}>No matches</Text>
        </View>
      </CardContent>
      <View style={{ paddingHorizontal: 16, paddingBottom: 16 }}>
        <Text style={[CardStyle.subText, { fontStyle: 'italic' }]}>
          No products found matching this item
        </Text>
      </View>
    </Card>
  );
};

// ===== SCREEN: itemMatch =====

function ItemMatch() {
  const router = useRouter();

  // ----- State -----
  const [candidatesByItem, setCandidatesByItem] = useState<CandidatesByItem>({});
  const [unmatchedItems, setUnmatchedItems] = useState<ListItemResponse[]>([]);
  const [selections, setSelections] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showConfirmOverlay, setShowConfirmOverlay] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJobType, setActiveJobType] = useState<'FANOUT' | 'OPTIMIZE' | null>(null);

  // Route plan ID and list ID from store
  const routePlanId = getRoutePlanId();
  const listId = getListId();

  // API base URL
  const apiBase = useMemo(
    () => process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api',
    []
  );

  // ----- API helper -----
  const apiFetch = useCallback(
    async (path: string, init?: RequestInit) => {
      const res = await fetch(`${apiBase}${path}`, {
        headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
        ...init,
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`API ${res.status}: ${body || res.statusText}`);
      }
      return res;
    },
    [apiBase]
  );

  // ----- Fetch candidates and list items -----
  useEffect(() => {
    const fetchData = async () => {
      if (!routePlanId || !listId) {
        setError('No route plan or list found');
        setLoading(false);
        return;
      }

      try {
        // Fetch candidates and list items in parallel
        const [candidatesRes, listItemsRes] = await Promise.all([
          apiFetch(`/route-plans/${routePlanId}/item-match-candidates`),
          apiFetch(`/shopping-lists/${listId}/items`),
        ]);

        const candidates: CandidateResponse[] = await candidatesRes.json();
        const allListItems: ListItemResponse[] = await listItemsRes.json();

        // Group candidates by list item
        const grouped = candidates.reduce((acc, c) => {
          const key = c.list_item.id;
          if (!acc[key]) acc[key] = [];
          acc[key].push(c);
          return acc;
        }, {} as CandidatesByItem);

        setCandidatesByItem(grouped);

        // Find items without any matches
        const matchedItemIds = new Set(Object.keys(grouped));
        const unmatched = allListItems.filter((item) => !matchedItemIds.has(item.id));
        setUnmatchedItems(unmatched);

        // Initialize selections based on rejected_by_user (selected = !rejected)
        const initialSelections: Record<string, boolean> = {};
        for (const candidate of candidates) {
          initialSelections[candidate.id] = !candidate.rejected_by_user;
        }
        setSelections(initialSelections);
      } catch (err) {
        console.error('Failed to fetch data', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [routePlanId, listId, apiFetch]);

  // ----- Check for active job on mount and forward if needed -----
  useEffect(() => {
    const checkFlowAndForward = async () => {
      const listId = getListId();
      if (!listId) return;

      const flow = await loadFlowState(listId);
      if (!flow) return;

      // If we should be at finalList, forward there
      if (['OPTIMIZED', 'COMPLETE'].includes(flow.currentStep)) {
        router.push('/finalList');
        return;
      }

      // Check for active job (for app restart resilience)
      if (flow.activeJobId && (flow.activeJobType === 'FANOUT' || flow.activeJobType === 'OPTIMIZE')) {
        setActiveJobId(flow.activeJobId);
        setActiveJobType(flow.activeJobType);
        setShowConfirmOverlay(true);
      }
    };

    checkFlowAndForward();
  }, [router]);

  // ----- Update flow state when screen gains focus (handles back navigation) -----
  useFocusEffect(
    useCallback(() => {
      const updateFlow = async () => {
        let currentListId = listId || getListId();
        let currentRoutePlanId = routePlanId || getRoutePlanId();

        // If IDs are missing, try to restore from flow state
        if (!currentListId || !currentRoutePlanId) {
          const flow = await getActiveFlow();
          if (flow?.listId && !currentListId) {
            setListId(flow.listId);
            currentListId = flow.listId;
          }
          if (flow?.routePlanId && !currentRoutePlanId) {
            setRoutePlanId(flow.routePlanId);
            currentRoutePlanId = flow.routePlanId;
          }
        }

        if (!currentListId) return;

        // Update flow state to MATCHED since user is on this screen
        // Skip if there's an active job (we're in the middle of processing)
        if (!showConfirmOverlay) {
          await updateFlowState(currentListId, {
            currentStep: 'MATCHED',
            routePlanId: currentRoutePlanId ?? undefined,
            activeJobId: undefined,
            activeJobType: undefined,
          });
        }
      };

      // Only update if not in initial loading state
      if (!loading) {
        updateFlow();
      }
    }, [listId, routePlanId, loading, showConfirmOverlay])
  );

  // ----- Selection logic -----
  const handleToggle = useCallback(
    async (candidateId: string, selected: boolean) => {
      // Update local state immediately for responsive UI
      setSelections((prev) => ({
        ...prev,
        [candidateId]: selected,
      }));

      // Sync with API: selected = !rejected_by_user
      try {
        await apiFetch(`/item-match-candidates/${candidateId}`, {
          method: 'PATCH',
          body: JSON.stringify({ rejected_by_user: !selected }),
        });
      } catch (err) {
        console.error('Failed to update candidate selection', err);
        // Revert local state on error
        setSelections((prev) => ({
          ...prev,
          [candidateId]: !selected,
        }));
      }
    },
    [apiFetch]
  );

  // Check if all items have at least one selection
  const allItemsHaveSelection = useMemo(() => {
    const itemIds = Object.keys(candidatesByItem);
    if (itemIds.length === 0) return false;

    return itemIds.every((itemId) => {
      const candidates = candidatesByItem[itemId];
      return candidates.some((c) => selections[c.id]);
    });
  }, [candidatesByItem, selections]);

  // ----- Confirm Items flow -----
  const handleConfirmItems = useCallback(async () => {
    if (!routePlanId) return;

    try {
      // 1. Mark unselected candidates as rejected
      const allCandidates = Object.values(candidatesByItem).flat();
      for (const candidate of allCandidates) {
        const isSelected = selections[candidate.id];
        if (!isSelected && !candidate.rejected_by_user) {
          await apiFetch(`/item-match-candidates/${candidate.id}`, {
            method: 'PATCH',
            body: JSON.stringify({ rejected_by_user: true }),
          });
        }
      }

      // 2. Start FANOUT job
      const fanoutRes = await apiFetch(`/route-plans/${routePlanId}/item-fanout-jobs`, {
        method: 'POST',
      });
      const fanoutJob = await fanoutRes.json();

      setActiveJobId(fanoutJob.id);
      setActiveJobType('FANOUT');
      setShowConfirmOverlay(true);

      // Update flow state
      const listId = getListId();
      if (listId) {
        await updateFlowState(listId, {
          currentStep: 'CONFIRMING',
          activeJobId: fanoutJob.id,
          activeJobType: 'FANOUT',
        });
      }
    } catch (err) {
      console.error('Failed to confirm items', err);
      setError(err instanceof Error ? err.message : 'Failed to confirm items');
    }
  }, [routePlanId, candidatesByItem, selections, apiFetch]);

  // ----- Job completion handlers -----
  const handleFanoutComplete = useCallback(async () => {
    if (!routePlanId) return;

    try {
      // Start OPTIMIZE job
      const optimizeRes = await apiFetch(`/route-plans/${routePlanId}/plan-route-jobs`, {
        method: 'POST',
      });
      const optimizeJob = await optimizeRes.json();

      setActiveJobId(optimizeJob.id);
      setActiveJobType('OPTIMIZE');

      // Update flow state
      const listId = getListId();
      if (listId) {
        await updateFlowState(listId, {
          activeJobId: optimizeJob.id,
          activeJobType: 'OPTIMIZE',
        });
      }
    } catch (err) {
      console.error('Failed to start optimize job', err);
      setError(err instanceof Error ? err.message : 'Failed to start optimization');
      setShowConfirmOverlay(false);
    }
  }, [routePlanId, apiFetch]);

  const handleOptimizeComplete = useCallback(async () => {
    setShowConfirmOverlay(false);
    setActiveJobId(null);
    setActiveJobType(null);

    // Update flow state to OPTIMIZED
    const listId = getListId();
    if (listId) {
      await updateFlowState(listId, {
        currentStep: 'OPTIMIZED',
        activeJobId: undefined,
        activeJobType: undefined,
      });
    }

    router.push('/finalList');
  }, [router]);

  const handleJobComplete = useCallback(
    async (job: any) => {
      if (activeJobType === 'FANOUT') {
        await handleFanoutComplete();
      } else if (activeJobType === 'OPTIMIZE') {
        await handleOptimizeComplete();
      }
    },
    [activeJobType, handleFanoutComplete, handleOptimizeComplete]
  );

  const handleJobCancel = useCallback(() => {
    setShowConfirmOverlay(false);
    setActiveJobId(null);
    setActiveJobType(null);
  }, []);

  // Retry handler - restarts the appropriate job based on activeJobType
  const handleJobRetry = useCallback(async () => {
    if (!routePlanId || !activeJobType) return;

    try {
      if (activeJobType === 'FANOUT') {
        // Restart FANOUT job
        const fanoutRes = await apiFetch(`/route-plans/${routePlanId}/item-fanout-jobs`, {
          method: 'POST',
        });
        const fanoutJob = await fanoutRes.json();
        setActiveJobId(fanoutJob.id);

        const listId = getListId();
        if (listId) {
          await updateFlowState(listId, {
            activeJobId: fanoutJob.id,
            activeJobType: 'FANOUT',
          });
        }
      } else if (activeJobType === 'OPTIMIZE') {
        // Restart OPTIMIZE job
        const optimizeRes = await apiFetch(`/route-plans/${routePlanId}/plan-route-jobs`, {
          method: 'POST',
        });
        const optimizeJob = await optimizeRes.json();
        setActiveJobId(optimizeJob.id);

        const listId = getListId();
        if (listId) {
          await updateFlowState(listId, {
            activeJobId: optimizeJob.id,
            activeJobType: 'OPTIMIZE',
          });
        }
      }
    } catch (err) {
      console.error('Failed to retry job', err);
      setError(err instanceof Error ? err.message : 'Failed to retry job');
      setShowConfirmOverlay(false);
    }
  }, [routePlanId, activeJobType, apiFetch]);

  // ----- Render -----
  // Loading state
  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator size="large" color="#4AA8D8" />
          <Text className="mt-4 text-gray-500">Loading product matches...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Error state
  if (error) {
    return (
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <Text className="text-center text-gray-600" style={{ fontSize: 16 }}>
            Unable to load product matches
          </Text>
          <Text className="mt-2 text-center text-gray-400" style={{ fontSize: 14 }}>
            Please check your connection and try again
          </Text>
          <Button
            variant="outline"
            className="mt-4"
            onPress={() => {
              setError(null);
              setLoading(true);
            }}
          >
            <Text>Retry</Text>
          </Button>
        </View>
      </SafeAreaView>
    );
  }

  // Empty state - only show if no candidates AND no unmatched items
  const itemEntries = Object.entries(candidatesByItem);
  if (itemEntries.length === 0 && unmatchedItems.length === 0) {
    return (
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <Text className="text-center text-gray-500">No items found.</Text>
          <Text className="mt-2 text-center text-sm text-gray-400">
            Try adding more items to your list or selecting different stores.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  // Combined list data: matched items first, then unmatched items
  type ListDataItem =
    | { type: 'matched'; itemId: string; candidates: CandidateResponse[] }
    | { type: 'unmatched'; item: ListItemResponse };

  const listData: ListDataItem[] = [
    ...itemEntries.map(([itemId, candidates]) => ({
      type: 'matched' as const,
      itemId,
      candidates,
    })),
    ...unmatchedItems.map((item) => ({
      type: 'unmatched' as const,
      item,
    })),
  ];

  const renderListItem: ListRenderItem<ListDataItem> = ({ item }) => {
    if (item.type === 'matched') {
      return (
        <ItemCandidateCard
          rawText={item.candidates[0]?.list_item.raw_text_item ?? 'Unknown Item'}
          candidates={item.candidates}
          selections={selections}
          onToggle={handleToggle}
        />
      );
    } else {
      return <UnmatchedItemCard item={item.item} />;
    }
  };

  return (
    <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
      <View style={{ flex: 1, marginHorizontal: 20, marginTop: 16 }}>
        <FlatList
          data={listData}
          keyExtractor={(item) =>
            item.type === 'matched' ? item.itemId : `unmatched-${item.item.id}`
          }
          renderItem={renderListItem}
          contentContainerStyle={{ paddingBottom: 140 }}
        />

        {/* Confirm Items Button - only shown when all items have at least one selection */}
        {allItemsHaveSelection && (
          <View style={{ position: 'absolute', left: 0, right: 0, bottom: 30 }}>
            <Button variant="continue" size="xl" onPress={handleConfirmItems}>
              <Text style={{ textAlign: 'center', fontSize: 20 }}>Confirm Items</Text>
              <ArrowRight size={20} color="white" />
            </Button>
          </View>
        )}
      </View>

      {/* Job Progress Overlay for FANOUT/OPTIMIZE jobs */}
      {routePlanId && (
        <JobProgressOverlay
          visible={showConfirmOverlay}
          title={activeJobType === 'FANOUT' ? 'Preparing items...' : 'Optimizing route...'}
          routePlanId={routePlanId}
          jobId={activeJobId}
          jobType={activeJobType ?? 'FANOUT'}
          onComplete={handleJobComplete}
          onCancel={handleJobCancel}
          onRetry={handleJobRetry}
        />
      )}
    </SafeAreaView>
  );
}

export default ItemMatch;
