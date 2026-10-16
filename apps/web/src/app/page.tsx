import { Landing } from '@/components/landing/landing';

// Signed-in visitors go straight to the studio (src/proxy.ts), so this page is the same for everyone and prerendered
export default function Home() {
  return <Landing />;
}
