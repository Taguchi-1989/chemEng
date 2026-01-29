#!/bin/bash
# ChemEng AWS EC2 Setup Script
# Ubuntu 22.04 LTS用

set -e

echo "=== ChemEng AWS Setup Script ==="
echo ""

# システム更新
echo "[1/6] システム更新中..."
sudo apt update && sudo apt upgrade -y

# Python と必要パッケージ
echo "[2/6] Python・パッケージインストール中..."
sudo apt install -y python3.10 python3.10-venv python3-pip git nginx

# スワップ設定 (t2.microのメモリ対策)
echo "[3/6] スワップ設定中..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 1G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "スワップ作成完了"
else
    echo "スワップは既に存在します"
fi

# アプリケーションディレクトリ
echo "[4/6] ディレクトリ作成中..."
sudo mkdir -p /opt/chemeng
sudo chown ubuntu:ubuntu /opt/chemeng

# ログディレクトリ
sudo mkdir -p /var/log/chemeng
sudo chown ubuntu:ubuntu /var/log/chemeng

echo "[5/6] セットアップ完了"
echo ""
echo "=== 次のステップ ==="
echo ""
echo "1. GitHubからコードをクローン:"
echo "   cd /opt/chemeng"
echo "   git clone https://github.com/Taguchi-1989/chemEng.git ."
echo ""
echo "2. 仮想環境を作成:"
echo "   python3.10 -m venv venv"
echo "   source venv/bin/activate"
echo ""
echo "3. 依存関係をインストール:"
echo "   pip install --upgrade pip"
echo "   pip install -e \".[api]\""
echo ""
echo "4. systemdサービスを設定:"
echo "   sudo cp /opt/chemeng/deploy/aws/chemeng.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable chemeng"
echo "   sudo systemctl start chemeng"
echo ""
echo "5. nginxを設定:"
echo "   sudo cp /opt/chemeng/deploy/aws/nginx.conf /etc/nginx/sites-available/chemeng"
echo "   sudo ln -s /etc/nginx/sites-available/chemeng /etc/nginx/sites-enabled/"
echo "   sudo rm -f /etc/nginx/sites-enabled/default"
echo "   sudo nginx -t"
echo "   sudo systemctl restart nginx"
echo ""
echo "6. 動作確認:"
echo "   curl http://localhost/api"
echo ""
