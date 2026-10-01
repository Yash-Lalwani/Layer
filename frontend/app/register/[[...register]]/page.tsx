import Link from 'next/link';
import { SignUp } from '@clerk/nextjs';
import styles from '@/components/auth/auth-page.module.css';

export default function RegisterPage() {
  return <main className={styles.page}>
    <Link className={styles.brand} href="/"><img src="/layer-logo.svg" width="36" height="36" alt="" />Layer</Link>
    <SignUp routing="path" path="/register" fallbackRedirectUrl="/workspace" />
  </main>;
}
