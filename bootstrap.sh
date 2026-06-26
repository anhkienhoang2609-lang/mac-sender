#!/bin/bash
set -e

DEST="$HOME/MacSender"
echo "==> Tải code về $DEST ..."
rm -rf "$DEST"
mkdir -p "$DEST"
curl -fsSL https://github.com/anhkienhoang2609-lang/mac-sender/archive/refs/heads/main.tar.gz \
    | tar -xz -C "$DEST" --strip-components=1

cd "$DEST"
bash install.sh

echo "==> Mở app..."
open "$DEST/Mac Sender.command"
