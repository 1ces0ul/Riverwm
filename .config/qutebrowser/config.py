#!/usr/bin/env python3
# qutebrowser 配置文件（修正版）
# 位置: ~/.config/qutebrowser/config.py
# 全面覆盖日常使用场景 + 奇技淫巧

# ==================== 基本设置 ====================
import os
import shlex

# 加载自动配置（需要时取消注释）
config.load_autoconfig(False)
if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
    term = 'ghostty'
else:
    term = 'kitty -T Floating_Term'
term_cmd = shlex.split(term)
c.editor.command = term_cmd + ['-e', 'nvim', '{file}', '-c', 'normal {line}G{column0}l']
fileChooser = term_cmd + ['-e', 'yazi', '--chooser-file={}']
c.fileselect.handler = "external"
c.fileselect.folder.command = fileChooser
c.fileselect.multiple_files.command = fileChooser
c.fileselect.single_file.command = fileChooser

c.confirm_quit = ['downloads']  # 有下载任务时确认退出
c.downloads.location.directory = os.path.expanduser('~/Downloads')

# ==================== 外观与主题 ====================

# 暗色主题（保护眼睛）
c.colors.webpage.darkmode.enabled = True
c.colors.webpage.darkmode.policy.page = 'smart'  # 智能选择暗色模式
c.colors.webpage.preferred_color_scheme = 'dark'

# 字体设置
c.fonts.default_family = ['JetBrains Mono', 'Noto Sans CJK SC', 'DejaVu Sans']
c.fonts.default_size = '11pt'
c.fonts.web.family.standard = 'Noto Sans CJK SC'
c.fonts.web.family.fixed = 'JetBrains Mono'
c.fonts.web.size.default = 16
c.fonts.web.size.default_fixed = 15

# 界面美化
# The status bar is shown when in modes other than the default "normal" mode (e.g., insert, command, or caret modes).
c.statusbar.show = 'in-mode'
c.statusbar.position = 'bottom'
c.tabs.show = 'multiple'
c.tabs.position = 'left'
c.tabs.indicator.width = 3
c.tabs.title.format = '{index}: {audio} {current_title}'
c.tabs.title.format_pinned = '[P]{audio}{current_title}'  # 固定标签页
# 滚动条设置（简约风格）
c.scrolling.bar = 'when-searching'
c.scrolling.smooth = True

# ==================== 搜索与导航 ====================

# 起始页（可自定义）
c.url.start_pages = ['http://127.0.0.1:9090/ui/#/proxies']
c.url.default_page = 'https://start.duckduckgo.com'


# 快速书签（按 b + 字母访问）
c.aliases.update({
    'wiki': 'open https://www.wikipedia.org',
    'c': 'open http://127.0.0.1:9090/ui/#/proxies',
    'h': 'open https://portal.cmy.network/login?redirect=%2Fsubcenter%2Findex',
    'y': 'open https://www.youtube.com',
    'bd': 'open https://www.boot.dev/',
    'cf': 'open https://algo.codefather.cn/',
    'em': 'open https://evomap.ai/',
    'ai': 'open https://www.aigocode.com/dashboard/keys',
    'ds': 'open https://platform.deepseek.com/usage',
    'oc': 'open https://learnopencode.com/5-advanced/20-compaction',
    'vva': 'open https://vvacard.com/index/index.html',
    'cmy': 'open https://portal.cmy.network/',
    'gh': 'open https://github.com',
    'cfg': 'config-edit',  # 编辑本配置文件
    'src': 'config-source',
    'au': 'adblock-update',
    'cb': 'open https://codeberg.org/',
})

# 搜索引擎（快速搜索） - 确保每个都包含 {} 占位符
c.url.searchengines = {
    'DEFAULT': 'https://www.google.com/search?q={}',
    'g': 'https://www.google.com/search?q={}',
    'ddg': 'https://duckduckgo.com/?q={}',
    'w': 'https://en.wikipedia.org/wiki/{}',
    'yt': 'https://www.youtube.com/results?search_query={}',
    'gh': 'https://github.com/search?q={}',
    'aw': 'https://wiki.archlinux.org/index.php?search={}',
    'so': 'https://stackoverflow.com/search?q={}',
    'reddit': 'https://www.reddit.com/search?q={}',
    'b': 'https://search.brave.com/search?q={}',
    'tb': 'https://thepiratebay.org/search.php?q={}',
    'gpt': 'https://chatgpt.com/?q={}',
    'ai': 'https://claude.ai/chat?q={}',
}
c.url.yank_ignored_parameters = [
    'ref', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term',
    'utm_content', 'utm_name', 'fbclid', 'gclid', 'mc_cid', 'mc_eid',
]

# ==================== 隐私与安全 ====================

c.content.canvas_reading = False  # 禁止网站读取 canvas 数据（防指纹追踪）
c.content.geolocation = False     # 禁用地理位置
c.content.webrtc_ip_handling_policy = "default-public-interface-only"  # WebRTC IP 泄露保护
c.content.cookies.accept = 'no-3rdparty'

