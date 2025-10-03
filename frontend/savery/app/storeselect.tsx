import React from 'react';
import { Text } from '@/components/ui/text';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { View } from 'react-native';
import { Link } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

function StoreSelect() {
  const [tab, setTab] = React.useState('tab1');
  return (
    <View style={{ flex: 1, gap: 10, marginTop: 80, marginLeft: 20, marginRight: 20 }}>
      <Text variant={'h2'} style={{ textAlign: 'center' }}>
        Store Selection
      </Text>

      {/* Tab list */}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="Price">
            <Text>Price</Text>
          </TabsTrigger>
          <TabsTrigger value="Distance">
            <Text>Distance</Text>
          </TabsTrigger>
          <TabsTrigger value="Unit Price">
            <Text>Unit Price</Text>
          </TabsTrigger>
        </TabsList>

        {/* Tab Content */}
        <TabsContent value="Price">
          <View style={{ height: 500, alignItems: 'center', backgroundColor: 'lightgray' }}>
            <Text style={{ color: 'black' }}>Map for Price Based Search</Text>
            {/* <Button variant="store"></Button> */}
          </View>
          <Link href="/itemInput" asChild>
            <Button variant="continue" size="xl">
              <Text style={{ textAlign: 'center', fontSize: 20 }}>Match Items</Text>
              <Ionicons name="arrow-forward" size={20} color="white" />
            </Button>
          </Link>
        </TabsContent>
        <TabsContent value="Distance">
          <View style={{ height: 500, alignItems: 'center', backgroundColor: 'lightgray' }}>
            <Text style={{ color: 'black' }}>Map for Distance Based Search</Text>
          </View>
          <Link href="/itemInput" asChild>
            <Button variant="continue" size="xl">
              <Text style={{ textAlign: 'center', fontSize: 20 }}>Match Items</Text>
              <Ionicons name="arrow-forward" size={20} color="white" />
            </Button>
          </Link>
        </TabsContent>
        <TabsContent value="Unit Price">
          <View style={{ height: 500, alignItems: 'center', backgroundColor: 'lightgray' }}>
            <Text style={{ color: 'black' }}>Map for Unit Price Based Search</Text>
          </View>
          <Link href="/itemInput" asChild>
            <Button variant="continue" size="xl">
              <Text style={{ textAlign: 'center', fontSize: 20 }}>Match Items</Text>
              <Ionicons name="arrow-forward" size={20} color="white" />
            </Button>
          </Link>
        </TabsContent>
      </Tabs>
    </View>
  );
}

export default StoreSelect;
