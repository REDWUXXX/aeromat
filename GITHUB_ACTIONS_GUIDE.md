# 航材库存管理系统 v2.0 - GitHub Actions 自动打包指南

## 🚀 快速开始（GitHub Actions自动打包）

### 第一步：创建GitHub仓库

1. 登录 https://github.com （没有账号先注册）
2. 点击右上角 **+** → **New repository**
3. 填写信息：
   - Repository name: `aeromat`（或其他名字）
   - 选择 **Public** 或 **Private**
   - ✅ 勾选 **Add a README file**
4. 点击 **Create repository**

### 第二步：上传代码到GitHub

#### 方法A：网页上传（最简单）

1. 在GitHub仓库页面，点击 **Add file** → **Upload files**
2. 把 `/tmp/aeromat` 文件夹里的**所有文件**拖进去
3. 包括：
   - `main.py`
   - `build_exe.py`
   - `requirements.txt`
   - `README.md`
   - `.github/` 文件夹（**重要！**）
4. 在底部填写 commit message：`Initial commit`
5. 点击 **Commit changes**

#### 方法B：使用Git命令行（推荐）

在你的Mac上：

```bash
# 进入源码文件夹
cd /tmp/aeromat

# 初始化Git
git init
git add .
git commit -m "Initial commit"

# 关联GitHub仓库（替换成你的仓库地址）
git remote add origin https://github.com/你的用户名/aeromat.git

# 推送到GitHub
git push -u origin main
```

### 第三步：等待自动打包

1. 上传完成后，进入GitHub仓库
2. 点击顶部 **Actions** 标签
3. 你会看到 **Build Windows EXE** 正在运行
4. 等待约 **5-10分钟**

### 第四步：下载exe

1. 打包完成后，在Actions页面点击刚才的运行记录
2. 在底部 **Artifacts** 区域，点击 **航材库存管理系统_v2.0**
3. 下载zip文件，解压后得到 `航材库存管理系统_v2.0.exe`

---

## 📦 手动打包（备用方案）

如果GitHub Actions失败，可以在Windows电脑上手动打包：

### Windows手动打包步骤

1. 在Windows上安装Python 3.8+
   - 下载：https://www.python.org/downloads/
   - 安装时勾选 **Add Python to PATH**

2. 打开命令提示符（Win+R → 输入`cmd`）

3. 进入源码文件夹：
   ```cmd
   cd C:\path\to\aeromat
   ```

4. 安装依赖：
   ```cmd
   pip install pandas openpyxl pyinstaller
   ```

5. 打包：
   ```cmd
   python build_exe.py
   ```

6. 生成的exe在：`dist\航材库存管理系统_v2.0.exe`

---

## 🔧 常见问题

### Q: GitHub Actions打包失败怎么办？

**A:** 检查以下几点：
1. 确保 `.github/workflows/build-windows.yml` 文件已上传
2. 检查Actions页面的错误日志
3. 尝试重新运行（Actions页面 → 右上角 **Re-run all jobs**）

### Q: exe文件太大（超过100MB）？

**A:** 这是正常的，PyInstaller会把Python运行环境打包进去。可以：
1. 使用UPX压缩（在`build_exe.py`中添加`--upx-dir`参数）
2. 使用Nuitka打包（更小更快）

### Q: 下载的exe在Windows上无法运行？

**A:** 可能是杀毒软件误报，尝试：
1. 右键exe → 属性 → 解除锁定
2. 添加信任到杀毒软件白名单

### Q: 如何更新程序？

**A:** 
1. 修改代码后，重新上传到GitHub
2. GitHub Actions会自动重新打包
3. 下载最新的exe

---

## 📊 系统功能

### 核心功能
- ✅ 双层库存管理（航材型号 + 个体件）
- ✅ 件序号管理（自动生成唯一编号）
- ✅ 架位号显示（主界面 + 个体件详情）
- ✅ 有效期管理（灭火瓶/PBE等，提前90/60/30天预警）
- ✅ 出入库管理（自动加减库存，生成件序号）
- ✅ 低库存预警
- ✅ 统计分析（库存总览 + 出入库趋势）
- ✅ 数据导入（适配Excel格式）
- ✅ 数据导出（导出Excel报表）

### 使用方法

1. **第一次使用**：导入Excel库存数据
   - 点击"文件" → "导入Excel"
   - 选择你的库存列表文件

2. **日常操作**：
   - 入库：选中航材 → 点击"入库"
   - 出库：选中航材 → 点击"出库"
   - 查看个体件：双击航材

3. **预警查看**：
   - 点击"查询" → "低库存预警"
   - 点击"查询" → "有效期预警"

---

## 🛠️ 技术栈

- **语言**：Python 3.8+
- **GUI**：Tkinter
- **数据库**：SQLite
- **依赖**：pandas, openpyxl
- **打包**：PyInstaller (Windows exe)

---

## 📞 技术支持

如有问题，请检查：
1. GitHub Actions日志
2. README.md详细说明
3. 或在GitHub仓库提Issue

---

**版本**：v2.0  
**更新日期**：2026-06-24  
**开发者**：AI Assistant
