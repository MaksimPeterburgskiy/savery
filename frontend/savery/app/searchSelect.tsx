import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Text } from '@/components/ui/text';
import { JobProgressOverlay } from '@/components/JobProgressOverlay';
import { distanceInMiles } from '@/lib/geo';
import * as Location from 'expo-location';
import {
  getListId,
  getRoutePlanId,
  setListId,
  setRoutePlanId,
  getActiveFlow,
  loadFlowState,
  updateFlowState,
} from '@/lib/itemStore';
import { Link, useFocusEffect, useRouter } from 'expo-router';
import { ArrowRight, MapPin, Scale, Store, X } from 'lucide-react-native';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Keyboard, KeyboardAvoidingView, Platform, ScrollView, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

// ===== TYPES =====

/** Optimization mode values matching backend OptimizationMode enum */
type OptimizationMode = 'SPEED' | 'BALANCED' | 'PRICE';

/** Selected store from the API */
interface SelectedStore {
  id: string;
  name: string;
  address_line1: string;
  city: string;
  region: string;
  postal_code: string;
  longitude?: number;
  latitude?: number;
  distance_mi?: number; // computed client-side from user location
}

/** Route plan from the API */
interface RoutePlan {
  id: string;
  list_id: string;
  status: string;
  opt_mode: OptimizationMode;
  lowest_unit_price: boolean;
  max_stores: number;
  selected_stores: SelectedStore[];
  user_longitude?: number;
  user_latitude?: number;
  total_price?: number;
  total_distance_m?: number;
  total_travel_sec?: number;
}

