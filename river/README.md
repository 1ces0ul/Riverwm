# Arch Linux 下使用 river-classic 的完整配置教程

更新时间：2026-06-09

这份教程整理的是当前这套 `~/.config/river` 配置从最初检查到现在逐步修过的内容。对象是 `river-classic`，不是新版 `river`。两者命令和行为高度相似，但本文只按 `river-classic` 当前配置和源码能力来解释，不假设新版 `river` 的新接口一定存在。

当前目标：

- 使用 LuaJIT 写 `init`，由 river 启动时执行。
- 保留 8 个常用 tag，tag 9 专门作为 scratchpad。
- Fcitx5 在 Wayland 下稳定工作，首次打开 terminal 也能切换输入法。
- Fcitx5 候选框尽量不再出现 CJK 扩展区汉字的豆腐块。
- 多显示器自动布局，不单独拆一个脚本，全部由 `init` 控制。
- 重新整理 river 选项、窗口规则、键位、输入设备、通知和排错方法。

## 1. 推荐软件组成

核心组件：

```bash
sudo pacman -S --needed luajit wlr-randr wlopm swayidle waybar mako fuzzel wl-clipboard cliphist grim slurp playerctl brightnessctl
```

输入法相关：

```bash
sudo pacman -S --needed fcitx5 fcitx5-configtool fcitx5-rime fcitx5-qt fcitx5-gtk
```

常用字体：

```bash
sudo pacman -S --needed noto-fonts noto-fonts-cjk noto-fonts-emoji
```

`river-classic` 本体要按你的软件源或自编译方式安装。注意 Arch 官方仓库里的 `river` 不一定等于 `river-classic`。本文参考的源码仓库是：

```text
https://codeberg.org/river/river-classic
```

当前配置还用到了这些程序：

- `ghostty`：默认 terminal。
- `qutebrowser`：浏览器快捷键目标。
- `yazi`：文件管理器。
- `waylock`：锁屏。
- `awww`：壁纸服务。
- `rivertile`：布局生成器。
- `mako`：通知。
- `wlr-randr`：输出设备布局。
- `wlopm`：显示器电源控制。
- `swayidle`：空闲时关闭显示器。

## 2. 启动入口：river-wrapper

当前 `river-wrapper` 的职责不是复杂启动器，而是把 session 环境整理干净：

```bash
#!/bin/bash
export XDG_CURRENT_DESKTOP=river

for f in ~/.config/environment.d/*.conf; do
  [ -f "$f" ] && set -a && source "$f" && set +a
done

unset GTK_IM_MODULE
unset WAYLAND_DISPLAY

exec river "$@"
```

关键点：

- `XDG_CURRENT_DESKTOP=river` 让桌面环境识别当前 session。
- 加载 `~/.config/environment.d/*.conf`，这样 Fcitx5 的环境变量会进入 river 进程。
- `unset GTK_IM_MODULE` 是这次 Fcitx5 修复的重点。Wayland GTK 程序应优先走 text-input-v3，不应被全局 `GTK_IM_MODULE=fcitx` 强行切到老路径。
- `unset WAYLAND_DISPLAY` 避免旧 socket 残留，特别是重启 river 或 display manager 复用环境时。

如果你用 display manager，启动项应执行这个 wrapper，而不是直接执行 `river`。

### 2.1 环境变量继承模型

这个 wrapper 不是形式问题，而是由 Unix 环境变量模型决定的。

基本原则：

- 单向继承：环境变量只能从父进程传递给子进程，不能反向传播。
- 执行时确定：环境变量在进程创建时确定；正常情况下，一个运行中的进程环境不会被后续 shell 命令反向修改。
- 进程隔离：一个进程不能通过普通 `export` 修改另一个已经运行的进程环境。

流程可以理解为：

```text
TTY shell / display manager
  ↓ 继承环境
river / river-classic 主进程
  ↓ 继承环境
子进程：terminal、launcher、browser、fcitx5 等应用
```

所以 `XDG_CURRENT_DESKTOP=river`、Fcitx5 变量、Qt/SDL/GLFW 输入法变量，最可靠的设置点是在启动 river 之前。只要 river 主进程一开始拿到了这些变量，后续 `riverctl spawn` 出来的应用就能继承。

### 2.2 为什么在 init 里 export 无效

常见错误写法：

```lua
os.execute("export XDG_CURRENT_DESKTOP=river")
```

它无效的原因：

- `os.execute()` 会创建一个子 shell 执行命令。
- `export` 只在这个子 shell 里生效。
- 子 shell 退出后，它的环境变量随进程消失。
- 它无法修改父进程，也就是正在运行的 river 会话。

