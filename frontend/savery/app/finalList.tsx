import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Text } from '@/components/ui/text';
import { Button } from '@/components/ui/button';
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
import { useFocusEffect } from 'expo-router';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, ListRenderItem, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MapPin, Clock, DollarSign } from 'lucide-react-native';

// ===== TYPES =====

/** Plan item from the API - an item to purchase at a specific store */
interface PlanItemResponse {
  id: string;
  list_item: {
    id: string;
    item_name: string | null;
    raw_text_item: string | null;
  };
  store_product: {
    id: string;
    product: {
      brand: string;
      name: string;
    };
  };
  price_entry: {
    price: number;
    unit_price: number;
  } | null;
  qty: number;
  extended_price: number | null;
  is_checked: boolean;
  checked_at?: string;
}

/** Store visit from the API - a stop on the shopping route */
interface StoreVisitResponse {
  id: string;
  store: {
    id: string;
    name: string;
    address_line1: string;
  };
  sequence: number;
  travel_distance_m?: number;
  travel_time_sec?: number;
  subtotal_price?: number;
  plan_items: PlanItemResponse[];
}

/** Route plan summary from the API */
interface RoutePlanResponse {
  id: string;
  total_price?: number;
  total_travel_distance_m?: number;
  total_travel_time_sec?: number;
}

// ===== COMPONENTS =====

interface StoreVisitCardProps {
  visit: StoreVisitResponse;
  onItemCheck: (itemId: string, checked: boolean) => void;
}

const StoreVisitCard: React.FC<StoreVisitCardProps> = ({ visit, onItemCheck }) => {
  // Format distance for display
  const formatDistance = (meters?: number) => {
    if (!meters) return null;
    const miles = meters / 1609.34;
    return miles < 0.1 ? `${Math.round(meters)}m` : `${miles.toFixed(1)} mi`;
  };

  // Format time for display
  const formatTime = (seconds?: number) => {
    if (!seconds) return null;
    const minutes = Math.round(seconds / 60);
    return `${minutes} min`;
  };

  const distance = formatDistance(visit.travel_distance_m);
  const time = formatTime(visit.travel_time_sec);

  return (
    <Card style={CardStyle.card}>
      <CardContent className="w-full p-0">
        {/* Store header */}
        <View style={CardStyle.headerSpaceBetween}>
          <View style={{ flex: 1 }}>
            <Text style={CardStyle.mainText}>
              Stop {visit.sequence}: {visit.store.name}
            </Text>
            <Text style={[CardStyle.subText, { fontSize: 12 }]}>
              {visit.store.address_line1}
            </Text>
          </View>
          <Text style={CardStyle.mainText}>
            ${(visit.subtotal_price ?? 0).toFixed(2)}
          </Text>
        </View>

        {/* Travel info */}
        {(distance || time) && (
          <View style={{ flexDirection: 'row', gap: 12, marginTop: 4 }}>
            {distance && (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                <MapPin size={12} color="#666" />
                <Text style={[CardStyle.subText, { fontSize: 12 }]}>{distance}</Text>
              </View>
            )}
            {time && (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                <Clock size={12} color="#666" />
                <Text style={[CardStyle.subText, { fontSize: 12 }]}>{time}</Text>
              </View>
            )}
          </View>
        )}
      </CardContent>

      {/* Items at this store */}
      <View style={{ gap: 2, marginTop: 8 }}>
        {visit.plan_items.map((item) => (
          <View
            key={item.id}
            style={[
              CardStyle.itemRow,
              item.is_checked && { opacity: 0.6 },
            ]}
          >
            <View style={CardStyle.imagePlaceholder} />

            <View style={CardStyle.itemInfo}>
              <Text
                style={[
                  CardStyle.mainText,
                  item.is_checked && { textDecorationLine: 'line-through' },
                ]}
              >
                {item.store_product.product.brand} {item.store_product.product.name}
              </Text>
              <Text style={CardStyle.subText}>
                {item.list_item.raw_text_item || item.list_item.item_name || 'Item'}
                {item.qty > 1 && ` × ${item.qty}`}
              </Text>
              {item.price_entry && (
                <Text style={[CardStyle.subText, { fontSize: 12 }]}>
                  ${item.price_entry.price.toFixed(2)}
                  {item.extended_price && item.qty > 1 && (
                    <Text> (${item.extended_price.toFixed(2)} total)</Text>
                  )}
                </Text>
              )}
            </View>

            <Checkbox
              style={CardStyle.checkContainer}
              accessibilityLabel={`Mark ${item.store_product.product.name} as purchased`}
              checked={item.is_checked}
              onCheckedChange={(checked: boolean) => onItemCheck(item.id, checked)}
            />
          </View>
        ))}
      </View>
    </Card>
  );
};

// ===== SCREEN: finalList =====

