# Windows 打包指南

## 准备工作

### 1. 安装 Python
- 访问 https://www.python.org/downloads/
- 下载 Python 3.8 或更高版本
- 安装时勾选 **"Add Python to PATH"**

### 2. 下载源码包
将以下文件放到同一个文件夹（例如 `C:\AeroMat`）：
- `main.py` - 主程序
- `build_exe.py` - 打包脚本
- `requirements.txt` - 依赖列表
- `README.md` - 使用说明

## 打包步骤

### 方法一：使用打包脚本（推荐）

1. 打开命令提示符（Win+R，输入 `cmd`）

2. 进入源码目录：
   ```cmd
   cd C:\AeroMat
   ```

3. 安装依赖：
   ```cmd
   pip install -r requirements.txt
   ```
   
   或者手动安装：
   ```cmd
   pip install pandas openpyxl pyinstaller
   ```

4. 运行打包脚本：
   ```cmd
   python build_exe.py
   ```

5. 等待打包完成（可能需要5-10分钟）

6. 打包完成后，exe文件在：
   ```
   C:\AeroMat\dist\航材库存管理系统.exe
   ```

### 方法二：手动打包

1. 安装依赖（同上）

2. 运行PyInstaller命令：
   ```cmd
   pyinstaller --onefile --windowed --name="航材库存管理系统" main.py
   ```

3. exe文件在 `dist\航材库存管理系统.exe`

## 测试exe

1. 双击 `航材库存管理系统.exe`

2. 如果提示"Windows保护计算机"，点击"仍要运行"

3. 程序应该正常启动，显示主界面

## 分发exe

打包后的exe是独立可执行文件，可以直接复制到其他Windows电脑运行，无需安装Python。

建议分发时包含：
- `航材库存管理系统.exe` - 主程序
- `README.md` - 使用说明
- 示例Excel文件（如果有）

## 常见问题

### Q: 打包失败，提示"找不到模块"
**A:** 确保已安装所有依赖：
```cmd
pip install pandas openpyxl pyinstaller
```

### Q: exe运行报错"缺少DLL"
**A:** 可能是Python版本问题，尝试使用Python 3.8或3.9重新打包。

### Q: exe文件太大（超过100MB）
**A:** 这是正常的，因为PyInstaller会把Python运行环境和所有依赖都打包进去。可以使用UPX压缩（添加 `--upx-dir` 参数）。

### Q: 杀毒软件误报
**A:** PyInstaller打包的程序可能被某些杀毒软件误报。可以添加数字签名，或使用Nuitka替代PyInstaller。

## 进阶：使用Nuitka打包（更小更快）

Nuitka是另一个打包工具，生成的exe更小，启动更快。

1. 安装Nuitka：
   ```cmd
   pip install nuitka
   ```

2. 打包命令：
   ```cmd
   python -m nuitka --standalone --onefile --windows-disable-console --output-filename="航材库存管理系统.exe" main.py
   ```

## 下一步

打包成功后，建议：
1. 在多台电脑测试exe
2. 创建桌面快捷方式
3. 定期备份数据库文件（`aeromat.db`）

---
如有问题，请联系开发者。
