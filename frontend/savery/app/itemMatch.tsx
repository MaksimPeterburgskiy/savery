import { View } from 'react-native';
import { Button } from '@/components/ui/button';
import { Text } from '@/components/ui/text';
import { Link } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { ItemMatchList } from '@/components/ui/card';
import React, { useState } from 'react';

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
