import { Text, TextClassContext } from '@/components/ui/text';
import { Button } from '@/components/ui/button';
import { Input } from './input';
import { cn } from '@/lib/utils';
import { View, type ViewProps } from 'react-native';
import { Ionicons as IonIcons } from '@expo/vector-icons';

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
        <Input placeholder="qty." keyboardType="numeric" className="w-12" />
        <Text className="text-base text-[#000000ff]">{name}</Text>
        <Button variant="ghost" size="icon" onPress={onDelete} className="w-10 h-10 rounded-full">
            <IonIcons name="trash-outline" size={20} color="#FF5C5C" />
        </Button>
      </CardContent>
    </Card>
  );
}

export { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle, ItemCard };
