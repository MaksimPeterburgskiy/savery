import React from 'react';
import { Text } from '@/components/ui/text';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { View } from 'react-native';
import { Link } from 'expo-router';
import { ArrowRight } from 'lucide-react-native';

function SearchSelect() {
  const [tab, setTab] = React.useState<string>('');
  return (
    <View style={{ flex: 1, gap: 10, marginTop: 80, marginLeft: 20, marginRight: 20 }}>
      <Text variant={'h2'} style={{ textAlign: 'center' }}>
        Item Search Selection
      </Text>

      {/* Tab list */}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="Speed">
            <Text>Speed</Text>
          </TabsTrigger>
          <TabsTrigger value="Balanced">
            <Text>Balanced</Text>
          </TabsTrigger>
          <TabsTrigger value="Price">
            <Text>Price</Text>
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {/* TODO: Implement a location display on a map */}
      <View
        style={{
          height: 500,
          borderRadius: 10,
          alignItems: 'center',
          backgroundColor: 'lightgray',
        }}>
        <Text style={{ color: 'black' }}>Placeholder for a map implementation</Text>
      </View>

      {tab && (
        <Link href="/itemMatch" asChild>
          <Button variant="continue" size="xl">
            <Text style={{ textAlign: 'center', fontSize: 20 }}>Match Items</Text>
            <ArrowRight size={20} color="white" />
          </Button>
        </Link>
      )}
    </View>
  );
}

export default SearchSelect;
