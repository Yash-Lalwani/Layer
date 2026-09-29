'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useAuth } from './auth-provider';
import styles from './auth-form.module.css';

export function AuthForm({ mode }: { mode: 'login' | 'register' }) {
  const router = useRouter();
  const { user, loading, signIn } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!loading && user) router.replace('/workspace');
  }, [loading, user, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const auth = mode === 'register'
        ? await api.register(name.trim(), email.trim(), password)
        : await api.login(email.trim(), password);
      signIn(auth);
      router.replace('/workspace');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Something went wrong');
    } finally {
      setSubmitting(false);
    }
  }

  return <main className={styles.page}>
    <Link className={styles.brand} href="/"><img src="/layer-logo.svg" width="36" height="36" alt="" />Layer</Link>
    <section className={styles.card}>
      <h1>{mode === 'register' ? 'Get started with Layer' : 'Welcome back'}</h1>
      <p>{mode === 'register' ? 'Create your account to make space for your projects.' : 'Log in to your workspace.'}</p>
      <form onSubmit={submit}>
        {mode === 'register' && <label>Name<input value={name} onChange={event => setName(event.target.value)} autoComplete="name" required maxLength={100} /></label>}
        <label>Email<input type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="email" required /></label>
        <label>Password<input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete={mode === 'register' ? 'new-password' : 'current-password'} required minLength={mode === 'register' ? 8 : undefined} /></label>
        {error && <div className={styles.error} role="alert">{error}</div>}
        <button className={styles.submit} type="submit" disabled={submitting}>{submitting ? 'Please wait…' : mode === 'register' ? 'Create account' : 'Log in'}</button>
      </form>
      <div className={styles.switch}>
        {mode === 'register' ? 'Already have an account?' : 'New to Layer?'}{' '}
        <Link href={mode === 'register' ? '/login' : '/register'}>{mode === 'register' ? 'Log in' : 'Get started'}</Link>
      </div>
    </section>
  </main>;
}

