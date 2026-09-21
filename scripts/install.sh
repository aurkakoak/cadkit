#!/bin/sh
# Install a native CadKit release without requiring Python or Node.
set -eu

install_cadkit() {
  repo=${CADKIT_REPOSITORY:-aurkakoak/cadkit}
  version=${CADKIT_VERSION:-}
  fail() { printf 'CadKit: %s\n' "$*" >&2; exit 1; }
  case "$(uname -s)" in
    Darwin) platform=macos; extension=zip ;;
    Linux) platform=linux; extension=tar.gz ;;
    *) fail 'This installer supports macOS and Linux.' ;;
  esac
  case "$(uname -m)" in
    arm64|aarch64) arch=arm64 ;;
    x86_64) arch=x64 ;;
    *) fail 'Supported architectures are x86_64 and arm64.' ;;
  esac
  case "$repo" in *[!a-zA-Z0-9_./-]*|'') fail 'Invalid repository.' ;; esac
  for tool in curl mktemp; do
    command -v "$tool" >/dev/null 2>&1 || fail "Required command is missing: $tool"
  done
  if command -v sha256sum >/dev/null 2>&1; then hash_command=sha256sum
  elif command -v shasum >/dev/null 2>&1; then hash_command='shasum -a 256'
  else fail 'A SHA-256 tool (sha256sum or shasum) is required.'; fi
  if [ "$platform" = macos ]; then
    command -v ditto >/dev/null 2>&1 || fail 'ditto is required.'
    destination=${CADKIT_INSTALL_DIR:-"$HOME/Applications"}/CadKit.app
  else
    command -v tar >/dev/null 2>&1 || fail 'tar is required.'
    data_dir=${XDG_DATA_HOME:-"$HOME/.local/share"}
    destination=${CADKIT_INSTALL_DIR:-"$data_dir/cadkit"}
    bin_dir=${CADKIT_BIN_DIR:-"$HOME/.local/bin"}
    case "$destination" in /*) ;; *) fail 'CADKIT_INSTALL_DIR must be an absolute path.' ;; esac
    if [ -e "$destination" ] && [ ! -x "$destination/cadkit-desktop" ]; then
      fail "Refusing to replace a directory that is not a CadKit installation: $destination"
    fi
    [ ! -d "$bin_dir/cadkit-desktop" ] || fail 'The launcher path is a directory.'
  fi
  if [ -z "$version" ]; then
    metadata=$(curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
      "https://api.github.com/repos/$repo/releases/latest") || fail 'No published release could be downloaded. See the GitHub releases page.'
    version=$(printf '%s\n' "$metadata" | sed -n 's/^[[:space:]]*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)
  fi
  version=${version#v}
  printf '%s\n' "$version" | LC_ALL=C grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$' || fail 'Invalid release version.'
  asset="CadKit-$version-$platform-$arch.$extension"
  base="https://github.com/$repo/releases/download/v$version"
  scratch=$(mktemp -d "${TMPDIR:-/tmp}/cadkit-install.XXXXXX")
  stage=
  cleanup() {
    rm -rf "$scratch"
    if [ -n "$stage" ]; then
      if [ -e "$stage/previous" ] && [ ! -e "$destination" ]; then
        mv "$stage/previous" "$destination" || return
      fi
      rm -rf "$stage"
    fi
  }
  trap cleanup EXIT
  trap 'exit 1' HUP INT TERM
  printf 'Downloading CadKit %s for %s %s…\n' "$version" "$platform" "$arch"
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "$base/$asset" -o "$scratch/$asset"
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "$base/SHA256SUMS" -o "$scratch/SHA256SUMS"
  expected=$(awk -v name="$asset" '$2 == name { print $1 }' "$scratch/SHA256SUMS")
  printf '%s\n' "$expected" | LC_ALL=C grep -Eq '^[a-f0-9]{64}$' || fail 'Release checksum is missing or ambiguous.'
  actual=$($hash_command "$scratch/$asset" | awk '{ print $1 }')
  [ "$actual" = "$expected" ] || fail 'Checksum verification failed; the app has not been changed.'
  mkdir -p "$scratch/unpacked"
  if [ "$platform" = macos ]; then
    ditto -x -k "$scratch/$asset" "$scratch/unpacked"
    source_app="$scratch/unpacked/CadKit.app"
    [ -x "$source_app/Contents/MacOS/CadKit" ] || fail 'The archive does not contain CadKit.app.'
  else
    tar -xzf "$scratch/$asset" -C "$scratch/unpacked"
    source_app="$scratch/unpacked/CadKit-$version-linux-$arch"
    [ -x "$source_app/cadkit-desktop" ] || fail 'The archive does not contain the CadKit executable.'
  fi
  parent=$(dirname "$destination")
  mkdir -p "$parent"
  stage=$(mktemp -d "$parent/.cadkit-install.XXXXXX")
  if [ "$platform" = macos ]; then ditto "$source_app" "$stage/application"
  else cp -R "$source_app" "$stage/application"; fi
  # Stage on the destination filesystem and keep the old app until replacement succeeds.
  if [ -e "$destination" ]; then mv "$destination" "$stage/previous"; fi
  if ! mv "$stage/application" "$destination"; then
    fail 'Could not install CadKit; restoring the previous version.'
  fi
  if [ "$platform" = macos ]; then
    printf 'Installed %s\nOpen it in Finder to get started.\n' "$destination"
  else
    mkdir -p "$bin_dir" "$data_dir/applications"
    ln -sfn "$destination/cadkit-desktop" "$bin_dir/cadkit-desktop"
    # Desktop Entry quoting differs from shell quoting. Escape reserved path characters.
    desktop_executable=$(printf '%s' "$destination/cadkit-desktop" | sed 's/[\\"`$]/\\&/g')
    cat > "$data_dir/applications/cadkit.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=CadKit
Comment=Inspect CadQuery projects
Exec="$desktop_executable"
Icon=$destination/resources/cadkit.svg
Terminal=false
Categories=Graphics;Engineering;
DESKTOP
    chmod 644 "$data_dir/applications/cadkit.desktop"
    printf 'Installed %s\nLaunch CadKit from your application menu or run %s/cadkit-desktop.\n' "$destination" "$bin_dir"
    case ":$PATH:" in *":$bin_dir:"*) ;; *) printf 'Add %s to PATH to use cadkit-desktop from any terminal.\n' "$bin_dir" ;; esac
  fi
}

# Execute only after the full script has been downloaded.
install_cadkit