把 `export` 放进 autostart 也一样无效：

```lua
local autostarts = {
  { "export XDG_CURRENT_DESKTOP=river" },
  { "systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP" },
  { "dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP=river" },
}

local function run_autostarts(autostart_commands)
  for _, cmdline in ipairs(autostart_commands) do
    exec(fmt([[riverctl spawn '%s']], cmd(cmdline)))
  end
end
```

这里的问题是：`riverctl spawn` 也是让 river 启动一个子进程执行命令。即使这个子进程里执行了 `export`，也只影响这个子进程自己，不会影响 river 主进程，也不会影响之后别的 `riverctl spawn`。

`systemctl --user import-environment` 和 `dbus-update-activation-environment` 仍然有用，但它们解决的是 systemd user manager 和 D-Bus 激活服务的环境，不会反向修改 river 主进程环境。因此它们应该作为补充，而不是替代 wrapper。

### 2.3 wrapper 里 exec 的作用

wrapper 末尾使用：

```bash
exec river "$@"
```

逐项解释：

- `exec`：用新程序替换当前 shell 进程。执行后 wrapper 的 shell 进程消失，进程镜像变成 `river`。
- `river`：要启动的窗口管理器程序。这里指当前系统安装的 river-classic 可执行文件。
- `"$@"`：把 wrapper 收到的所有参数原样传给 `river`，并保留每个参数的边界，避免空格或特殊字符被错误拆分。

不用 `exec` 时，`river` 会作为 wrapper shell 的子进程运行，环境变量仍然会继承，所以多数情况下也能工作。但 `exec` 更干净：少一个常驻 shell 父进程，退出和信号传递也更直接。

### 2.4 手动启动方式

如果从 TTY 手动启动，可以直接运行：

```bash
~/.config/river/river-wrapper
```

确保 wrapper 可执行：

```bash
chmod +x ~/.config/river/river-wrapper
```

也可以给交互式 shell 加一个别名：

```bash
echo "alias rw='~/.config/river/river-wrapper'" >> ~/.bashrc
```

之后在 bash 里运行：

```bash
rw
```

这个别名只适合 TTY 或手动 shell 启动。display manager 不会读取你的交互式 `.bashrc`，所以 display manager 的 session 文件仍然要直接指向 `~/.config/river/river-wrapper`，不要只依赖 `rw`。

## 3. Fcitx5 的 Wayland 环境变量

当前 `~/.config/environment.d/fcitx5.conf` 是：

```ini
XMODIFIERS=@im=fcitx
QT_IM_MODULE=fcitx
QT_IM_MODULES=wayland;fcitx;ibus
SDL_IM_MODULE=fcitx
GLFW_IM_MODULE=ibus
```

不设置全局 `GTK_IM_MODULE`。

原因：

- GTK Wayland 程序现在应使用 compositor 的 Wayland 输入法协议。
- `GTK_IM_MODULE=fcitx` 更适合 X11 或 XWayland 兼容路径。
- Qt5 仍需要 `QT_IM_MODULE=fcitx`。
- Qt6 可以使用 `QT_IM_MODULES=wayland;fcitx;ibus` 这样的优先级列表。
- SDL 和 GLFW 有各自的输入法环境变量。

当前 `init` 里还有一层 spawn 包装：

```lua
local input_method_env_args =
  "XMODIFIERS=@im=fcitx QT_IM_MODULE=fcitx QT_IM_MODULES='wayland;fcitx;ibus' SDL_IM_MODULE=fcitx GLFW_IM_MODULE=ibus"
local input_method_spawn_env = "env -u GTK_IM_MODULE " .. input_method_env_args

local function with_input_method_env(command)
  return input_method_spawn_env .. " " .. command
end
```

然后 terminal、fuzzel、qutebrowser、fcitx5 都通过 `with_input_method_env(...)` 启动。

## 4. “首次打开 terminal 不能切输入法”的根因

之前的问题是：刚进入 river 后第一次打开 terminal 不能切换输入法，再打开第二个 terminal 又可以。

根因不是 terminal 自身，而是环境变量传播路径：

- `systemctl --user import-environment` 和 `dbus-update-activation-environment` 可以更新 systemd/dbus 激活服务的环境。
- 但它们不会反向修改已经运行的 `river` 进程环境。
- `riverctl spawn` 启动的程序继承的是 `river` 进程当前环境。
- 所以如果 river 启动时没有拿到 Fcitx5 变量，第一次由 river spawn 出来的 terminal 也拿不到。
- 第二个 terminal 有时能用，是因为 Fcitx5、dbus 或应用自身状态已经初始化完成，看起来像“第二次正常”，但根因仍是启动环境不一致。

