# Step 1: Install Homebrew

Homebrew is the standard package manager for macOS and simplifies the installation of all further tools.

Open Terminal (found via Spotlight: `Cmd + Space` → type "Terminal") and run the following command:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the on-screen instructions. After installation, add Homebrew to your shell path (the installation script shows this command at the end — copy and run it).

Verify the installation was successful:

```bash
brew --version
```
