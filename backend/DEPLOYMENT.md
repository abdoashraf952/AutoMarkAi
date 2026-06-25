# AutoMark AI — Deployment Guide (AWS backend + Vercel frontend)

A step-by-step, beginner-friendly guide to take this project from "runs on my
laptop" to "fully live on the internet." Each step explains **what** you do and
**why**, so you learn AWS while you deploy.

> You only need to read top-to-bottom once. Every step has a 🧠 **Intuition**
> note. Commands you run **on AWS** are marked `server $`. Commands on **your
> laptop** are marked `local $`.

---

## 0. The big picture (read this first)

Your app has two halves that get deployed in two different places:

```
                 ┌────────────────────────┐
   Browser  ───▶ │  Next.js frontend      │   (static + JS)
   (user)        │  hosted on Vercel       │   HTTPS, e.g. automark.vercel.app
                 └───────────┬────────────┘
                             │  fetch() + EventSource (SSE)
                             │  calls NEXT_PUBLIC_API_BASE
                             ▼
                 ┌────────────────────────┐
                 │  FastAPI backend        │   (Docker container)
                 │  on AWS (one EC2 box)   │   HTTPS, e.g. api.yourdomain.com
                 └───────────┬────────────┘
                             │  outbound API calls
                             ▼
                   Groq · Gemini · Meta
```

- **Frontend (Vercel):** just static files + JavaScript. Vercel is purpose-built
  for Next.js — push to GitHub, it builds and serves it on HTTPS. Easy.
- **Backend (AWS):** a long-running Python process. This is the part you'll
  containerize with Docker and run on a small AWS server.

### Three things about *this* app that decide how we deploy it

These aren't generic — they come from your actual code, and they rule some
options in and out:

