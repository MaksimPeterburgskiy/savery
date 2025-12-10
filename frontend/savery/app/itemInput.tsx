import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Text } from '@/components/ui/text';
// TEMP: Using global item store for demo until API integration is complete
import { setItems as setGlobalItems, setListId, getListId, saveFlowState, createInitialFlowState, loadFlowState, updateFlowState } from '@/lib/itemStore';
// end of TEMP: Using global item store for demo until API integration is complete
import { useFocusEffect, useRouter } from 'expo-router';
import { ArrowRight, Plus, Trash } from 'lucide-react-native';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    KeyboardAvoidingView,
    Platform,
    TextInput,
    TouchableOpacity,
    View,
} from 'react-native';
import DraggableFlatList, {
    RenderItemParams,
    ScaleDecorator,
} from 'react-native-draggable-flatlist';
import { SafeAreaView } from 'react-native-safe-area-context';

// ===== TYPES =====
interface Item {
  id: string;
  name: string;
  price?: number;
  quantity?: number;
  rawQty?: string | null;
  position: number;
}

type ItemInputCardProps = {
  name: string;
  quantity?: string | null;
  onNameChange: (value: string) => void;
  onQuantityChange: (value: string) => void;
  onDelete: () => void;
  onDrag?: () => void;
  isActive?: boolean; // True while being dragged
};

type ItemInputListProps = {
  items: Item[];
  onAddItem: (name: string, quantity?: number | null, rawQty?: string | null) => void;
  onDeleteItem: (id: string) => void;
  onUpdateItem: (id: string, changes: Partial<Item>) => void;
  onReorder: (reorderedItems: Item[]) => void;
  loading?: boolean;
};

