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
// import { Ionicons as IonIcons } from '@expo/vector-icons';
import React, { useEffect, useState } from 'react';
import { FlatList } from 'react-native';
import { Checkbox, XBox } from '@/components/ui/checkbox';
import { CardStyle } from '@/lib/theme';

export interface Item {
  id: string;
  name: string;
  price: number;
  alts: Item[];
}

export interface Store {
  id: string;
  name: string;
  distance: string;
  totalCost: number;
  items: Item[];
}

const alternates: Item[] = [
  { id: '4a', name: 'Alt 1', price: 3.99, alts: [] },
  { id: '4b', name: 'Alt 2', price: 4.29, alts: [] },
  { id: '4c', name: 'Alt 3', price: 2.99, alts: [] },
];
// Example Item Data
const itemData: Item[] = [
  { id: '1a', name: 'Bananas', price: 2.49, alts: alternates },
  { id: '2a', name: 'Milk', price: 3.19, alts: alternates },
  { id: '2b', name: 'Bread', price: 2.49, alts: alternates },
  { id: '2c', name: 'Eggs', price: 5.59, alts: alternates },
  { id: '3a', name: 'Almonds', price: 10.0, alts: alternates },
  { id: '3b', name: 'Oat Milk', price: 5.5, alts: alternates },
];

// Example Store Data (dynamic integration from backend later)
const storeData: Store[] = [
  {
    id: '1',
    name: 'Walmart',
    distance: '2.1mi',
    totalCost: 23.5,
    items: [{ id: '1a', name: 'Bananas', price: 2.49, alts: [] }],
  },
  {
    id: '2',
    name: 'Target',
    distance: '3.6mi',
    totalCost: 57.2,
    items: [
      { id: '2a', name: 'Milk', price: 3.19, alts: [] },
      { id: '2b', name: 'Bread', price: 2.49, alts: [] },
      { id: '2c', name: 'Eggs', price: 5.59, alts: [] },
    ],
  },
  {
    id: '3',
    name: 'Trader Joes',
    distance: '5.4mi',
    totalCost: 32.8,
    items: [
      { id: '3a', name: 'Almonds', price: 10.0, alts: [] },
      { id: '3b', name: 'Oat Milk', price: 5.5, alts: [] },
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
//   ItemInputCard,
//   ItemInputList,
  StoreList,
//   ItemMatchList,
};
