import { Button } from '@/components/ui/button';
import { Text } from '@/components/ui/text';
import { Coordinates, distanceInMiles } from '@/lib/geo';
import { getListId, getRoutePlanId, setRoutePlanId } from '@/lib/itemStore';
import BottomSheet, { BottomSheetFlatList, BottomSheetView } from '@gorhom/bottom-sheet';
import * as Location from 'expo-location';
import { AppleMaps, GoogleMaps } from 'expo-maps';
import { router } from 'expo-router';
import { ArrowLeft, Check, Crosshair, MapPin, MapPinned, Plus, Search, Store, X } from 'lucide-react-native';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    ActivityIndicator,
    Animated,
    Dimensions,
    Keyboard,
    Platform,
    ScrollView,
    TextInput,
    TouchableOpacity,
    View,
} from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import Reanimated, { useAnimatedStyle, useSharedValue } from 'react-native-reanimated';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

// ===== TYPES =====

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
  chain_name?: string;
}

/** Store search result from the API */
interface StoreResult {
  id: string;
  name: string;
  address_line1: string;
  city: string;
  region: string;
  postal_code: string;
  longitude?: number;
  latitude?: number;
  chain_name?: string;
  distance_mi?: number;
}

/** Route plan from the API */
interface RoutePlan {
  id: string;
  list_id: string;
  status: string;
  opt_mode: string;
  lowest_unit_price: boolean;
  max_stores: number;
  selected_stores: SelectedStore[];
  user_longitude?: number;
  user_latitude?: number;
}

/** Map marker for stores */
interface StoreMarker {
  id: string;
  coordinate: {
    latitude: number;
    longitude: number;
  };
  title: string;
  description: string;
  isSelected: boolean;
}

// ===== CONSTANTS =====

/** Default region when user location is unavailable (centered on US) */
const DEFAULT_REGION = {
  latitude: 39.8283,
  longitude: -98.5795,
  latitudeDelta: 30,
  longitudeDelta: 30,
};

/** Default zoom delta for when we have a location */
const DEFAULT_ZOOM_DELTA = 0.05;

/** Debounce delay for search suggestions (ms) */
const SEARCH_DEBOUNCE_MS = 300;

/** Default search radius for suggestions (km) */
const SUGGESTION_RADIUS_KM = 5;

/** Minimum search radius (km) */
const MIN_SEARCH_RADIUS_KM = 2;

/** Maximum search radius (km) */
const MAX_SEARCH_RADIUS_KM = 80;

/** Default zoom level */
const DEFAULT_ZOOM = 14;

/**
 * Calculate search radius in km based on map zoom level.
 * Higher zoom = smaller area visible = smaller search radius.
 * 
 * Approximate visible spans at different zoom levels:
 * - Zoom 10: ~100 km
 * - Zoom 12: ~25 km
 * - Zoom 14: ~6 km
 * - Zoom 16: ~1.5 km
 */
function getSearchRadiusFromZoom(zoom: number): number {
  // Base formula: radius decreases exponentially as zoom increases
  // At zoom 14 (default), we want ~25 km radius
  // Each zoom level change roughly halves/doubles the visible area
  const baseRadius = 5; // km at zoom 14
  const baseZoom = 14;
  
  // Calculate radius: baseRadius * 2^(baseZoom - currentZoom)
  const radius = baseRadius * Math.pow(2, baseZoom - zoom);
  
  // Clamp to reasonable bounds
  return Math.max(MIN_SEARCH_RADIUS_KM, Math.min(MAX_SEARCH_RADIUS_KM, radius));
}

/** Max suggestions to show */
const MAX_SUGGESTIONS = 8;

/** Max full search results */
const MAX_SEARCH_RESULTS = 25;

/** Max initial load results */
const MAX_INITIAL_RESULTS = 50;

// ===== SCREEN: storeMap =====