function FinalList() {
  // ----- State -----
  const [visits, setVisits] = useState<StoreVisitResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [routePlan, setRoutePlan] = useState<RoutePlanResponse | null>(null);

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

  // ----- Fetch route plan and store visits -----
  useEffect(() => {
    const fetchData = async () => {
      if (!routePlanId) {
        setError('No route plan found');
        setLoading(false);
        return;
      }

      try {
        // Fetch route plan and store visits in parallel
        const [planRes, visitsRes] = await Promise.all([
          apiFetch(`/route-plans/${routePlanId}`),
          apiFetch(`/route-plans/${routePlanId}/plan-store-visits`),
        ]);

        const plan: RoutePlanResponse = await planRes.json();
        const visitsData: StoreVisitResponse[] = await visitsRes.json();

        setRoutePlan(plan);
        setVisits(visitsData.sort((a, b) => a.sequence - b.sequence));
      } catch (err) {
        console.error('Failed to fetch final list data', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [routePlanId, apiFetch]);

  // ----- Verify flow state on mount -----
  useEffect(() => {
    const verifyFlowState = async () => {
      if (!listId) return;
      const flow = await loadFlowState(listId);
      // Could add navigation logic here if needed
    };
    verifyFlowState();
  }, [listId]);

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

        // Update flow state to OPTIMIZED since user is on this screen
        // (unless they've already completed everything)
        const flow = await loadFlowState(currentListId);
        if (flow?.currentStep !== 'COMPLETE') {
          await updateFlowState(currentListId, {
            currentStep: 'OPTIMIZED',
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
    }, [listId, routePlanId, loading])
  );

  // ----- Check item logic -----
  const handleItemCheck = useCallback(
    async (itemId: string, checked: boolean) => {
      if (!routePlanId) return;

      // Optimistic update
      setVisits((prev) =>
        prev.map((visit) => ({
          ...visit,
          plan_items: visit.plan_items.map((item) =>
            item.id === itemId
              ? { ...item, is_checked: checked, checked_at: checked ? new Date().toISOString() : undefined }
              : item
          ),
        }))
      );

      try {
        // API call to update item
        await apiFetch(`/route-plans/${routePlanId}/plan-items/${itemId}`, {
          method: 'PATCH',
          body: JSON.stringify({ is_checked: checked }),
        });

        // Check if all items are now checked
        const allChecked = visits.every((v) =>
          v.plan_items.every((i) => (i.id === itemId ? checked : i.is_checked))
        );

        if (allChecked && listId) {
          await updateFlowState(listId, { currentStep: 'COMPLETE' });
        }
      } catch (err) {
        console.error('Failed to update item', err);
        // Revert optimistic update on error
        setVisits((prev) =>
          prev.map((visit) => ({
            ...visit,
            plan_items: visit.plan_items.map((item) =>
              item.id === itemId ? { ...item, is_checked: !checked } : item
            ),
          }))
        );
      }
    },
    [routePlanId, listId, visits, apiFetch]
  );

  // ----- Calculate totals -----
  const totalItems = useMemo(
    () => visits.reduce((sum, v) => sum + v.plan_items.length, 0),
    [visits]
  );

  const checkedItems = useMemo(
    () => visits.reduce((sum, v) => sum + v.plan_items.filter((i) => i.is_checked).length, 0),
    [visits]
  );

  const formatTotalDistance = (meters?: number) => {
    if (!meters) return null;
    const miles = meters / 1609.34;
    return `${miles.toFixed(1)} mi`;
  };

  const formatTotalTime = (seconds?: number) => {
    if (!seconds) return null;
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    const remainingMins = minutes % 60;
    return `${hours}h ${remainingMins}m`;
  };

  // ----- Render list item -----
  const renderVisit: ListRenderItem<StoreVisitResponse> = ({ item }) => (
    <StoreVisitCard visit={item} onItemCheck={handleItemCheck} />
  );

  // ----- Loading state -----
  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator size="large" color="#4AA8D8" />
          <Text className="mt-4 text-gray-500">Loading your shopping route...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // ----- Error state -----
  if (error) {
    return (
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <Text className="text-center text-gray-600" style={{ fontSize: 16 }}>
            Unable to load your shopping route
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

  // ----- Empty state -----
  if (visits.length === 0) {
    return (
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <Text className="text-center text-gray-500">No store visits found.</Text>
          <Text className="mt-2 text-center text-sm text-gray-400">
            Your optimized route will appear here once items are matched.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
      <View style={{ flex: 1, marginHorizontal: 20, marginTop: 16 }}>
        {/* Summary header */}
        <View
          style={{
            backgroundColor: '#4AA8D8',
            borderRadius: 12,
            padding: 16,
            marginBottom: 16,
          }}
        >
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <View>
              <Text style={{ color: 'white', fontSize: 24, fontWeight: '700' }}>
                ${(routePlan?.total_price ?? 0).toFixed(2)}
              </Text>
              <Text style={{ color: 'white', opacity: 0.9 }}>
                Estimated Total
              </Text>
            </View>

            <View style={{ alignItems: 'flex-end' }}>
              <Text style={{ color: 'white', fontSize: 18, fontWeight: '600' }}>
                {visits.length} {visits.length === 1 ? 'stop' : 'stops'}
              </Text>
              <Text style={{ color: 'white', opacity: 0.9 }}>
                {checkedItems}/{totalItems} items
              </Text>
            </View>
          </View>

          {/* Travel summary */}
          {(routePlan?.total_travel_distance_m || routePlan?.total_travel_time_sec) && (
            <View style={{ flexDirection: 'row', gap: 16, marginTop: 12 }}>
              {routePlan?.total_travel_distance_m && (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                  <MapPin size={14} color="white" />
                  <Text style={{ color: 'white', opacity: 0.9 }}>
                    {formatTotalDistance(routePlan.total_travel_distance_m)}
                  </Text>
                </View>
              )}
              {routePlan?.total_travel_time_sec && (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                  <Clock size={14} color="white" />
                  <Text style={{ color: 'white', opacity: 0.9 }}>
                    {formatTotalTime(routePlan.total_travel_time_sec)}
                  </Text>
                </View>
              )}
            </View>
          )}
        </View>

        {/* Store visits list */}
        <FlatList
          data={visits}
          keyExtractor={(visit) => visit.id}
          renderItem={renderVisit}
          contentContainerStyle={{ paddingBottom: 40 }}
        />
      </View>
    </SafeAreaView>
  );
}

export default FinalList;
