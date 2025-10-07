import { Text, TextClassContext } from '@/components/ui/text';
import { Button } from '@/components/ui/button';
import { Input } from './input';
import { cn } from '@/lib/utils';
import {
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  View,
  type ViewProps,
  ListRenderItem,
} from 'react-native';
import { Ionicons as IonIcons } from '@expo/vector-icons';
import React, { useEffect, useState } from 'react';
import { FlatList } from 'react-native';
import { Checkbox } from '@/components/ui/checkbox';

// ---- Types ----
export interface Item {
  id: string;
  name: string;
  price: number;
}

export interface Store {
  id: string;
  name: string;
  distance: string;
  totalCost: number;
  items: Item[];
}

// Example Store Data (dynamic integration from backend later)
const storeData: Store[] = [
  {
    id: '1',
    name: 'Walmart',
    distance: '2.1mi',
    totalCost: 23.5,
    items: [{ id: '1a', name: 'Bananas', price: 2.49 }],
  },
  {
    id: '2',
    name: 'Target',
    distance: '3.6mi',
    totalCost: 57.2,
    items: [
      { id: '2a', name: 'Milk', price: 3.19 },
      { id: '2b', name: 'Bread', price: 2.49 },
      { id: '2c', name: 'Eggs', price: 5.59 },
    ],
  },
  {
    id: '3',
    name: 'Trader Joes',
    distance: '5.4mi',
    totalCost: 32.8,
    items: [
      { id: '3a', name: 'Almonds', price: 10.0 },
      { id: '3b', name: 'Oat Milk', price: 5.5 },
    ],
  },
];

function Card({ className, ...props }: ViewProps & React.RefAttributes<View>) {
  return (
    <TextClassContext.Provider value="text-card-foreground">
      <View
        className={cn(
          'flex flex-col gap-6 rounded-xl border border-border bg-card py-6 shadow-sm shadow-black/5',
          className
        )}
        {...props}
      />
    </TextClassContext.Provider>
  );
}

function CardHeader({ className, ...props }: ViewProps & React.RefAttributes<View>) {
  return <View className={cn('flex flex-col gap-1.5 px-6', className)} {...props} />;
}

function CardTitle({
  className,
  ...props
}: React.ComponentProps<typeof Text> & React.RefAttributes<Text>) {
  return (
    <Text
      role="heading"
      aria-level={3}
      className={cn('font-semibold leading-none', className)}
      {...props}
    />
  );
}

function CardDescription({
  className,
  ...props
}: React.ComponentProps<typeof Text> & React.RefAttributes<Text>) {
  return <Text className={cn('text-sm text-muted-foreground', className)} {...props} />;
}

function CardContent({ className, ...props }: ViewProps & React.RefAttributes<View>) {
  return <View className={cn('px-6', className)} {...props} />;
}

function CardFooter({ className, ...props }: ViewProps & React.RefAttributes<View>) {
  return <View className={cn('flex flex-row items-center px-6', className)} {...props} />;
}

// Specific card for added items to list
type ItemCardProps = {
  name: string;
  onDelete: () => void;
};

function ItemCard({ name, onDelete }: ItemCardProps) {
  return (
    <Card className="flex-row items-center rounded-xl bg-[#E5E5E5] px-4 py-3">
      <CardContent className="w-full flex-row items-center justify-between p-0">
        <Input placeholder="qty." className="w-12" />
        <Text className="text-base text-[#000000ff]">{name}</Text>
        <Button variant="ghost" size="icon" onPress={onDelete} className="h-10 w-10 rounded-full">
          <IonIcons name="trash-outline" size={20} color="#FF5C5C" />
        </Button>
      </CardContent>
    </Card>
  );
}

const StoreList: React.FC = () => {
  const [stores, setStores] = useState<Store[]>(storeData);

  const renderStore: ListRenderItem<Store> = ({ item }) => <StoreCard store={item} />;

  return (
    <FlatList
      data={stores}
      keyExtractor={(store) => store.id}
      renderItem={renderStore}
      contentContainerStyle={styles.container}
    />
  );
};

interface StoreCardProps {
  store: Store;
}

const StoreCard: React.FC<StoreCardProps> = ({ store }) => (
  <View style={styles.card}>
    <View style={styles.header}>
      <Text style={styles.storeName}>
        {store.name} - {store.distance}
      </Text>
      <Text style={styles.totalCost}>${store.totalCost.toFixed(2)}</Text>
    </View>

    {store.items.map((item) => (
      <View key={item.id} style={styles.itemRow}>
        <View style={styles.imagePlaceholder} />
        <View style={styles.itemInfo}>
          <Text style={styles.itemName}>{item.name}</Text>
          <Text style={styles.itemPrice}>${item.price.toFixed(2)}</Text>
        </View>
        {/* <Checkbox accessibilityLabel={`Select ${item.name}`} checked={false} onCheckedChange={function (checked: boolean): void {
                checked = !checked;
            }} /> */}
      </View>
    ))}
  </View>
);

const styles = StyleSheet.create({
  container: {
    // padding: 16,
  },
  card: {
    backgroundColor: '#EDEDED',
    borderRadius: 12,
    padding: 12,
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  storeName: {
    fontWeight: '700',
    color: '#000',
  },
  totalCost: {
    fontWeight: '700',
    color: '#000',
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFF',
    borderRadius: 12,
    padding: 8,
    marginTop: 6,
  },
  imagePlaceholder: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: '#D3D3D3',
    marginRight: 10,
  },
  itemInfo: {
    color: '#000',
    flex: 1,
  },
  itemName: {
    color: '#000',
    fontWeight: '600',
  },
  itemPrice: {
    color: '#555',
  },
  checkContainer: {
    width: 36,
    height: 36,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: '#4ADE80',
    justifyContent: 'center',
    alignItems: 'center',
  },
  xContainer: {
    width: 36,
    height: 36,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: '#FF5C5C',
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkIcon: {
    color: '#4ADE80',
    fontWeight: '700',
  },
  xIcon: {
    color: '#FF5C5C',
    fontWeight: '700',
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});

export {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  ItemCard,
  StoreList,
};
