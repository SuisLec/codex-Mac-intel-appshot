# codex-Mac-intel-appshot (Codex Appshot Intel Mac Patch)

这是一个专门为 Intel 芯片 macOS 设备准备的 Codex Desktop "Appshots"（应用快照）功能修复与优化补丁。

## 背景

官方版本的 Codex Desktop 在实现 Appshot 时，依赖了一个名为 `SkyComputerUseService` 的独立后台二进制服务和 Node.js 原生插件 `sky.node`。由于这些组件仅编译了 `arm64`（Apple Silicon）版本，在 Intel（x86_64）芯片的 Mac 上运行时会因为架构不兼容导致程序崩溃或静默失效，并在前端显示“无法附加应用快照”的错误横幅。

本补丁通过重新实现窗口捕获、前台应用元数据获取和无障碍文本（AXText）提取等核心功能，完全在本地使用 Swift 编写并编译了替代工具，重新打补丁并封包了 JavaScript assets，使 Intel Mac 能够完美运行全部 Appshot 功能。

## 组成部分

1. **get_window_id.swift**: 通过应用的 Bundle Identifier 查找并获取当前活动窗口的窗口 ID（CGWindowID），用于精确截图。
2. **get_ax_text.swift**: 使用 macOS NSAccessibility API（无障碍接口）递归遍历前台窗口，提取结构化的文本树（AXText），供 AI 获取屏幕外的上下文或小字体文本。
3. **get_frontmost_window.swift**: 获取前台活动应用的名称、Bundle ID、应用图标的 Base64 字符串以及当前的窗口网页/文件标题，用于在输入框中渲染带图标的截图预览。
4. **patch.py**: 自动化的安装和打补丁脚本。负责：
   - 编译 Swift 源码为本地二进制文件
   - 解包 `app.asar`
   - 对核心 JS 代码（`worker.js`、`main.js`、`composer.js`）实施定向插桩修改
   - 封包并替换 `app.asar`
   - 对 Codex.app 进行本地重签名并清理权限数据库

## 运行步骤

1. 打开终端并进入本项目根目录。
2. 运行安装与打补丁脚本：
   ```bash
   python3 patch.py
   ```
3. 脚本会自动完成 Swift 编译、ASAR 解包、代码修改、封包替换、重签名以及权限重置。
4. 运行结束后，请重新打开 **Codex.app**。

## 权限授权说明（重要）

因为本补丁重新对 Codex.app 进行了本地签名（codesign），macOS 的安全防护数据库（TCC）会失效此前的权限缓存。当重新启动 Codex 并首次触发 Appshot 时，系统会弹出权限请求：
1. **屏幕录制权限**：根据系统弹窗提示，进入“系统设置 -> 隐私与安全性 -> 屏幕录制”，找到 Codex 并重新开启/勾选开关。
2. **辅助功能权限**：进入“系统设置 -> 隐私与安全性 -> 辅助功能”，确认开启 Codex 的辅助功能开关（用于抓取窗口文本和屏幕外内容）。
3. 授权完毕后，**请完全退出并重启一次 Codex.app** 即可永久生效。
