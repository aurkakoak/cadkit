#!/bin/sh
# Install the latest CadKit macOS release without requiring Python or Node.
set -eu

install_cadkit() {
  repo=${CADKIT_REPOSITORY:-aurkakoak/cadkit}
  version=${CADKIT_VERSION:-}
  destination=${CADKIT_INSTALL_DIR:-"$HOME/Applications"}
  fail() { printf 'CadKit: %s\n' "$*" >&2; exit 1; }
  [ "$(uname -s)" = Darwin ] || fail 'This installer supports macOS. On Windows use install.ps1 or the .exe release. Linux binaries are not yet available.'
  case "$(uname -m)" in
    arm64) arch=arm64 ;;
    x86_64) arch=x64 ;;
    *) fail 'Unsupported Mac architecture.' ;;
  esac
  case "$repo" in *[!a-zA-Z0-9_./-]*|'') fail 'Invalid repository.' ;; esac
  for tool in curl shasum ditto mktemp; do
    command -v "$tool" >/dev/null 2>&1 || fail "Required command is missing: $tool"
  done
  if [ -z "$version" ]; then
    metadata=$(curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
      "https://api.github.com/repos/$repo/releases/latest") || fail 'No published release could be downloaded. See the GitHub releases page.'
    version=$(printf '%s\n' "$metadata" | sed -n 's/^[[:space:]]*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)
  fi
  version=${version#v}
  printf '%s\n' "$version" | LC_ALL=C grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$' || fail 'Invalid release version.'
  asset="CadKit-$version-macos-$arch.zip"
  base="https://github.com/$repo/releases/download/v$version"
  scratch=$(mktemp -d "${TMPDIR:-/tmp}/cadkit-install.XXXXXX")
  stage=
  cleanup() {
    rm -rf "$scratch"
    if [ -n "$stage" ]; then
      if [ -e "$stage/previous.app" ] && [ ! -e "$destination/CadKit.app" ]; then
        mv "$stage/previous.app" "$destination/CadKit.app" || return
      fi
      rm -rf "$stage"
    fi
  }
  trap cleanup EXIT
  trap 'exit 1' HUP INT TERM
  printf 'Downloading CadKit %s for macOS %s…\n' "$version" "$arch"
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "$base/$asset" -o "$scratch/$asset"
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "$base/SHA256SUMS" -o "$scratch/SHA256SUMS"
  expected=$(awk -v name="$asset" '$2 == name { print $1 }' "$scratch/SHA256SUMS")
  printf '%s\n' "$expected" | LC_ALL=C grep -Eq '^[a-f0-9]{64}$' || fail 'Release checksum is missing or ambiguous.'
  actual=$(shasum -a 256 "$scratch/$asset" | awk '{ print $1 }')
  [ "$actual" = "$expected" ] || fail 'Checksum verification failed; the app has not been changed.'
  ditto -x -k "$scratch/$asset" "$scratch/unpacked"
  [ -x "$scratch/unpacked/CadKit.app/Contents/MacOS/CadKit" ] || fail 'The archive does not contain CadKit.app.'
  mkdir -p "$destination"
  stage=$(mktemp -d "$destination/.cadkit-install.XXXXXX")
  ditto "$scratch/unpacked/CadKit.app" "$stage/CadKit.app"
  # Stage on the destination filesystem, retain the previous app until replacement succeeds.
  if [ -e "$destination/CadKit.app" ]; then
    mv "$destination/CadKit.app" "$stage/previous.app"
  fi
  if ! mv "$stage/CadKit.app" "$destination/CadKit.app"; then
    if [ -e "$stage/previous.app" ]; then mv "$stage/previous.app" "$destination/CadKit.app"; fi
    fail 'Could not install CadKit.'
  fi
  printf 'Installed %s/CadKit.app\nOpen it in Finder to get started.\n' "$destination"
}

# Keep execution at the end so a truncated download cannot execute a partial installer.
install_cadkit
