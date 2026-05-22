# Custom GPT Setup Guide

## What this gives you

A ChatGPT Custom GPT that silently searches the manuscript before answering
any question. No copy-pasting context blocks — it retrieves automatically.

---

## Step 1 — Expose the API publicly with ngrok

The API runs on your machine. ngrok creates a secure tunnel so ChatGPT can reach it.

### Install ngrok
1. Go to https://ngrok.com and create a free account
2. Download ngrok for Windows and extract it somewhere (e.g. `C:\ngrok\`)
3. In ngrok's dashboard, copy your authtoken
4. Open PowerShell and run:
   ```
   C:\ngrok\ngrok.exe config add-authtoken YOUR_TOKEN_HERE
   ```

### Start the API + tunnel (do this every time you want the GPT to work)
Open **two** PowerShell windows in the project folder:

**Window 1 — Start the API:**
```
.venv\Scripts\activate
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

**Window 2 — Start the tunnel:**
```
C:\ngrok\ngrok.exe http 8000
```

ngrok will show a URL like:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
```

Copy that `https://...` URL. You'll need it in Step 3.

> **Note:** This URL changes every time you restart ngrok (free tier).
> You'll need to update the Custom GPT action URL when it changes.
> For a permanent URL, set up the IONOS VPS instead.

---

## Step 2 — Create the Custom GPT

1. Go to https://chatgpt.com
2. Click your profile → **My GPTs** → **Create a GPT**
3. Switch to the **Configure** tab

### Name & description
- **Name:** Chronicles of Ven
- **Description:** Writing assistant for The Chronicles of Ven. Searches the manuscript and continuity documents to answer questions about plot, characters, lore, and continuity.

### Instructions
Open `deploy/custom_gpt/system_prompt.md` and paste everything after the dashed line into the Instructions box.

### Conversation starters (optional, but nice)
```
Find all passages where Ven shows vulnerability
What does the Magelord know about Ven's past?
List every scene that takes place in Harrowgate
Was the Silver Oath ever explained?
What unresolved threads involve the Blackened War?
```

---

## Step 3 — Add the Action (connects GPT to your API)

1. Scroll down to **Actions** → click **Create new action**
2. Click **Import from URL** and enter:
   ```
   https://YOUR_NGROK_URL/openapi.json
   ```
   (replace with your actual ngrok URL from Step 1)

3. ChatGPT will import the schema automatically — you should see the `ask`
   and `entity` endpoints listed

4. Under **Authentication**: select **None** (your ngrok URL is already private
   enough for personal use; add API key auth later if you want)

5. Click **Save**

---

## Step 4 — Test it

Back in the Configure tab, click **Preview** (or save and open the GPT).

Try:
```
What do we know about Ven's time in Harrowgate before the knight found him?
```

The GPT should call the search tool silently, then give a sourced answer.

---

## Updating the URL (when ngrok restarts)

1. Start a new ngrok tunnel (Step 1)
2. Go to your GPT → Edit → Actions
3. Click the action → **Edit** → update the server URL to the new ngrok URL
4. Save

---

## Making the URL permanent

When you set up the IONOS VPS, the API will run there 24/7 with a stable URL.
Update the action URL once and it never needs to change again.
