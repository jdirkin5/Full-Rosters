# Runbook: get a System User token for the Marketing API

One-time setup, about 20 to 30 minutes. You need to be an admin of the
Business Portfolio (formerly Business Manager) that owns the ad account.

Meta renames menus often. The steps below use the current names and, in
brackets, the older ones.

## Part A. Make sure you have an app

System User tokens are issued against an app, so you need one even though
nothing "runs" in it.

1. Go to https://developers.facebook.com/apps and click **Create App**.
2. Use case: choose **Other**, then app type **Business**. Name it something
   like "Full Rosters Ads Tool". Pick your Business Portfolio when asked.
3. In the app dashboard, under **Add products**, add **Marketing API**.
4. Leave the app in **Development** mode. For managing your own business's
   ad accounts that is enough. App Review is only needed to manage other
   businesses' accounts.

## Part B. Create the System User

1. Go to https://business.facebook.com/settings (Business Portfolio settings
   [Business Settings]).
2. Left menu: **Users** -> **System users** -> **Add**.
3. Name: "claude-ads". Role: **Admin**. Create.

## Part C. Give the System User access to the assets

Still on the System User, click **Assign assets** [Add assets]. Do all three:

1. **Ad accounts**: pick the ad account, turn on **Manage ad account**
   (full control). Save.
2. **Pages**: pick the Page the ads run under, turn on **Manage Page**
   (full control). Save.
3. **Datasets** [Pixels]: if you track conversions, pick the pixel and turn
   on **Manage**. Save.

If the app from Part A is not listed under **Accounts -> Apps** in Business
settings, add it there too and assign it to the System User with
**Develop app** permission. Without this the token generator will not show
the app.

This assignment step is where most people get stuck. If `meta-ads whoami`
later shows the ad account or Page as missing, come back here.

## Part D. Generate the token

1. On the System User, click **Generate new token**.
2. App: choose the app from Part A.
3. Token expiration: **Never**.
4. Permissions, tick exactly these:
   - `ads_management`
   - `ads_read`
   - `business_management`
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_ads`
   - `instagram_basic` (only if ads run under an Instagram account)
5. Generate, then **copy the token now**. Meta shows it once. Treat it like a
   password to your ad account.

## Part E. Collect the ids

You do not have to look these up by hand. After Part F, run `meta-ads whoami`
in a new session: it lists every ad account and Page the System User can see,
with ids, and prints a starting `clients.yaml` for you.

### Managing several accounts

Each account you manage gets an entry in `clients.yaml` (copy
`clients.example.yaml`). Every one of those ad accounts and Pages must be
assigned to the System User in Part C. If a client's ad account belongs to
their own Business Portfolio, they first share it with yours as a partner
(their Business settings -> Ad accounts -> Assign partner -> your Business
ID), and then you assign it to the System User.

Select a client per command: `meta-ads --client breakaway campaigns list`.
Without `--client`, the `default` entry in `clients.yaml` is used.

If you only want to find the ids manually:

- **Ad account id**: Ads Manager URL contains `act=1234567890`. Use
  `act_1234567890`.
- **Page id**: Page -> About -> Page transparency, or Business settings ->
  Accounts -> Pages.
- **Pixel id** (optional): Events Manager -> the dataset -> Settings.
- **Instagram account id** (optional): Business settings -> Accounts ->
  Instagram accounts.

## Part F. Put them where the tool can read them

### Claude Code on the web (this repo's sessions)

The environment editor is NOT in Settings. It is in the session itself.

1. Go to https://claude.ai/code and open any session (or start a new one).
2. Look just above the message box for a small cloud button showing the
   environment name, usually **Default**. Click it.
3. In the menu that opens, under **Cloud**, hover over **Default** and click
   the **gear icon** that appears on the right. The **Update cloud
   environment** dialog opens.
4. **Network access**: change **Trusted** to **Custom**. In **Allowed
   domains** type `graph.facebook.com`. Tick **Also include default list of
   common package managers** so pip still works.
5. Add the token, using ONE of these two ways:

   **Option 1, preferred (Pro and Max plans): API credential.** Claude never
   sees the token; Anthropic's proxy attaches it to requests as they leave
   the sandbox.
   - Scroll to **API credentials** (below Environment variables) and click
     **Add credential**.
   - Credential type: **Bearer**. Hosts: `graph.facebook.com`.
   - Custom headers: keep the row with Name `Authorization` and Prefix
     `Bearer`, and paste the token as the **Value**.
   - Then in **Environment variables** add the ids and the proxy flag:

     ```
     META_TOKEN_VIA_PROXY=1
     ```

     Account and Page ids go in `clients.yaml` in the repo (Part E), not
     here. `META_AD_ACCOUNT_ID` / `META_PAGE_ID` still work for a
     single-account setup.

   **Option 2: environment variable.** Simpler, but anyone using the
   environment (and Claude) can read it. In **Environment variables** add:

     ```
     META_ACCESS_TOKEN=paste_token_here
     ```

     Account and Page ids go in `clients.yaml` (Part E).

   If you don't see an **API credentials** section, your plan doesn't have
   it yet; use Option 2.

6. Optional extra lines for either option: `META_PIXEL_ID=`,
   `META_INSTAGRAM_ACTOR_ID=`, `META_MAX_DAILY_BUDGET=`.
7. Click **Update environment** (or Save).
8. Start a **new** session. Running sessions keep the old values.

Docs: https://code.claude.com/docs/en/cloud-environments

### Local machine

Copy `.env.example` to `.env`, fill it in. `.env` is git-ignored.

## Part G. Verify

```
meta-ads whoami
```

Expected: your System User's name, `token_type` = `SYSTEM_USER` [or `USER`],
`expires` = `never`, `missing_scopes` = `none`, the ad account listed with
`allowlisted` = `True`, and the Page listed.

Common failures:

| Message | Fix |
|---|---|
| `Invalid OAuth access token` (code 190) | Token pasted wrong or regenerated. Redo Part D. |
| `(#100) Missing permissions` or `(#200)` on an ad account call | Part C step 1: assign the ad account with Manage. |
| Page not listed under Pages | Part C step 2: assign the Page with Manage. |
| `(#10) Application does not have permission for this action` | Part A step 3: Marketing API product not added, or app not assigned to the System User. |
| `allowlist_not_visible` shows your account | The id in `META_AD_ACCOUNT_ID` does not match what the token can see. Check the `act_` prefix and the number. |
| `CONNECT tunnel failed, response 403` | The environment's network access is still Trusted; set it to Custom and allow `graph.facebook.com` (Part F step 4). |