// ===== COMPONENT: ItemInputCard =====
function ItemInputCard({
  name,
  quantity,
  onDelete,
  onNameChange,
  onQuantityChange,
  onDrag,
  isActive,
}: ItemInputCardProps) {
  const nameInputRef = useRef<TextInput>(null);

  const focusNameInput = () => {
    nameInputRef.current?.focus();
  };

  return (
    <Card
      className="flex-row items-center rounded-xl bg-[#E5E5E5] px-2 py-3"
      style={{ opacity: isActive ? 0.9 : 1, marginBottom: 6 }}
    >
      <CardContent className="w-full flex-row items-center justify-between p-0">
        {/* Drag handle - long press to drag */}
        <TouchableOpacity
          onLongPress={onDrag}
          delayLongPress={100}
          disabled={isActive}
          style={{
            height: 40,
            width: 32,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {/* Six dots in a grid pattern */}
          <View className="flex-col items-center justify-center gap-[3px]">
            <View className="flex-row gap-[3px]">
              <View className="h-[4px] w-[4px] rounded-full bg-gray-400" />
              <View className="h-[4px] w-[4px] rounded-full bg-gray-400" />
            </View>
            <View className="flex-row gap-[3px]">
              <View className="h-[4px] w-[4px] rounded-full bg-gray-400" />
              <View className="h-[4px] w-[4px] rounded-full bg-gray-400" />
            </View>
            <View className="flex-row gap-[3px]">
              <View className="h-[4px] w-[4px] rounded-full bg-gray-400" />
              <View className="h-[4px] w-[4px] rounded-full bg-gray-400" />
            </View>
          </View>
        </TouchableOpacity>

        {/* Quantity input field */}
        <Input
          placeholder="Qty"
          className="w-24"
          value={quantity ?? ''}
          onChangeText={onQuantityChange}
          returnKeyType="next"
          onSubmitEditing={focusNameInput}
          blurOnSubmit={false}
        />
        {/* Item name input field */}
        <TextInput
          ref={nameInputRef}
          value={name}
          onChangeText={onNameChange}
          className="flex-1 text-center text-base leading-5 text-[#000000ff] py-2"
          placeholder="Item name"
          placeholderTextColor="#9ca3af"
          returnKeyType="done"
          textAlignVertical="center"
          selectTextOnFocus
        />
        {/* Delete button */}
        <Button variant="ghost" size="icon" onPress={onDelete} className="h-10 w-10 rounded-full">
          <Trash size={20} color="#FF5C5C" />
        </Button>
      </CardContent>
    </Card>
  );
}

// ===== COMPONENT: ItemInputList =====
const ItemInputList: React.FC<ItemInputListProps> = ({
  items,
  onAddItem,
  onDeleteItem,
  onUpdateItem,
  onReorder,
  loading,
}) => {
  // Text in the name input field
  const [name, setName] = useState('');
  // Text in the quantity input field
  const [qty, setQty] = useState<string>('');
  // Reference to focus the name input programmatically
  const nameInputRef = useRef<TextInput>(null);

  // Sort items by their position so they display in order
  const sortedItems = useMemo(
    () => [...items].sort((a, b) => a.position - b.position),
    [items]
  );

  // Called when user submits a new item
  const addItem = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    // Parse quantity, default to 1 if invalid
    const quantity = qty ? Math.max(1, parseInt(qty, 10) || 1) : undefined;
    onAddItem(trimmed, quantity, qty || null);
    // Clear inputs after adding
    setName('');
    setQty('');
  };

  // Move focus to the name input (called after qty input)
  const focusNameInput = () => {
    nameInputRef.current?.focus();
  };

  // How each item card is rendered in the list
  const renderItem = useCallback(
    ({ item, drag, isActive }: RenderItemParams<Item>) => (
      <ScaleDecorator>
        <ItemInputCard
          name={item.name}
          quantity={item.rawQty ?? (item.quantity ? String(item.quantity) : '')}
          onNameChange={(newName) => onUpdateItem(item.id, { name: newName })}
          onQuantityChange={(newQty) => onUpdateItem(item.id, { rawQty: newQty })}
          onDelete={() => onDeleteItem(item.id)}
          onDrag={drag}
          isActive={isActive}
        />
      </ScaleDecorator>
    ),
    [onUpdateItem, onDeleteItem]
  );

  // Called when user finishes dragging an item to a new position
  const handleDragEnd = useCallback(
    ({ data }: { data: Item[] }) => {
      // Assign new position numbers based on new order
      const reordered = data.map((item, index) => ({
        ...item,
        position: index,
      }));
      onReorder(reordered);
    },
    [onReorder]
  );

  return (
    <View style={{ flex: 1 }}>
      {/* Input bar at the top for adding new items */}
      <View className="flex-row items-center gap-3 mb-5" style={{ marginHorizontal: 20 }}>
        {/* Quantity input */}
        <Input
          placeholder="Qty"
          className="w-20"
          value={qty}
          onChangeText={setQty}
          returnKeyType="next"
          onSubmitEditing={focusNameInput}
          blurOnSubmit={false}
        />
        {/* Item name input */}
        <Input
          ref={nameInputRef}
          placeholder="Add Item"
          className="flex-1"
          value={name}
          onChangeText={setName}
          onSubmitEditing={addItem}
          returnKeyType="done"
        />
        {/* Add button */}
        <Button size="icon" variant="secondary" onPress={addItem} disabled={!name.trim()}>
          <Plus size={12} strokeWidth={Platform.OS === 'web' ? 2.5 : 3.5} color="#ffffff" />
        </Button>
      </View>

      {/* Loading message while fetching from API */}
      {loading && (
        <Text className="text-center mb-3 text-gray-500" style={{ marginHorizontal: 20 }}>Loading your list…</Text>
      )}

      {/* Scrollable list of item cards that can be dragged to reorder */}
      <View style={{ flex: 1 }}>
        <DraggableFlatList
          data={sortedItems}
          onDragEnd={handleDragEnd}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          showsVerticalScrollIndicator={false}
          containerStyle={{ flex: 1 }}
          contentContainerStyle={{ paddingBottom: 40, paddingHorizontal: 20, flexGrow: 1 }}
        />
      </View>
    </View>
  );
};

// ===== SCREEN: itemInput =====
function itemInput() {
  const router = useRouter();
  
  // ----- State -----
  // Whether the list has any items (for showing confirm button)
  const [hasItems, setHasItems] = useState(false);
  // All items in the list
  const [items, setItems] = useState<Item[]>([]);
  // ID of the shopping list from the API
  const [localListId, setLocalListId] = useState<string | null>(null);
  // True while fetching initial data
  const [loading, setLoading] = useState(true);
  // Error state for initial load
  const [error, setError] = useState<string | null>(null);
  // Timers for debouncing API updates per item
  const syncTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  // Base URL for API calls
  const API_BASE = useMemo(
    () => process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api',
    []
  );
  // User identifier for the API
  const CLIENT_ID = 'user';

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

  // Convert API response to Item format
  const mapApiItem = useCallback(
    (apiItem: any, positionOverride?: number): Item => ({
      id: apiItem.id,
      name: apiItem.raw_text_item || apiItem.item_name || 'Item',
      quantity: typeof apiItem.qty_value === 'number' ? apiItem.qty_value : undefined,
      rawQty: apiItem.raw_text_qty ?? null,
      position: typeof positionOverride === 'number' ? positionOverride : apiItem.position ?? 0,
    }),
    []
  );

  // ----- Effects -----
  // Track whether list has any items (for showing confirm button)
  useEffect(() => {
    setHasItems(items.length > 0);
  }, [items]);

  // On mount: fetch existing list or create a new one, then load items
  // Also check flow state to see if we should forward to a later screen
  useEffect(() => {
    let cancelled = false;
    const bootstrap = async () => {
      try {
        // Try to get existing lists for this user
        const existing = await apiFetch(`/shopping-lists?client_id=${CLIENT_ID}`);
        const lists = await existing.json();
        let selected = lists?.[0];
        // If no list exists, create one
        if (!selected) {
          const created = await apiFetch(`/shopping-lists`, {
            method: 'POST',
            body: JSON.stringify({ client_id: CLIENT_ID, title: 'My List' }),
          });
          selected = await created.json();
        }
        if (cancelled) return;
        setListId(selected.id); // Store in global store for cross-screen access
        setLocalListId(selected.id);

        // Check existing flow state - only create initial if none exists
        const existingFlow = await loadFlowState(selected.id);
        if (!existingFlow) {
          const initialFlowState = createInitialFlowState(selected.id);
          await saveFlowState(initialFlowState);
        } else if (existingFlow.currentStep !== 'ITEMS_ENTERED') {
          // Flow state indicates we should be at a later screen - forward there
          if (cancelled) return;
          router.push('/searchSelect');
          return; // Don't continue loading items, we're forwarding
        }

        // Fetch all items in the list
        const itemRes = await apiFetch(`/shopping-lists/${selected.id}/items`);
        const apiItems = await itemRes.json();
        if (cancelled) return;
        const mapped = apiItems.map((i: any, idx: number) => mapApiItem(i, idx));
        setItems(mapped);
      } catch (err) {
        console.error('Failed to initialize list', err);
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
  }, [apiFetch, mapApiItem, router]);

  // Reload items when screen regains focus (handles back navigation)
  // Also update flow state to reflect user navigated back to this screen
  useFocusEffect(
    useCallback(() => {
      const reloadItems = async () => {
        // Use local or global listId
        const listId = localListId || getListId();
        if (!listId) return; // No list ID yet, initial bootstrap will handle it

        try {
          // Update flow state to ITEMS_ENTERED since user is on this screen
          // This handles the case where user navigated back from a later screen
          await updateFlowState(listId, {
            currentStep: 'ITEMS_ENTERED',
            activeJobId: undefined,
            activeJobType: undefined,
          });

          const itemRes = await apiFetch(`/shopping-lists/${listId}/items`);
          const apiItems = await itemRes.json();
          const mapped = apiItems.map((i: any, idx: number) => mapApiItem(i, idx));
          setItems(mapped);
        } catch (err) {
          console.error('Failed to reload items on focus', err);
        }
      };

      // Only reload if we already have a list (not during initial load)
      if (!loading && (localListId || getListId())) {
        reloadItems();
      }
    }, [localListId, loading, apiFetch, mapApiItem])
  );

  // Get the list ID or throw if not ready
  const ensureListId = useCallback(() => {
    if (!localListId) throw new Error('List not ready yet');
    return localListId;
  }, [localListId]);

  // ----- Item mutation & sync helpers -----
  // Add a new item - creates it locally first, then syncs to API
  const handleAddItem = useCallback(
    async (name: string, quantity?: number | null, rawQty?: string | null) => {
      if (!localListId) return;
      const position = items.length;
      // Create temporary ID until API responds
      const tempId = `temp-${Date.now()}`;
      const tempItem: Item = { id: tempId, name, quantity: quantity ?? undefined, rawQty: rawQty ?? null, position };
      // Add to list immediately for responsive UI
      setItems((prev) => [...prev, tempItem]);
      try {
        // Send to API
        const res = await apiFetch(`/shopping-lists/${localListId}/items`, {
          method: 'POST',
          body: JSON.stringify({
            raw_text_item: name,
            raw_text_qty: rawQty,
            position,
          }),
        });
        const created = await res.json();
        // Replace temp item with real one from API
        setItems((prev) =>
          prev.map((it) => (it.id === tempId ? mapApiItem(created, position) : it))
        );
      } catch (err) {
        console.error('Failed to add item', err);
        // Remove temp item if API call failed
        setItems((prev) => prev.filter((it) => it.id !== tempId));
      }
    },
    [apiFetch, items.length, localListId, mapApiItem]
  );

  // Send an item update to the API
  const syncItem = useCallback(
    (item: Item) => {
      const currentListId = ensureListId();
      apiFetch(`/shopping-lists/${currentListId}/items/${item.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          raw_text_item: item.name,
          raw_text_qty: item.rawQty,
          position: item.position,
        }),
      }).catch((err) => console.error('Failed to sync item', err));
    },
    [apiFetch, ensureListId]
  );

  // Debounce sync calls so we dont spam API while user types
  const scheduleSync = useCallback(
    (item: Item) => {
      // Clear any existing timer for this item
      if (syncTimers.current[item.id]) {
        clearTimeout(syncTimers.current[item.id]);
      }
      // Schedule new sync after 250ms
      syncTimers.current[item.id] = setTimeout(() => syncItem(item), 250);
    },
    [syncItem]
  );

  // Update an item locally and schedule API sync
  const handleUpdateItem = useCallback(
    (id: string, changes: Partial<Item>) => {
      setItems((prev) => {
        const next = prev.map((it) => (it.id === id ? { ...it, ...changes } : it));
        const target = next.find((i) => i.id === id);
        // Only sync if its a real item (not temp)
        if (target && !id.startsWith('temp-')) {
          scheduleSync(target);
        }
        return next;
      });
    },
    [scheduleSync]
  );

  // Delete an item locally and from API
  const handleDeleteItem = useCallback(
    async (id: string) => {
      // Remove from local state immediately
      setItems((prev) => prev.filter((i) => i.id !== id));
      // Skip API call for temp items
      if (id.startsWith('temp-') || !localListId) return;
      try {
        await apiFetch(`/shopping-lists/${localListId}/items/${id}`, { method: 'DELETE' });
      } catch (err) {
        console.error('Failed to delete item', err);
      }
    },
    [apiFetch, localListId]
  );

  // Handle drag-to-reorder: update local state and sync all items
  const handleReorder = useCallback(
    (reorderedItems: Item[]) => {
      setItems(reorderedItems);
      // Sync each real item to save new positions
      reorderedItems.forEach((item) => {
        if (!item.id.startsWith('temp-')) {
          scheduleSync(item);
        }
      });
    },
    [scheduleSync]
  );

  // ----- Render -----
  // Show error state with retry option
  if (error) {
    return (
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <Text className="text-center text-gray-600" style={{ fontSize: 16 }}>
            Unable to load your list
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
    // Adjust layout when keyboard appears
    <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
      <KeyboardAvoidingView behavior="padding" style={{ flex: 1 }}>
        <View style={{ flex: 1, marginTop: 16 }}>
          <View style={{ flex: 1 }}>
            {/* The input bar and item list */}
            <ItemInputList
              items={items}
              onAddItem={handleAddItem}
              onDeleteItem={handleDeleteItem}
              onUpdateItem={handleUpdateItem}
              onReorder={handleReorder}
              loading={loading}
            />
          </View>
          {/* Confirm button - only shown when there are items */}
          {hasItems && (
            <View style={{ paddingVertical: 20, marginHorizontal: 20 }}>
              <Button
                variant="continue"
                size="xl"
                onPress={() => {
                  // TEMP: Sync items to global store for demo - remove when API integration is complete
                  setGlobalItems(items.map((it) => ({
                    id: it.id,
                    name: it.name,
                    price: it.price,
                    quantity: it.quantity,
                  })));
                  // end of TEMP: Sync items to global store for demo
                  router.push('/searchSelect');
                }}
              >
                <Text style={{ textAlign: 'center', fontSize: 20 }}>Confirm Items</Text>
                <ArrowRight size={20} color="white" />
              </Button>
            </View>
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export default itemInput;
export { ItemInputList };
