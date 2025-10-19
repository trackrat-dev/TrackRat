---
title: "Installation"
path: "installation"
---

The Ocuroot client is provided as an open source tool that provides you with everything you
need to run Ocuroot-enabled releases from your CI platform of choice.

### MacOS (Homebrew)

```bash
brew install ocuroot/tap/ocuroot
```

### Linux (Package Managers)

> **Note:** Check the [releases page](https://github.com/ocuroot/ocuroot/releases) to find the latest version number and available architectures.

#### Debian/Ubuntu (.deb)

Download and install the `.deb` package from the [releases page](https://github.com/ocuroot/ocuroot/releases):

```bash
# Download the package (replace $VERSION and $ARCH as needed)
wget https://github.com/ocuroot/ocuroot/releases/download/v$VERSION/ocuroot_$VERSION_$ARCH.deb

# Install the package
sudo dpkg -i ocuroot_$VERSION_$ARCH.deb

# Fix dependencies if needed
sudo apt-get install -f
```

#### RHEL/CentOS/Fedora (.rpm)

Download and install the `.rpm` package from the [releases page](https://github.com/ocuroot/ocuroot/releases):

```bash
# Download the package (replace $VERSION and $ARCH as needed)
wget https://github.com/ocuroot/ocuroot/releases/download/v$VERSION/ocuroot_$VERSION_$ARCH.rpm

# Install the package
sudo rpm -i ocuroot_$VERSION_$ARCH.rpm

# Or using dnf/yum
sudo dnf install ocuroot_$VERSION_$ARCH.rpm
```

### Using bin

You can use the excellent [bin](https://github.com/marcosnils/bin) tool to install directly from the latest GitHub release:

```bash
bin install github.com/ocuroot/ocuroot
```

This automatically downloads the correct binary for your platform from the [releases page](https://github.com/ocuroot/ocuroot/releases).


## From Source

If you have [Go](https://go.dev/) installed, you can build Ocuroot directly from the source repo:

```bash
go install github.com/ocuroot/ocuroot/cmd/ocuroot@latest
```

