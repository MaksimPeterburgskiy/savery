import React, { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { Text } from '@/components/ui/text';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Image,
  type ImageStyle,
  View,
  Keyboard,
  KeyboardAvoidingView,
  ScrollView,
  Platform,
} from 'react-native';
import { Link, Stack } from 'expo-router';
import { Plus, Trash, ArrowRight } from 'lucide-react-native';
import { setItems as setStoredItems } from '@/lib/itemStore';

interface Item {
  id: string;
  name: string;
  price?: number;
  quantity?: number;
}

type ItemInputListProps = {
  items: Item[];
  onDeleteItem: (id: string) => void;
  onListChange?: (list: { id: string; name: string; quantity?: number }[]) => void;
};

const ItemInputList: React.FC<ItemInputListProps> = ({
  items: _items,
  onDeleteItem,
  onListChange,
}) => {
  const [list, setList] = useState<{ id: string; name: string; quantity?: number }[]>([]);
  const [name, setName] = useState('');
  const [qty, setQty] = useState<string>('');

  useEffect(() => {
    onListChange?.(list);
  }, [list, onListChange]);

  const addItem = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const id = `${Date.now()}`;
    const quantity = qty ? Math.max(1, parseInt(qty, 10) || 1) : undefined;
    setList((prev) => [{ id, name: trimmed, quantity }, ...prev]);
    setName('');
    setQty('');
  };

  //   Delete items from the list (does so immutably)
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
          <Plus size={12} strokeWidth={Platform.OS === 'web' ? 2.5 : 3.5} color="#ffffff" />
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

type ItemInputCardProps = {
  name: string;
  quantity?: number;
  onDelete: () => void;
};

function ItemInputCard({ name, quantity, onDelete }: ItemInputCardProps) {
  return (
    <Card className="flex-row items-center rounded-xl bg-[#E5E5E5] px-4 py-3">
      <CardContent className="w-full flex-row items-center justify-between p-0">
        <Input placeholder="" className="w-16" />
        <Text className="text-base text-[#000000ff]">{name}</Text>
        <Button variant="ghost" size="icon" onPress={onDelete} className="h-10 w-10 rounded-full">
          <Trash size={20} color="#FF5C5C" />
        </Button>
      </CardContent>
    </Card>
  );
}

function itemInput() {
  const [hasItems, setHasItems] = useState(false);

  // For random price place holders
  function randomFloatFixed(min: number, max: number): number {
    const v = Math.random() * (max - min) + min;
    return Number(v.toFixed(2));
  }

  return (
    <KeyboardAvoidingView behavior="padding" style={{ flex: 1 }}>
      <View
        style={{
          flex: 1,
          gap: 10,
          marginTop: 80,
          marginHorizontal: 20,
          position: 'relative',
        }}>
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{
            paddingBottom: 140,
            gap: 10,
          }}
          nestedScrollEnabled={true}
          // Allow dragging to dismiss keyboard and ensure drags starting on
          // child elements (inputs, buttons, cards) still trigger scroll.
          keyboardDismissMode="on-drag"
          // Keep tap handling so buttons/inputs still receive taps
          keyboardShouldPersistTaps="handled">
          <View style={{ flex: 1 }}>
            <ItemInputList
              items={[]}
              onDeleteItem={(id) => {
                console.log('delete', id);
              }}
              onListChange={(list) => {
                setHasItems(list.length > 0);
                // keep shared store in sync so other screens (eg itemMatch)
                // can read the current item list. Add simple dummy `alts` and 'price'
                const dummy = list.map((it) => {
                  const price = randomFloatFixed(1, 50);
                  return {
                    ...it,
                    price,
                    alts: (it as any).alts ?? [
                      {
                        id: `${it.id}-a`,
                        name: `suggestion A`,
                        price,
                        quantity: it.quantity,
                        alts: [],
                      },
                      {
                        id: `${it.id}-b`,
                        name: `suggestion B`,
                        price,
                        quantity: it.quantity,
                        alts: [],
                      },
                      {
                        id: `${it.id}-c`,
                        name: `suggestion C`,
                        price,
                        quantity: it.quantity,
                        alts: [],
                      },
                    ],
                  };
                });
                setStoredItems(dummy);
              }}
            />
          </View>
        </ScrollView>
        {/* Confirm button fixed to bottom, list scrolls behind */}
        <View
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 30,
            zIndex: 10,
          }}
          pointerEvents="box-none">
          {hasItems && (
            <Link href="/storeselect" asChild>
              <Button variant="continue" size="xl">
                <Text style={{ textAlign: 'center', fontSize: 20 }}>Confirm Items</Text>
                <ArrowRight size={20} color="white" />
              </Button>
            </Link>
          )}
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

export default itemInput;
export { ItemInputList };
