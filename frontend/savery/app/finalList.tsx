import { View } from 'react-native';
import { Text } from '@/components/ui/text';
import { StoreList } from '@/components/ui/card';

function FinalList() {
  return (
    <View style={{ flex: 1, gap: 10, marginTop: 80, marginLeft: 20, marginRight: 20 }}>
      <StoreList />
    </View>
  );
}

export default FinalList;
