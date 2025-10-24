import React from 'react';
import { Text } from '@/components/ui/text';
import { ItemInputCard, ItemInputList } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Image,
  type ImageStyle,
  View,
  Keyboard,
  KeyboardAvoidingView,
  TouchableWithoutFeedback,
  ScrollView,
} from 'react-native';
import { Link, Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

function itemInput() {
  const [showList, setShowList] = React.useState(false);

  const handleAddPress = () => {
    // toggle showing the input list
    setShowList((s) => !s);
  };
  return (
    <ScrollView>
      <KeyboardAvoidingView behavior="padding" style={{ flex: 1 }}>
        <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
          <View
            style={{
              flex: 1,
              gap: 10,
              marginTop: 80,
              marginHorizontal: 20,
              position: 'relative',
            }}>
            <View style={{ flex: 1 }}>
              <ItemInputList
                items={[]}
                onDeleteItem={(id) => {
                  // no-op for now; ItemInputList maintains its own items
                  console.log('delete', id);
                }}
              />
            </View>

            {/* Spacer so last list items aren't hidden behind the fixed button */}
            <View style={{ height: 120 }} />

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
              <Link href="/storeselect" asChild>
                <Button variant="continue" size="xl">
                  <Text style={{ textAlign: 'center', fontSize: 20 }}>Confirm Items</Text>
                  <Ionicons name="arrow-forward" size={20} color="white" />
                </Button>
              </Link>
            </View>
          </View>
        </TouchableWithoutFeedback>
      </KeyboardAvoidingView>
    </ScrollView>
  );
}

export default itemInput;
