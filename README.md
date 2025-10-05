## 图片拍摄日期水印命令行工具

批量读取图片 EXIF 拍摄时间（取年月日），将日期作为文本水印绘制到图片，输出到原目录的子目录 `<原目录名>_watermark`。

### 功能特性
- **EXIF 日期解析**：按 `DateTimeOriginal → CreateDate → DateTime` 优先级读取；支持无 EXIF 时按需回退到文件修改时间。
- **水印类型（GUI）**：
  - 日期水印：将拍摄日期（YYYY-MM-DD）加到图片。
  - 文本水印：自定义任意文本，支持颜色、透明度、描边、阴影、字体文件。
  - 图片水印：选择本地图片（支持 PNG 透明通道），支持缩放比例与透明度。
- **水印样式**：可配置字体大小、颜色（含透明度）、位置（九宫格锚点）与边距，支持指定字体文件；可选描边/阴影提升可读性。
- **批量处理**：支持处理单文件或整个目录（可递归），按扩展名过滤。
- **输出规则**：保持源目录层级结构，输出到 `<原目录名>_watermark` 子目录；可选择添加文件名后缀或覆盖已有文件。
- **保留 JPEG EXIF**：保存 JPEG 时尽力保留原 EXIF 信息。

### 环境与安装
PowerShell（Windows）：
```powershell
cd "C:\Users\Lenovo\Desktop\作业\software_homework"
python -m venv .venv
\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

如果在命令行直接运行模块需要能找到 `src`，建议临时设置 `PYTHONPATH`：
```powershell
$env:PYTHONPATH="src;$env:PYTHONPATH"
```

Git Bash（可选）：
```bash
cd "/c/Users/Lenovo/Desktop/作业/software_homework"
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
export PYTHONPATH=src:$PYTHONPATH
```

### 快速开始
- 干跑（仅列出将处理的文件与解析到的日期，不写文件）：
```powershell
python -m photodate_wm --path "D:\Photos" --dry-run --recursive
```

- 实际写入水印（默认右下角、白色、字号 32）：
```powershell
python -m photodate_wm --path "D:\Photos" --recursive
```

### 启动图形界面（GUI）
```powershell
python -m photodate_wm --gui
```

GUI 功能点：
- 导入图片：
  - “添加图片”支持多选；“添加文件夹”导入整个目录（含子文件夹）。
  - 支持拖拽到列表（已安装 tkinterdnd2 时可用）。
- 列表展示：文件名与缩略图。
- 输出设置：选择输出文件夹（默认禁止与源文件夹相同，避免覆盖原图）。
- 命名规则：可设置前缀、后缀（如 `wm_` 或 `_watermarked`）。
- 输出格式：可选 JPEG 或 PNG（PNG 支持透明通道）。
- 高级选项：
  - JPEG 质量：0-100（越高越清晰、体积越大）。
  - 调整尺寸：按宽度、按高度或按百分比缩放。
- 水印样式：位置（九宫格锚点）、字号、颜色/透明度、边距、字体路径。
- EXIF 策略：仅含 EXIF 日期时才处理、或无 EXIF 回退到文件修改时间。

### 新增：水印类型与高级样式
- 水印类型：`date`（日期）、`text`（自定义文本）、`image`（图片水印）。
  - 文本水印：支持颜色、透明度、描边（宽度/颜色）、阴影（偏移/颜色/透明度）、字体文件、字号、位置、边距。
  - 图片水印：选择本地图片（建议 PNG 透明背景），支持缩放比例（相对原图宽度的百分比）与透明度、位置、边距。
- 实时预览：上方“预览”画布实时显示效果；选择图片列表项可切换预览对象。
- 手动拖拽：在预览图按住左键拖拽，可把水印移动到任意位置；也可用“手动X,Y”微调。
- 旋转：`0-359°` 旋转滑块，文本/图片水印均支持。
- 滚动参数面板：全屏时不会溢出，滚动查看更多选项。
- 进度与取消：导出时显示进度条，可随时取消。

### 新增：模板/配置管理
- 保存模板：点击“保存模板”把当前所有设置保存为 JSON（路径：`%USERPROFILE%\.photodate_wm\<name>.json`）。
- 加载模板：点击“加载模板”选择 JSON 应用。
- 删除模板：点击“删除模板”移除 JSON。
- 自动加载：程序启动自动读取并应用 `%USERPROFILE%\.photodate_wm\last.json`；退出时自动保存当前设置到该文件。

#### GUI 的“水印类型”
- 在“参数”面板选择“水印类型”：`date / text / image`
  - `date`：基于 EXIF/修改时间生成 `YYYY-MM-DD` 文本；其它样式跟随“水印样式”设置。
  - `text`：在“自定义文本”中输入内容，可设置颜色、透明度、描边（宽度与颜色）、阴影（偏移、颜色、透明度）、字体文件、字号、位置、边距。
  - `image`：点击“选择图片”指定水印图片（建议 PNG 透明背景），设置“图片水印比例(%)”与透明度，水印将按位置与边距贴到图片上。

### 常用参数
- `--path <string>`：文件或目录路径（必填）。
- `--recursive`：目录递归处理。
- `--include-ext <csv>`：扩展名过滤，默认 `.jpg,.jpeg,.png,.tif,.tiff,.heic,.heif`。
- `--exif-only`：仅处理含拍摄时间 EXIF 的图片；无则跳过。
- `--fallback-mtime/--no-fallback-mtime`：无 EXIF 是否回退到文件修改时间（默认回退）。
- 样式相关：
  - `--font-size <int>`：字体大小（px），默认 32。
  - `--color <string>`：颜色，支持 `#RRGGBB/#RRGGBBAA` 或色名，默认 `#FFFFFF`。
  - `--opacity <0-1>`：透明度，默认 1.0（当颜色已含 alpha 时忽略）。
  - `--position <enum>`：位置锚点，`tl, tc, tr, cl, cc, cr, bl, bc, br`，默认 `br`。
  - `--margin-x <int>` / `--margin-y <int>`：边距（px），默认 24 / 24。
  - `--font-path <string>`：字体文件路径（ttf/otf）。
