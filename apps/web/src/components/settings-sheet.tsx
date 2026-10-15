import { SettingsIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';

export function SettingsSheet() {
  return (
    <Sheet>
      <SheetTrigger render={<Button variant="ghost" size="icon" aria-label="Open settings" />}>
        <SettingsIcon />
      </SheetTrigger>
      <SheetContent side="bottom" className="max-h-[85dvh] rounded-t-xl">
        <SheetHeader>
          <SheetTitle>Settings</SheetTitle>
          <SheetDescription>Nothing to set yet.</SheetDescription>
        </SheetHeader>
      </SheetContent>
    </Sheet>
  );
}