// ===== SCREEN: searchSelect =====
function SearchSelect() {
  const router = useRouter();

  // ----- State -----
  // Search mode: Speed, Balanced, or Price (maps to backend OptimizationMode)
  const [searchMode, setSearchMode] = useState<OptimizationMode>('BALANCED');
  // Whether to compare by lowest unit price
  const [unitPriceMode, setUnitPriceMode] = useState(false);
  // Maximum number of stores to visit (as string for input field)
  const [maxStores, setMaxStores] = useState('3');
  // Selected stores from the route plan
  const [selectedStores, setSelectedStores] = useState<SelectedStore[]>([]);
  // Route plan ID from the API
  const [routePlanId, setLocalRoutePlanId] = useState<string | null>(null);
  // True while fetching initial data
  const [loading, setLoading] = useState(true);
  // Error state for initial load
  const [error, setError] = useState<string | null>(null);
  // Job tracking state for MATCH job
  const [showMatchOverlay, setShowMatchOverlay] = useState(false);
  const [matchJobId, setMatchJobId] = useState<string | null>(null);
  // Timers for debouncing API updates
  const syncTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  // Base URL for API calls
  const API_BASE = useMemo(
    () => process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api',
    []
  );
  // User identifier for the API
  const CLIENT_ID = 'user';
  // Keyboard state for floating done button
  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const keyboardHeight = useRef(new Animated.Value(0)).current;

  // ----- API utilities -----
  // Helper function for making API requests with error handling
  const apiFetch = useCallback(
    async (path: string, init?: RequestInit) => {
      const res = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
        ...init,
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`API ${res.status}: ${body || res.statusText}`);
      }
      return res;
    },
    [API_BASE]
  );

  // Convert API response to RoutePlan format
  const mapApiRoutePlan = useCallback((apiPlan: any): RoutePlan => ({
    id: apiPlan.id,
    list_id: apiPlan.list_id,
    status: apiPlan.status,
    opt_mode: apiPlan.opt_mode as OptimizationMode,
    lowest_unit_price: apiPlan.lowest_unit_price,
    max_stores: apiPlan.max_stores,
    selected_stores: (apiPlan.selected_stores || []).map((store: any) => ({
      id: store.id,
      name: store.name,
      address_line1: store.address_line1,
      city: store.city,
      region: store.region,
      postal_code: store.postal_code,
      longitude: store.longitude,
      latitude: store.latitude,
    })),
    user_longitude: apiPlan.user_longitude,
    user_latitude: apiPlan.user_latitude,
    total_price: apiPlan.total_price,
    total_distance_m: apiPlan.total_distance_m,
    total_travel_sec: apiPlan.total_travel_sec,
  }), []);

  // ----- Effects -----
  // On mount: fetch existing route plan or create a new one
  // Also check flow state to see if we should forward to a later screen
  useEffect(() => {
    let cancelled = false;
    const bootstrap = async () => {
      try {
        let listId = getListId();

        // If listId is missing, try to restore from flow state (handles back navigation)
        if (!listId) {
          const flow = await getActiveFlow();
          if (flow?.listId) {
            setListId(flow.listId);
            if (flow.routePlanId) {
              setRoutePlanId(flow.routePlanId);
            }
            listId = flow.listId;
          }
        }

        if (!listId) {
          console.error('No list ID available');
          setError('No shopping list found');
          setLoading(false);
          return;
        }

        // Check flow state - if we should be at a later screen, forward there
        const existingFlow = await loadFlowState(listId);
        if (existingFlow && ['MATCHED', 'CONFIRMING', 'OPTIMIZED', 'COMPLETE'].includes(existingFlow.currentStep)) {
          if (cancelled) return;
          router.push('/itemMatch');
          return;
        }

        // Try to get existing route plans for this list
        const existing = await apiFetch(`/shopping-lists/${listId}/route-plans`);
        const plans = await existing.json();
        let selected = plans?.[0];

        // If no route plan exists, create one
        if (!selected) {
          const created = await apiFetch(`/shopping-lists/${listId}/route-plans`, {
            method: 'POST',
            body: JSON.stringify({
              client_id: CLIENT_ID,
              opt_mode: 'BALANCED',
              lowest_unit_price: false,
              max_stores: 3,
            }),
          });
          selected = await created.json();
        }

        if (cancelled) return;

        const routePlan = mapApiRoutePlan(selected);
        setLocalRoutePlanId(routePlan.id);
        setRoutePlanId(routePlan.id); // Store in global store for cross-screen access
        setSearchMode(routePlan.opt_mode);
        setUnitPriceMode(routePlan.lowest_unit_price);
        setMaxStores(String(routePlan.max_stores));
        setSelectedStores(routePlan.selected_stores);
      } catch (err) {
        console.error('Failed to initialize route plan', err);
        if (!cancelled) setError('Failed to load');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    bootstrap();
    // Cleanup: cancel pending work if component unmounts
    return () => {
      cancelled = true;
      Object.values(syncTimers.current).forEach(clearTimeout);
    };
  }, [apiFetch, mapApiRoutePlan, router]);

  // Refresh route plan when screen regains focus (e.g., returning from map or back navigation)
  // Also update flow state to reflect user navigated back to this screen
  useFocusEffect(
    useCallback(() => {
      const refreshRoutePlan = async () => {
        let planId = routePlanId || getRoutePlanId();
        let listId = getListId();

        // If planId is missing, try to restore from flow state (handles back navigation)
        if (!planId) {
          const flow = await getActiveFlow();
          if (flow?.routePlanId) {
            setRoutePlanId(flow.routePlanId);
            planId = flow.routePlanId;
          }
          if (flow?.listId && !listId) {
            setListId(flow.listId);
            listId = flow.listId;
          }
        }

        if (!planId) return;

        try {
          // Update flow state to STORES_SELECTED since user is on this screen
          // This handles the case where user navigated back from a later screen
          if (listId) {
            await updateFlowState(listId, {
              currentStep: 'STORES_SELECTED',
              routePlanId: planId,
              activeJobId: undefined,
              activeJobType: undefined,
            });
          }

          const res = await apiFetch(`/route-plans/${planId}`);
          const apiPlan = await res.json();
          const plan = mapApiRoutePlan(apiPlan);

          // Update local state if needed
          if (!routePlanId) {
            setLocalRoutePlanId(plan.id);
          }

          // Compute distances if user location is available
          if (plan.user_longitude != null && plan.user_latitude != null) {
            const userCoords = { latitude: plan.user_latitude, longitude: plan.user_longitude };
            const storesWithDist = plan.selected_stores.map((store) => {
              if (store.longitude == null || store.latitude == null) return store;
              const dist = distanceInMiles(userCoords, {
                latitude: store.latitude,
                longitude: store.longitude,
              });
              return { ...store, distance_mi: Math.round(dist * 10) / 10 };
            });
            setSelectedStores(storesWithDist);
          } else {
            setSelectedStores(plan.selected_stores);
          }
        } catch (err) {
          console.error('Failed to refresh route plan on focus', err);
        }
      };

      // Refresh on focus - either if we have a route plan, or if we need to restore one
      if (!loading) {
        refreshRoutePlan();
      }
    }, [routePlanId, loading, apiFetch, mapApiRoutePlan])
  );

  // Keyboard event listeners for floating done button (works on iOS and Android)
  useEffect(() => {
    // iOS uses 'will' events for smoother animation, Android uses 'did' events
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';

    const onKeyboardShow = (e: any) => {
      setKeyboardVisible(true);
      Animated.timing(keyboardHeight, {
        toValue: e.endCoordinates.height,
        duration: Platform.OS === 'ios' ? (e.duration - 200|| 150) : 150,
        useNativeDriver: false,
      }).start();
    };

    const onKeyboardHide = (e: any) => {
      Animated.timing(keyboardHeight, {
        toValue: 0,
        duration: Platform.OS === 'ios' ? (e.duration - 200 || 150) : 150,
        useNativeDriver: false,
      }).start(() => setKeyboardVisible(false));
    };

    const showSub = Keyboard.addListener(showEvent, onKeyboardShow);
    const hideSub = Keyboard.addListener(hideEvent, onKeyboardHide);

    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, [keyboardHeight]);

  // ----- Route plan sync helpers -----
  // Send a route plan update to the API
  const syncRoutePlan = useCallback(
    async (updates: { opt_mode?: OptimizationMode; lowest_unit_price?: boolean; max_stores?: number }) => {
      if (!routePlanId) return;
      try {
        const res = await apiFetch(`/route-plans/${routePlanId}`, {
          method: 'PATCH',
          body: JSON.stringify(updates),
        });
        const updated = await res.json();
        const routePlan = mapApiRoutePlan(updated);
        setSelectedStores(routePlan.selected_stores);
      } catch (err) {
        console.error('Failed to sync route plan', err);
      }
    },
    [apiFetch, routePlanId, mapApiRoutePlan]
  );

  // Debounce sync calls so we don't spam API while user changes settings
  const scheduleSync = useCallback(
    (key: string, updates: { opt_mode?: OptimizationMode; lowest_unit_price?: boolean; max_stores?: number }) => {
      // Clear any existing timer for this key
      if (syncTimers.current[key]) {
        clearTimeout(syncTimers.current[key]);
      }
      // Schedule new sync after 300ms
      syncTimers.current[key] = setTimeout(() => syncRoutePlan(updates), 300);
    },
    [syncRoutePlan]
  );

  // ----- Event handlers -----
  // Handle search mode tab change
  const handleSearchModeChange = useCallback(
    (value: string) => {
      const mode = value as OptimizationMode;
      setSearchMode(mode);
      scheduleSync('opt_mode', { opt_mode: mode });
    },
    [scheduleSync]
  );

  // Handle unit price mode toggle
  const handleUnitPriceModeChange = useCallback(
    (checked: boolean) => {
      setUnitPriceMode(checked);
      scheduleSync('lowest_unit_price', { lowest_unit_price: checked });
    },
    [scheduleSync]
  );

  // Handle max stores input change
  const handleMaxStoresChange = useCallback(
    (value: string) => {
    // Only allow numeric input
    const numeric = value.replace(/[^0-9]/g, '');
    setMaxStores(numeric);
      const parsed = parseInt(numeric, 10);
      if (parsed >= 1) {
        scheduleSync('max_stores', { max_stores: parsed });
      }
    },
    [scheduleSync]
  );

  // Handle removing a store from selection
  const handleRemoveStore = useCallback(
    async (storeId: string) => {
      if (!routePlanId) return;
      // Optimistic update
      setSelectedStores((prev) => prev.filter((s) => s.id !== storeId));
      try {
        const res = await apiFetch(`/route-plans/${routePlanId}/selected-stores/${storeId}`, {
          method: 'DELETE',
        });
        const updated = await res.json();
        const routePlan = mapApiRoutePlan(updated);
        setSelectedStores(routePlan.selected_stores);
      } catch (err) {
        console.error('Failed to remove store', err);
        // Revert on error - refetch the route plan
        try {
          const res = await apiFetch(`/route-plans/${routePlanId}`);
          const updated = await res.json();
          const routePlan = mapApiRoutePlan(updated);
          setSelectedStores(routePlan.selected_stores);
        } catch {
          // Ignore refetch errors
        }
      }
    },
    [apiFetch, routePlanId, mapApiRoutePlan]
  );

  // ----- Match Items handlers -----
  // Handle Match Items button press - starts MATCH job
  const handleMatchItems = useCallback(async () => {
    if (!routePlanId) return;

    try {
      // Get user's current location and persist to route plan before matching
      try {
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status === 'granted') {
          const location = await Location.getCurrentPositionAsync({
            accuracy: Location.Accuracy.Balanced,
          });
          // PATCH the route plan with user's location
          await apiFetch(`/route-plans/${routePlanId}`, {
            method: 'PATCH',
            body: JSON.stringify({
              user_longitude: location.coords.longitude,
              user_latitude: location.coords.latitude,
            }),
          });
        }
      } catch (locationErr) {
        // Location errors are non-fatal - continue with match job
        console.warn('Could not get user location:', locationErr);
      }

      // POST to create a new MATCH job
      const res = await apiFetch(`/route-plans/${routePlanId}/item-match-jobs`, {
        method: 'POST',
      });
      const job = await res.json();
      setMatchJobId(job.id);
      setShowMatchOverlay(true);

      // Update flow state to MATCHING
      const listId = getListId();
      if (listId) {
        await updateFlowState(listId, {
          currentStep: 'MATCHING',
          activeJobId: job.id,
          activeJobType: 'MATCH',
          routePlanId,
        });
      }
    } catch (err) {
      console.error('Failed to start match job', err);
    }
  }, [routePlanId, apiFetch]);

  // Handle match job completion
  const handleMatchComplete = useCallback(async () => {
    setShowMatchOverlay(false);
    setMatchJobId(null);

    // Update flow state to MATCHED
    const listId = getListId();
    if (listId) {
      await updateFlowState(listId, {
        currentStep: 'MATCHED',
        activeJobId: undefined,
        activeJobType: undefined,
      });
    }

    router.push('/itemMatch');
  }, [router]);

  // Handle match job cancel
  const handleMatchCancel = useCallback(() => {
    setShowMatchOverlay(false);
    setMatchJobId(null);
  }, []);

  // Retry handler - restarts the MATCH job
  const handleMatchRetry = useCallback(async () => {
    if (!routePlanId) return;

    try {
      const res = await apiFetch(`/route-plans/${routePlanId}/item-match-jobs`, {
        method: 'POST',
      });
      const job = await res.json();
      setMatchJobId(job.id);

      const listId = getListId();
      if (listId) {
        await updateFlowState(listId, {
          activeJobId: job.id,
          activeJobType: 'MATCH',
        });
      }
    } catch (err) {
      console.error('Failed to retry match job', err);
      setShowMatchOverlay(false);
    }
  }, [routePlanId, apiFetch]);

  // Check for active MATCH job on mount (for app restart resilience)
  useEffect(() => {
    const checkActiveJob = async () => {
      const listId = getListId();
      if (!listId) return;

      const flow = await loadFlowState(listId);
      if (flow?.activeJobId && flow.activeJobType === 'MATCH' && flow.routePlanId) {
        // Resume showing the overlay for the active job
        setMatchJobId(flow.activeJobId);
        setShowMatchOverlay(true);
      }
    };

    checkActiveJob();
  }, []);

  // ----- Render -----
  // Show loading state while fetching initial data
  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <Text className="text-gray-500">Loading route plan…</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Show error state with retry option
  if (error) {
    return (
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <Text className="text-center text-gray-600" style={{ fontSize: 16 }}>
            Unable to load search settings
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

  return (
    <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
      <KeyboardAvoidingView behavior="padding" style={{ flex: 1 }}>
        <View style={{ flex: 1, marginHorizontal: 20, marginTop: 16 }}>
          {/* Scrollable content */}
          <ScrollView
            style={{ flex: 1 }}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={{ paddingBottom: 20 }}>
          {/* Search Options Card */}
          <Card className="mb-4 rounded-2xl bg-white/80 py-0 dark:bg-zinc-900/80">
            <CardContent className="px-4 py-4">
              {/* Search Mode Tabs */}
              <Text className="mb-3 text-sm font-semibold text-gray-600 dark:text-gray-400">
                Search Mode
              </Text>
                <Tabs value={searchMode} onValueChange={handleSearchModeChange}>
                <TabsList className="w-full">
                    <TabsTrigger value="SPEED" className="flex-1">
                    <Text>Speed</Text>
                  </TabsTrigger>
                    <TabsTrigger value="BALANCED" className="flex-1">
                    <Text>Balanced</Text>
                  </TabsTrigger>
                    <TabsTrigger value="PRICE" className="flex-1">
                    <Text>Price</Text>
                  </TabsTrigger>
                </TabsList>
              </Tabs>

              {/* Separator */}
              <View className="my-4 h-px bg-gray-200 dark:bg-gray-700" />

              {/* Max Stores Setting */}
              <View className="mb-4 flex-row items-center justify-between">
                <View className="flex-1">
                  <View className="flex-row items-center gap-2">
                    <Store size={18} color="#4AA8D8" />
                    <Text className="font-medium">Max Stores</Text>
                  </View>
                  <Text className="mt-1 text-xs text-gray-500">
                    Limit the number of stores to visit
                  </Text>
                </View>
                  <Input
                    value={maxStores}
                    onChangeText={handleMaxStoresChange}
                    keyboardType="number-pad"
                    maxLength={2}
                    className="w-16 text-center"
                    placeholder="3"
                    inputAccessoryViewID=""
                  />
              </View>

              {/* Separator */}
              <View className="my-2 h-px bg-gray-200 dark:bg-gray-700" />

              {/* Unit Price Mode Toggle */}
              <View className="mt-2 flex-row items-center justify-between">
                <View className="flex-1 pr-4">
                  <View className="flex-row items-center gap-2">
                    <Scale size={18} color="#4AA8D8" />
                    <Text className="font-medium">Lowest Unit Price</Text>
                  </View>
                  <Text className="mt-1 text-xs text-gray-500">
                    Compare items by price per unit
                  </Text>
                </View>
                <Switch
                  checked={unitPriceMode}
                    onCheckedChange={handleUnitPriceModeChange}
                  className="scale-125"
                />
              </View>
            </CardContent>
          </Card>

          {/* Selected Stores */}
          <Card className="mb-4 rounded-2xl bg-white/80 py-0 dark:bg-zinc-900/80">
            <CardContent className="px-4 py-4">
              <View className="mb-3 flex-row items-center justify-between">
                <View className="flex-row items-center gap-2">
                  <Store size={18} color="#4AA8D8" />
                  <Text className="text-sm font-semibold text-gray-600 dark:text-gray-400">
                    Selected Stores
                  </Text>
                </View>
                <Text className="text-xs text-gray-400">
                  {selectedStores.length} selected
                </Text>
              </View>

              {/* Selected Store Cards */}
              {selectedStores.length > 0 ? (
                <View className="gap-2">
                  {selectedStores.map((store) => (
                    <View
                      key={store.id}
                      className="flex-row items-center rounded-xl bg-gray-100 p-3 dark:bg-zinc-800">
                      <View className="mr-3 h-10 w-10 items-center justify-center rounded-full bg-[#4AA8D8]/10">
                        <Store size={18} color="#4AA8D8" />
                      </View>
                      <View className="flex-1">
                        <Text className="font-semibold">{store.name}</Text>
                        <Text className="text-xs text-gray-500">
                          {store.address_line1}, {store.city}
                        </Text>
                      </View>
                      {store.distance_mi && (
                        <Text className="mr-3 text-xs text-gray-400">
                          {store.distance_mi} mi
                        </Text>
                      )}
                      <TouchableOpacity
                        onPress={() => handleRemoveStore(store.id)}
                        className="h-8 w-8 items-center justify-center rounded-full bg-gray-200 dark:bg-zinc-700">
                        <X size={16} color="#9CA3AF" />
                      </TouchableOpacity>
                    </View>
                  ))}
                </View>
              ) : (
                <View className="items-center py-4">
                  <Text className="text-sm text-gray-400">No stores selected</Text>
                  <Text className="mt-1 text-xs text-gray-400">
                    Tap the map below to add stores
                  </Text>
                </View>
              )}

              {/* Separator */}
              <View className="my-4 h-px bg-gray-200 dark:bg-gray-700" />

              {/* Map preview area - tap to open full map */}
              <Link href="/storeMap" asChild>
                <TouchableOpacity
                  activeOpacity={0.8}
                  style={{
                    height: 200,
                    borderRadius: 12,
                    overflow: 'hidden',
                    position: 'relative',
                  }}>
                  {/* Map-styled background */}
                  <View
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      backgroundColor: '#E8F4E8',
                    }}>
                    {/* Simplified map grid pattern */}
                    <View style={{ flex: 1, position: 'relative' }}>
                      {/* Horizontal "streets" */}
                      <View style={{ position: 'absolute', top: '25%', left: 0, right: 0, height: 2, backgroundColor: '#D1D5DB' }} />
                      <View style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: 3, backgroundColor: '#F5D96A' }} />
                      <View style={{ position: 'absolute', top: '75%', left: 0, right: 0, height: 2, backgroundColor: '#D1D5DB' }} />
                      {/* Vertical "streets" */}
                      <View style={{ position: 'absolute', left: '20%', top: 0, bottom: 0, width: 2, backgroundColor: '#D1D5DB' }} />
                      <View style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 3, backgroundColor: '#F5D96A' }} />
                      <View style={{ position: 'absolute', left: '80%', top: 0, bottom: 0, width: 2, backgroundColor: '#D1D5DB' }} />
                      {/* "Buildings" / blocks */}
                      <View style={{ position: 'absolute', top: '10%', left: '5%', width: '12%', height: '12%', backgroundColor: '#D9EAD9', borderRadius: 4 }} />
                      <View style={{ position: 'absolute', top: '5%', left: '25%', width: '20%', height: '18%', backgroundColor: '#C8DFC8', borderRadius: 4 }} />
                      <View style={{ position: 'absolute', top: '8%', left: '55%', width: '22%', height: '15%', backgroundColor: '#D9EAD9', borderRadius: 4 }} />
                      <View style={{ position: 'absolute', top: '30%', left: '5%', width: '12%', height: '18%', backgroundColor: '#C8DFC8', borderRadius: 4 }} />
                      <View style={{ position: 'absolute', top: '55%', left: '25%', width: '20%', height: '18%', backgroundColor: '#D9EAD9', borderRadius: 4 }} />
                      <View style={{ position: 'absolute', top: '80%', left: '55%', width: '22%', height: '15%', backgroundColor: '#C8DFC8', borderRadius: 4 }} />
                      <View style={{ position: 'absolute', top: '60%', left: '5%', width: '12%', height: '14%', backgroundColor: '#D9EAD9', borderRadius: 4 }} />
                      <View style={{ position: 'absolute', top: '55%', left: '83%', width: '12%', height: '20%', backgroundColor: '#C8DFC8', borderRadius: 4 }} />
                    </View>
                  </View>
                  {/* Overlay gradient for text readability */}
                  <View
                    style={{
                      position: 'absolute',
                      bottom: 0,
                      left: 0,
                      right: 0,
                      height: 100,
                      backgroundColor: 'rgba(0,0,0,0.35)',
                    }}
                  />
                  {/* Center pin icon */}
                  <View style={{ position: 'absolute', top: '35%', left: '50%', marginLeft: -16, marginTop: -24 }}>
                    <MapPin size={32} color="#4AA8D8" fill="#4AA8D8" />
                  </View>
                  {/* Bottom text */}
                  <View style={{ position: 'absolute', bottom: 16, left: 0, right: 0, alignItems: 'center' }}>
                    <Text style={{ color: '#FFFFFF', fontSize: 16, fontWeight: '600' }}>
                      Tap to Open Map
                    </Text>
                    <Text style={{ color: 'rgba(255,255,255,0.8)', fontSize: 12, marginTop: 4 }}>
                      Search and select stores nearby
                    </Text>
                  </View>
                </TouchableOpacity>
              </Link>
            </CardContent>
          </Card>
        </ScrollView>
        </View>
      </KeyboardAvoidingView>

      {/* Match Items Button - Fixed at Bottom, outside KeyboardAvoidingView so it doesn't move with keyboard */}
      {selectedStores.length > 0 && (
        <View style={{ paddingVertical: 20, marginHorizontal: 20 }}>
          <Button variant="continue" size="xl" onPress={handleMatchItems}>
            <Text style={{ textAlign: 'center', fontSize: 18, fontWeight: '600' }}>
              Match Items
            </Text>
            <ArrowRight size={20} color="white" />
          </Button>
        </View>
      )}

      {/* Floating Done button above keyboard */}
      {keyboardVisible && (
        <Animated.View
          style={{
            position: 'absolute',
            bottom: keyboardHeight,
            right: 16,
            marginBottom: 10,
          }}>
          <TouchableOpacity
            onPress={() => Keyboard.dismiss()}
            activeOpacity={0.8}
            style={{
              backgroundColor: '#4AA8D8',
              paddingHorizontal: 20,
              paddingVertical: 10,
              borderRadius: 20,
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 2 },
              shadowOpacity: 0.3,
              shadowRadius: 4,
              elevation: 5,
            }}>
            <Text style={{ color: '#FFFFFF', fontSize: 15, fontWeight: '600' }}>
              Done
            </Text>
          </TouchableOpacity>
        </Animated.View>
      )}

      {/* Job Progress Overlay for MATCH job */}
      {routePlanId && (
        <JobProgressOverlay
          visible={showMatchOverlay}
          routePlanId={routePlanId}
          jobId={matchJobId}
          jobType="MATCH"
          onComplete={handleMatchComplete}
          onCancel={handleMatchCancel}
          onRetry={handleMatchRetry}
        />
      )}
    </SafeAreaView>
  );
}

export default SearchSelect;
