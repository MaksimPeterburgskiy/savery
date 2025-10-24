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

type ItemInputListProps = {
  items: Item[];
  onDeleteItem: (id: string) => void;
};

const ItemInputList: React.FC<ItemInputListProps> = ({ items: _items, onDeleteItem }) => {
  const [list, setList] = useState<{ id: string; name: string; quantity?: number }[]>([]);
  const [name, setName] = useState('');
  const [qty, setQty] = useState<string>('');

  const addItem = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const id = `${Date.now()}`;
    const quantity = qty ? Math.max(1, parseInt(qty, 10) || 1) : undefined;
    setList((prev) => [{ id, name: trimmed, quantity }, ...prev]);
    setName('');
    setQty('');
  };

  const handleDelete = (id: string) => {
    setList((prev) => prev.filter((i) => i.id !== id));
    onDeleteItem(id);
  };

  return (
    <View className="gap-3">
      <View className="flex-row items-center gap-3">
        <Input
          placeholder="Add item"
          className="flex-1"
          value={name}
          onChangeText={setName}
          onSubmitEditing={addItem}
          returnKeyType="done"
        />
        <Button size="icon" variant="secondary" onPress={addItem} disabled={!name.trim()}>
          <IonIcons name="add" size={20} color="#000" />
        </Button>
      </View>

      {list.map((i) => (
        <ItemInputCard
          key={i.id}
          name={i.name}
          quantity={i.quantity}
          onDelete={() => handleDelete(i.id)}
        />
      ))}
    </View>
  );
};

// Specific card for added items to list
type ItemInputCardProps = {
  name: string;
  quantity?: number;
  onDelete: () => void;
};

function ItemInputCard({ name, quantity, onDelete }: ItemInputCardProps) {
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

type ItemMatchListProps = {
  onAllSelected?: (allSelected: boolean) => void;
};

const ItemMatchList: React.FC<ItemMatchListProps> = ({ onAllSelected }) => {
  const [items, setItems] = useState<Item[]>(itemData);
  const [selections, setSelections] = useState<Record<string, 'include' | 'exclude' | undefined>>(
    {}
  );

  // Notify the parent when all items are selected for inclusion
  // To be used to enable the "confirm items" button on the itemMatch screemn
  useEffect(() => {
    const allSelected = items.length > 0 && items.every((it) => selections[it.id] === 'include');
    onAllSelected?.(allSelected);
  }, [selections, items, onAllSelected]);

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
          <Text className="text-base text-[#000000ff]">${item.price.toFixed(2)}</Text>
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
  ItemInputCard,
  ItemInputList,
  StoreList,
  ItemMatchList,
};