现在的修复是两层：

- `river-wrapper` 在启动 river 前加载 `environment.d`。
- `init` 对关键应用显式加 `env -u GTK_IM_MODULE ...`。

验证方法：

```bash
env | rg 'XMODIFIERS|QT_IM|GTK_IM|SDL_IM|GLFW_IM'
```

在 river 里打开 terminal 后也执行同样命令。应看到 Fcitx5 相关变量，但不应看到全局 `GTK_IM_MODULE=fcitx`。

## 5. GTK 配置如何保留

当前仍保留 GTK 配置文件：

```ini
# ~/.config/gtk-3.0/settings.ini
[Settings]
gtk-im-module=fcitx
gtk-dialogs-use-header=false
```

```ini
# ~/.config/gtk-4.0/settings.ini
[Settings]
gtk-im-module=fcitx
```

这和 `unset GTK_IM_MODULE` 不冲突。

理解方式：

- 环境变量 `GTK_IM_MODULE` 是全局强制，影响更大。
- GTK settings 文件是 GTK 自己的配置，主要兼容 X11/XWayland 路径。
- 在 Wayland 下不要用全局环境变量强制 GTK 走 fcitx 模块，让它优先走 Wayland text-input。

## 6. Fcitx5 候选框豆腐块和 CJK 扩展字体

你遇到的豆腐块不是所有中文都显示不了，而是候选框里某些生僻字显示不了，例如：

```text
𡀗 𠇳 𠩔 𠀍
```

这些属于 CJK 扩展区字符。普通 `Noto Sans CJK` 或 `Source Han` 不保证覆盖全部扩展区汉字，所以必须加更大的 fallback 字体。

当前采取的字体栈：

- `Noto Sans CJK SC`：常用简体中文主字体。
- `BabelStone Han`：补充大量 CJK 扩展字。
- `Jigmo`、`Jigmo2`、`Jigmo3`：继续补 CJK 扩展区。
- `Noto Color Emoji`：表情 fallback。

当前用户字体安装位置：

```text
~/.local/share/fonts/BabelStoneHan.ttf
~/.local/share/fonts/Jigmo.ttf
~/.local/share/fonts/Jigmo2.ttf
~/.local/share/fonts/Jigmo3.ttf
```

刷新字体缓存：

```bash
fc-cache -f ~/.local/share/fonts
```

如果你的软件源里有对应包，可以用包管理安装。不同 Arch 源可用性不同，可能需要 AUR 或 archlinuxcn：

```bash
sudo pacman -S --needed ttf-jigmo ttf-babelstone-han
```

如果包不存在，就手动下载字体放到 `~/.local/share/fonts/`，再执行 `fc-cache`。

## 7. Fcitx5 专用字体别名

当前 fontconfig 文件是：

```xml
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <alias>
    <family>Fcitx CJK</family>
    <prefer>
      <family>Noto Sans CJK SC</family>
      <family>BabelStone Han</family>
      <family>Jigmo</family>
      <family>Jigmo2</family>
      <family>Jigmo3</family>
      <family>Noto Color Emoji</family>
    </prefer>
  </alias>

  <alias>
    <family>sans-serif</family>
    <accept>
      <family>BabelStone Han</family>
      <family>Jigmo</family>
      <family>Jigmo2</family>
      <family>Jigmo3</family>
    </accept>
  </alias>

  <alias>
    <family>serif</family>
    <accept>
      <family>BabelStone Han</family>
      <family>Jigmo</family>
      <family>Jigmo2</family>
      <family>Jigmo3</family>
    </accept>
  </alias>

  <alias>
    <family>monospace</family>
    <accept>
      <family>BabelStone Han</family>
      <family>Jigmo</family>
      <family>Jigmo2</family>
      <family>Jigmo3</family>
    </accept>
  </alias>
</fontconfig>
```

路径：

```text
~/.config/fontconfig/conf.d/99-fcitx-cjk-fallback.conf
```

这里专门创建了一个 `Fcitx CJK` 字体族。好处是：

- Fcitx5 候选框可以指定这个字体。
- 不需要把所有应用的默认字体都强行改成 Jigmo。
- 常用字优先走 Noto Sans CJK，生僻字才 fallback 到 BabelStone/Jigmo。

当前 Fcitx5 classic UI 配置：

```ini
Font="Fcitx CJK 16"
MenuFont="Fcitx CJK 16"
TrayFont="Fcitx CJK 16"
```

路径：

```text
~/.config/fcitx5/conf/classicui.conf
```

验证某个字能否匹配字体：