function StoreMap() {
  const insets = useSafeAreaInsets();

  // ----- State -----
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingLocation, setLoadingLocation] = useState(false);
  const [routePlanId, setLocalRoutePlanId] = useState<string | null>(null);
  const [routePlan, setRoutePlan] = useState<RoutePlan | null>(null);
  const [userLocation, setUserLocation] = useState<Coordinates | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [selectedStoreIds, setSelectedStoreIds] = useState<Set<string>>(new Set());

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [suggestions, setSuggestions] = useState<StoreResult[]>([]);
  const [searchResults, setSearchResults] = useState<StoreResult[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [addingStoreId, setAddingStoreId] = useState<string | null>(null);

  // Map viewport tracking state
  const [searchCenter, setSearchCenter] = useState<Coordinates | null>(null);
  const [mapMoved, setMapMoved] = useState(false);
  const [currentZoom, setCurrentZoom] = useState(DEFAULT_ZOOM);
  const [initialCameraSet, setInitialCameraSet] = useState(false);
  const [markersVersion, setMarkersVersion] = useState(0); // Used to force marker updates
  const searchHereButtonOpacity = useRef(new Animated.Value(0)).current;

  // Map ref for controlling camera
  const mapRef = useRef<any>(null);
  const searchInputRef = useRef<TextInput>(null);
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Ref to track camera position to restore after map remount (for marker updates)
  const restoreCameraRef = useRef<{ coordinates: Coordinates; zoom: number } | null>(null);
  // Bottom sheet ref
  const bottomSheetRef = useRef<BottomSheet>(null);

  // Bottom sheet snap points (28% keeps it below the search button)
  const snapPoints = useMemo(() => ['28%', '50%', '75%'], []);
  
  // Animated position for smooth recenter button movement
  const animatedPosition = useSharedValue(0);
  const { height: screenHeight } = Dimensions.get('window');
  
  // Animated style for recenter button that moves smoothly with bottom sheet
  // animatedPosition is the Y position from top of screen to top of sheet
  // So the sheet height = screenHeight - animatedPosition
  // We want button to be positioned above the sheet
  const recenterButtonStyle = useAnimatedStyle(() => {
    // Calculate the bottom position: screenHeight - animatedPosition gives us sheet height
    // Add offset (16px) above the sheet
    const sheetHeight = screenHeight - animatedPosition.value;
    return {
      bottom: sheetHeight + 16,
    };
  });
  
  // Animated style for bottom sheet content that adjusts height based on sheet position
  // This ensures the scrollable list properly fits within the visible sheet area
  const SHEET_HANDLE_HEIGHT = 25; // handleStyle padding (12 + 8) + indicator (5)
  const SHEET_HEADER_HEIGHT = 44; // Approximate header height
  
  const listContainerStyle = useAnimatedStyle(() => {
    // Calculate available height for list content
    // Sheet height = screenHeight - animatedPosition
    // Available for list = sheet height - handle - header - bottom inset
    const sheetHeight = screenHeight - animatedPosition.value;
    const availableHeight = Math.max(0, sheetHeight - SHEET_HANDLE_HEIGHT - SHEET_HEADER_HEIGHT);
    return {
      height: availableHeight,
    };
  });

  // Base URL for API calls
  const API_BASE = useMemo(
    () => process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api',
    []
  );

  // ----- API utilities -----
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
    opt_mode: apiPlan.opt_mode,
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
      chain_name: store.chain_name,
    })),
    user_longitude: apiPlan.user_longitude,
    user_latitude: apiPlan.user_latitude,
  }), []);

  // Convert API store response to StoreResult with distance
  const mapApiStoreResult = useCallback((store: any, userLoc: Coordinates | null): StoreResult => {
    const result: StoreResult = {
      id: store.id,
      name: store.name,
      address_line1: store.address_line1,
      city: store.city,
      region: store.region,
      postal_code: store.postal_code,
      longitude: store.longitude,
      latitude: store.latitude,
      chain_name: store.chain_name,
    };

    // Calculate distance if we have both user location and store coordinates
    if (userLoc && store.latitude != null && store.longitude != null) {
      result.distance_mi = distanceInMiles(userLoc, {
        latitude: store.latitude,
        longitude: store.longitude,
      });
    }

    return result;
  }, []);

  // ----- Map camera move handler -----
  const handleCameraMove = useCallback(
    (event: { coordinates: { latitude?: number; longitude?: number }; zoom: number; tilt: number; bearing: number }) => {
      const { coordinates, zoom } = event;
      
      // Ensure coordinates are defined before using
      if (coordinates.latitude == null || coordinates.longitude == null) {
        return;
      }
      
      const newCenter: Coordinates = {
        latitude: coordinates.latitude,
        longitude: coordinates.longitude,
      };
      
      // Update search center to current map center
      setSearchCenter(newCenter);
      setCurrentZoom(zoom);

      // Check if map has moved significantly from user location
      if (userLocation) {
        const distanceFromUser = distanceInMiles(userLocation, newCenter);
        // Consider "moved" if more than ~0.1 miles from user location or zoom changed significantly
        const hasMoved = distanceFromUser > 0.1;
        
        if (hasMoved && !mapMoved) {
          setMapMoved(true);
          // Animate button appearance
          Animated.spring(searchHereButtonOpacity, {
            toValue: 1,
            useNativeDriver: true,
            tension: 50,
            friction: 7,
          }).start();
        }
      } else if (!mapMoved) {
        // No user location, show button after any movement
        setMapMoved(true);
        Animated.spring(searchHereButtonOpacity, {
          toValue: 1,
          useNativeDriver: true,
          tension: 50,
          friction: 7,
        }).start();
      }
    },
    [userLocation, mapMoved, searchHereButtonOpacity]
  );

  // ----- Location acquisition -----
  const acquireLocation = useCallback(async () => {
    setLoadingLocation(true);
    setLocationError(null);

    try {
      // Request permission
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setLocationError('Location permission denied');
        setLoadingLocation(false);
        return null;
      }

      // Get current position
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });

      const coords: Coordinates = {
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
      };

      setUserLocation(coords);
      setLoadingLocation(false);
      return coords;
    } catch (err) {
      console.error('Failed to get location:', err);
      setLocationError('Failed to get location');
      setLoadingLocation(false);
      return null;
    }
  }, []);

  // Persist user location to route plan
  const persistUserLocation = useCallback(
    async (coords: Coordinates, planId?: string) => {
      const targetPlanId = planId || routePlanId;
      if (!targetPlanId) return;
      try {
        await apiFetch(`/route-plans/${targetPlanId}`, {
          method: 'PATCH',
          body: JSON.stringify({
            user_longitude: coords.longitude,
            user_latitude: coords.latitude,
          }),
        });
      } catch (err) {
        console.error('Failed to persist user location:', err);
      }
    },
    [apiFetch, routePlanId]
  );

  // ----- Search functionality -----

  // Get the effective search location (searchCenter if map moved, otherwise userLocation)
  const getEffectiveSearchLocation = useCallback((): Coordinates | null => {
    // If map has been moved, use the search center
    if (mapMoved && searchCenter) {
      return searchCenter;
    }
    // Otherwise use user location
    return userLocation;
  }, [mapMoved, searchCenter, userLocation]);

  // Fetch search suggestions (debounced)
  const fetchSuggestions = useCallback(
    async (query: string) => {
      if (query.length < 2) {
        setSuggestions([]);
        return;
      }

      setLoadingSuggestions(true);
      setSearchError(null);

      const location = getEffectiveSearchLocation();

      try {
        const params = new URLSearchParams({
          q: query,
          limit: String(MAX_SUGGESTIONS),
        });

        if (location) {
          params.append('latitude', String(location.latitude));
          params.append('longitude', String(location.longitude));
          params.append('distance_km', String(SUGGESTION_RADIUS_KM));
        }

        const res = await apiFetch(`/stores/search?${params.toString()}`);
        const stores = await res.json();

        setSuggestions(stores.map((s: any) => mapApiStoreResult(s, userLocation)));
      } catch (err) {
        console.error('Failed to fetch suggestions:', err);
        setSearchError('Failed to search stores');
      } finally {
        setLoadingSuggestions(false);
      }
    },
    [apiFetch, mapApiStoreResult, getEffectiveSearchLocation, userLocation]
  );

  // Perform full search (with optional query - empty string searches all stores in area)
  const performSearch = useCallback(
    async (query: string) => {
      setLoadingSearch(true);
      setSearchError(null);
      setShowSuggestions(false);

      const location = getEffectiveSearchLocation();
      // Calculate search radius based on current zoom level
      const searchRadius = getSearchRadiusFromZoom(currentZoom);

      try {
        const params = new URLSearchParams({
          limit: String(MAX_SEARCH_RESULTS),
        });

        // Only add query if not empty
        if (query.trim()) {
          params.append('q', query);
        }

        if (location) {
          params.append('latitude', String(location.latitude));
          params.append('longitude', String(location.longitude));
          params.append('distance_km', String(searchRadius));
        }

        const res = await apiFetch(`/stores/search?${params.toString()}`);
        const stores = await res.json();

        const results = stores.map((s: any) => mapApiStoreResult(s, userLocation));
        setSearchResults(results);
        setShowResults(true);
        
        // Save current camera position before forcing marker update (map will remount)
        const currentLocation = getEffectiveSearchLocation();
        if (currentLocation) {
          restoreCameraRef.current = {
            coordinates: currentLocation,
            zoom: currentZoom,
          };
        }
        setMarkersVersion((v) => v + 1); // Force marker update by changing map key

        // Hide the "Search Here" button after searching
        setMapMoved(false);
        Animated.timing(searchHereButtonOpacity, {
          toValue: 0,
          duration: 200,
          useNativeDriver: true,
        }).start();

        // Fit map to show all result markers
        if (results.length > 0 && mapRef.current) {
          const coords = results
            .filter((s: StoreResult) => s.latitude != null && s.longitude != null)
            .map((s: StoreResult) => ({
              latitude: s.latitude!,
              longitude: s.longitude!,
            }));

          if (coords.length > 0) {
            // Calculate bounds and animate map
            // Note: expo-maps may have different camera animation APIs
            // For now, the region will update via initialRegion recalc
          }
        }

        Keyboard.dismiss();
      } catch (err) {
        console.error('Failed to search stores:', err);
        setSearchError('Failed to search stores');
      } finally {
        setLoadingSearch(false);
      }
    },
    [apiFetch, mapApiStoreResult, getEffectiveSearchLocation, userLocation, searchHereButtonOpacity, currentZoom]
  );

  // Handle search input change with debounce
  const handleSearchChange = useCallback(
    (text: string) => {
      setSearchQuery(text);
      setShowSuggestions(text.length >= 2);
      setShowResults(false);

      // Clear existing debounce timer
      if (searchDebounceRef.current) {
        clearTimeout(searchDebounceRef.current);
      }

      // Debounce the suggestion fetch
      if (text.length >= 2) {
        searchDebounceRef.current = setTimeout(() => {
          fetchSuggestions(text);
        }, SEARCH_DEBOUNCE_MS);
      } else {
        setSuggestions([]);
      }
    },
    [fetchSuggestions]
  );

  // Handle search submit
  const handleSearchSubmit = useCallback(() => {
    performSearch(searchQuery);
  }, [performSearch, searchQuery]);

  // Handle "Search Here" button press
  const handleSearchHere = useCallback(() => {
    performSearch(searchQuery);
  }, [performSearch, searchQuery]);

  // Load initial stores near a location (used on mount)
  const loadInitialStores = useCallback(
    async (location: Coordinates, zoom: number = DEFAULT_ZOOM) => {
      setLoadingSearch(true);
      setSearchError(null);

      // Calculate search radius based on zoom level
      const searchRadius = getSearchRadiusFromZoom(zoom);

      try {
        const params = new URLSearchParams({
          latitude: String(location.latitude),
          longitude: String(location.longitude),
          distance_km: String(searchRadius),
          limit: String(MAX_INITIAL_RESULTS),
        });

        const res = await apiFetch(`/stores/search?${params.toString()}`);
        const stores = await res.json();

        const results = stores.map((s: any) => mapApiStoreResult(s, location));
        setSearchResults(results);
        setShowResults(true);
        
        // Save camera position before forcing marker update (map will remount)
        restoreCameraRef.current = {
          coordinates: location,
          zoom,
        };
        setMarkersVersion((v) => v + 1); // Force marker update by changing map key
      } catch (err) {
        console.error('Failed to load initial stores:', err);
        // Don't show error for initial load - not critical
      } finally {
        setLoadingSearch(false);
      }
    },
    [apiFetch, mapApiStoreResult]
  );

  // Clear search
  const handleClearSearch = useCallback(() => {
    setSearchQuery('');
    setSuggestions([]);
    setSearchResults([]);
    setShowSuggestions(false);
    setShowResults(false);
    setSearchError(null);
  }, []);

  // ----- Add/Remove store functionality -----

  const handleAddStore = useCallback(
    async (store: StoreResult) => {
      if (!routePlanId) return;

      setAddingStoreId(store.id);

      try {
        const res = await apiFetch(`/route-plans/${routePlanId}/selected-stores`, {
          method: 'POST',
          body: JSON.stringify({ store_id: store.id }),
        });

        const updated = await res.json();
        const plan = mapApiRoutePlan(updated);
        setRoutePlan(plan);
        setSelectedStoreIds(new Set(plan.selected_stores.map((s) => s.id)));
      } catch (err: any) {
        // Handle 409 conflict (duplicate) gracefully
        if (err.message?.includes('409')) {
          // Store already selected, refresh state
          try {
            const res = await apiFetch(`/route-plans/${routePlanId}`);
            const apiPlan = await res.json();
            const plan = mapApiRoutePlan(apiPlan);
            setRoutePlan(plan);
            setSelectedStoreIds(new Set(plan.selected_stores.map((s) => s.id)));
          } catch {
            // Ignore refresh errors
          }
        } else {
          console.error('Failed to add store:', err);
          setSearchError('Failed to add store');
        }
      } finally {
        setAddingStoreId(null);
      }
    },
    [apiFetch, routePlanId, mapApiRoutePlan]
  );

  const handleRemoveStore = useCallback(
    async (storeId: string) => {
      if (!routePlanId) return;

      // Optimistic update
      setSelectedStoreIds((prev) => {
        const next = new Set(prev);
        next.delete(storeId);
        return next;
      });
      setRoutePlan((prev) =>
        prev ? { ...prev, selected_stores: prev.selected_stores.filter((s) => s.id !== storeId) } : prev
      );

      try {
        const res = await apiFetch(`/route-plans/${routePlanId}/selected-stores/${storeId}`, {
          method: 'DELETE',
        });

        const updated = await res.json();
        const plan = mapApiRoutePlan(updated);
        setRoutePlan(plan);
        setSelectedStoreIds(new Set(plan.selected_stores.map((s) => s.id)));
      } catch (err) {
        console.error('Failed to remove store:', err);
        // Revert on error - refetch route plan
        try {
          const res = await apiFetch(`/route-plans/${routePlanId}`);
          const apiPlan = await res.json();
          const plan = mapApiRoutePlan(apiPlan);
          setRoutePlan(plan);
          setSelectedStoreIds(new Set(plan.selected_stores.map((s) => s.id)));
        } catch {
          // Ignore refetch errors
        }
      }
    },
    [apiFetch, routePlanId, mapApiRoutePlan]
  );

  // ----- Bootstrap on mount -----
  useEffect(() => {
    let cancelled = false;

    const bootstrap = async () => {
      try {
        // Try to get route plan ID from global store
        let planId = getRoutePlanId();

        // If no route plan ID, try to create one from the list
        if (!planId) {
          const listId = getListId();
          if (listId) {
            console.log('No route plan ID found, attempting to create from list:', listId);
            try {
              // Check for existing route plans
              const existingRes = await apiFetch(`/shopping-lists/${listId}/route-plans`);
              const existing = await existingRes.json();

              if (existing && existing.length > 0) {
                planId = existing[0].id;
              } else {
                // Create new route plan
                const createRes = await apiFetch(`/shopping-lists/${listId}/route-plans`, {
                  method: 'POST',
                  body: JSON.stringify({
                    client_id: 'user',
                    opt_mode: 'BALANCED',
                    lowest_unit_price: false,
                    max_stores: 3,
                  }),
                });
                const created = await createRes.json();
                planId = created.id;
              }

              // Store the plan ID globally
              if (planId) {
                setRoutePlanId(planId);
              }
            } catch (err) {
              console.error('Failed to create route plan:', err);
            }
          }
        }

        if (!planId) {
          console.error('No route plan ID available');
          setLoading(false);
          return;
        }

        setLocalRoutePlanId(planId);

        // Fetch the route plan
        const res = await apiFetch(`/route-plans/${planId}`);
        const apiPlan = await res.json();

        if (cancelled) return;

        const plan = mapApiRoutePlan(apiPlan);
        setRoutePlan(plan);
        setSelectedStoreIds(new Set(plan.selected_stores.map((s) => s.id)));

        // Set user location from route plan if available
        if (plan.user_longitude != null && plan.user_latitude != null) {
          setUserLocation({
            latitude: plan.user_latitude,
            longitude: plan.user_longitude,
          });
        } else {
          // Acquire location from device
          const coords = await acquireLocation();
          if (coords && planId) {
            await persistUserLocation(coords, planId);
          }
        }
      } catch (err) {
        console.error('Failed to initialize store map:', err);
        if (!cancelled) setLoadError('Failed to load');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    bootstrap();

    return () => {
      cancelled = true;
      if (searchDebounceRef.current) {
        clearTimeout(searchDebounceRef.current);
      }
    };
  }, [apiFetch, mapApiRoutePlan, acquireLocation, persistUserLocation]);

  // ----- Load initial stores when map opens -----
  useEffect(() => {
    // Only load initial stores once we have user location and loading is complete
    // and we haven't already loaded results
    if (!loading && userLocation && searchResults.length === 0 && !showResults) {
      loadInitialStores(userLocation, currentZoom);
    }
  }, [loading, userLocation, loadInitialStores, searchResults.length, showResults, currentZoom]);

  // ----- Set initial camera position once, then let user control freely -----
  useEffect(() => {
    if (!initialCameraSet && userLocation && mapRef.current) {
      mapRef.current.setCameraPosition({
        coordinates: userLocation,
        zoom: DEFAULT_ZOOM,
      });
      setInitialCameraSet(true);
    }
  }, [initialCameraSet, userLocation]);

  // ----- Restore camera position after map remounts due to marker update -----
  useEffect(() => {
    if (restoreCameraRef.current && mapRef.current) {
      // Small delay to ensure map is fully mounted after key change
      const timer = setTimeout(() => {
        if (mapRef.current && restoreCameraRef.current) {
          mapRef.current.setCameraPosition(restoreCameraRef.current);
          restoreCameraRef.current = null;
        }
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [markersVersion]);

  // ----- Computed values -----

  // Get the initial map region based on user location or selected stores
  // Note: This is only used for the INITIAL camera position, not for subsequent searches
  // The map maintains its position when user searches via "Search This Area"
  const initialRegion = useMemo(() => {
    // If we have a current search center (map was moved), use that
    if (searchCenter) {
      return {
        latitude: searchCenter.latitude,
        longitude: searchCenter.longitude,
        latitudeDelta: DEFAULT_ZOOM_DELTA,
        longitudeDelta: DEFAULT_ZOOM_DELTA,
      };
    }

    // If we have user location, center there
    if (userLocation) {
      return {
        latitude: userLocation.latitude,
        longitude: userLocation.longitude,
        latitudeDelta: DEFAULT_ZOOM_DELTA,
        longitudeDelta: DEFAULT_ZOOM_DELTA,
      };
    }

    // If we have selected stores with coordinates, fit to them
    const storesWithCoords = routePlan?.selected_stores.filter(
      (s) => s.latitude != null && s.longitude != null
    );
    if (storesWithCoords && storesWithCoords.length > 0) {
      const lats = storesWithCoords.map((s) => s.latitude!);
      const lons = storesWithCoords.map((s) => s.longitude!);
      const minLat = Math.min(...lats);
      const maxLat = Math.max(...lats);
      const minLon = Math.min(...lons);
      const maxLon = Math.max(...lons);
      const latDelta = Math.max(0.02, (maxLat - minLat) * 1.5);
      const lonDelta = Math.max(0.02, (maxLon - minLon) * 1.5);
      return {
        latitude: (minLat + maxLat) / 2,
        longitude: (minLon + maxLon) / 2,
        latitudeDelta: latDelta,
        longitudeDelta: lonDelta,
      };
    }

    // Fallback to default
    return DEFAULT_REGION;
  }, [userLocation, routePlan, searchCenter]);

  // Create markers for selected stores and search results
  const allMarkers: StoreMarker[] = useMemo(() => {
    const markers: StoreMarker[] = [];
    const addedIds = new Set<string>();

    // Add selected stores first (higher priority)
    if (routePlan) {
      routePlan.selected_stores
        .filter((store) => store.latitude != null && store.longitude != null)
        .forEach((store) => {
          markers.push({
            id: `selected-${store.id}`,
            coordinate: {
              latitude: store.latitude!,
              longitude: store.longitude!,
            },
            title: store.name,
            description: `${store.address_line1}, ${store.city}`,
            isSelected: true,
          });
          addedIds.add(store.id);
        });
    }

    // Add search results (if not already selected)
    // Include markersVersion in ID to force expo-maps to update markers
    if (showResults) {
      searchResults
        .filter((store) => store.latitude != null && store.longitude != null && !addedIds.has(store.id))
        .forEach((store) => {
          markers.push({
            id: `search-${markersVersion}-${store.id}`,
            coordinate: {
              latitude: store.latitude!,
              longitude: store.longitude!,
            },
            title: store.name,
            description: `${store.address_line1}, ${store.city}`,
            isSelected: false,
          });
        });
    }

    return markers;
  }, [routePlan, showResults, searchResults, markersVersion]);

  // Calculate distance from user to each selected store
  const storesWithDistance = useMemo(() => {
    if (!routePlan || !userLocation) return routePlan?.selected_stores || [];
    return routePlan.selected_stores.map((store) => {
      if (store.latitude == null || store.longitude == null) return store;
      const distanceMi = distanceInMiles(userLocation, {
        latitude: store.latitude,
        longitude: store.longitude,
      });
      return { ...store, distance_mi: distanceMi };
    });
  }, [routePlan, userLocation]);

  // ----- Handlers -----

  const handleBack = useCallback(() => {
    router.back();
  }, []);

  const handleRecenterLocation = useCallback(async () => {
    const coords = await acquireLocation();
    if (coords) {
      await persistUserLocation(coords);
      
      // Reset map moved state
      setMapMoved(false);
      setSearchCenter(null);
      setCurrentZoom(DEFAULT_ZOOM);
      Animated.timing(searchHereButtonOpacity, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }).start();
      
      // Move camera to user location
      if (mapRef.current) {
        mapRef.current.setCameraPosition({
          coordinates: coords,
          zoom: DEFAULT_ZOOM,
        });
      }
      
      // Reload stores at user location with default zoom
      loadInitialStores(coords, DEFAULT_ZOOM);
    }
  }, [acquireLocation, persistUserLocation, searchHereButtonOpacity, loadInitialStores]);

  // ----- Render helpers -----

  // Render a store row (for suggestions or results)
  const renderStoreRow = useCallback(
    (store: StoreResult, isCompact: boolean = false) => {
      const isSelected = selectedStoreIds.has(store.id);
      const isAdding = addingStoreId === store.id;

      return (
        <View
          key={store.id}
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            paddingVertical: isCompact ? 10 : 12,
            paddingHorizontal: 12,
            backgroundColor: isSelected ? '#E0F2FE' : 'white',
            borderBottomWidth: 1,
            borderBottomColor: '#F3F4F6',
          }}>
          {/* Store icon */}
          <View
            style={{
              width: isCompact ? 32 : 40,
              height: isCompact ? 32 : 40,
              borderRadius: isCompact ? 16 : 20,
              backgroundColor: isSelected ? '#4AA8D8' : '#F3F4F6',
              alignItems: 'center',
              justifyContent: 'center',
              marginRight: 10,
            }}>
            <Store size={isCompact ? 14 : 18} color={isSelected ? 'white' : '#6B7280'} />
          </View>

          {/* Store info */}
          <View style={{ flex: 1 }}>
            <Text
              style={{ fontWeight: '600', fontSize: isCompact ? 13 : 14, color: '#1F2937' }}
              numberOfLines={1}>
              {store.name}
            </Text>
            <Text style={{ fontSize: isCompact ? 11 : 12, color: '#6B7280', marginTop: 2 }} numberOfLines={1}>
              {store.address_line1}, {store.city}
            </Text>
            {store.chain_name && (
              <Text style={{ fontSize: 10, color: '#9CA3AF', marginTop: 1 }}>{store.chain_name}</Text>
            )}
          </View>

          {/* Distance */}
          {store.distance_mi != null && (
            <Text style={{ fontSize: 11, color: '#9CA3AF', marginRight: 8 }}>
              {store.distance_mi.toFixed(1)} mi
            </Text>
          )}

          {/* Add/Selected button */}
          {isSelected ? (
            <TouchableOpacity
              onPress={() => handleRemoveStore(store.id)}
              style={{
                width: 32,
                height: 32,
                borderRadius: 16,
                backgroundColor: '#4AA8D8',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
              <Check size={16} color="white" />
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              onPress={() => handleAddStore(store)}
              disabled={isAdding}
              style={{
                width: 32,
                height: 32,
                borderRadius: 16,
                backgroundColor: '#10B981',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
              {isAdding ? (
                <ActivityIndicator size="small" color="white" />
              ) : (
                <Plus size={16} color="white" />
              )}
            </TouchableOpacity>
          )}
        </View>
      );
    },
    [selectedStoreIds, addingStoreId, handleAddStore, handleRemoveStore]
  );

  // ----- Render -----

  // Show loading state
  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: '#F5F5F5' }} edges={['top']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator size="large" color="#4AA8D8" />
          <Text className="mt-4 text-gray-500">Loading map…</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Error or no route plan available
  if (loadError || !routePlanId || !routePlan) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: '#F5F5F5' }} edges={['top']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <MapPin size={48} color="#9CA3AF" />
          <Text className="mt-4 text-center text-gray-600" style={{ fontSize: 16 }}>
            Unable to load map
          </Text>
          <Text className="mt-2 text-center text-gray-400" style={{ fontSize: 14 }}>
            Please check your connection and try again
          </Text>
          <View style={{ flexDirection: 'row', gap: 12, marginTop: 24 }}>
            <Button variant="outline" onPress={handleBack}>
              <Text>Go Back</Text>
            </Button>
            <Button
              onPress={() => {
                setLoadError(null);
                setLoading(true);
              }}
            >
              <Text>Retry</Text>
            </Button>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  // Render the map with markers
  const MapViewComponent = Platform.OS === 'ios' ? AppleMaps.View : GoogleMaps.View;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      {/* Full-screen map */}
      <MapViewComponent
        key={`map-${markersVersion}`}
        ref={mapRef}
        style={{ flex: 1 }}
        cameraPosition={
          // Only set initial camera position, then let user control freely
          !initialCameraSet
            ? {
                coordinates: {
                  latitude: initialRegion.latitude,
                  longitude: initialRegion.longitude,
                },
                zoom: DEFAULT_ZOOM,
              }
            : undefined
        }
        properties={{
          isMyLocationEnabled: true,
        }}
        uiSettings={{
          compassEnabled: true,
          scaleBarEnabled: true,
        }}
        markers={allMarkers.map((marker) => ({
          id: marker.id,
          coordinates: marker.coordinate,
          title: marker.title,
          snippet: marker.description,
          // iOS uses tintColor, Android might ignore this but won't error
          tintColor: marker.isSelected ? '#4AA8D8' : '#10B981',
        }))}
        onCameraMove={handleCameraMove}
      />

      {/* Top overlay: Back button and search bar */}
      <View
        style={{
          position: 'absolute',
          top: insets.top,
          left: 0,
          right: 0,
          zIndex: 10,
        }}>
        {/* Back button and search bar row */}
        <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12 }}>
          {/* Back button */}
          <TouchableOpacity
            onPress={handleBack}
            activeOpacity={0.8}
            style={{
              width: 44,
              height: 44,
              borderRadius: 22,
              backgroundColor: 'white',
              alignItems: 'center',
              justifyContent: 'center',
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 2 },
              shadowOpacity: 0.15,
              shadowRadius: 4,
              elevation: 4,
            }}>
            <ArrowLeft size={24} color="#374151" />
          </TouchableOpacity>

          {/* Search bar */}
          <View
            style={{
              flex: 1,
              marginLeft: 12,
              height: 44,
              borderRadius: 22,
              backgroundColor: 'white',
              flexDirection: 'row',
              alignItems: 'center',
              paddingHorizontal: 14,
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 2 },
              shadowOpacity: 0.15,
              shadowRadius: 4,
              elevation: 4,
            }}>
            <Search size={18} color="#9CA3AF" />
            <TextInput
              ref={searchInputRef}
              value={searchQuery}
              onChangeText={handleSearchChange}
              onSubmitEditing={handleSearchSubmit}
              placeholder="Search stores..."
              placeholderTextColor="#9CA3AF"
              returnKeyType="search"
              style={{
                flex: 1,
                marginLeft: 10,
                fontSize: 15,
                color: '#1F2937',
              }}
            />
            {searchQuery.length > 0 && (
              <TouchableOpacity onPress={handleClearSearch} style={{ padding: 4 }}>
                <X size={18} color="#9CA3AF" />
              </TouchableOpacity>
            )}
            {loadingSuggestions && (
              <ActivityIndicator size="small" color="#4AA8D8" style={{ marginLeft: 4 }} />
            )}
          </View>
        </View>

        {/* Suggestions dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <View
            style={{
              marginHorizontal: 16,
              marginTop: 4,
              backgroundColor: 'white',
              borderRadius: 12,
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 2 },
              shadowOpacity: 0.15,
              shadowRadius: 6,
              elevation: 6,
              maxHeight: 300,
              overflow: 'hidden',
            }}>
            <ScrollView
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}>
              {suggestions.map((store) => renderStoreRow(store, true))}
            </ScrollView>
          </View>
        )}

        {/* "Search Here" button - appears when map is moved */}
        {mapMoved && !showSuggestions && (
          <Animated.View
            style={{
              opacity: searchHereButtonOpacity,
              alignItems: 'center',
              marginTop: 8,
            }}>
            <TouchableOpacity
              onPress={handleSearchHere}
              activeOpacity={0.8}
              disabled={loadingSearch}
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: 8,
                paddingHorizontal: 20,
                paddingVertical: 12,
                backgroundColor: '#4AA8D8',
                borderRadius: 24,
                shadowColor: '#000',
                shadowOffset: { width: 0, height: 3 },
                shadowOpacity: 0.2,
                shadowRadius: 6,
                elevation: 6,
              }}>
              {loadingSearch ? (
                <ActivityIndicator size="small" color="white" />
              ) : (
                <MapPinned size={18} color="white" />
              )}
              <Text style={{ color: 'white', fontWeight: '600', fontSize: 15 }}>
                Search This Area
              </Text>
            </TouchableOpacity>
          </Animated.View>
        )}

        {/* Location error banner */}
        {locationError && (
          <View
            style={{
              marginHorizontal: 16,
              marginTop: 8,
              paddingHorizontal: 16,
              paddingVertical: 10,
              backgroundColor: '#FEF3C7',
              borderRadius: 8,
              flexDirection: 'row',
              alignItems: 'center',
            }}>
            <Text className="flex-1 text-sm text-amber-800">{locationError}</Text>
            <TouchableOpacity onPress={handleRecenterLocation}>
              <Text className="text-sm font-semibold text-amber-800">Retry</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Search error banner */}
        {searchError && (
          <View
            style={{
              marginHorizontal: 16,
              marginTop: 8,
              paddingHorizontal: 16,
              paddingVertical: 10,
              backgroundColor: '#FEE2E2',
              borderRadius: 8,
              flexDirection: 'row',
              alignItems: 'center',
            }}>
            <Text className="flex-1 text-sm text-red-800">{searchError}</Text>
            <TouchableOpacity onPress={() => setSearchError(null)}>
              <X size={16} color="#991B1B" />
            </TouchableOpacity>
          </View>
        )}
      </View>

      {/* Bottom right: Recenter button - animated to move smoothly with bottom sheet */}
      <Reanimated.View
        style={[
          {
            position: 'absolute',
            right: 16,
            zIndex: 10,
          },
          recenterButtonStyle,
        ]}>
        <TouchableOpacity
          onPress={handleRecenterLocation}
          activeOpacity={0.8}
          disabled={loadingLocation}
          style={{
            width: 48,
            height: 48,
            borderRadius: 24,
            backgroundColor: 'white',
            alignItems: 'center',
            justifyContent: 'center',
            shadowColor: '#000',
            shadowOffset: { width: 0, height: 2 },
            shadowOpacity: 0.15,
            shadowRadius: 4,
            elevation: 4,
          }}>
          {loadingLocation ? (
            <ActivityIndicator size="small" color="#4AA8D8" />
          ) : (
            <Crosshair size={24} color="#4AA8D8" />
          )}
        </TouchableOpacity>
      </Reanimated.View>

      {/* Draggable Bottom Sheet: Search results or selected stores */}
      <BottomSheet
        ref={bottomSheetRef}
        index={0}
        snapPoints={snapPoints}
        enableDynamicSizing={false}
        enableContentPanningGesture={false}
        enableHandlePanningGesture={true}
        animatedPosition={animatedPosition}
        handleIndicatorStyle={{
          backgroundColor: '#D1D5DB',
          width: 40,
          height: 5,
          borderRadius: 3,
        }}
        handleStyle={{
          paddingTop: 12,
          paddingBottom: 8,
          backgroundColor: 'white',
          borderTopLeftRadius: 20,
          borderTopRightRadius: 20,
        }}
        backgroundStyle={{
          backgroundColor: 'white',
          borderTopLeftRadius: 20,
          borderTopRightRadius: 20,
          shadowColor: '#000',
          shadowOffset: { width: 0, height: -2 },
          shadowOpacity: 0.1,
          shadowRadius: 8,
          elevation: 8,
        }}
      >
        {/* Show search results or selected stores */}
        {showResults && searchResults.length > 0 ? (
          <>
            {/* Fixed header - outside scrollable area */}
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingBottom: 8, backgroundColor: 'white' }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Search size={18} color="#4AA8D8" />
                <Text style={{ fontWeight: '600', color: '#374151' }}>Search Results</Text>
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <View style={{ backgroundColor: '#4AA8D8', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 }}>
                  <Text style={{ fontSize: 12, fontWeight: '500', color: 'white' }}>{searchResults.length} found</Text>
                </View>
                <TouchableOpacity onPress={() => setShowResults(false)}>
                  <X size={18} color="#9CA3AF" />
                </TouchableOpacity>
              </View>
            </View>
            {/* Scrollable results - wrapped in animated container for dynamic height */}
            <Reanimated.View style={[{ overflow: 'hidden' }, listContainerStyle]}>
              <BottomSheetFlatList
                data={searchResults}
                keyExtractor={(item: StoreResult) => item.id}
                renderItem={({ item }: { item: StoreResult }) => renderStoreRow(item)}
                showsVerticalScrollIndicator={true}
                keyboardShouldPersistTaps="handled"
                contentContainerStyle={{ paddingBottom: insets.bottom + 8 }}
              />
            </Reanimated.View>
          </>
        ) : storesWithDistance.length > 0 ? (
          <>
            {/* Fixed header - outside scrollable area */}
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingBottom: 12, backgroundColor: 'white' }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Store size={20} color="#4AA8D8" />
                <Text className="font-semibold text-gray-800">Selected Stores</Text>
              </View>
              <View style={{ backgroundColor: '#4AA8D8', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 }}>
                <Text className="text-xs font-medium text-white">{storesWithDistance.length} selected</Text>
              </View>
            </View>
            {/* Scrollable selected stores - wrapped in animated container for dynamic height */}
            <Reanimated.View style={[{ overflow: 'hidden' }, listContainerStyle]}>
              <BottomSheetFlatList
                data={storesWithDistance}
                keyExtractor={(item: (typeof storesWithDistance)[number]) => item.id}
                showsVerticalScrollIndicator={true}
                contentContainerStyle={{ paddingBottom: insets.bottom + 8, paddingHorizontal: 16 }}
                renderItem={({ item: store }: { item: (typeof storesWithDistance)[number] }) => (
                  <View
                    style={{
                      flexDirection: 'row',
                      alignItems: 'center',
                      paddingVertical: 8,
                      paddingHorizontal: 12,
                      backgroundColor: '#F9FAFB',
                      borderRadius: 10,
                      marginBottom: 8,
                    }}>
                    <View
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: 18,
                        backgroundColor: '#E0F2FE',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginRight: 10,
                      }}>
                      <Store size={16} color="#4AA8D8" />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text className="font-medium text-gray-800" numberOfLines={1}>
                        {store.name}
                      </Text>
                      <Text className="text-xs text-gray-500" numberOfLines={1}>
                        {store.address_line1}, {store.city}
                      </Text>
                    </View>
                    {'distance_mi' in store && typeof store.distance_mi === 'number' && (
                      <Text className="mr-2 text-xs text-gray-400">{store.distance_mi.toFixed(1)} mi</Text>
                    )}
                    <TouchableOpacity
                      onPress={() => handleRemoveStore(store.id)}
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: 14,
                        backgroundColor: '#FEE2E2',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}>
                      <X size={14} color="#EF4444" />
                    </TouchableOpacity>
                  </View>
                )}
              />
            </Reanimated.View>
          </>
        ) : (
          <BottomSheetView style={{ flex: 1 }}>
            {/* Selected stores header */}
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, marginBottom: 12 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Store size={20} color="#4AA8D8" />
                <Text className="font-semibold text-gray-800">Selected Stores</Text>
              </View>
              <View style={{ backgroundColor: '#4AA8D8', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 }}>
                <Text className="text-xs font-medium text-white">{storesWithDistance.length} selected</Text>
              </View>
            </View>
            <View style={{ alignItems: 'center', paddingVertical: 16, paddingHorizontal: 16 }}>
              <Text className="text-sm text-gray-400">No stores selected yet</Text>
              <Text className="mt-1 text-xs text-gray-400">Search above to find and add stores</Text>
            </View>
          </BottomSheetView>
        )}
      </BottomSheet>
    </GestureHandlerRootView>
  );
}

export default StoreMap;
