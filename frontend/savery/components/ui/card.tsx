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
import { Checkbox, XBox } from '@/components/ui/checkbox';
import { CardStyle } from '@/lib/theme';

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

// Example Item Data
const itemData: Item[] = [
  { id: '1a', name: 'Bananas', price: 2.49 },
  { id: '2a', name: 'Milk', price: 3.19 },
  { id: '2b', name: 'Bread', price: 2.49 },
  { id: '2c', name: 'Eggs', price: 5.59 },
  { id: '3a', name: 'Almonds', price: 10.0 },
  { id: '3b', name: 'Oat Milk', price: 5.5 },
];
const alternates: Item[] = [
  { id: '4a', name: 'Alt 1', price: 3.99 },
  { id: '4b', name: 'Alt 2', price: 4.29 },
  { id: '4c', name: 'Alt 3', price: 2.99 },
];

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

const ItemMatchList: React.FC = () => {
  const [items, setItems] = useState<Item[]>(itemData);
  const renderItem: ListRenderItem<Item> = ({ item }) => <ItemMatchCard item={item} />;

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
}

const ItemMatchCard: React.FC<ItemMatchCardProps> = ({ item }) => {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  return (
    <Card className="flex-row items-center rounded-xl bg-[#E5E5E5] px-4 py-3">
      <CardContent className="w-full flex-row items-start justify-between p-0">
        <View className="flex-col items-start justify-between p-0">
          <Text className="text-base text-[#000000ff]">{item.name}</Text>
          <Text className="text-base text-[#000000ff]">${item.price.toFixed(2)}</Text>
        </View>

        <View className="flex-row items-end align-center gap-2 items-center justify-between p-0">
          <Checkbox
            style={CardStyle.checkContainer}
            accessibilityLabel={`Include ${item.name}`}
            checked={selectedIds.has(`${item.id}::include`)}
            onCheckedChange={(v: boolean) => {
              setSelectedIds(() => {
            const next = new Set<string>();
            if (v) next.add(`${item.id}::include`);
            return next;
              });
            }}
          />
          <XBox
            style={CardStyle.xContainer}
            accessibilityLabel={`Exclude ${item.name}`}
            checked={selectedIds.has(`${item.id}::exclude`)}
            onCheckedChange={(v: boolean) => {
              setSelectedIds(() => {
            const next = new Set<string>();
            if (v) next.add(`${item.id}::exclude`);
            return next;
              });
            }}
          />
        </View>
      </CardContent>
    </Card>
  );
};

// List of Items Grouped by store for the final list
const StoreList: React.FC = () => {
  const [stores, setStores] = useState<Store[]>(storeData);
  const renderStore: ListRenderItem<Store> = ({ item }) => <StoreCard store={item} />;

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
  store: Store;
}

const StoreCard: React.FC<StoreCardProps> = ({ store }) => {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  return (
    <View style={CardStyle.card}>
      <View style={CardStyle.header}>
        <Text style={CardStyle.storeName}>
          {store.name} - {store.distance}
        </Text>
        <Text style={CardStyle.totalCost}>${store.totalCost.toFixed(2)}</Text>
      </View>

      {store.items.map((item) => (
        <View key={item.id} style={CardStyle.itemRow}>
          <View style={CardStyle.imagePlaceholder} />
          <View style={CardStyle.itemInfo}>
            <Text style={CardStyle.itemName}>{item.name}</Text>
            <Text style={CardStyle.itemPrice}>${item.price.toFixed(2)}</Text>
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

export {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  ItemCard,
  StoreList,
  ItemMatchList,
};
