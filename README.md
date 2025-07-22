# 安卓应用修改器

这是一个用于修改Android APK的桌面工具。该工具可以自动修改APK的网络安全配置，使其信任用户提供的证书，并进行自动重签名对齐等操作。

## 功能特性

- APK文件反编译和重打包
- 自动修改网络安全配置
- 支持新证书签名
- 图形用户界面
- 文件拖放支持

## 系统要求

- Python 3.13.2
- Windows 或 macOS 操作系统
- Java Development Kit (JDK) - 用于APK签名
- Android SDK Build Tools - 用于apktool

## 安装

1. 确保已安装Python 3.13.2
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 安装外部工具：
   - 安装JDK
   - 安装Android SDK Build Tools
   - 确保apktool在系统路径中可用

## 使用方法

1. 运行程序：
   ```bash
   python src/main.py
   ```
2. 在界面中选择或拖放APK文件
3. 选择或拖放证书文件
4. 填写证书相关信息
5. 点击"处理"按钮开始处理

## 注意事项

- 请在处理前备份原始APK文件
- 确保有足够的磁盘空间
- 确保具有适当的文件访问权限
