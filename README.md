# Number Info API — Vercel Deploy

## Setup Steps

### 1. Upstash Redis (Free DB) banao
- https://upstash.com par free account banao
- **Create Database** → naam do → Region select karo (Asia me Mumbai/Singapore)
- Database khulne ke baad **REST API** section me jaao
- Copy karo: `UPSTASH_REDIS_REST_URL` aur `UPSTASH_REDIS_REST_TOKEN`

### 2. GitHub par push karo
- Naya repo banao
- Upar wali 5 files upload karo (same structure me)

### 3. Vercel par import karo
- https://vercel.com par GitHub se sign in
- **Add New → Project** → apna repo import karo
- **Environment Variables** me daalo:
  - `UPSTASH_REDIS_REST_URL` = (Upstash se copy kiya)
  - `UPSTASH_REDIS_REST_TOKEN` = (Upstash se copy kiya)
  - `ADMIN_USER` = anish  (optional, default already anish)
  - `ADMIN_PASS` = anish123  (optional, ye change karna recommended hai)
- **Deploy** click karo

### 4. Use karo
- Admin panel: `https://your-app.vercel.app/`
- Public API: `https://your-app.vercel.app/api?key=YOUR_KEY&num=9876543210`

## Default Admin Login
- Username: `anish`
- Password: `anish123`