```bash
fc-list ':charset=21017' file family
fc-match 'Fcitx CJK:charset=21017'
fc-match 'Fcitx CJK:charset=201f3'
fc-match 'Fcitx CJK:charset=20a54'
```

当前验证结果里，`𡀗`、`𠇳`、`𠩔` 这些字可以被 Jigmo 系列覆盖。

补充：`𡀗` 是 Unicode `U+21017`，属于 `CJK Unified Ideographs Extension B`。它不是常用中文字体通常会完整覆盖的范围，所以显示成豆腐块是字体覆盖问题，不是 Fcitx5 输入本身坏了。

## 8. Fcitx5 候选框位置随机

候选框位置是否跟随光标，取决于应用、toolkit、Fcitx5 和 compositor 之间是否正确传递 cursor rectangle。

排查顺序：

1. 确认没有全局 `GTK_IM_MODULE=fcitx`。
2. 确认 terminal 是通过 `with_input_method_env(terminal)` 启动。
3. 用不同应用对比，例如 GTK 程序、Qt 程序、Ghostty、浏览器。
4. 运行 `fcitx5-diagnose` 看 Wayland frontend 是否正常。
5. 如果只有某个应用位置随机，优先怀疑该应用或 toolkit 没有正确发送光标矩形。

这类问题不是简单装字体能解决的。字体只解决豆腐块，候选框定位依赖 Wayland 输入法协议和应用实现。

## 9. init 的整体结构

当前 `init` 是 LuaJIT 脚本：

```lua
#!/usr/bin/luajit
```

它不只是简单 shell 命令列表，而是分成几个模块：

- 通用 helper：`trim`、`cmd`、`shell_quote`、`popen`、`spawn_once`。
- 变量：terminal、wallpaper、状态栏、输入法环境。
- autostart：环境、服务、视觉、oneshot。
- 多显示器：解析 `wlr-randr` 并自动布局。
- 输入设备：遍历 touchpad 并设置选项。
- river options：边框、焦点、cursor、默认布局、spawn tagmask。
- key mappings：普通模式、locked 模式、用户模式。
- switch mappings：合盖和开盖触发显示器配置。
- tag mappings：8 个普通 tag 加 1 个 scratchpad tag。
- window rules：浮动、装饰、撕裂、指定 tag、指定位置。
- display power management：swayidle 和 wlopm。
- 最后 `execlp("rivertile", ...)` 启动布局生成器。

## 10. 为什么要用 shell_quote

当前 helper：

```lua
local function shell_quote(str)
  return "'" .. tostring(str):gsub("'", "'\\''") .. "'"
end
```

它解决这些问题：

- 输出名可能有特殊字符。
- 命令字符串里可能有空格。
- 文件路径可能有空格或特殊字符。
- `riverctl spawn` 需要把整条命令作为一个参数传给 shell。

典型用法：

```lua
exec(fmt("riverctl spawn %s", shell_quote(command)))
exec("wlr-randr --output " .. shell_quote(internal_output) .. " --toggle")
```

如果不 quote，`DP-4 via HDMI` 这类输出描述或复杂 spawn 命令就容易被 shell 拆坏。

## 11. 什么是有序命令列表

这次把一些配置改成了“有序命令列表”。意思是用 Lua array：

```lua
local touchpad_options = {
  { "events", "disabled-on-external-mouse" },
  { "accel-profile", "adaptive" },
  { "pointer-accel", "0.6" },
  { "click-method", "clickfinger" },
}
```

然后用 `ipairs` 顺序执行。

不要写成这种无序表：

```lua
local touchpad_options = {
  ["events"] = "disabled-on-external-mouse",
  ["accel-profile"] = "adaptive",
}
```

原因：

- `pairs` 遍历顺序不稳定。
- 配置命令有时顺序会影响最终行为。
- Lua table 同一个 key 重复时，后写的值会覆盖前面的值，前面的规则看起来存在，其实不会生效。

窗口规则也因此整理为 action 对应列表，避免重复 key 被覆盖。

## 12. spawn_once 的修复

当前 `spawn_once` 支持显式进程名：

```lua
local function spawn_once(command, process_name)
  local program = process_name or command:match("^%s*([^%s]+)")
  ...
end
```

现在 oneshot 是：

```lua
local oneshot_commands = {
  { command = { with_input_method_env("fcitx5") }, process = "fcitx5" },
  { "wl-paste", "--watch", "cliphist", "store" },
}
```

为什么要加 `process = "fcitx5"`：

- `with_input_method_env("fcitx5")` 生成的命令以 `env` 开头。
- 如果直接从命令首词判断进程名，会去检查 `pgrep env`，这是错的。
- 显式写 `fcitx5` 后，重新加载 init 不会重复启动 Fcitx5。

