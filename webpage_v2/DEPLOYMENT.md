# Deployment Guide

## Automated GitHub Pages Deployment

This web app automatically deploys to GitHub Pages when changes are pushed to the `main` branch.

**Live URL:** https://trackrat-dev.github.io/TrackRat/

---

## How It Works

1. **Push to main branch** with changes to `webpage_v2/`
2. **GitHub Actions workflow** automatically:
   - Checks out the code
   - Installs dependencies
   - Builds the production bundle
   - Deploys to `gh-pages` branch
3. **GitHub Pages** serves the site from `gh-pages` branch
4. **Live in ~2 minutes**

---

## First-Time Setup

### Step 1: Enable GitHub Pages

1. Go to your repository on GitHub
2. Click **Settings** → **Pages**
3. Under **Source**, select:
   - Branch: `gh-pages`
   - Folder: `/ (root)`
4. Click **Save**

**Note:** The `gh-pages` branch will be created automatically on the first deployment.

### Step 2: Configure Repository Settings

The workflow file is already configured and ready to use. No additional setup needed!

---

## Testing the Deployment

### Option 1: Test on a Branch

```bash
# Create a test branch
git checkout -b test-deployment

# Make a small change to trigger workflow
echo "# Test" >> webpage_v2/README.md

# Commit and push
git add webpage_v2/README.md
git commit -m "Test deployment workflow"
git push origin test-deployment

# Manually trigger the workflow
# Go to GitHub → Actions → Deploy Web Frontend → Run workflow
# Select your test-deployment branch
```

### Option 2: Manual Trigger

1. Go to **Actions** tab on GitHub
2. Select **Deploy Web Frontend to GitHub Pages**
3. Click **Run workflow**
4. Select branch and click **Run workflow**

---

## Monitoring Deployments

### View Workflow Status

1. Go to **Actions** tab on GitHub
2. Click on the latest workflow run
3. See real-time logs of each step

### Check Deployment Status

1. Go to **Settings** → **Pages**
2. See "Your site is live at..." message
3. Click the URL to verify

### View Built Files

1. Switch to `gh-pages` branch
2. See the built static files (HTML, CSS, JS)

---

## Workflow Details

### Trigger Conditions

The workflow runs when:
- Changes are pushed to `main` branch
- Changes affect `webpage_v2/` directory
- Workflow file itself is modified
- Manually triggered via GitHub UI

### Build Process

```yaml
1. Checkout code
2. Setup Node.js 20
3. Install dependencies (npm ci)
4. Build (npm run build)
5. Deploy to gh-pages branch
```

### Build Time

- First build: ~2 minutes
- Cached builds: ~30-45 seconds

---

## Configuration

### Base Path

The app is configured for GitHub Pages project site:

**vite.config.ts:**
```typescript
base: '/TrackRat/'
```

**App.tsx:**
```typescript
<BrowserRouter basename="/TrackRat">
```

### Custom Domain (Optional)

To use a custom domain like `trackrat.net`:

1. Update workflow file:
```yaml
- uses: peaceiris/actions-gh-pages@v3
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    publish_dir: ./webpage_v2/dist
    cname: trackrat.net  # Add your domain
```

2. Update vite.config.ts:
```typescript
base: '/'  // Change from '/TrackRat/'
```

3. Update App.tsx:
```typescript
<BrowserRouter basename="">  // Remove basename
```

4. Configure DNS:
   - Add A records or CNAME pointing to GitHub Pages
   - See [GitHub Docs](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site)

---

## Troubleshooting

### Workflow Fails

**Check the logs:**
1. Go to Actions tab
2. Click the failed workflow
3. Read error messages

**Common issues:**

| Error | Solution |
|-------|----------|
| TypeScript errors | Fix type errors locally, test with `npm run build` |
| Dependency issues | Delete `node_modules` and `package-lock.json`, run `npm install` |
| Permission denied | Check repository permissions in Settings |

### Blank Page After Deployment

**Cause:** Base path misconfiguration

**Solution:**
1. Verify `vite.config.ts` has `base: '/TrackRat/'`
2. Verify `App.tsx` has `basename="/TrackRat"`
3. Rebuild and redeploy

### 404 on Assets

**Cause:** Assets loaded from wrong path

**Solution:**
- Check browser console for 404 errors
- Verify base path configuration
- Clear browser cache

### Changes Not Appearing

**Cause:** GitHub Pages cache

**Solution:**
1. Wait 2-3 minutes for cache to clear
2. Hard refresh browser (Cmd+Shift+R or Ctrl+Shift+R)
3. Check workflow completed successfully

---

## Manual Deployment (Alternative)

If you need to deploy manually without GitHub Actions:

```bash
# Build the app
cd webpage_v2
npm run build

# Deploy to gh-pages branch
cd dist
git init
git add .
git commit -m "Deploy to GitHub Pages"
git branch -M gh-pages
git remote add origin git@github.com:trackrat-dev/TrackRat.git
git push -f origin gh-pages
```

---

## Rollback

If a deployment breaks the site:

### Quick rollback:
```bash
# Revert the commit
git revert HEAD
git push origin main

# Workflow will auto-deploy previous version
```

### Manual rollback:
```bash
# Check out gh-pages branch
git checkout gh-pages

# Reset to previous commit
git reset --hard HEAD~1

# Force push
git push -f origin gh-pages
```

---

## Performance

### Bundle Size
- Initial bundle: ~72 KB gzipped
- Total assets: ~230 KB (within GitHub Pages limits)

### Load Time
- First load: ~1-2 seconds
- Subsequent loads: <500ms (browser cache)

### Build Optimization

The production build includes:
- Tree shaking (removes unused code)
- Minification (reduces file size)
- Code splitting (faster initial load)
- Asset optimization (images, fonts)

---

## Monitoring

### Add Status Badge

Add to README.md:
```markdown
![Deploy Status](https://github.com/trackrat-dev/TrackRat/actions/workflows/deploy-webpage.yml/badge.svg)
```

### View Deployment History

1. Go to **Deployments** in GitHub sidebar
2. See all deployment history
3. Click to view details

---

## Security

### Secrets
- No API keys required ✅
- Backend API is public ✅
- GITHUB_TOKEN automatically provided ✅

### CORS
Ensure your backend at `apiv2.trackrat.net` has CORS headers:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, OPTIONS
```

---

## Support

For issues with:
- **Deployment:** Check Actions logs
- **App functionality:** Test locally with `npm run dev`
- **GitHub Pages:** See [GitHub Pages docs](https://docs.github.com/en/pages)

---

## Next Steps

1. ✅ Workflow is configured
2. ✅ App is ready to deploy
3. ⏭️ Push to main branch or test on a branch
4. ⏭️ Configure GitHub Pages settings after first deploy
5. ⏭️ Visit https://trackrat-dev.github.io/TrackRat/

Happy deploying! 🚀