# 按站点放宽隐私限制，减少登录、验证码和 Web App 兼容性问题
config.set('content.canvas_reading', True, '*://chatgpt.com/*')
config.set('content.canvas_reading', True, '*://claude.ai/*')
config.set('content.cookies.accept', 'all', '*://accounts.google.com/*')
config.set('content.cookies.accept', 'all', '*://mail.google.com/*')
config.set('content.cookies.accept', 'all', '*://youtube.com/*')
config.set('content.cookies.accept', 'all', '*://*.youtube.com/*')

# 内容拦截（广告拦截）
c.content.blocking.enabled = True
c.content.blocking.method = 'both'  # 使用 hosts 和 AdBlock 列表

c.content.blocking.adblock.lists = [
  "https://easylist.to/easylist/easylist.txt",
  "https://secure.fanboy.co.nz/fanboy-cookiemonster.txt",
  "https://easylist.to/easylist/easyprivacy.txt",
  "https://secure.fanboy.co.nz/fanboy-annoyance.txt",]

#c.content.headers.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

# Cookie 策略切换
config.bind('za', 'set content.cookies.accept all')
config.bind(';can', 'set content.cookies.accept no-3rdparty')
config.bind(';cav', 'set content.cookies.accept never')

# UA 切换
config.bind(';ua1', 'set content.headers.user_agent "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"')
config.bind(';ua2', 'set content.headers.user_agent "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) QtWebEngine/5.15.0 Chrome/87.0.4280.144 Safari/537.36"')

# JavaScript 控制（按需开启）
c.content.javascript.enabled = True
c.content.javascript.can_open_tabs_automatically = False

# 限制最大化在窗口模式下的行为，允许全屏但不自动最大化
c.content.fullscreen.window = True
# 自动播放控制
c.content.autoplay = False

# ==================== 标签页与窗口管理 ====================

# 标签页行为
c.tabs.last_close = 'close'
c.tabs.select_on_remove = 'last-used'
c.tabs.show_switching_delay = 0
c.tabs.tabs_are_windows = False

# 新建标签页位置
c.tabs.new_position.unrelated = 'next'

# 窗口管理
c.window.hide_decoration = True

# ==================== 下载与媒体 ====================

# 下载设置
c.downloads.location.prompt = False       # 不询问下载位置
c.downloads.location.suggestion = 'both'  # 显示路径和文件名建议
c.downloads.location.remember = False     # 不记住下载位置
c.downloads.remove_finished = 3300        # 3.3秒后删除完成的下载
c.downloads.position = "bottom"           # 下载栏在底部显示
# 媒体控制
c.content.media.audio_capture = False
c.content.media.video_capture = False
c.content.media.audio_video_capture = False
c.content.mute = False

# PDF 查看器
c.content.pdfjs = True

# ==================== 性能优化 ====================

# 硬件加速 - 使用字符串 'false' 而不是布尔值 False
#c.qt.highdpi = True
#c.qt.force_software_rendering = 'none'

# unbind
config.unbind('<Ctrl-v>')

# ==================== 直通模式 ====================
# 直通模式：所有按键直接传给网页，不被 qutebrowser 拦截
# 比 insert 模式更彻底，适合网页版 IDE、终端等需要完整键盘的场景
config.bind('<Ctrl-Shift-v>', 'mode-enter passthrough')

# ==================== 奇技淫巧 ====================
# 重新加载配置文件（改完 config.py 后用）
config.bind('cs', 'config-source')

# 清除状态栏消息
config.bind('cm', 'clear-messages')

# 隐藏搜索引擎下拉推荐的快捷键（;H = hide）
config.bind(';H', 'fake-key <Escape>')

# 显示/隐藏标签页列表的快捷键
config.bind(',', 'config-cycle tabs.show never multiple')

# 显示/隐藏状态栏的快捷键
config.bind('.', 'config-cycle statusbar.show always in-mode')

# 视频控制（空格播放/暂停，f全屏）
#config.bind('<Space>', 'hint links spawn --detach mpv --ytdl-format=bestvideo+bestaudio/best {hint-url}')
config.bind(';Dv', 'hint links spawn ' + ' '.join(term_cmd + ['-e', 'yt-dlp', '{hint-url}']))

# 用 mpv 播放当前页面 URL（最高画质）
config.bind(';vm', 'spawn --detach mpv --ytdl-format=bestvideo+bestaudio/best {url}')

# 快速搜索选中文本（多种引擎）
#config.bind('sg', 'cmd-set-text /')
#config.bind('sG', 'cmd-set-text ?')
#config.bind('ss', 'cmd-set-text -s :search')
#config.bind('sd', 'cmd-set-text :open -t duckduckgo.com/?q={}')
#config.bind('sw', 'cmd-set-text :open -t en.wikipedia.org/wiki/{}')