`wl-paste --watch cliphist store` 也通过 `spawn_once` 避免重复监听剪贴板。

## 13. 多显示器自动布局

你要的行为是：

- 检测到外接屏，就自动挂到合适位置，通常在右边。
- 如果外接屏存在且内屏开启，内屏在左边 `0,0`，外屏依次向右排。
- 如果外接屏存在且你手动关了内屏，外屏放到 `0,0`，焦点到外屏。
- 如果检测不到外接屏，只启用内屏。
- 合盖、开盖都走同一套逻辑。
- 不单独拆脚本，全部写在 `init`。

当前核心变量：

```lua
local internal_output = "eDP-1"
local internal_output_mode = "2256x1504@59.999001Hz"

local output_profile_cmd = RIVERCFG .. "init --apply-output-profile"
local internal_display_toggle_cmd = RIVERCFG .. "init --toggle-internal-output"
```

`parse_outputs()` 读取：

```bash
wlr-randr
```

并记录每个输出：

- `name`
- `enabled`
- `current_mode`
- `preferred_mode`
- `first_mode`

`apply_output_profile()` 的决策：

```text
没有外接屏：
  eDP-1 --on --mode 2256x1504@59.999001Hz --pos 0,0
  riverctl focus-output eDP-1

有外接屏，且 eDP-1 当前 enabled=yes：
  eDP-1 放 0,0
  外接屏按 wlr-randr 输出顺序依次 --right-of 前一个输出

有外接屏，但 eDP-1 当前 enabled=no：
  第一个外接屏放 0,0
  后续外接屏依次 --right-of 前一个外接屏
  riverctl focus-output 第一个外接屏
```

如果接多个外接屏，会按 `wlr-randr` 返回顺序自动向右排开。

手动应用：

```bash
~/.config/river/init --apply-output-profile
```

切换内屏开关并重新布局：

```bash
~/.config/river/init --toggle-internal-output
```

当前键位：

```text
Super+D        切换内屏开关，然后重新应用输出布局
Super+Shift+D  用 wlopm 切换所有显示器电源
```

注意：`Super+D` 和 `Super+Shift+D` 不是一回事。前者改变 eDP-1 的 enabled 状态，后者只是用 `wlopm` 做显示器电源开关。

合盖和开盖：

```lua
local switch_mappings = {
  {
    mode = "normal",
    switch = "lid",
    state = "close",
    command = { "spawn", shell_quote(output_profile_cmd) },
  },
  {
    mode = "normal",
    switch = "lid",
    state = "open",
    command = { "spawn", shell_quote(output_profile_cmd) },
  },
}
```

所以合盖、开盖都只重新计算当前输出状态，不强行猜测你想不想关内屏。

## 14. 当前显示器例子

你提供过的输出是：

```text
DP-4  1920x1080@143.981Hz  enabled yes  position 2256,0
eDP-1 2256x1504@59.999Hz   enabled no
```

在这时外接屏存在，内屏 disabled，所以 profile 会让：

```text
DP-4 -> 0,0
focus-output DP-4
```

如果你再用 `Super+D` 打开内屏，则会变成：

```text
eDP-1 -> 0,0
DP-4  -> right-of eDP-1
```

如果再接第二个外屏，例如 `HDMI-A-1`，会变成：

```text
eDP-1 -> 0,0
DP-4 -> right-of eDP-1
HDMI-A-1 -> right-of DP-4
```

## 15. 8 个 tag 和 scratchpad tag 9

当前设置：

```lua
local tag_count = 8
local normal_tags_mask = bit.lshift(1, tag_count) - 1
local scratch_tags = bit.lshift(1, tag_count)
```

计算结果：

```text
tag 1       1
tag 2       2
tag 3       4
tag 4       8
tag 5       16
tag 6       32
tag 7       64
tag 8       128
normal mask 255
tag 9       256
```

你只需要 8 个普通 tag，所以 `1-8` 是正常工作区。`9` 不再作为普通工作区，而是 scratchpad。

当前 scratchpad 键位：

```text
Super+S          toggle-focused-tags 256
Super+Shift+S    set-view-tags 256
Super+9          set-focused-tags 256
Super+Shift+9    set-view-tags 256
```

区别：

- `Super+Shift+S` 和 `Super+Shift+9` 作用一样，都是把当前窗口送到 scratchpad。
- `Super+S` 是把 scratchpad tag 叠加显示或取消显示在当前输出上。
- `Super+9` 是直接切到 scratchpad tag，只看 tag 9。

