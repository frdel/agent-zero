#!/bin/bash
set -e

# Xpra's ARM64 Release can mark Packages as empty while its signed gzip index is intact.
APT_OPTIONS=(
  -o "Dir::Etc::sourcelist=${1:?Xpra source file is required}"
  -o Dir::Etc::sourceparts=-
  -o APT::Get::List-Cleanup=false
  -o APT::Update::Error-Mode=any
  -o 'Acquire::IndexTargets::deb::Packages::MetaKey=$(COMPONENT)/binary-$(ARCHITECTURE)/Packages.gz'
  -o Acquire::IndexTargets::deb::Packages::KeepCompressed=true
  -o Acquire::IndexTargets::deb::Packages::KeepCompressedAs=gz
)
apt-get "${APT_OPTIONS[@]}" update
indexes="$(apt-get "${APT_OPTIONS[@]}" indextargets --format '$(FILENAME)' 'Created-By: Packages')"
# Normal package lookups expect Packages.gz instead of this target's Packages.gz.gz.
while IFS= read -r index; do
  mv -- "$index" "${index%.gz}"
done <<<"$indexes"
