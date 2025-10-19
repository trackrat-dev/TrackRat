---
title: "CI Integration"
path: "usage/ci-integration"
---

As detailed in the [Scheduling Work](/docs/usage/scheduling-work) page, Ocuroot integrates with CI
platforms via a set of commands that can be executed in response to commits or changes to intent.

This page details concrete configuration that can be applied to various CI platforms to integrate with
Ocuroot.

## General approach

We're always aiming for Ocuroot to be tooling-agnostic, and your choice of CI platform is no exception!
Integrating Ocuroot with your platform of choice is as simple as configuring execution of three key commands.

### Releases

Releases are where everything starts, and you will typically want to trigger a release on every commit to the
default branch of your source repo(s).

When a new push is received, you'll want to configure your platform to run:

```bash
# Create a new release
ocuroot release new release.ocu.star --cascade
```

Where *release.ocu.star* is the path to an Ocuroot config for the appropriate release. In a monorepo environment,
you may want to run `ocuroot release new` multiple times for different files. To help with controlling which commands
are run based on which files change, we've provided a free tool: [ifdiff](https://github.com/ocuroot/ifdiff).

### Handling Intent updates

Finally, you need to be able to handle changes to the intent repo, like manual modification of environments or custom
state. On pushes to the intent repo, your CI platform should fun the following command:

```bash
ocuroot work cascade
```

## GitHub Actions

Code for this example can also be found at [https://github.com/ocuroot/gh-actions-example](https://github.com/ocuroot/gh-actions-example).

### Releases

Below is an example workflow config to execute release on pushes to the "main" branch of your repo.

You would put this file under `.github/workflows/ocuroot-release.yml`.

```yaml
name: Ocuroot Release

on:
  push:
    branches: [main]

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@v5
        with:
          fetch-depth: 0

      - name: Download ocuroot binary
        run: |
          curl -Lv https://github.com/ocuroot/ocuroot/releases/download/v0.3.16/ocuroot_linux-amd64.tar.gz -o ocuroot.tar.gz
          tar -xzf ocuroot.tar.gz
          chmod +x ocuroot

      - name: Release
        env:
          GH_TOKEN: ${{ secrets.PAT_TOKEN }}
        run: |
          ./ocuroot release new release.ocu.star --cascade
```

There are two additional pieces of configuration to be aware of.

`secrets.PAT_TOKEN` should contain a [GitHub PAT](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) token with access to the Git repo(s) containing state and intent. If source, state and intent are all branches of the same repo, you can use the built-in `GITHUB_TOKEN` secret.

### Handing Intent updates

You'll also need to add a workflow to your **intent repo** to handle intent changes:

```yaml
name: Ocuroot Cascade

on:
  push:
    branches: [intent]

jobs:
  cascade:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@v5
        with:
          fetch-depth: 0

      - name: Download ocuroot binary
        run: |
          curl -Lv https://github.com/ocuroot/ocuroot/releases/download/v0.3.16/ocuroot_linux-amd64.tar.gz -o ocuroot.tar.gz
          tar -xzf ocuroot.tar.gz
          chmod +x ocuroot

      - name: Cascade
        env:
          GH_TOKEN: ${{ secrets.PAT_TOKEN }}
        run: |
          ./ocuroot work cascade
```

### Configuring remotes

For Ocuroot to clone repos, it needs to know where they are. Since Git remotes can vary quite a lot even for
the same repo (https vs ssh anyone?), there is now the option to provide a set of remotes to try in `repo.ocu.star`.
Even better, because all Ocuroot config is Starlark, you can write logic to build a remote based on where Ocuroot
is running. For example, you can support local execution and GitHub Actions at the same time:

```python
def repo_url():
    env_vars = env()
    # When running outside GitHub Actions, use the origin remote as-is
    if "GH_TOKEN" not in env_vars:
        return host.shell("git remote get-url origin").stdout.strip()
    # Always use https for checkout with the appropriate token on GitHub actions
    return "https://x-access-token:{}@github.com/ocuroot/gh-actions-example.git".format(env_vars["GH_TOKEN"])

remotes([repo_url()])
```

## Coming soon

We're aiming to provide instructions for other platforms over time, including, but not limited to:

* Jenkins
* CircleCI

If you'd like to see instructions for your CI platform of choice here, feel free to raise a [GitHub issue](https://github.com/ocuroot/ocuroot/issues).

