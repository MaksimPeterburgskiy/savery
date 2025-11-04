import { FlatList, ListRenderItem, View } from 'react-native';
import { Button } from '@/components/ui/button';
import { Text } from '@/components/ui/text';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox, XBox } from '@/components/ui/checkbox';
import React, { useEffect, useState } from 'react';
import { CardStyle } from '@/lib/theme';
import { getItems, subscribe, setItems } from '@/lib/itemStore';
import type { ItemRef } from '@/lib/itemStore';
type Item = ItemRef;

type ItemMatchListProps = {
  onAllSelected?: (allSelected: boolean) => void;
  items: Item[];
  selections: Record<string, 'include' | 'exclude' | undefined>;
  setSelections: React.Dispatch<
    React.SetStateAction<Record<string, 'include' | 'exclude' | undefined>>
  >;
};

const ItemMatchList: React.FC<ItemMatchListProps> = ({
  onAllSelected,
  items,
  selections,
  setSelections,
}) => {
  // Notify the parent when all items are selected for inclusion
  // To be used to enable the "confirm items" button on the itemMatch screen
  useEffect(() => {
    const allSelected =
      items.length > 0 &&
      items.every((it) => {
        if (selections[it.id] === 'include') return true;
        const alts = it.alts;
        if (alts && alts.length > 0) {
          return alts.some((alt) => selections[alt.id] === 'include');
        }
        return false;
      });

    onAllSelected?.(allSelected);
  }, [selections, items, onAllSelected]);

  const renderItem: ListRenderItem<Item> = ({ item }) => (
    <View>
      <ItemMatchCard
        item={item}
        selection={selections[item.id]}
        onSelect={(sel) => {
          setSelections((prev) => {
            const next: Record<string, 'include' | 'exclude' | undefined> = {
              ...prev,
              [item.id]: sel,
            };
            // If parent is included, clear alts (they don't apply)
            // Also if the selection becomes undefined clear alts
            if (sel === 'include' || sel === undefined) {
              if (item.alts && item.alts.length > 0) {
                for (const alt of item.alts) {
                  next[alt.id] = undefined;
                }
              }
            }
            return next;
          });
        }}
      />

      {/* If the item is explicitly excluded, render its alternatives beneath it */}
      {selections[item.id] === 'exclude' && item.alts && item.alts.length > 0 ? (
        <View style={{ marginLeft: 18, marginTop: 8, gap: 8 }}>
          {item.alts.map((alt) => (
            <ItemMatchCard
              key={`${item.id}-alt-${alt.id}`}
              item={alt}
              selection={selections[alt.id]}
              onSelect={(sel) => setSelections((prev) => ({ ...prev, [alt.id]: sel }))}
            />
          ))}
          <View style={{ height: 0 }} />
        </View>
      ) : null}
    </View>
  );

  return (
    <FlatList
      data={items}
      keyExtractor={(item) => item.id}
      renderItem={renderItem}
      contentContainerStyle={CardStyle.container}
    />
  );
};

interface ItemMatchCardProps {
  item: Item;
  selection?: 'include' | 'exclude' | undefined;
  onSelect: (sel: 'include' | 'exclude' | undefined) => void;
}

const ItemMatchCard: React.FC<ItemMatchCardProps> = ({ item, selection, onSelect }) => {
  return (
    <Card className="flex-row items-center rounded-xl bg-[#E5E5E5] px-4 py-3">
      <CardContent className="w-full flex-row items-start justify-between p-0">
        <View className="flex-col items-start justify-between p-0">
          <Text className="text-base text-[#000000ff]">{item.name}</Text>
          {typeof item.price === 'number' ? (
            <Text className="text-base text-[#000000ff]">${item.price.toFixed(2)}</Text>
          ) : null}
        </View>

        <View className="align-center flex-row items-end items-center justify-between gap-2 p-0">
          <Checkbox
            style={CardStyle.checkContainer}
            accessibilityLabel={`Include ${item.name}`}
            checked={selection === 'include'}
            onCheckedChange={(v: boolean) => onSelect(v ? 'include' : undefined)}
          />
          <XBox
            style={CardStyle.xContainer}
            accessibilityLabel={`Exclude ${item.name}`}
            checked={selection === 'exclude'}
            onCheckedChange={(v: boolean) => onSelect(v ? 'exclude' : undefined)}
          />
        </View>
      </CardContent>
    </Card>
  );
};

function ItemMatch() {
  const [items, setItemsState] = useState<Item[]>(() => getItems());
  const [selections, setSelections] = useState<Record<string, 'include' | 'exclude' | undefined>>(
    {}
  );
  const [allSelected, setAllSelected] = useState(false);
  const router = useRouter();

  // subscribe to shared item store so this list updates when items are
  // added/removed from the previous screen
  useEffect(() => {
    const unsub = subscribe((next) => setItemsState(next));
    return unsub;
  }, []);

  const confirmAndProceed = () => {
    // include any original items or alts explicitly marked 'include'
    const included: Item[] = [];
    for (const it of items) {
      if (selections[it.id] === 'include') {
        included.push(it);
      }
      if (it.alts && it.alts.length > 0) {
        for (const alt of it.alts) {
          if (selections[alt.id] === 'include') {
            included.push(alt);
          }
        }
      }
    }

    // send included items to the shared store so FinalList consumes them
    setItems(included);
    router.push('/finalList');
  };

  return (
    <View style={{ flex: 1, gap: 10, marginTop: 80, marginLeft: 20, marginRight: 20 }}>
      <ItemMatchList
        onAllSelected={(v) => setAllSelected(v)}
        items={items}
        selections={selections}
        setSelections={setSelections}
      />
      {allSelected && (
        <View style={{ position: 'absolute', left: 0, right: 0, bottom: 40 }}>
          <Button variant="continue" size="xl" onPress={confirmAndProceed}>
            <Text style={{ textAlign: 'center', fontSize: 20 }}>Confirm Items</Text>
            <Ionicons name="arrow-forward" size={20} color="white" />
          </Button>
        </View>
      )}
    </View>
  );
}

export default ItemMatch;
