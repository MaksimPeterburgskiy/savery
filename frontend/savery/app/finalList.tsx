import { FlatList, ListRenderItem, View } from 'react-native';
import { Text } from '@/components/ui/text';
import { Checkbox } from '@/components/ui/checkbox';
import { CardStyle } from '@/lib/theme';
import { useEffect, useState } from 'react';
import { getStores, subscribeStores, StoreRef } from '@/lib/itemStore';

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
      contentContainerStyle={CardStyle.container}
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
      <View style={CardStyle.header}>
        <Text style={CardStyle.storeName}>
          {store.name} - {store.distance}
        </Text>
        <Text style={CardStyle.totalCost}>${(store.totalCost ?? 0).toFixed(2)}</Text>
      </View>

      {store.items.map((item) => (
        <View key={item.id} style={CardStyle.itemRow}>
          <View style={CardStyle.imagePlaceholder} />
          <View style={CardStyle.itemInfo}>
            <Text style={CardStyle.itemName}>{item.name}</Text>
            <Text style={CardStyle.itemPrice}>${(item.price ?? 0).toFixed(2)}</Text>
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
    <View style={{ flex: 1, gap: 10, marginTop: 80, marginLeft: 20, marginRight: 20 }}>
      <StoreList />
    </View>
  );
}

export default FinalList;
