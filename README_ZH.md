# e621 Tagger 标签校准工具 · e621 Tag Calibration Toolkit

## 项目简介 · Project Overview
本仓库在原始 e621 tagger 的基础上进行了深度扩展，提供一个基于 PyQt5 的桌面应用，用于批量查看、翻译、标注和锁定插画标签。  
This repository extends the original e621 tagger with a PyQt5 desktop application that streamlines batch reviewing, translating, editing, and locking of illustration tags.

## 功能特性 · Features
- 🏷️ **标签管理 Tag Management**：双列同步显示英文/中文标签，支持增删改、撤销重做、批量替换。  
- 🌐 **多级翻译链 Translation Pipeline**：优先使用 Google API，失败时回退 LibreTranslate、Argos Translate、内置词典，并带缓存。  
- 📷 **图片预览 Image Viewer**：自适应窗口、滚轮缩放、双击复位，`←/→` 快速切换图片。  
- 📋 **复制粘贴 Copy & Paste**：复制当前标签到剪贴板，粘贴到任何文件并自动补齐缺失翻译。  
- 🔒 **完成标记 Locking**：一键“🔓 标记为完成 / 🔒 取消标记”，锁定后所有编辑操作禁用，状态栏和按钮均显示锁图标提示。  
- 🧹 **批量工具 Bulk Utilities**：批量删除标签时自动跳过锁定文件并输出统计报告。  
- 💾 **安全写入 Safe Saves**：保存前自动生成 `.bak` 备份，“恢复初始”随时回到加载状态。  
- ⚙️ **可配置后缀 Configurable Suffix**：默认标签后缀为 `.final.txt`，可在工具栏动态调整。

## 目录结构 · Directory Layout
```
├─tag_viewer.py           # PyQt 程序入口 / Application entry point
├─tagger/
│  ├─app.py               # QApplication 引导 / Bootstrap
│  ├─main_window.py       # 主界面、业务流程 / Main window & logic
│  ├─widgets.py           # 自定义控件（标签行、图片视图）/ Custom widgets
│  ├─translation.py       # 翻译管线与缓存 / Translation pipeline
│  ├─commands.py          # 撤销命令封装 / QUndoCommand implementations
│  ├─fileops.py           # 文件扫描、读写、锁定 / IO & locking helpers
│  ├─config.py            # 常量配置 / Global constants
│  ├─utils.py             # 工具函数（语言检测等）/ Utility helpers
│  └─dto.py               # 数据结构 / Data objects
├─docs/                   # 需求与进度记录 / Requirements & changelog
├─data/poren/             # 示例图片与标签 / Sample images & tags
├─train/                  # 训练脚本 / Training utilities
├─requirements.txt        # 依赖列表（需额外安装 PyQt5 等）/ Base dependencies
└─其它辅助脚本（webui.py、gpt_merge_tags_batch.py 等）/ Additional utilities
```

## 环境准备 · Setup
1. **Python 3.9+**（建议）/ Python 3.9 or above recommended。  
2. （可选）创建虚拟环境 / Create a virtual environment:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```
3. 安装依赖 / Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install PyQt5 requests
   # 如需离线翻译 / optional offline translation
   pip install argostranslate
   ```
4. 首次启动会在 `data/local_dictionary.json` 自动生成词典文件，可按需补充。  
   A local dictionary (`data/local_dictionary.json`) is created on first launch and can be extended manually.

## 启动方式 · How to Run
```bash
python tag_viewer.py
```
启动后 / On launch：
1. 选择图片与标签所在目录（默认 `data/poren`）。  
2. 左侧标签面板显示英文/中文，右侧展示图片预览。  
3. 主要按钮 / Key buttons:
   - **添加标签 Add Tag**：支持中文或英文输入，自动生成另一语言翻译。  
   - **重新翻译 Retranslate**：刷新当前所有标签的翻译。  
   - **恢复初始 Restore Initial**：回滚到文件加载时状态并清除撤销记录。  
   - **复制 & 粘贴 Copy & Paste**：在文件之间快速复用标签。  
   - **🔓/🔒 标记为完成 Toggle Lock**：切换锁定状态；锁定后仅可查看与复制。
4. 快捷键 / Shortcuts：  
   - `Ctrl+S` 保存 / Save  
   - `Ctrl+Z` / `Ctrl+Shift+Z` 撤销 / 重做  
   - `← / →` 切换上一张 / 下一张图片  
   - 鼠标滚轮缩放图片，双击复位。

## 进阶说明 · Advanced Notes
- **锁定提示 Lock Indicators**：状态栏与按钮文案采用 `🔒`/`🔓` 图标，随时可见。  
- **翻译缓存 Translation Cache**：避免重复调用 API，提升性能。  
- **批量删除 Bulk Delete**：锁定文件会被自动跳过并在结果中统计。  
- **文件命名 File Naming**：默认 `xxx.png` 对应 `xxx.final.txt`，可在“设置后缀”中自定义。  
- **翻译扩展 Extending Translation**：可在 `translation.py` 注册新的翻译服务或调整优先级。

## 开发者提示 · Developer Notes
- 撤销体系基于 `QUndoStack`/`QUndoCommand`，核心命令定义于 `tagger/commands.py`。  
- 锁定机制通过 `.lock` 文件持久化，可手动删除以解锁。  
- 提交代码时请更新 `docs/当前开发进度.md`，保持进度同步。  
- 若要发布至自己的仓库，请遵循原项目许可并在 README 中保留引用。

## 许可 & 致谢 · License & Credits
本项目延续原 e621 tagger 的许可协议；请在再发布或分支开发时核实并遵循原始授权条款。  
The project follows the original e621 tagger license. Verify and respect the upstream license when redistributing or branching.

---

如需报告问题或提交功能建议，可在 `docs/需求整理.md` 记录，或在你的仓库 Issue 区进行跟踪。  
For bug reports or feature requests, feel free to document them in `docs/需求整理.md` or via your issue tracker.
