import React from 'react';
import { Text } from '@/components/ui/text';
import { ItemCard } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Image,
  type ImageStyle,
  View,
  Keyboard,
  KeyboardAvoidingView,
  TouchableWithoutFeedback,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

function itemInput() {
  return (
    <KeyboardAvoidingView behavior="padding" style={{ flex: 1 }}>
      <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
        <View style={{ flex: 1, gap: 10 }}>
          {/* Starting Before Items are added */}
          <Text variant="h2" style={{ textAlign: 'center' }}>
            Add Items To Begin!
          </Text>
          <Button variant="dashed" size="xl">
            <Ionicons name="add" size={30} color="#4AA8D8" />
          </Button>

          {/* After Items are added */}
          <ItemCard name="Apples" onDelete={() => console.log('Delete Apples')} />

          {/* Add item or move to store */}
          <View style={{ flexDirection: 'row', alignItems: 'stretch', width: '100%', gap: 10 }}>
            <Button variant="dashed" size="xl" style={{ flex: 1 }}>
              <Ionicons name="add" size={30} color="#4AA8D8" />
            </Button>
            <Button variant="store" size="xl" style={{ flex: 1 }}>
              <Text style={{ textAlign: 'center', fontSize: 20 }}>Stores</Text>
              <Ionicons name="arrow-forward" size={20} color="white" />
            </Button>
          </View>
        </View>
      </TouchableWithoutFeedback>
    </KeyboardAvoidingView>
  );
}

export default itemInput;
