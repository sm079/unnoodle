import { Suspense } from 'react';
import type { Metadata } from 'next';
import { AccountForm } from '@/components/account-form';

export const metadata: Metadata = {
  title: 'Sign in · unnoodle'
};

export default function SignInPage() {
  return (
    // The form reads where to go next from the address, which is only known in the browser
    <Suspense>
      <AccountForm mode="sign-in" />
    </Suspense>
  );
}
