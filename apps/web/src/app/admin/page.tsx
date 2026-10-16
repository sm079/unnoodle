import type { Metadata } from 'next';
import { Admin } from '@/components/admin';

export const metadata: Metadata = {
  title: 'Admin · unnoodle'
};

export default function AdminPage() {
  return <Admin />;
}
