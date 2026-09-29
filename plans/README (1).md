# History Channel Pipeline

Twice a day this makes a finished history video. You download it and upload it to YouTube yourself, which takes about 10 minutes per video.

**Done automatically for you (on GitHub's servers, even when your computer is off):**
- picks a new topic (never repeats)
- researches it, checking facts against two or more sources
- writes an 8–12 minute script, then fact-checks it
- records the narration with ElevenLabs
- finds accurate, free-to-use images on Wikimedia Commons and checks each one matches the narration
- edits the video: slow pans, image captions, chapter titles, end card, optional music
- makes the thumbnail, subtitles, title, description (chapters, sources, image credits) and tags
- opens a **"Ready to upload"** issue on GitHub, which emails you

**Done by you:** watch it, then upload and schedule it in YouTube Studio.

No Google Cloud is needed.

---

## What it costs

| Service | For 2 videos a day |
|---|---|
| **Anthropic (Claude)** | Prepaid credits. Check your real cost per video after the first run and set your limit from that. |
| **ElevenLabs** | **Pro plan, $99/month**, with the `eleven_flash_v2_5` voice model. The richer `eleven_multilingual_v2` model needs the $330 plan. |
| **GitHub** | **Free if the repository is Public** (see step 3). |

---

## Part A: one-time setup (about 45 minutes)

### Step 1: Anthropic API key
1. Go to **console.anthropic.com** and sign in.
2. **Settings → Billing → Buy credits**: add $25–50. Leave **Auto-reload off**, so it can never spend more than you've added.
3. **Settings → Workspaces → Add Workspace**: name it `history-pipeline` and click Create.
4. Open the workspace, then **Limits → Change Limit**: set a monthly cap. Then **Add notification** at half that amount.
5. In the workspace, go to **API Keys → Create Key** and name it `github`. **Copy the key now**, because it's only shown once. Paste it somewhere safe for step 5.

### Step 2: ElevenLabs key and voice
1. Go to **elevenlabs.io** and choose **Subscription → Pro**.
2. **Developers → API Keys → Create API Key**: switch on **Text to Speech** and **Voices: Read**. Copy the key.
3. **Voice Library**: filter to *Category: Narration* and *Language: English*, and pick a calm documentary voice with a long notice period.
4. Click **+** to add it to My Voices. Then in **My Voices**, click **⋯ → Copy voice ID**. Keep this for step 4.

### Step 3: Put the code on GitHub
1. Sign in at **github.com**, then click **+** (top right) → **New repository**.
2. Name it `history-pipeline` and choose **Public**. Private also works, but its free storage (500 MB) fills up after a couple of videos. Your keys stay secret either way.
3. Click **Create repository**, then click **uploading an existing file**.
4. Unzip this folder on your computer and drag **everything inside it** onto the page, including the hidden `.github` folder. On a Mac, press **Cmd + Shift + .** in Finder to show hidden files; on Windows, go to **View → Show → Hidden items**.
5. Click **Commit changes**.
6. Check that you can see a `.github` folder in the file list. If not, repeat step 4 for that folder.

### Step 4: Your settings
1. In your repo, click **config.yaml**, then the **pencil icon** ✏️.
2. Change only these lines, keeping the quote marks:
   ```yaml
   channel_name: "Your History Channel Name"
   elevenlabs_voice_id: "the-voice-id-from-step-2"
   elevenlabs_model: "eleven_flash_v2_5"
   ```
3. Click **Commit changes** twice.

### Step 5: Add your two keys to GitHub
1. In your repo: **Settings → Secrets and variables → Actions → New repository secret**.
2. Name `ANTHROPIC_API_KEY`, paste the key from step 1, then **Add secret**.
3. **New repository secret** again: name `ELEVENLABS_API_KEY`, paste the key from step 2, then **Add secret**.

### Step 6: Allow it to save its progress
1. In your repo: **Settings → Actions → General**.
2. Under **Workflow permissions**, choose **Read and write permissions**, then **Save**.

### Step 7: Get email alerts
Click **Watch** (top of your repo) → **All Activity**. You'll now get an email every time a video is ready.

### Step 8: First test run
1. Click the **Actions** tab. If asked, click **I understand my workflows, go ahead and enable them**.
2. Click **Produce video** on the left, then **Run workflow**. Leave *How many videos* on **1** for the test and click the green **Run workflow**.
3. Wait about 30–40 minutes. A green tick means it worked. A red cross means it failed; click it to see the error and check the troubleshooting table below.
4. Go to the **Issues** tab and you'll find **"Ready to upload: …"**. Follow Part B.

From now on it runs by itself at about **6am and 12pm UK time** every day.

---

## Part B: uploading a video (about 10 minutes each)

### 1. Download
1. Open the **"Ready to upload"** email or issue and click the **Download** link at the bottom.
2. Scroll to the bottom of that page. Under **Artifacts**, click **video-…** to download the zip.
3. Unzip it. You'll have: `video.mp4`, `thumbnail.jpg`, `captions.srt`, `UPLOAD.txt`, `script.txt` (and sometimes `pinned_comment.txt`).

⏱ Downloads are kept for **7 days**, so upload within a week.

### 2. Check it (the important part)
- Open the issue and read **"Worth a look before you upload"**. If the issue title starts with **⚠️**, read `script.txt` properly first.
- Watch the video, or at least skim through it: check that the images match what's being said and the voice sounds right.
- Not happy? Just don't upload it. Close the issue and a new video comes at the next run.

### 3. Upload to the right channel
1. Go to **studio.youtube.com**.
2. **Make sure you're on the history channel:** click your profile picture (top right) → **Switch account** → choose the history channel.
3. Click **Create** (top right) → **Upload videos** → **Select files** → choose `video.mp4`.

### 4. Fill in the details (copy from `UPLOAD.txt`)
- **Title:** paste the title.
- **Description:** paste everything under DESCRIPTION.
- **Thumbnail:** click **Upload file** and choose `thumbnail.jpg`. If it's greyed out, see Part C.
- **Audience:** **No, it's not made for kids**.
- Click **Show more**:
  - **Altered content:** **Yes**, because the narration is AI.
  - **Tags:** paste the tags.
  - **Category:** Education.
- Click **Next**.

### 5. Add the subtitles
1. On **Video elements**, click **Add** next to Subtitles.
2. Choose **Upload file → With timing → Continue**, pick `captions.srt`, then click **Done**.
3. Optional: **End screen → Add** to promote your latest video.
4. Click **Next**, wait for **Checks** to finish (look out for copyright claims), then click **Next**.

### 6. Schedule it
1. On **Visibility**, choose **Schedule**.
2. Set the date and time to the **SUGGESTED PUBLISH TIME** in `UPLOAD.txt`.
3. Click **Schedule**.

### 7. Finish
- If there was a `pinned_comment.txt`: once the video is live, post its text as a comment, then click **⋮ → Pin**.
- Close the GitHub issue (the **Close issue** button) so your inbox shows only videos still to upload.

---

## Making videos without Anthropic API credits (recommended)

The research and script are written **in the Claude chat** (part of your Claude plan), and GitHub does only the voice, images and editing. That step uses ElevenLabs and Wikimedia, not Claude's API, so **no Anthropic console credits are used**.

1. **Turn off the API version:** **Actions → Produce video → ⋯ → Disable workflow.**
2. **In Claude, ask:** *"Make 3 history video plans"* (any number up to 5, or name the topics). Claude researches each one, writes the script, picks the images and gives you one `.json` file per video.
3. **Upload them:** in your repo, open the **plans** folder, click **Add file → Upload files**, drag all the `.json` files in, and click **Commit changes**.
4. **Wait about 20–30 minutes.** The **Render videos from plans** workflow starts on its own and makes all the videos at the same time. You get one **"Ready to upload"** issue per video.
5. **Upload them to YouTube** as in Part B.

Finished plans move to `plans/done/`. If a video fails, its plan stays in `plans/` and you can retry it with **Actions → Render videos from plans → Run workflow**.

---

## Part C: optional extras
- **Make up to 5 videos at once:** **Actions → Produce video → Run workflow**, choose **2–5** under *How many videos*, then **Run workflow**. Each video gets a different topic (rotating through the four history lanes) and its own publish slot, and they're all made at the same time on separate servers, so 5 take about as long as 1. You get one "Ready to upload" issue per video. If one fails, the others still finish. Check you have enough ElevenLabs credits first: each video uses about 9,000.
- **Custom thumbnails greyed out?** Verify your channel in YouTube Studio: **Settings → Channel → Feature eligibility → Verify phone number**.
- **Background music:** in your repo, open the `assets` folder, then **Add file → Upload files**, and upload a royalty-free track named exactly `music.mp3` (the YouTube Audio Library is free).
- **One video a day instead of two:** open `.github/workflows/produce.yml`, click the pencil, delete one of the two `- cron:` lines, and commit.
- **Pause everything:** **Actions → Produce video → ⋯ → Disable workflow**. Turn it back on the same way.
- **Change the publish times:** edit `publish_times` in `config.yaml`.

---

## Troubleshooting

| What you see | What to do |
|---|---|
| Red cross, error mentions **ANTHROPIC** or **401** | Check the `ANTHROPIC_API_KEY` secret and your Anthropic credit balance. |
| Red cross, error mentions **ElevenLabs** 401/402 | Check the `ELEVENLABS_API_KEY` secret, its permissions (step 2.2) and your credits. |
| Red cross, error mentions **config.yaml** | A quote mark or space got changed. Compare your file with step 4. |
| Red cross at **"Save state"** | Step 6 wasn't saved. Set Read and write permissions. |
| "No usable images found" | That topic had too few free images. The next run picks a different one. |
| No email arrived | Step 7, and check your spam folder for github.com emails. |
| No Artifacts at the bottom of the run | More than 7 days have passed, or the run failed. |

## Keeping the channel healthy
YouTube judges the whole channel, and it penalises channels that look mass-produced. What protects you is the check in Part B step 2, and not publishing videos you're not happy with. If views are low after a month, **post fewer, better videos, not more.**

## What's in the folder
- `config.yaml`: your settings
- `pipeline/writer.py`: the topic, research, script and fact-check instructions (edit these to change the style)
- `pipeline/images.py`: image search and checks
- `pipeline/render.py`: the automatic video editing
- `state/state.json`: topics used so far (updated automatically)
- `archive/`: a copy of every video's research, script and upload details
