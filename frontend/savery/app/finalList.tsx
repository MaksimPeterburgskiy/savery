import { Checkbox } from '@/components/ui/checkbox';
import { Text } from '@/components/ui/text';
import { getStores, StoreRef, subscribeStores } from '@/lib/itemStore';
import { CardStyle } from '@/lib/theme';
import React, { useEffect, useState } from 'react';
import { FlatList, ListRenderItem, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

// List of Items Grouped by store for the final list
const StoreList: React.FC = () => {
  const [stores, setStores] = useState<StoreRef[]>(() => getStores());
  useEffect(() => {
    const unsub = subscribeStores((next) => setStores(next));
    return unsub;
  }, []);

  const renderStore: ListRenderItem<StoreRef> = ({ item }) => <StoreCard store={item} />;

  return (
    <FlatList
      data={stores}
      keyExtractor={(store) => store.id}
      renderItem={renderStore}
    //   contentContainerStyle={CardStyle.container}
    />
  );
};

interface StoreCardProps {
  store: StoreRef;
}

const StoreCard: React.FC<StoreCardProps> = ({ store }) => {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  return (
    <View style={CardStyle.card}>
      <View style={CardStyle.headerSpaceBetween}>
        <Text style={CardStyle.mainText}>
          {store.name} - {store.distance}
        </Text>
        <Text style={CardStyle.mainText}>${(store.totalCost ?? 0).toFixed(2)}</Text>
      </View>

      {store.items.map((item) => (
        <View key={item.id} style={CardStyle.itemRow}>
          <View style={CardStyle.imagePlaceholder} />
          <View style={CardStyle.itemInfo}>
            <Text style={CardStyle.mainText}>{item.name}</Text>
            <Text style={CardStyle.subText}>${(item.price ?? 0).toFixed(2)}</Text>
          </View>

          <Checkbox
            style={CardStyle.checkContainer}
            accessibilityLabel={`Select ${item.name}`}
            checked={selectedIds.has(item.id)}
            onCheckedChange={(v: boolean) => {
              setSelectedIds((prev) => {
                const next = new Set(prev);
                if (v) next.add(item.id);
                else next.delete(item.id);
                return next;
              });
            }}
          />
        </View>
      ))}
    </View>
  );
};

function FinalList() {
  return (
    <SafeAreaView style={{ flex: 1 }} edges={['top', 'left', 'right']}>
      <View style={{ flex: 1, gap: 10, marginHorizontal: 20, marginTop: 16 }}>
        <StoreList />
      </View>
    </SafeAreaView>
  );
}

export default FinalList;