如果你把窗口送进 scratchpad 后按数字 `9` 不显示，要确认按的是 `Super+9`，不是单独的 `9`。river 的 tag 操作都是 modifier 快捷键。

为什么要设置：

```lua
{ "spawn-tagmask", normal_tags_mask }
```

因为不希望新窗口默认生成在 scratchpad tag。新窗口只应该出现在 `1-8`，除非手动送去 tag 9。

## 16. 旧的 Super+Control+9 为什么删除

之前 tag 9 曾经可能有普通 tag 的 toggle 绑定：

```text
Super+Control+9
Super+Control+Shift+9
```

现在它们被 unmap：

```lua
exec("riverctl unmap normal Super+Control 9 2>/dev/null")
exec("riverctl unmap normal Super+Control+Shift 9 2>/dev/null")
```

原因：

- tag 9 已经被定义为 scratchpad。
- 保留旧的 tag 9 toggle 逻辑会让 scratchpad 行为和普通工作区混在一起。
- 重新加载 init 时，river 可能还保留旧映射，所以显式 unmap 可以清干净。

旧功能和现在功能的区别：

- 旧 `Super+Control+9`：把 tag 9 作为普通 tag 叠加到当前 tag。
- 现在 `Super+S`：也是叠加 scratchpad，但语义明确。
- 旧 `Super+Control+Shift+9`：把窗口 toggle 到 tag 9，可能保留原 tag。
- 现在 `Super+Shift+9` 或 `Super+Shift+S`：直接 `set-view-tags 256`，窗口只进入 scratchpad。

这就是为什么隐藏到 scratchpad 的窗口不会还留在原来的工作区。

## 17. river 基础选项

当前重要 river options：

```lua
local river_options = {
  { "default-attach-mode", "bottom" },
  { "border-width", 2 },
  { "border-color-focused", "0x939393" },
  { "border-color-unfocused", "0x585858" },
  { "border-color-urgent", "0xDC322F" },
  { "background-color", "0x000000" },
  { "allow-tearing", "disabled" },
  { "focus-follows-cursor", "normal" },
  { "hide-cursor", "when-typing", "enabled" },
  { "hide-cursor", "timeout", 3000 },
  { "set-cursor-warp", "on-output-change" },
  { "set-repeat", 50, 300 },
  { "xcursor-theme", xcursor_theme, xcursor_size },
  { "default-layout", "rivertile" },
  { "spawn-tagmask", normal_tags_mask },
}
```

含义：

- `default-attach-mode bottom`：新窗口插入布局栈底部，减少抢主窗口。
- `allow-tearing disabled`：默认不允许撕裂，只给游戏单独 rule 开。
- `focus-follows-cursor normal`：鼠标移动到窗口时焦点跟随。
- `hide-cursor when-typing enabled`：打字时隐藏光标。
- `set-cursor-warp on-output-change`：切换输出时移动光标到对应输出。
- `set-repeat 50 300`：键盘 repeat 参数。
- `default-layout rivertile`：默认布局交给 rivertile。
- `spawn-tagmask 255`：新窗口默认只能出现在 1-8。

## 18. rivertile 布局

`init` 最后用 `execlp` 启动 rivertile：

```lua
execlp(
  "rivertile",
  "rivertile",
  "-view-padding",
  "3",
  "-outer-padding",
  "3",
  "-main-location",
  "left",
  "-main-count",
  "1",
  "-main-ratio",
  "0.6",
  nil
)
```

它必须作为 init 的最终进程运行。river 的 init 进程退出后，布局生成器也会影响 session 行为，所以这里用 `execlp` 替换当前进程。

当前布局初始值：

```text
窗口间距 3
外边距 3
主区域在左
主窗口数量 1
主区域比例 0.6
```

运行时调节：

```text
Super+H / Super+L              主区域比例 -0.02 / +0.02
Super+Shift+H / Super+Shift+L  主窗口数量 -1 / +1
Ctrl+Alt+H/J/K/L               主区域位置 left/bottom/top/right
```

## 19. 关键快捷键

应用启动：

```text
Super+T          打开 ghostty
Super+E          用 ghostty 打开 yazi
Super+B          打开 qutebrowser
Super+R          打开 fuzzel
Super+Shift+R    重新加载 ~/.config/river/init
Super+Q          关闭当前窗口
Super+Shift+Q    退出 river
Super+Shift+X    锁屏
```

输出和窗口：

```text
Super+J / Super+K              切换到下一个/上一个输出
Super+Shift+J / Super+Shift+K  把当前窗口送到下一个/上一个输出，并保留当前 tag 语义
Super+Alt+N / Super+Alt+P      跳过浮动窗口，聚焦下一个/上一个平铺窗口
Super+Shift+E                  zoom，提升当前窗口到布局主位置
Super+Space                    切换浮动
Super+F                        切换全屏
Super+Tab                      回到上一次 tag 组合
Super+Shift+Tab                把当前窗口送到上一次 tag 组合
```