1. **Sessions are stored in memory** (`_sessions = {}` in `api.py`). That means
   **all requests for one user must hit the same running process.** So we run
   **one single always-on instance**, not a fleet of copies behind a load
   balancer. (To scale out later you'd move sessions to Redis — see §13.)
2. **It uses SSE streaming** (`/session/{id}/stream`). SSE is a long-lived HTTP
   connection that pushes events. This needs a server that keeps connections
   open and a proxy that **doesn't buffer** responses. This is why we **don't
   use AWS Lambda** (Lambda is for short, stateless request/response).
3. **The pipeline is slow-ish** (LLM calls + image generation). We need
   generous request timeouts, again pointing to a normal always-on server.

> 🧠 **Intuition:** "Stateful + streaming + long-running" = run it like a normal
> server you keep switched on. The simplest AWS shape for that is **one virtual
> machine running your Docker container**. That's the path this guide takes
> because it's the most *learnable* and fits your app perfectly. Fancier options
> (ECS, App Runner) are in the Appendix.

---

## 1. Create your AWS account and put up safety rails

New AWS accounts are powerful and bill by the second. Spend 15 minutes here so
you never get a scary invoice.

1. **Sign up** at <https://aws.amazon.com> → "Create an AWS Account." You'll need
   a card (most of this guide is a few dollars/month; some is free-tier).
2. **Turn on MFA for the root user.** Account name (top-right) → *Security
   credentials* → assign an MFA device (your phone authenticator app).
3. **Set a budget alarm.** Search "Billing and Cost Management" → *Budgets* →
   *Create budget* → "Zero spend" or a monthly budget like **$20** → add your
   email. AWS will email you before you overspend.
4. **Pick a Region** (top-right dropdown), e.g. `eu-central-1` (Frankfurt),
   `eu-west-1` (Ireland), or `us-east-1` (Virginia). Stick with **one region**
   for everything.

> 🧠 **Intuition:**
> - **Root user** = the master key to your whole account. You enable MFA and
>   then *stop using it for daily work* (next step).
> - **Region** = a physical cluster of data centers. Choose one close to your
>   users for lower latency. Resources in different regions don't see each other,
>   so don't accidentally hop regions.
> - **Budget alarm** = your smoke detector. Cloud's #1 beginner mistake is
>   leaving something expensive running. This catches it.

### Create an IAM user for yourself (don't use root daily)

1. Search **IAM** → *Users* → *Create user* → name it `admin-you`.
2. Tick "Provide user access to the AWS Management Console."
3. Attach the policy **AdministratorAccess** (fine for learning; tighten later).
4. Sign out of root, sign in as `admin-you` from now on.

> 🧠 **Intuition:** **IAM** (Identity and Access Management) is AWS's "who can do
> what." The root user is too powerful to use casually — like doing your daily
> browsing as the computer's Administrator. An IAM user is your normal account.

---

## 2. The AWS vocabulary you'll meet (glossary with intuition)

You don't need to memorize this — skim it, then refer back as steps mention each.

| AWS thing | What it really is | Everyday analogy |
| --- | --- | --- |
| **EC2** | A virtual server (a Linux box in the cloud) | Renting a computer you SSH into |
| **AMI** | The OS image your server boots from | The Ubuntu/Windows install disc |
| **Instance type** (`t3.small`) | CPU + RAM size of the server | "Small / Medium / Large" |
| **EBS volume** | The server's hard disk | The SSD inside the computer |
| **Security Group** | A firewall around your server | A bouncer: which ports/IPs may enter |
| **Key pair** | SSH keys to log in | The physical key to the building |
| **Elastic IP** | A fixed public IP that won't change | A permanent street address |
| **ECR** | A private registry for Docker images | Your own private Docker Hub |
| **CloudWatch** | Logs, metrics, alarms | The dashboard + black box recorder |
| **Route 53** | AWS's DNS (domain → IP) | The phone book |
| **SSM Parameter Store / Secrets Manager** | A safe for secrets (API keys) | A locked drawer for passwords |
| **IAM Role** | Permissions *a machine* can assume | A badge your server wears |

> 🧠 **Intuition:** Almost every AWS tutorial is just gluing a few of these
> together. For us: an **EC2** box, guarded by a **Security Group**, reachable at
> an **Elastic IP**, running your **Docker** container, with secrets in a file,
> logs in **CloudWatch**.

---

## 3. Containerize the backend with Docker

You already have Docker intuition, so this is your comfort zone. We package the
FastAPI app into an **image** (a frozen, runnable snapshot). Anywhere that can
run Docker can then run your backend identically.

Work inside the backend folder: `AutoMarkAi/`.

### 3a. Create `AutoMarkAi/Dockerfile`

```dockerfile
# Start from a small official Python image
FROM python:3.12-slim

# Don't write .pyc files; stream logs immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (this layer is cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend source
COPY . .

# Run as a non-root user (good security hygiene)
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# The app listens on 8000
EXPOSE 8000

# 0.0.0.0 = accept connections from outside the container
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3b. Create `AutoMarkAi/.dockerignore`

This keeps junk — **and secrets** — out of the image.

```
.env
__pycache__/
*.pyc
tests/
output/
.pytest_cache/
.venv/
venv/
```

> ⚠️ **Critical:** `.env` is in `.dockerignore` on purpose. **Never bake API keys
> into an image.** Images get pushed to registries and shared; a leaked image =
> leaked keys. We inject secrets at *run time* instead (§7).

### 3c. Build and test it locally

```
local $ cd AutoMarkAi
local $ docker build -t automark-api .
local $ docker run --rm -p 8000:8000 --env-file ../.env automark-api
```

Then open <http://localhost:8000/health> — you should see `{"status":"ok"}`.
Also try <http://localhost:8000/docs> (FastAPI's auto API explorer).

> 🧠 **Intuition:**
> - An **image** is the recipe + ingredients frozen together; a **container** is a
>   running meal made from it. `build` makes the image; `run` starts a container.
> - `--env-file ../.env` hands your keys to the container as environment
>   variables *without* storing them in the image. This is exactly how we'll do it
>   on the server.
> - If it runs the same locally and on AWS, you've eliminated "works on my
>   machine" — that's the whole point of Docker.

---

## 4. One small code change before you ship: lock down CORS

Right now `api.py` allows requests from **any** website:

```python
allow_origins=["*"]
```

That's fine for local dev, but in production you want only *your* frontend to be
allowed to call the backend. After you know your Vercel URL (§10), change it to:

```python
allow_origins=["https://your-frontend.vercel.app"]
```

> 🧠 **Intuition:** **CORS** (Cross-Origin Resource Sharing) is a browser safety
> rule: a page on site A can only call site B if site B says "I allow A." Your
> frontend (Vercel) and backend (AWS) are different origins, so the backend must
> name the frontend as allowed. `*` means "anyone," which works but is sloppy for
> production. *(You can deploy first with `*` to get things working, then tighten
> it and redeploy.)*

---

## 5. Launch your server (EC2)

Now we rent the Linux box that will run the container.

1. Console → search **EC2** → *Launch instance*.
2. **Name:** `automark-backend`.
3. **AMI:** *Ubuntu Server 24.04 LTS* (familiar, great Docker support).
4. **Instance type:**
   - `t3.micro` — free-tier eligible (1 GB RAM). OK to start, but image
     processing may feel tight.
   - `t3.small` (2 GB) or `t3.medium` (4 GB) — recommended, ~$15–30/mo.
5. **Key pair:** *Create new key pair* → name `automark-key` → download the
   `.pem` file → **keep it safe** (this is your only way in).
6. **Network / Firewall (Security Group):** *Create security group* and allow:
   - **SSH (port 22)** — Source: **My IP** (only you can log in).
   - **HTTP (port 80)** — Source: Anywhere (needed for HTTPS certificate setup).
   - **HTTPS (port 443)** — Source: Anywhere (your real user traffic).
7. **Storage:** 30 GB gp3 is plenty.
8. *Launch instance.*

> 🧠 **Intuition:**
> - **Instance type** is just how big a computer you rent. Bigger = faster +
>   pricier. You can resize later (stop → change type → start).
> - The **Security Group is a firewall**. By default *everything inbound is
>   blocked*; you open exactly the doors you need. We open 22 only to your IP
>   (private door) and 80/443 to the world (public doors). **We deliberately do
>   NOT expose 8000 to the world** — the public will reach the app through the
>   HTTPS reverse proxy on 443 (§8).
> - The **key pair** is SSH security: you keep the private `.pem`, AWS keeps the
>   public half. Lose the `.pem` and you're locked out.

### 5a. Give it a permanent address (Elastic IP)

EC2 → *Elastic IPs* → *Allocate* → then *Actions → Associate* → pick your
instance.

> 🧠 **Intuition:** A normal instance's public IP **changes if you stop/start it**,
> which would break your DNS and your frontend config. An **Elastic IP** is a
> fixed address you own. (It's free while attached to a *running* instance; AWS
> charges a tiny fee for an EIP that's allocated but unused.)

### 5b. Connect to it

```
local $ chmod 400 automark-key.pem               # macOS/Linux: tighten perms
local $ ssh -i automark-key.pem ubuntu@YOUR_ELASTIC_IP
```

On Windows, use PowerShell's `ssh` the same way, or the "EC2 Instance Connect"
button in the console (browser SSH, no key needed).

---

## 6. Install Docker on the server

```
server $ curl -fsSL https://get.docker.com | sh
server $ sudo usermod -aG docker ubuntu        # run docker without sudo
server $ exit                                  # log out & back in to apply group
local  $ ssh -i automark-key.pem ubuntu@YOUR_ELASTIC_IP
server $ docker --version                      # verify
server $ docker compose version                # the Compose plugin comes with it
```

> 🧠 **Intuition:** `get.docker.com` is Docker's official one-line installer.
> Adding your user to the `docker` group lets you skip `sudo` on every command.
> The **Compose plugin** lets us describe multiple containers (app + HTTPS proxy)
> in one file and start them together.

---

## 7. Get your code + secrets onto the server

### 7a. Bring the code over (Git is easiest)

```
server $ git clone https://github.com/YOU/your-repo.git
server $ cd your-repo/AutoMarkAi
```

(No GitHub repo yet? Push your project to GitHub first — you'll need it for
Vercel anyway, §10. Alternatively `scp` the folder up.)

### 7b. Create the secrets file on the server

```
server $ nano .env
```

Paste your real keys (the same variables as your local `.env`):

```
GROQ_API_KEY=...
GEMINI_API_KEY=...
META_SIMULATION_MODE=true
# (Meta keys only if you set simulation mode to false)
```

Then lock its permissions so only you can read it:

```
server $ chmod 600 .env
```

> 🧠 **Intuition:** Secrets live **on the server as a file**, never in the image
> and never in Git. `chmod 600` = "only the owner can read/write." For a bigger
> setup you'd graduate to **AWS SSM Parameter Store** or **Secrets Manager** (a
> managed locked drawer with audit logs) — see §13. A file is perfectly fine to
> start.

---

## 8. Run it with automatic HTTPS (the key step)

Your Vercel frontend is served over **HTTPS**. Browsers **refuse** to let an
HTTPS page call an insecure `http://` backend ("mixed content"). So your backend
**must** be HTTPS too. We get a free certificate automatically using **Caddy** (a
tiny web server that does Let's Encrypt for you).

### 8a. You need a domain name pointing at your Elastic IP

- Buy a cheap domain (Namecheap, Cloudflare, or AWS **Route 53**), **or** use a
  free subdomain service like <https://www.duckdns.org>.
- Create a **DNS "A" record**: `api.yourdomain.com → YOUR_ELASTIC_IP`.
- Wait a few minutes, then verify: `ping api.yourdomain.com` shows your EIP.

> 🧠 **Intuition:** **DNS** maps a human name to an IP address. An **A record**
> says "this name lives at this IPv4 address." Caddy needs a real domain because
> Let's Encrypt issues certificates to *names*, not bare IPs.

### 8b. Create `AutoMarkAi/docker-compose.yml`

```yaml
services:
  api:
    build: .
    env_file: .env
    restart: unless-stopped
    expose:
      - "8000"          # visible to caddy only, NOT to the public internet

  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
```

### 8c. Create `AutoMarkAi/Caddyfile`

```
api.yourdomain.com {
    reverse_proxy api:8000
}
```

### 8d. Start everything

```
server $ docker compose up -d --build
server $ docker compose ps           # both api and caddy should be "running"
server $ docker compose logs -f      # watch startup; Ctrl-C to stop watching
```

Now visit **https://api.yourdomain.com/health** in your browser — you should see
`{"status":"ok"}` with a valid padlock 🔒.

> 🧠 **Intuition:**
> - A **reverse proxy** sits in front of your app: the public talks to Caddy on
>   443, Caddy forwards to your app on 8000 inside the private Docker network.
>   This is why we never exposed 8000 publicly — Caddy is the only public door.
> - **TLS termination** = Caddy handles all the HTTPS/certificate work; your
>   FastAPI app stays plain HTTP internally and doesn't care.
> - `restart: unless-stopped` = if the app crashes or the server reboots, Docker
>   brings it back automatically. That's your "keep it running" insurance.
> - Caddy **auto-renews** the certificate forever. SSE streaming works through
>   Caddy out of the box (it flushes data instead of buffering).

---

## 9. Quick backend smoke test

```
local $ curl https://api.yourdomain.com/health
local $ curl -X POST https://api.yourdomain.com/session
```

The second should return a JSON `session_id`. If both work, your backend is live
on the internet. 🎉

---

## 10. Deploy the frontend to Vercel

1. Push the whole project to **GitHub** (if you haven't).
2. Go to <https://vercel.com> → *Add New Project* → import your repo.
3. **Root Directory:** set it to `web` (your Next.js app lives there, not the
   repo root).
4. **Environment Variables:** add
   `NEXT_PUBLIC_API_BASE = https://api.yourdomain.com`
5. *Deploy.* Vercel gives you a URL like `https://automark-xxxx.vercel.app`.

> 🧠 **Intuition:**
> - Vercel auto-detects Next.js, builds it, and serves it globally on HTTPS — no
>   servers for you to manage on the frontend side.
> - `NEXT_PUBLIC_API_BASE` is how the browser knows where your backend lives. The
>   `NEXT_PUBLIC_` prefix means "safe to expose in the browser bundle." Changing
>   it requires a **redeploy** (it's baked in at build time).
> - Every `git push` now auto-redeploys the frontend. Nice.

### Then close the CORS loop

Go back and set `allow_origins=["https://automark-xxxx.vercel.app"]` in
`api.py` (§4), commit, and on the server:

```
server $ cd ~/your-repo && git pull
server $ cd AutoMarkAi && docker compose up -d --build
```

---

## 11. End-to-end test

Open your Vercel URL and run a full campaign: upload a photo → answer questions →
review/regenerate the image → review copy → publish (simulated). If anything
hangs:

- **Frontend can't reach backend?** Open the browser DevTools → Network tab.
  CORS error → fix `allow_origins`. `net::ERR` / mixed content → backend isn't
  HTTPS or `NEXT_PUBLIC_API_BASE` is wrong.
- **Backend errors?** On the server: `docker compose logs -f api`.
- **Image streaming/SSE stalls?** Confirm you're hitting it via Caddy (https),
  not directly on port 8000.

---

## 12. Updating the app later (your normal workflow)

Frontend: just `git push` → Vercel redeploys automatically.

Backend:
```
server $ cd ~/your-repo && git pull
server $ cd AutoMarkAi && docker compose up -d --build
```

> 🧠 **Intuition:** `up -d --build` rebuilds the image with new code and swaps the
> container in place. Your `.env` and Caddy's certificate (stored in the
> `caddy_data` volume) survive across rebuilds.

---

## 13. Day-2: operations, cost, and growing up

**Save money while learning:** when you're not demoing, you can **Stop** the EC2
instance (EC2 → Instances → Stop). You stop paying for compute; you keep your
disk and Elastic IP. *Start* it again when needed (the EIP keeps the address
stable).

**Cost:** see the dedicated **§14 — Cost estimation & going (almost) free**
below. Short version: **$0/month for your first 12 months on the AWS Free Tier**,
then ~$11–21/month — or free *forever* with the alternative in §14.

**Logs & monitoring:** `docker compose logs` is enough at first. To centralize,
install the **CloudWatch agent** so logs/metrics show up in the AWS console with
alarms (e.g., alert if CPU pegs or the box goes unhealthy).

**Security checklist:**
- [ ] Root MFA on, daily work as IAM user
- [ ] SSH (22) restricted to your IP only
- [ ] Port 8000 never exposed publicly (only 80/443 via Caddy)
- [ ] `.env` is `chmod 600`, in `.dockerignore`, and **not** in Git
- [ ] CORS restricted to your Vercel domain
- [ ] Run `sudo apt update && sudo apt upgrade` occasionally

**When you outgrow one box** (real traffic, need zero-downtime / multiple
instances):
1. **Move sessions out of memory into Redis** (AWS **ElastiCache**). This is the
   prerequisite — remember §0: the in-memory `_sessions` dict is what currently
   forces a single instance.
2. Put an **Application Load Balancer (ALB)** in front, terminate HTTPS there with
   a free **ACM** certificate, and run multiple containers via **ECS Fargate**
   (no servers to manage). See the Appendix.

---

## 14. Cost estimation & going (almost) free

**Can this whole project be free? Mostly yes.** Here's the honest breakdown.

### The verdict at a glance

| Piece | Free? | How |
| --- | --- | --- |
| **Frontend (Vercel)** | ✅ **Free forever** | Vercel **Hobby** plan (personal/non-commercial) |
| **HTTPS certificate** | ✅ **Free forever** | Caddy + Let's Encrypt (§8) |
| **Domain name** | ✅ Free / 💲 ~$1/mo | Free subdomain (DuckDNS) **or** a paid domain ~$10–15/yr |
| **Backend hosting (AWS)** | ✅ **Free for 12 months**, then ~$11–21/mo | AWS Free Tier `t3.micro` (see below) |
| **Backend hosting (free *forever* alt.)** | ✅ **Free forever** | Oracle Cloud **Always Free** VM (same Docker steps) |
| **AI APIs (Groq / Gemini / Meta)** | ⚠️ Mostly free, with caveats | See "App-running costs" below |

> 🧠 **Intuition:** *Hosting* (keeping the app online) and *usage* (the AI API
> calls the app makes) are two separate bills. This guide makes **hosting** free;
> the **AI usage** depends on the providers, covered at the end.

---

### Option A (recommended) — AWS Free Tier: $0 for 12 months

New AWS accounts get a **12-month Free Tier**. A single small server fits inside
it completely:

| Resource | Free Tier allowance | Your usage | Cost |
| --- | --- | --- | --- |
| EC2 `t3.micro` (or `t2.micro`) | 750 hours/month | 1 instance 24/7 = 730 hrs | **$0** |
| EBS storage (gp3) | 30 GB/month | 30 GB | **$0** |
| Public IPv4 address | 750 hours/month | 1 address 24/7 | **$0** |
| Data transfer out | 100 GB/month | tiny for a demo | **$0** |
| **Total (months 1–12)** | | | **$0 / month** |

> ⚠️ Use **`t3.micro`** (free-tier), **not** `t3.small`, to stay at $0. In §5
> step 4, pick `t3.micro`.

**The one catch: 1 GB of RAM.** Image work can spike memory. Two easy fixes:
- Your app sends image *generation* to Gemini's cloud (not local), and only does
  light Pillow downscaling locally — so 1 GB is usually enough for a demo.
- Add a **swap file** for safety (a disk-backed memory cushion):
  ```
  server $ sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
  server $ sudo mkswap /swapfile && sudo swapon /swapfile
  server $ echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```

> 🧠 **Intuition:** **Swap** lets the OS use disk as overflow when RAM fills up.
> It's slower than real RAM but prevents the container from being killed under a
> brief memory spike. Cheap insurance on a 1 GB box.

**What it costs *after* the 12 months** (or if you exceed free tier), 24/7,
on-demand, region-dependent:

| Resource | `t3.micro` | `t3.small` |
| --- | --- | --- |
| EC2 compute (24/7) | ~$7.5 | ~$15 |
| Public IPv4 (since Feb 2024, ~$0.005/hr) | ~$3.6 | ~$3.6 |
| 30 GB EBS | ~$2.4 | ~$2.4 |
| **≈ Total / month** | **~$13.5** | **~$21** |

> 💡 **Cut the bill to near-zero even after free tier:** **Stop** the instance
> when you're not demoing (§13). You only pay for the disk (~$2.4/mo) and the
> idle IPv4 (~$3.6/mo) while it's stopped — roughly **$6/mo** for an
> on-demand-only demo, **$0** while the free tier lasts.

---

### Option B — free *forever* (not AWS): Oracle Cloud Always Free

If "free forever" matters more than "must be AWS," **Oracle Cloud's Always Free**
tier gives you a real VM that never expires — generous enough to run this app
comfortably:

- Up to **4 ARM (Ampere) cores + 24 GB RAM**, or 2 small AMD VMs — **free forever**.
- It's still just *a Linux VM running Docker*, so **§3, §6, §7, §8 of this guide
  work almost unchanged** — your Docker skills transfer directly.
- Trade-offs: occasional ARM capacity shortages when creating the VM, and Oracle
  may reclaim instances that sit idle for long periods. Card required for signup
  (not charged on Always Free).

> 🧠 **Intuition:** Every "rent a VM and run Docker" provider works the same way.
> Learning it on AWS (Option A) means you can redeploy to Oracle, a DigitalOcean
> droplet, etc., in minutes — the concepts (image, ports, firewall, HTTPS, DNS)
> are identical.

---

### Free platforms to be careful with (they "sleep")

Platforms like **Render free**, **Railway**, **Hugging Face Spaces**, or
**Google Cloud Run** have free tiers, but most **sleep when idle / scale to zero**
and/or **run multiple copies**. For *this* app that causes real bugs:

- Your sessions live **in memory** (`_sessions` in `api.py`). If the host sleeps
  or spins up a second copy, **in-progress sessions vanish mid-campaign.**
- Your **SSE stream** is a long-lived connection; a cold start or scale-down
  **drops it**.

So if you go free, prefer an **always-on single VM** (AWS Free Tier or Oracle
Always Free), **not** a scale-to-zero platform — unless you first move sessions
into Redis (§13).

---

### Keeping the domain + HTTPS free

- **HTTPS** is always free (Caddy + Let's Encrypt).
- **Domain:** a free subdomain from **DuckDNS** (e.g. `automark.duckdns.org`)
  works perfectly with Caddy and costs nothing. A custom domain (e.g.
  `api.yourbrand.com`) is ~$10–15/year if you want it to look professional.

---

### App-running costs (the AI APIs — separate from hosting)

Even with $0 hosting, the AI calls your app makes have their own pricing:

| Provider | Used for | Free? |
| --- | --- | --- |
| **Groq** | All text + vision→text | ✅ Free tier (rate-limited). Great for demos. |
| **Google Gemini** | Ad **image** generation only | ⚠️ The image model may require a **billed** Google account; check current Google AI pricing. Failures degrade gracefully (`generated_images: []`). |
| **Meta Marketing API** | Publishing ads | ✅ **Free** while `META_SIMULATION_MODE=true` (no real spend). Real ads cost real ad budget. |

> ✅ **To stay fully free end-to-end for a demo:** keep
> `META_SIMULATION_MODE=true`, rely on Groq's free tier, and either accept that
> Gemini image generation may incur small charges or run in
> `image_mode=use_original` (which skips AI image generation entirely and uses
> the user's uploaded photo).

---

### Bottom line

- **Cheapest realistic path that still teaches you AWS:** AWS Free Tier
  `t3.micro` + Vercel + DuckDNS + Caddy = **$0/month for a year**, then ~$6–13/mo
  (less if you stop the box between demos).
- **Free forever:** swap AWS for **Oracle Always Free** using the same steps.
- **Frontend, HTTPS, Meta (simulated), and Groq are free regardless.** The only
  thing that *might* cost a little is Gemini image generation.

---

## Appendix — Other AWS paths (and why we didn't start there)

You chose EC2 + Docker because it's the most *learnable* and fits a stateful,
streaming app. Here's the wider landscape so you understand your options:

| Option | What it is | Good for | Why not first |
| --- | --- | --- | --- |
| **EC2 + Docker** *(this guide)* | One VM you run containers on | Learning, stateful/streaming apps, full control | You manage the OS yourself |
| **AWS App Runner** | "Give me a container, I'll host it" PaaS | Fastest container deploy | Autoscaling fights in-memory sessions (you'd pin min=max=1); SSE/timeout caveats |
| **ECS Fargate** | Run containers with no servers to manage | Production, scaling, no OS upkeep | More moving parts (task defs, ALB, target groups) — steeper first climb |
| **Elastic Beanstalk** | Older PaaS that wraps EC2 for you | Hands-off EC2 | More magic, less learning; aging |
| **Lightsail** | Simplified EC2 with flat pricing | Predictable cost, simple | Less flexible than EC2 |
| **Lambda + API Gateway** | Serverless functions | Short, stateless request/response | ❌ Bad fit: your app has SSE, in-memory state, and long runs |

> 🧠 **Intuition:** As you move down the list, AWS manages more *for* you but you
> understand less of *what's happening*. Starting on EC2 means that when you later
> graduate to Fargate, every concept (image, port, env vars, firewall, HTTPS,
> DNS) is already familiar — Fargate just automates the box.

---

## TL;DR checklist

- [ ] AWS account + MFA + budget alarm + IAM user
- [ ] `Dockerfile` + `.dockerignore`, tested locally
- [ ] Launch EC2 (Ubuntu), Security Group (22=you, 80/443=world), Elastic IP
- [ ] Install Docker on the server
- [ ] `git clone` + create `.env` (chmod 600)
- [ ] Point `api.yourdomain.com` DNS → Elastic IP
- [ ] `docker-compose.yml` + `Caddyfile` → `docker compose up -d --build`
- [ ] Verify `https://api.yourdomain.com/health`
- [ ] Deploy frontend on Vercel (root = `web`, set `NEXT_PUBLIC_API_BASE`)
- [ ] Lock CORS to the Vercel domain, rebuild backend
- [ ] Full end-to-end test
```
