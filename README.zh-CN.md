# 手机课件自动化（中文）

用 Linux 电脑通过 ADB 操作安卓学习类 App（超星学习通 / U校园 Unipus）：读出手机上
正在显示什么，判断答案，再把点击和输入做回去。

[English README](./README.md)

## 为什么有这个项目

U校园繁杂的刷课致使我在去年就在寻找一个开源项目，但至今没有找到稳定、成熟且开箱即用的方案。我曾尝试用 Agent 去修改和适配现有的开源项目，过程非常麻烦；而且市面上许多方案都是配合 AI 大模型（LLM）来做题，在没有现成题库答案的情况下，大模型的错误率很高。

由此我想：与其在接口层面修修补补，为什么不直接让 AI / 程序控制电脑答题？再结合我前段时间在折腾 AI Agent 通过 ADB 控制手机，并且特意买了刷了原生系统且已 Root 的备用机——那为什么不能直接让程序/AI 接管手机，通过读取屏幕并点击屏幕来答题呢？于是便有了这个项目。

这里面的每一条结论都是 2026-10-09 在两台真机上量出来的，不是推测。

## 都有什么

| 文件 | 干什么用 |
|---|---|
| `ua.py` | 主力工具：截屏、OCR、点击、滑动、输入、以及"现在哪个选项被选中了" |
| `probe.py` | 导出当前界面的控件树，用来判断这一页到底读不读得到文字 |
| `validate_ocr.py` | 已知答案校验：先证明 OCR 认得对，再相信它给的坐标 |
| `dump_doc.py` | 把一部长文档逐屏滚着抓成一个本地文本文件 |
| `fill_blanks.py` | 按像素找出填空的下划线，把答案写进去 |
| `cdp.py` `drive.py` `cdp_probe.py` | 另一条路线：通过 Chrome DevTools 协议直接读网页 DOM（需要 root） |

## 安装

```bash
python3 -m venv .venv                      # 独立环境，别污染系统 Python
./.venv/bin/python -m pip install -r requirements.txt
```

`rapidocr-onnxruntime` 自带 OCR 模型文件，识别过程不联网、不下载。
`opencv-python-headless` 是故意选的——本工具从不弹窗显示图像，能省 150MB。

如果你的 `adb` 不在 PATH 里，用环境变量指定：

```bash
ADB=~/platform-tools/adb ./.venv/bin/python ua.py look
```

## 用法

```bash
./.venv/bin/python ua.py look              # 列出屏幕上所有文字块及其设备坐标
./.venv/bin/python ua.py shot page         # 截屏存文件 + 打印文字块，一趟搞定
./.venv/bin/python ua.py state             # 现在哪个选项被填成了实心蓝
./.venv/bin/python ua.py tap "答题"         # 按文字找到并点击
./.venv/bin/python ua.py tapxy 720 1500    # 直接按坐标点
./.venv/bin/python ua.py swipe up          # 向上滑
./.venv/bin/python ua.py type "some text"  # 按设备 shell 的规则安全输入
./.venv/bin/python ua.py back              # 手机返回键
```

## 实测耗时（这部分最有用）

| 操作 | 耗时 |
|---|---|
| `adb exec-out screencap -p`（1440x3136 PNG） | 918 毫秒 |
| `uiautomator2 d.screenshot()` | **230 毫秒** |
| RapidOCR 识别整屏 1440x3136 | **1921 毫秒** |
| RapidOCR 识别裁出来的局部条带 / 半分辨率整屏 | 1357 / 1390 毫秒 |
| `adb shell input tap` | 32 毫秒 |
| CDP 执行一次 JS 求值 | 约 50 毫秒 |

**瓶颈是 OCR，不是截图。** 裁屏只省三成，所以正确的优化方向不是"把识别做快",
而是"少识别几次"：一屏只截一次、只 OCR 一次，把这一页所有要做的动作全部规划出来
一次做完，最后再截一次核对。一个 10 空的页面就从"识别 10 次约 28 秒"变成 2 次。

## 花掉真实时间才踩到的坑

**网页内容不在控件树里——但要按 Activity 区分，不能按 App 区分。** U校园 的教材目录页
（`EmbeddedWebViewActivity`）文字在 uiautomator 里全都能读到，而做题页
（`CustomWebViewActivity`）里的 `android.webkit.WebView` 是一个空叶子节点。
只看过一页就下的结论不成立，每一类页面都要单独验。

**没有 root 就没有 DOM 这条路。** 原厂系统上两个 App 都不暴露
`webview_devtools_remote` 端口，只能截屏 + OCR。而在 LineageOS 上 `adb root` 能用的
那台机器，同一个 App **确实**开着调试端口，H5 还由 App 内置的本地服务器
（`http://127.0.0.1:8290/...`）提供，于是 `cdp.py` 可行。这条路上有两个坑：调试端口只在
App 处于前台且页面已加载时应答；空的 `never_attached` target 连不上页面级 WebSocket，
必须走 browser 端点 + `Target.attachToTarget(flatten: true)`，并且要挑**真正有文字**的那个
target（列表第一个往往是已经被替换掉的旧页面）。

**OCR 只能用来拿坐标，绝不能用来做判断。** 它会把 `%o` 读成 `%0`，会丢引号和反斜杠，
纯数字选项经常整块识别不出来。任何决定答案的东西必须自己看图。特别强调一条：
**不要靠"哪个选项没被识别出来"反推答案**——今天就是这么做错了一道题。

**填空的可点击位置不是那个编号。** 真正能输入的是 `(N)` 编号右下方的那条下划线，
而且下划线在折行之末，所以按整行文字的中心去偏移，会落在一个普通单词上，
输入静默丢失、什么提示都没有。`fill_blanks.py` 改成在像素层面找那条灰色长横线。

**`adb shell input text` 的引号规则。** 整段字符串要用单引号包起来传给设备 shell
（这样空格才能用；`%s` 是它唯一认识的转义，`%2C`、`%20` 会被原样打出来）。
不加引号的 `(` `)` 会直接报 `syntax error: unexpected '('`。撇号要写成 `'\''`。

**绝对不要用 ESC 键去收键盘。** 有些课件把 ESC 绑成"退出本次作答"，会弹
"退出后本次作答记录不保存"，前面填的全部作废。

**宽表格会超出视口。** 手机上三列表格比屏幕宽，输入框会被裁到屏幕外面。做法是：
先回到最左边，填能看见的一半，做一次确定量的横向滑动，再填另一半。
不要临场猜横向偏移。

**选项顺序每次进入都会重排**，所以一律按文字内容定位，不要复用上一轮的坐标。

## 平台行为

学习通点重做时会**带出上一次的答案**（所以只需要改错的那一题），并且
**最终成绩取最高一次**，所以重做没有掉分风险。提交前必须所有空都填完，
否则提示"请全部作答完成后再提交"。

## 关于答案文件

仓库里**不含**任何答案文本。答案来自第三方教材/教辅资料，不适合公开分发。
自己准备一个 `answers.json`（已在 `.gitignore` 里），格式见 `answers.example.json`。

## 许可

MIT
