# Layer frontend

Next.js 16, React 19, TypeScript and Tailwind CSS. The light landing page contains an interactive sample; authenticated projects live in the dark workspace.

## Run locally

1. Install dependencies: `npm ci`.
2. Create a Clerk Development application with email sign-in and email verification enabled. In its API Keys page, put the publishable key in `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and the secret key in `CLERK_SECRET_KEY` in the ignored `frontend/.env.local`. Add the remaining values shown in `.env.example`. Never put the secret key in a `NEXT_PUBLIC_` variable.
3. Configure the matching backend key and run the database migration as described in `../backend/README.md`.
4. Start the backend, then run `npm run dev`.
5. Open `http://localhost:3000`, create a Clerk account, verify its email, and open the workspace.

Run `npm run typecheck` and `npm run build` to verify the frontend.
