#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "==> Kiểm tra Homebrew..."
if ! command -v brew >/dev/null 2>&1; then
    echo "==> Chưa có Homebrew, đang cài..."
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi

echo "==> Cài sshpass, rsync, python-tk@3.12..."
brew install sshpass rsync python-tk@3.12 python@3.12

PY="$(brew --prefix python@3.12)/bin/python3.12"

echo "==> Tạo virtualenv riêng cho app..."
"$PY" -m venv "$DIR/venv"
source "$DIR/venv/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet customtkinter

echo "==> Tạo file chạy 'Mac Sender.command'..."
cat > "$DIR/Mac Sender.command" << EOF
#!/bin/bash
cd "$DIR"
source "$DIR/venv/bin/activate"
python3 "$DIR/mac_sender.py"
EOF
chmod +x "$DIR/Mac Sender.command"

echo ""
echo "✅ Cài đặt xong! Double-click vào file 'Mac Sender.command' để mở app."
echo "   (Lần đầu mở: chuột phải -> Open để macOS cho phép chạy.)"
