#!/bin/bash
set -e

# install playwright - moved to install A0
# bash /ins/install_playwright.sh "$@"

# searxng - moved to base image
# bash /ins/install_searxng.sh "$@"

if ! command -v apt-get >/dev/null 2>&1; then
  echo "apt-get unavailable; skipping LibreOffice install"
  exit 0
fi

ATK_VERSION="2.60.3-1"
LIBREOFFICE_VERSION="4:26.2.4.2-1"
XPRA_VERSION="6.5.2-r0-1"
arch="$(dpkg --print-architecture)"

XPRA_HTML5_VERSION="19-r1-1"
if [ "$arch" = "arm64" ]; then
  XPRA_HTML5_VERSION="21-r1-1"
fi

ATK_PACKAGES=(
  "at-spi2-common=$ATK_VERSION"
  "libatk1.0-0t64=$ATK_VERSION"
  "libatk-bridge2.0-0t64=$ATK_VERSION"
  "libatspi2.0-0t64=$ATK_VERSION"
  "gir1.2-atk-1.0=$ATK_VERSION"
)
for package in at-spi2-core gir1.2-atspi-2.0; do
  if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
    ATK_PACKAGES+=("$package=$ATK_VERSION")
  fi
done

LIBREOFFICE_PACKAGES=(
  "libreoffice-core=$LIBREOFFICE_VERSION"
  "libreoffice-writer=$LIBREOFFICE_VERSION"
  "libreoffice-calc=$LIBREOFFICE_VERSION"
  "libreoffice-impress=$LIBREOFFICE_VERSION"
  "libreoffice-gtk3=$LIBREOFFICE_VERSION"
  "python3-uno=$LIBREOFFICE_VERSION"
)
XPRA_PACKAGES=(
  "xpra-common=$XPRA_VERSION"
  "xpra-server=$XPRA_VERSION"
  "xpra-client=$XPRA_VERSION"
  "xpra-client-gtk3=$XPRA_VERSION"
  "xpra-x11=$XPRA_VERSION"
  "xpra-html5=$XPRA_HTML5_VERSION"
)

# Keep the Python 3.13 desktop stack on a signed, dated archive. Kali's
# last-snapshot moves between releases and no longer carries these versions.
cat >/etc/apt/a0-desktop.list <<EOF
deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://snapshot.debian.org/archive/debian/20260624T000000Z/ forky main
EOF
APT_OPTIONS=(-o Dir::Etc::sourcelist=/etc/apt/a0-desktop.list -o Dir::Etc::sourceparts=- -o APT::Update::Error-Mode=any)

apt-get "${APT_OPTIONS[@]}" update
DEBIAN_FRONTEND=noninteractive apt-get "${APT_OPTIONS[@]}" install -y --no-install-recommends ca-certificates wget
wget -O /usr/share/keyrings/xpra.asc https://xpra.org/xpra.asc
cat >/etc/apt/sources.list.d/xpra.sources <<EOF
Types: deb
URIs: https://xpra.org
Suites: trixie
Components: main
Signed-By: /usr/share/keyrings/xpra.asc
Architectures: $arch
EOF
echo "deb [arch=$arch signed-by=/usr/share/keyrings/xpra.asc] https://xpra.org trixie main" >>/etc/apt/a0-desktop.list
bash /git/agent-zero/plugins/_desktop/helpers/refresh_xpra_index.sh /etc/apt/sources.list.d/xpra.sources
DEBIAN_FRONTEND=noninteractive apt-get "${APT_OPTIONS[@]}" install -y --no-install-recommends --allow-downgrades \
  "${ATK_PACKAGES[@]}" \
  gir1.2-gtk-3.0 \
  "${LIBREOFFICE_PACKAGES[@]}" \
  "${XPRA_PACKAGES[@]}" \
  xfce4-session \
  xfwm4 \
  xfce4-panel \
  xfdesktop4 \
  xfce4-settings \
  thunar \
  gvfs \
  libglib2.0-bin \
  xfce4-terminal \
  x11-xserver-utils \
  x11-utils \
  x11-apps \
  xdotool \
  xclip \
  xauth \
  xvfb \
  dbus-x11 \
  fonts-dejavu \
  fonts-liberation \
  fonts-crosextra-caladea \
  fonts-crosextra-carlito \
  fonts-noto-core \
  fonts-noto-cjk \
  fonts-noto-color-emoji

rm -rf /var/lib/apt/lists/*
