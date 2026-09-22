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

- **Ad account id**: Ads Manager URL contains `act=1234567890`. Use
  `act_1234567890`.
- **Page id**: Page -> About -> Page transparency, or Business settings ->
  Accounts -> Pages.
- **Pixel id** (optional): Events Manager -> the dataset -> Settings.
- **Instagram account id** (optional): Business settings -> Accounts ->
  Instagram accounts.

## Part F. Put them where the tool can read them

### Claude Code on the web (this repo's sessions)

1. Open https://claude.ai/code, go to the environment this repo uses, and
   edit it.
2. Under **Environment variables** add:

   | Name | Value |
   |---|---|
   | `META_ACCESS_TOKEN` | the token from Part D |
   | `META_AD_ACCOUNT_ID` | `act_...` |
   | `META_PAGE_ID` | the Page id |
   | `META_PIXEL_ID` | optional |
   | `META_INSTAGRAM_ACTOR_ID` | optional |

3. Under **Network access**, make sure `graph.facebook.com` is allowed. The
   default limited policy blocks it. Docs:
   https://code.claude.com/docs/en/claude-code-on-the-web
4. Start a new session so the variables are picked up.

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
| `CONNECT tunnel failed, response 403` | The environment's network policy blocks `graph.facebook.com` (Part F step 3). |
