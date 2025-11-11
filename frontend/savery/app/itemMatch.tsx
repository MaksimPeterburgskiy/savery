import { FlatList, ListRenderItem, View } from 'react-native';
import { Button } from '@/components/ui/button';
import { Text } from '@/components/ui/text';
import { useRouter } from 'expo-router';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import React, { useEffect, useState } from 'react';
import { CardStyle } from '@/lib/theme';
import { getItems, subscribe, setItems } from '@/lib/itemStore';
import type { ItemRef } from '@/lib/itemStore';
import { ArrowRight } from 'lucide-react-native';
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
    <ItemMatchCard
      key={item.id}
      item={item}
      selections={selections}
      setSelections={setSelections}
    />
  );

  return (
    <FlatList
      data={items}
      keyExtractor={(item) => item.id}
      renderItem={renderItem}
      contentContainerStyle={{ paddingBottom: 140 }}
    />
  );
};

interface ItemMatchCardProps {
  item: Item;
  selections: Record<string, 'include' | 'exclude' | undefined>;
  setSelections: React.Dispatch<
    React.SetStateAction<Record<string, 'include' | 'exclude' | undefined>>
  >;
}

const ItemMatchCard: React.FC<ItemMatchCardProps> = ({ item, selections, setSelections }) => {
  const suggestions = item.alts && item.alts.length > 0 ? item.alts : [item];
  const suggestionCount = suggestions.length;

  return (
    <View>
      <Card style={CardStyle.card}>
        <CardContent className="w-full p-0">
          <View style={CardStyle.headerSpaceBetween}>
            {/* Title: item name and number of suggestions underneath (no price, no controls) */}
            <Text style={CardStyle.mainText}>{item.name}</Text>
            <Text style={CardStyle.subText}>
              {suggestionCount} match{suggestionCount !== 1 ? 'es' : ''}
            </Text>
          </View>
          {/* Intentionally no include/exclude controls on the title — selections happen per suggestion below */}
        </CardContent>

        {/* Always show suggestions as rows beneath the title */}
        <View style={{ gap: 2 }}>
          {suggestions.map((sugg) => (
            <View key={`${item.id}-sugg-${sugg.id}`} style={CardStyle.itemRow}>
              <View style={CardStyle.imagePlaceholder} />
              <View style={CardStyle.itemInfo}>
                <Text style={CardStyle.mainText}>{sugg.name}</Text>
                <Text style={CardStyle.subText}>${(sugg.price ?? 0).toFixed(2)}</Text>
              </View>

              <Checkbox
                style={CardStyle.checkContainer}
                accessibilityLabel={`Select ${sugg.name}`}
                checked={selections[sugg.id] === 'include'}
                onCheckedChange={(v: boolean) =>
                  setSelections((prev: Record<string, 'include' | 'exclude' | undefined>) => {
                    const next = { ...prev };
                    next[sugg.id] = v ? 'include' : undefined;
                    return next;
                  })
                }
              />
            </View>
          ))}
        </View>
      </Card>
    </View>
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
        <View style={{ position: 'absolute', left: 0, right: 0, bottom: 30 }}>
          <Button variant="continue" size="xl" onPress={confirmAndProceed}>
            <Text style={{ textAlign: 'center', fontSize: 20 }}>Confirm Items</Text>
            <ArrowRight size={20} color="white" />
          </Button>
        </View>
      )}
    </View>
  );
}

export default ItemMatch;