浮动窗口操作：

```text
Super+Alt+H/J/K/L              移动浮动窗口
Super+Control+H/J/K/L          调整浮动窗口大小
Super+Alt+Control+H/J/K/L      吸附到屏幕边缘
```

截图和剪贴板：

```text
Super+Print       全屏截图
Print             区域截图并复制
Super+A           区域截图并复制
Super+Shift+A     全屏截图
Super+Alt+C       cliphist 选择并复制
Super+Alt+D       cliphist 选择并删除
```

通知：

```text
Super+U           清空 mako 通知
```

## 20. 键盘 layout 绑定

当前 `setup_mappings` 对 normal 模式下非 XF86 键位自动加：

```text
-layout 0
```

原因：

- 多键盘布局时，普通快捷键固定在第 0 个键盘布局上。
- 避免切到中文或其他布局后，river 快捷键匹配异常。
- XF86 多媒体键不加 layout 限制。

用户模式里的 power management 命令也应用同样策略。

## 21. 窗口规则

当前窗口规则大致分为两类：按 app-id 和按 title。

按 app-id：

```lua
["-app-id"] = {
  ["float"] = {
    "popup",
    "float",
  },
  ["ssd"] = {
    "com.mitchellh.ghostty",
  },
  ["csd"] = {
    "firefox",
    "mpv",
  },
  ["tearing"] = {
    "steam",
    "dota2",
    "cs2",
  },
  ["tags"] = {
    { "mpv", workspace(7) },
    { "steam", workspace(8) },
    { "dota2", workspace(8) },
    { "cs2", workspace(8) },
  },
}
```

按 title：

```lua
["-title"] = {
  ["float"] = {
    "Extension*",
    "Picture-in-Picture",
    "About Mozilla*",
    "Library*",
  },
  ["position"] = {
    { "Picture-in-Picture", "0", "0" },
  },
}
```

解释：

- `float`：让弹窗或特殊窗口默认浮动。
- `ssd`：使用 server side decoration。
- `csd`：使用 client side decoration。
- `tearing`：只给游戏允许撕裂。
- `tags`：让某些应用自动去指定 tag。
- `position`：让画中画固定到左上角。

添加新规则的方法：

1. 先查窗口的 app-id/title。
2. 判断应该按 app-id 还是 title 匹配。
3. 如果是无参数动作，加入 `float`、`csd`、`ssd`、`tearing` 这类列表。
4. 如果是带参数动作，加入 `{ pattern, arg1, arg2 }` 这种列表。

查窗口信息可以用：

```bash
riverctl list-views
```

如果命令不可用，就临时看应用日志或用 Wayland 调试工具确认 app-id。

## 22. 输入设备和触摸板

当前触摸板配置是按 `riverctl list-inputs` 自动找名称包含 `touchpad` 的设备：

```lua
local touchpad_options = {
  { "events", "disabled-on-external-mouse" },
  { "accel-profile", "adaptive" },
  { "pointer-accel", "0.6" },
  { "click-method", "clickfinger" },
  { "drag", "enabled" },
  { "disable-while-typing", "enabled" },
  { "middle-emulation", "enabled" },
  { "natural-scroll", "enabled" },
  { "tap", "enabled" },
  { "tap-button-map", "left-right-middle" },
  { "scroll-method", "two-finger" },
  { "scroll-factor", "1.0" },
}
```

重要修复：

- 设备名用 `shell_quote(device)`，避免空格或特殊字符导致命令失败。
- 选项用 ordered list，避免顺序不稳定。
- `scroll-factor 1.0` 显式写出，便于后续微调。

查看输入设备：

```bash
riverctl list-inputs
```

手动测试某个选项：

```bash
riverctl input '设备名' scroll-factor 1.2
```

## 23. 壁纸和 autostart

当前壁纸目录：

```text
~/.config/river/wallpapers/
```

`init` 用 Lua 随机找文件：

```lua
local function random_wallpaper(dir)
  local handle = io.popen(fmt("find %s -type f", shell_quote(dir)))
  ...
end
```

如果目录里没有文件，就不插入 `awww img` 命令。这样不会因为空 wallpaper 变量导致启动报错。

autostart 分为三层：

- `environment_autostarts`：systemd/dbus 环境同步。
- `service_autostarts`：例如 `awww.service`。
- `visual_autostarts`：例如随机壁纸。
- `oneshot_commands`：例如 `fcitx5` 和 `wl-paste --watch cliphist store`。