# 快速切换代理（需要先配置代理）
config.bind(';p1', 'set content.proxy http://localhost:7890')
config.bind(';p0', 'set content.proxy system')

# 暗色模式切换
config.bind(';Cc', 'config-cycle colors.webpage.darkmode.enabled true false')

# --- 缩放控制（z 前缀 = Zoom）---
config.bind('zi', 'zoom-in')                              # 放大
config.bind('zo', 'zoom-out')                              # 缩小
config.bind('zz', 'zoom {}'.format(c.zoom.default))        # 重置为默认缩放（巧妙：动态读取配置值）
config.bind('zf', 'config-cycle fonts.web.size.minimum 0 18')  # 切换最小字体：0（无限制）↔️ 18px（强制大字体，应对小字网页）

# --- Canvas 开关 ---
# Cloudflare 等网站需要 canvas，但平时关着防指纹追踪
# 这个写法很聪明：切换 + 显示当前值（末尾的 ? 会在状态栏显示切换后的状态）
config.bind(
        'zc',
        'config-cycle content.canvas_reading true false ;; \
         set content.canvas_reading?'
)

# 快速保存页面（截图/PDF/HTML）
config.bind(';ps', 'print')
config.bind(';pp', 'print --pdf')
config.bind(';ph', 'download --dest ~/Downloads/html/ --path %s.html')

# RSS 订阅检测
config.bind(';rss', 'hint feeds')

# 快速计算器（选中数学表达式后使用）
config.bind(';calc', 'spawn --userscript qute-calc')

# 密码管理：KeePassXC 集成
# 需要安装 keepassxc + python-pynacl；多账号选择使用本地 fuzzel 版本脚本。
config.bind('pw', 'spawn --userscript qute-keepassxc-fuzzel --insecure', mode='normal')
config.bind('<Alt-Shift-u>', 'spawn --userscript qute-keepassxc-fuzzel --insecure', mode='insert')
config.bind('pt', 'spawn --userscript qute-keepassxc-fuzzel --insecure --totp', mode='normal')
config.bind('<Alt-Shift-t>', 'spawn --userscript qute-keepassxc-fuzzel --insecure --totp', mode='insert')

# 命令行补全中用 Ctrl-P/N 浏览历史（和 shell/vim 习惯一致）
config.bind('<Ctrl-p>', 'completion-item-focus --history prev', mode='command')  # 上一条历史
config.bind('<Ctrl-n>', 'completion-item-focus --history next', mode='command')  # 下一条历史

# Ctrl-Shift-P 打开隐私窗口（和 Chrome/Firefox 习惯一致）
config.bind('<Ctrl-Shift-p>', 'open -p')

# 当前标签页转为隐私模式打开
config.bind('gp', 'open -p {url}')

# ==================== 用户脚本 ====================

# 创建用户脚本目录（如果不存在）
user_script_dir = os.path.expanduser('~/.config/qutebrowser/userscripts')
os.makedirs(user_script_dir, exist_ok=True)

# 示例：网页翻译脚本（需要安装 translate-shell）
translate_script = os.path.join(user_script_dir, 'translate')
if not os.path.exists(translate_script):
    with open(translate_script, 'w') as f:
        f.write('''#!/bin/bash
# 翻译选中文本
TEXT="$QUTE_SELECTED_TEXT"
LANG="zh"
trans -b "$TEXT" -t $LANG
''')
    os.chmod(translate_script, 0o755)

# ==================== 高级配置 ====================

# 自动补全设置
c.completion.shrink = True
c.completion.height = '30%'
c.completion.scrollbar.width = 12
# 补全类别设置
c.completion.open_categories = [
    'searchengines',
    'quickmarks',
    'bookmarks',
    'history',
    'filesystem',
]

# 提示模式设置
c.keyhint.delay = 0
c.hints.chars = 'asdfghjklqweruiop'
c.hints.mode = 'letter'
c.hints.auto_follow = 'always'
c.hints.auto_follow_timeout = 0

# 密码管理（需要 compatible 密码管理器）
c.auto_save.session = True
c.session.lazy_restore = True

# 鼠标行为 - 使用布尔值而不是元组
c.input.mouse.back_forward_buttons = True

# ==================== 环境特定配置 ====================
# Wayland 支持 + AMD VA-API 硬件加速
# 启动闪退时先不要传 Chromium/Qt 参数；确认稳定后再逐项加回。
# if os.environ.get('WAYLAND_DISPLAY'):
#     c.qt.args = [
#         'enable-features=WebRTCPipeWireCapturer,VaapiVideoDecoder',
#         'use-gl=egl',
#         'enable-gpu-rasterization',
#         'enable-zero-copy',
#     ]

# 解决视频黑屏闪烁问题 (QtWebEngine 6.11 + AMD GPU bug)
# 如需启用硬件加速看视频，可等待 v3.6.4 更新
#c.qt.args += ['--disable-gpu']
