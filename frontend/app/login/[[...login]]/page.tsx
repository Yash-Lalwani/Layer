import Link from 'next/link';
import { SignIn } from '@clerk/nextjs';
import styles from '@/components/auth/auth-page.module.css';

export default function LoginPage() {
  return <main className={styles.page}>
    <Link className={styles.brand} href="/"><img src="/layer-logo.svg" width="36" height="36" alt="" />Layer</Link>
    <SignIn routing="path" path="/login" fallbackRedirectUrl="/workspace" />
  </main>;
}