这种拆法比一串 shell 命令更容易控制重复启动和顺序。

## 24. 显示器电源管理

当前 idle 逻辑：

```lua
local swayidle_cmd = [[swayidle -w timeout 300 'wlopm --off "*"' resume 'wlopm --on "*"']]
```

含义：

- 空闲 300 秒后关闭所有输出电源。
- 恢复时打开所有输出电源。
- pid 写到 `/tmp/river-swayidle.pid`。
- 重新加载 init 时会杀掉旧 swayidle，避免重复运行。

手动切换所有显示器电源：

```text
Super+Shift+D
```

## 25. 常见排错

重新加载 init：

```bash
~/.config/river/init
```

检查 Lua 语法：

```bash
luajit -b ~/.config/river/init /tmp/river-init-check.ljbc
```

检查 wrapper：

```bash
bash -n ~/.config/river/river-wrapper
```

检查输出状态：

```bash
wlr-randr
```

手动应用输出 profile：

```bash
~/.config/river/init --apply-output-profile
```

检查 Fcitx5 环境变量：

```bash
env | rg 'XMODIFIERS|QT_IM|GTK_IM|SDL_IM|GLFW_IM'
```

检查 Fcitx5 诊断：

```bash
fcitx5-diagnose
```

检查某个生僻字是否有字体覆盖：

```bash
fc-list ':charset=21017' file family
fc-match 'Fcitx CJK:charset=21017'
```

重新加载字体缓存：

```bash
fc-cache -f ~/.local/share/fonts
```

重启 Fcitx5：

```bash
pkill -x fcitx5
fcitx5 &
```

## 26. 当前配置验证清单

已经做过或建议每次大改后做：

- `luajit -b init /tmp/river-init-check.ljbc` 通过。
- `bash -n river-wrapper` 通过。
- `wlr-randr` 能列出当前内屏和外屏。
- `~/.config/river/init --apply-output-profile` 能按当前输出状态重新布局。
- `Super+D` 能切换内屏并重新布局。
- 合盖和开盖触发 output profile。
- `Super+Shift+9` 和 `Super+Shift+S` 都能把窗口送去 scratchpad。
- `Super+9` 能直接进入 scratchpad。
- `Super+S` 能叠加或隐藏 scratchpad。
- 新窗口不会默认出现在 scratchpad。
- 第一次打开 `Super+T` 的 terminal 就能切 Fcitx5。
- `env` 中没有全局 `GTK_IM_MODULE=fcitx`。
- Fcitx5 候选框用 `Fcitx CJK 16`。
- `𡀗`、`𠇳`、`𠩔` 能被 `fc-match` 匹配到 Jigmo 系列字体。

## 27. 后续还可以继续优化的方向

窗口规则：

- 给更多应用分配固定 tag。
- 给设置窗口、文件选择器、浏览器弹窗增加 title 规则。
- 根据游戏实际 app-id 补充 tearing 规则。

多显示器：

- 如果未来常用上下摆放，可以给某些输出名加固定规则。
- 如果某个外屏需要缩放，可以在 `output_args` 里按 output name 设置 scale。
- 如果外屏顺序和你桌面物理顺序不一致，可以给外接屏维护一个优先级列表。

Fcitx5：

- 如果候选框位置仍只在某个应用随机，单独排查该应用的 Wayland 输入法实现。
- 如果某些更罕见字符仍是豆腐块，继续用 `fc-list ':charset=xxxx'` 找覆盖字体。
- 可以给 Fcitx5 单独做 theme，保证 candidate、menu、tray 使用同一字体。

按键：

- 可以把显示器 profile、scratchpad、layout 调节做成更清晰的 help 文档。
- 如果键位冲突，优先保留核心操作：terminal、launcher、tag、scratchpad、output、close、layout。

## 28. 参考资料

- river-classic 源码仓库：https://codeberg.org/river/river-classic
- Fcitx5 Wayland 文档：https://fcitx-im.org/wiki/Using_Fcitx_5_on_Wayland
- Fcitx5 设置文档：https://fcitx-im.org/wiki/Special:MyLanguage/Setup_Fcitx_5
- Fcitx5 主题和 UI 字体：https://fcitx-im.org/wiki/Theme_Customization
- BabelStone Han：https://www.babelstone.co.uk/Fonts/Han.html
- Jigmo 字体包说明：https://packages.guix.gnu.org/packages/font-jigmo/
- Unicode `𡀗` / U+21017：https://codepoints.net/U+21017
- 本地手册：`man riverctl`、`man rivertile`、`man wlr-randr`
