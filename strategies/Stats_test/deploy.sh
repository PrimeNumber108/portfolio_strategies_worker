#!/bin/bash

# Defaults
move_flag=copy

# Parse flags
while getopts s:m: flag; do
    case "${flag}" in
        s) server=${OPTARG};;
        m) move_flag=${OPTARG};;
    esac
done

if [ -z "$server" ]; then
    echo "❌ Missing server name. Usage: bash deploy.sh -s <server> [-m copy|move]"
    exit 1
fi

# Clean local old files
echo "🧹 Removing local .db and .log files..."
rm -rf *.db
rm -rf *.log

# Timestamp for backup
timestamp=$(date +%Y%m%d_%H%M%S)

# Move or copy old server folder if it exists
echo "🔁 Checking existing /var/www/strategies-src on server..."

if [ "$move_flag" == "copy" ]; then
    ssh "$server" << EOF
        if [ -d "/var/www/strategies-src" ]; then
            cp -r /var/www/strategies-src /var/www/strategies-src_$timestamp
            echo "📁 Copied /var/www/strategies-src to /var/www/strategies-src_$timestamp"
        else
            echo "ℹ️  /var/www/strategies-src does not exist, skipping copy."
        fi
EOF
elif [ "$move_flag" == "move" ]; then
    ssh "$server" << EOF
        if [ -d "/var/www/strategies-src" ]; then
            mv /var/www/strategies-src /var/www/strategies-src_$timestamp
            echo "📁 Moved /var/www/strategies-src to /var/www/strategies-src_$timestamp"
        else
            echo "ℹ️  /var/www/strategies-src does not exist, skipping move."
        fi
EOF
else
    echo "ℹ️  No move or copy option selected. Skipping backup of existing folder."
fi

# Deploy new files
echo "🚀 Deploying new files to $server:/var/www/strategies-src ..."
rsync -av --exclude='*.json' --exclude='*.git' --exclude='test_level*' * "$server":/var/www/strategies-src --rsync-path="sudo rsync"

# Run post-deployment steps on the server
ssh "$server" << EOF
    cd /var/www/strategies-src
    sudo chmod -R 775 /var/www/strategies-src
    sudo chmod -R 777 /var/www/strategies-src/logger
EOF

echo "✅ Deployment complete."