- 输出相关：
  - `--output-dir-name <string>`：自定义输出子目录名（默认 `<原目录名>_watermark`）。
  - `--suffix <string>`：输出文件名后缀（不含点）。
  - `--overwrite`：允许覆盖已存在的输出文件。
- 运行：
  - `--dry-run`：仅预览。
  - `--verbose`：详细日志。

### 示例
- 居中、半透明黑色、字号 48、边距 40/80、递归：
```powershell
python -m photodate_wm --path "D:\Photos" --position cc --color "#000000" --opacity 0.5 --font-size 48 --margin-x 40 --margin-y 80 --recursive
```

- 指定字体并给输出文件名加后缀：
```powershell
python -m photodate_wm --path "D:\Photos" --font-path "C:\\Windows\\Fonts\\msyh.ttc" --suffix wm --recursive
```

- 单文件处理（默认输出到 `D:\Photos\Photos_watermark\`）：
```powershell
python -m photodate_wm --path "D:\Photos\IMG_0001.jpg"
```

### 支持格式
- 输入：JPEG, PNG（含透明通道）, BMP, TIFF。
- 输出：JPEG 或 PNG（GUI 可选；CLI 默认跟随原扩展，或通过 `--suffix` 等进行区分）。

> 说明：
> - 目前 CLI 主流程专注于“日期水印”；文本/图片水印能力主要通过 GUI 提供。
> - HEIC/HEIF 支持依赖系统/库环境，建议优先使用 JPEG/PNG/BMP/TIFF。

### 输出规则
- 输入为目录：输出到 `<输入目录>\<输入目录名>_watermark\...`，保留相对层级。
- 输入为单文件：输出到与源文件同级的 `<上级目录名>_watermark\<文件名>`。
- 文件名冲突时：
  - 默认不覆盖（可加 `--overwrite` 覆盖），或使用 `--suffix` 添加文件名后缀避免冲突。

### 目录结构
```text
software_homework/
  src/photodate_wm/
    __main__.py        # 入口：python -m photodate_wm
    cli.py             # CLI 参数解析与主流程
    exif_utils.py      # EXIF/mtime 日期提取
    render.py          # 文本水印绘制
  tests/               # 单元与集成测试
  requirements.txt
  README.md
```

### 测试
```powershell
pytest -q
```

### 已知限制
- HEIC/HEIF 的 EXIF 支持与解码依赖系统/库环境，若失败建议先转 JPG 测试。
- 文本不自动换行与缩放（超界会有风险），建议通过字号与边距控制。

### 许可证
本项目采用 MIT License，详见 `LICENSE`。



