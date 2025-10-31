import { FlatList, ListRenderItem, View } from 'react-native';
import { Button } from '@/components/ui/button';
import { Text } from '@/components/ui/text';
import { Link } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox, XBox } from '@/components/ui/checkbox';
import React, { useEffect, useState } from 'react';
import { CardStyle } from '@/lib/theme';
import { getItems, subscribe } from '@/lib/itemStore';

interface Item {
  id: string;
  name: string;
  price?: number;
  quantity?: number;
  alts?: string[];
}

type ItemMatchListProps = {
  onAllSelected?: (allSelected: boolean) => void;
};

const ItemMatchList: React.FC<ItemMatchListProps> = ({ onAllSelected }) => {
  const [items, setItems] = useState<Item[]>(() => getItems());
  const [selections, setSelections] = useState<Record<string, 'include' | 'exclude' | undefined>>(
    {}
  );

  // Notify the parent when all items are selected for inclusion
  // To be used to enable the "confirm items" button on the itemMatch screemn
  useEffect(() => {
    const allSelected = items.length > 0 && items.every((it) => selections[it.id] === 'include');
    onAllSelected?.(allSelected);
  }, [selections, items, onAllSelected]);

  // subscribe to shared item store so this list updates when items are
  // added/removed from the previous screen
  useEffect(() => {
    const unsub = subscribe((next) => setItems(next));
    return unsub;
  }, []);

  const renderItem: ListRenderItem<Item> = ({ item }) => (
    <ItemMatchCard
      item={item}
      selection={selections[item.id]}
      onSelect={(sel) => {
        setSelections((prev) => ({ ...prev, [item.id]: sel }));
      }}
    />
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
  const [allSelected, setAllSelected] = useState(false);

  return (
    <View style={{ flex: 1, gap: 10, marginTop: 80, marginLeft: 20, marginRight: 20 }}>
      <ItemMatchList onAllSelected={(v) => setAllSelected(v)} />
      {allSelected && (
        <View style={{ position: 'absolute', left: 0, right: 0, bottom: 40 }}>
          <Link href="/finalList" asChild>
            <Button variant="continue" size="xl">
              <Text style={{ textAlign: 'center', fontSize: 20 }}>Confirm Items</Text>
              <Ionicons name="arrow-forward" size={20} color="white" />
            </Button>
          </Link>
        </View>
      )}
    </View>
  );
}

export default ItemMatch;
