# Denguard Frontend

Next.js dashboard for the public and admin Denguard interface.

## Local Development

1. Copy `.env.example` to `.env.local`.
2. Set:
   - `NEXT_PUBLIC_API_BASE_URL`
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
3. Run:

```bash
npm install
npm run dev
```

## Vercel Deployment

Deploy the `dengue-web` folder as the project root.

### Build settings

- Framework: `Next.js`
- Install command: `npm install`
- Build command: `npm run build`
- Output: default Next.js output

### Required environment variables

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Example:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-api-domain.up.railway.app
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

## Notes

- The dashboard fetches data from the FastAPI backend, so the API must be deployed and reachable first.
- If you update the API domain, redeploy the frontend so the public env variable is rebuilt into the client bundle.
