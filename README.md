# 🚀 JoinCare BOT

> Automated airdrop farming solution for efficient time and multi-account management


## 📦 Project Structure

```
Joincare-Auto-Bot/
├── accounts.txt
├── bot.py
├── proxy.txt
├── requirements.txt
└── README.md
```

## 🎯 Overview

JoinCare BOT is an automated tool designed to streamline onchain operations across multiple accounts. It provides seamless integration with BNB network and offers robust proxy support for enhanced security and reliability.

**🔗 Get Started:** [Register on JoinCare](https://joincarelabs.com)

> **Important:** Connect new evm wallet and need some BNB for gas fee.

## ✨ Features

- 🔄 **Automated Account Management** - Retrieve account information automatically
- 🌐 **Flexible Proxy Support** - Run with or without proxy configuration
- 🔀 **Smart Proxy Rotation** - Automatic rotation of invalid proxies
- ✍ **Account Registration** – Automated registration for new users
- ⏰ **Daily Check-In** – Automated perform daily check-in
- 👥 **Multi-Account Support** - Manage multiple accounts simultaneously

## 📋 Requirements

- **Python:** Version 3.9 or higher
- **pip:** Latest version recommended
- **Compatible libraries:** See requirements.txt

## 🛠 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yumidara/JoinCare-Auto-Bot.git
cd JoinCare-Auto-Bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
# or for Python 3 specifically
pip3 install -r requirements.txt
```

### 3. Library Version Management

> ⚠️ **Important:** Ensure library versions match those specified in `requirements.txt`

**Check installed library version:**
```bash
pip show library_name
```

**Uninstall conflicting library:**
```bash
pip uninstall library_name
```

**Install specific library version:**
```bash
pip install library_name==version
```

## ⚙️ Configuration

### Account Setup

Create or edit `accounts.txt` in the project directory:

```
your_private_key_1
your_private_key_2
your_private_key_3
```

### Proxy Configuration (Optional)

Create or edit `proxy.txt` in the project directory:

```
# Simple format (HTTP protocol by default)
192.168.1.1:8080

# With protocol specification
http://192.168.1.1:8080
https://192.168.1.1:8080

# With authentication
http://username:password@192.168.1.1:8080
```

## 🚀 Usage

Run the bot using one of the following commands:

```bash
python bot.py
# or for Python 3 specifically
python3 bot.py
```

### Runtime Options

When starting the bot, you'll be prompted to choose:

1. **Proxy Mode Selection:**
   - Option `1`: Run with proxy
   - Option `2`: Run without proxy

2. **Auto-Rotation:** 
   - `y`: Enable automatic invalid proxy rotation
   - `n`: Disable auto-rotation


## 🤝 Contributing

We welcome contributions from the community! Here's how you can help:

1. ⭐ **Star this repository** if you find it useful
2. 👥 **Follow** for updates on new features


---

## ⚠️ Security Warning

❌ DO NOT commit the .env file to GitHub
❌ DO NOT share your private key with anyone
✅ Use a separate wallet specifically for the bot
✅ Always test with a small amount first

## 📄 Lisensi

MIT License - Use wisely and at your own responsibility.