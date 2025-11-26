import { Text, TextClassContext } from '@/components/ui/text';
import { cn } from '@/lib/utils';
import {
    View,
    type ViewProps
} from 'react-native';
// import { Ionicons as IonIcons } from '@expo/vector-icons';
import React, { forwardRef } from 'react';

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

const Card = forwardRef<View, ViewProps>(({ className, ...props }, ref) => (
  <TextClassContext.Provider value="text-card-foreground">
    <View
      ref={ref}
      className={cn(
        'flex flex-col gap-6 rounded-xl border border-border bg-card py-6 shadow-sm shadow-black/5',
        className
      )}
      {...props}
    />
  </TextClassContext.Provider>
));

const CardHeader = forwardRef<View, ViewProps>(({ className, ...props }, ref) => (
  <View ref={ref} className={cn('flex flex-col gap-1.5 px-6', className)} {...props} />
));

const CardTitle = forwardRef<Text, React.ComponentProps<typeof Text>>(
  ({ className, ...props }, ref) => (
    <Text
      ref={ref}
      role="heading"
      aria-level={3}
      className={cn('font-semibold leading-none', className)}
      {...props}
    />
  )
);

const CardDescription = forwardRef<Text, React.ComponentProps<typeof Text>>(
  ({ className, ...props }, ref) => (
    <Text ref={ref} className={cn('text-sm text-muted-foreground', className)} {...props} />
  )
);

const CardContent = forwardRef<View, ViewProps>(({ className, ...props }, ref) => (
  <View ref={ref} className={cn('px-6', className)} {...props} />
));

const CardFooter = forwardRef<View, ViewProps>(({ className, ...props }, ref) => (
  <View ref={ref} className={cn('flex flex-row items-center px-6', className)} {...props} />
));





export {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle
};
