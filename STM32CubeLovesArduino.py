# app.py

import json
import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ENCODING = "utf-8"

# Arduino 核心已提供的标准 Cortex-M 异常处理函数，不需要在 .ino 中重复定义
CORTEX_HANDLERS = {
    "NMI_Handler", "HardFault_Handler", "MemManage_Handler",
    "BusFault_Handler", "UsageFault_Handler", "SVC_Handler",
    "DebugMon_Handler", "PendSV_Handler", "SysTick_Handler",
}


def insert_before(lines, marker, content):
    result = []
    for line in lines:
        if marker in line:
            result.extend(content)
        result.append(line)
    return result


def insert_after(lines, marker, content):
    result = []
    for line in lines:
        result.append(line)
        if marker in line:
            result.extend(content)
    return result


def process_main_c(file_path: Path):
    with open(file_path, "r", encoding=ENCODING) as f:
        content = f.read()

    # 幂等：已处理过则跳过
    if "#ifndef USE_ARDUINO" in content:
        return

    lines = content.splitlines(keepends=True)

    lines = insert_before(lines, "/* USER CODE END Header */", ["#ifndef USE_ARDUINO\n"])
    lines = insert_before(lines, "/* USER CODE END Includes */", ["#endif\n"])
    lines = insert_before(lines, "/* USER CODE END 0 */", ["#ifndef USE_ARDUINO\n"])
    lines = insert_before(lines, "/* USER CODE END 1 */", [
        "#else\n", "void HAL_main()\n", "{\n", "#endif\n"
    ])
    lines = insert_before(lines, "/* USER CODE END 4 */", ["#ifndef USE_ARDUINO\n"])
    lines = insert_after(lines, "/* USER CODE BEGIN Error_Handler_Debug */", [
        "#else\n", "void HAL_Error_Handler()\n", "{\n", "#endif\n"
    ])
    lines = insert_before(lines, "/* USER CODE END 2 */", ["#ifndef USE_ARDUINO\n"])
    lines = insert_before(lines, "/* USER CODE END 3 */", ["#endif\n"])

    with open(file_path, "w", encoding=ENCODING) as f:
        f.writelines(lines)


def process_msp_c(file_path: Path):
    with open(file_path, "r", encoding=ENCODING) as f:
        content = f.read()

    # 幂等：已处理过则跳过
    if "#ifndef USE_ARDUINO" in content:
        return

    lines = content.splitlines(keepends=True)

    lines = insert_before(lines, "/* USER CODE END Header */", ["#ifndef USE_ARDUINO\n"])
    lines = insert_before(lines, "/* USER CODE END Includes */", ["#endif\n"])

    with open(file_path, "w", encoding=ENCODING) as f:
        f.writelines(lines)


def extract_peripheral_handlers(it_path: Path) -> dict:
    """从 stm32*_it.c 中提取外设中断处理函数，排除标准 Cortex-M 异常处理函数。
    过滤掉空的 USER CODE 占位注释，返回 {函数名: "extern \"C\" 完整函数体"} 的字典。"""
    with open(it_path, "r", encoding=ENCODING) as f:
        content = f.read()

    # 匹配所有函数定义：void FuncName(...)
    pattern = re.compile(r"\bvoid\s+(\w+)\s*\([^)]*\)")
    handlers = {}

    for match in pattern.finditer(content):
        func_name = match.group(1)
        if func_name in CORTEX_HANDLERS:
            continue

        # 从函数签名开始，通过数大括号提取完整函数体
        start = match.start()
        brace_start = content.find("{", match.end())
        if brace_start == -1:
            continue

        depth = 0
        i = brace_start
        while i < len(content):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    body = content[start:i + 1]
                    # 过滤掉空的 USER CODE 占位行
                    lines = body.split("\n")
                    filtered = [
                        line for line in lines
                        if not re.search(r"/\*\s*USER CODE (BEGIN|END).*?\*/", line)
                        and line.strip() != ""
                    ]
                    body = "\n".join(filtered)
                    handlers[func_name] = f'extern "C" {body}'
                    break
            i += 1

    return handlers


def create_arduino_it(folder: Path, it_handlers: dict):
    """将提取的中断处理函数合并写入 ArduinoIT.h。
    已存在的函数保留不动，仅追加 it.c 中新增的函数。
    废弃函数被重新加入 it.c 时自动恢复为活跃状态。"""
    path = folder / "ArduinoIT.h"

    # 读取已有文件，提取已存在的函数名（包括活跃和废弃的）
    existing = {}  # 函数名 → 代码块
    deprecated_names = set()
    if path.exists():
        with open(path, "r", encoding=ENCODING) as f:
            old_content = f.read()
        deprecated_names = _extract_deprecated_names(old_content)
        # 活跃函数: extern "C" void FuncName(（排除废弃函数名，否则会误匹配到 // 注释行）
        for name in re.findall(r'extern\s+"C"\s+void\s+(\w+)\s*\(', old_content):
            if name not in deprecated_names:
                _extract_func_block(old_content, name, existing)
        # 废弃函数: // extern "C" void FuncName(  // --deprecated
        for name in deprecated_names:
            _extract_func_block(old_content, name, existing, deprecated=True)

    # 合并：保留旧 body（含用户修改）。废弃函数统一先去掉 // 前缀还原为
    # 活跃形式，写入阶段再按函数是否存在于 it.c 决定是否重新注释，保证幂等
    new_count = 0
    restored_count = 0
    merged = {}
    for name, body in existing.items():
        if name in deprecated_names:
            body = _uncomment(body)
        if name in it_handlers and name in deprecated_names:
            restored_count += 1
        merged[name] = body

    for name, body in it_handlers.items():
        if name not in merged:
            merged[name] = body
            new_count += 1

    if not merged:
        return

    header = _b("it_header1") + "\n"
    header += _b("it_header2") + "\n"
    header += _b("it_header3") + "\n"
    if new_count > 0:
        header += _b("it_new", new_count) + "\n"
    if restored_count > 0:
        header += _b("it_restored", restored_count) + "\n"

    lines = [header]
    for name, body in merged.items():
        if name not in it_handlers:
            # 每行添加 // 注释掉，并在函数签名行标记 --deprecated
            commented = []
            for i, line in enumerate(body.split("\n")):
                if i == 0:
                    commented.append(f"// {line}  // --deprecated")
                else:
                    commented.append(f"// {line}")
            lines.append("\n".join(commented) + "\n")
        else:
            lines.append(f"{body}\n")

    with open(path, "w", encoding=ENCODING) as f:
        f.write("\n".join(lines))


def _extract_func_block(content: str, name: str, storage: dict, deprecated: bool = False):
    """从文本中提取指定函数的完整代码块，存入 storage 字典。"""
    prefix = r"//\s*" if deprecated else r""
    pattern = re.compile(rf'{prefix}extern\s+"C"\s+void\s+{re.escape(name)}\s*\([^)]*\)')
    m = pattern.search(content)
    if not m:
        return
    brace_start = content.find("{", m.end())
    if brace_start == -1:
        return
    depth = 0
    i = brace_start
    while i < len(content):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                storage[name] = content[m.start():i + 1]
                return
        i += 1


def _extract_deprecated_names(content: str) -> set:
    """提取文件中所有废弃函数名。"""
    return set(re.findall(r'//\s*extern\s+"C"\s+void\s+(\w+)\s*\(', content))


def _uncomment(body: str) -> str:
    """去掉代码块每行的 // 注释前缀和 --deprecated 标记，保留用户手写修改。
    只删 // 和紧跟的一个空格，保留原有的代码缩进。"""
    lines = []
    for line in body.split("\n"):
        line = re.sub(r"^//\s?", "", line)
        line = re.sub(r"\s*//\s*--deprecated\s*$", "", line)
        lines.append(line)
    return "\n".join(lines)


def create_ino(folder: Path, main_path: Path, msp_path: Path, has_it: bool = False):
    ino_name = folder.name + ".ino"
    ino_path = folder / ino_name

    if ino_path.exists():
        # 已有 .ino 文件，保留用户修改，仅补充 ArduinoIT.h 的 include
        if has_it:
            with open(ino_path, "r", encoding=ENCODING) as f:
                content = f.read()
            if 'ArduinoIT.h' not in content:
                # 在 main.c 和 msp.c 的 include 之后插入
                msp_rel = msp_path.relative_to(folder).as_posix()
                marker = f'#include "{msp_rel}"'
                new_line = f'{marker}\n#include "ArduinoIT.h" // 引入中断处理函数'
                content = content.replace(marker, new_line, 1)
                with open(ino_path, "w", encoding=ENCODING) as f:
                    f.write(content)
        return

    # 首次生成 .ino 文件
    main_rel = main_path.relative_to(folder).as_posix()
    msp_rel = msp_path.relative_to(folder).as_posix()

    it_include = f'#include "ArduinoIT.h" {_b("ino_it_include")}\n' if has_it else ""

    content = f'''#include "hal_conf_extra.h" {_b("ino_hal_conf")}
#define USE_ARDUINO
#include "{main_rel}" {_b("ino_main_c")}
#include "{msp_rel}" {_b("ino_msp_c")}
{it_include}
void setup() {{
    HAL_main(); {_b("ino_setup")}
}}

void loop() {{
}}

{_b("ino_note1")}
// extern "C" void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)

{_b("ino_note2")}
{_b("ino_note2b")}
{_b("ino_note2c")}
'''

    with open(ino_path, "w", encoding=ENCODING) as f:
        f.write(content)


# HAL 句柄前缀 → (MODULE_ONLY 宏, 是否默认启用)
# 默认启用的模块（ADC/I2C/RTC/SPI/TIM）→ 只需 MODULE_ONLY 禁用 Arduino 封装
# 默认禁用的模块（CAN/DAC/ETH/SD/QSPI/FDCAN）→ 需要 MODULE_ENABLED 先启用 HAL 驱动
HAL_HANDLE_MAP = {
    "hadc":    ("HAL_ADC_MODULE_ONLY",    True),
    "hdac":    ("HAL_DAC_MODULE_ENABLED", False),
    "hspi":    ("HAL_SPI_MODULE_ONLY",    True),
    "hi2c":    ("HAL_I2C_MODULE_ONLY",    True),
    "huart":   ("HAL_UART_MODULE_ONLY",   True),
    "husart":  ("HAL_UART_MODULE_ONLY",   True),
    "htim":    ("HAL_TIM_MODULE_ONLY",    True),
    "hrtc":    ("HAL_RTC_MODULE_ONLY",    True),
    "hpwr":    ("HAL_PWR_MODULE_ONLY",    True),
    "hfdcan":  ("HAL_FDCAN_MODULE_ENABLED", False),
    "hcan":    ("HAL_CAN_MODULE_ENABLED",  False),
}


def detect_peripherals(main_path: Path) -> list:
    """扫描 main.c，检测项目中使用的 HAL 外设句柄，返回配置宏列表。"""
    with open(main_path, "r", encoding=ENCODING) as f:
        content = f.read()

    found = []
    for prefix, (macro, _) in HAL_HANDLE_MAP.items():
        if re.search(rf'\b{prefix}\d*\b', content):
            found.append(f"#define {macro} // {t('hal_detect')} {prefix}")
    return found


def create_hal_conf(folder: Path, peripherals: list):
    path = folder / "hal_conf_extra.h"

    # 保留用户设置的 HSE_VALUE 数值，注释随语言更新
    hse_val = "8000000"
    if path.exists():
        with open(path, "r", encoding=ENCODING) as f:
            for line in f:
                m = re.match(r"#define\s+HSE_VALUE\s+(\d+)", line)
                if m:
                    hse_val = m.group(1)
                    break
    hse_line = f"#define HSE_VALUE {hse_val} {_b('hal_hse')}"

    peri_lines = "\n".join(peripherals) if peripherals else _b("hal_no_peri")

    content = f'''{hse_line}
{peri_lines}

{_b("hal_ref")} https://github.com/stm32duino/Arduino_Core_STM32/wiki/HAL-configuration
//
{_b("hal_only_note")}
// #define HAL_UART_MODULE_ONLY
// #define HAL_TIM_MODULE_ONLY
// #define HAL_ADC_MODULE_ONLY
// #define HAL_DAC_MODULE_ONLY
// #define HAL_RTC_MODULE_ONLY
// #define HAL_PWR_MODULE_ONLY
//
{_b("hal_dis_note")}
// #define HAL_ADC_MODULE_DISABLED
// #define HAL_I2C_MODULE_DISABLED
// #define HAL_RTC_MODULE_DISABLED
// #define HAL_SPI_MODULE_DISABLED
// #define HAL_TIM_MODULE_DISABLED
'''

    with open(path, "w", encoding=ENCODING) as f:
        f.write(content)


def run_process(folder_path):
    folder = Path(folder_path)

    main_c = None
    msp_c = None
    it_c = None

    for file in folder.rglob("*.c"):
        if file.name == "main.c":
            main_c = file
        elif "hal_msp" in file.name:
            msp_c = file
        elif file.name.startswith("stm32") and file.name.endswith("_it.c"):
            it_c = file

    if not main_c or not msp_c:
        messagebox.showerror(t("error_title"), t("err_no_file"))
        return

    process_main_c(main_c)
    process_msp_c(msp_c)

    has_it = False
    if it_c:
        it_handlers = extract_peripheral_handlers(it_c)
        # 无条件调用：即使 it.c 中没有外设中断，也要把 ArduinoIT.h 中
        # 已不存在的函数注释掉（it_handlers 为空 dict 表示全部移除）
        if it_handlers or (folder / "ArduinoIT.h").exists():
            create_arduino_it(folder, it_handlers)
            has_it = True

    create_ino(folder, main_c, msp_c, has_it)

    peripherals = detect_peripherals(main_c)
    create_hal_conf(folder, peripherals)

    # 构建提示信息
    msg = t("done_msg")
    if peripherals:
        peri_list = "\n".join(peripherals)
        msg += f"\n\n{t('done_peri')}\n{peri_list}"
        msg += f"\n\n{t('done_hint')}"
    messagebox.showinfo(t("done_title"), msg)


def select_folder():
    folder = filedialog.askdirectory()
    if folder:
        run_process(folder)


# ============================================================
# i18n 多语言支持
# ============================================================
TEXTS = {
    "zh": {
        "title":              "STM32 → Arduino 转换工具",
        "label":              "选择 STM32 工程目录",
        "btn_process":        "选择文件夹并处理",
        "btn_lang":           "EN",
        "error_title":        "错误",
        "err_no_file":        "未找到 main.c 或 msp.c",
        "done_title":         "完成",
        "done_msg":           "处理成功 ✅",
        "done_peri":          "检测到以下外设，已写入 hal_conf_extra.h：",
        "done_hint":          "如需调整，请手动编辑 hal_conf_extra.h",
        "dialog_title":       "选择 STM32 工程目录",
        # 生成文件注释
        "ino_hal_conf":       "引入HAL库设置",
        "ino_main_c":         "引入main.c文件",
        "ino_msp_c":          "引入stm32yyxx_hal_msp.c文件",
        "ino_it_include":     "引入中断处理函数",
        "ino_setup":          "执行HAL库内的相关初始化操作",
        "ino_note1":          "一般回调函数需要加 extern \"C\"，如下",
        "ino_note2":          "由于我们只引入了 main.c 和 msp.c 文件，没有引入 it.c 文件，",
        "ino_note2b":         "所以遇到中断函数时需要从 stm32*_it.c 中提取并书写出来",
        "ino_note2c":         "提取的中断函数位于 ArduinoIT.h 中",
        "it_header1":         "自动从 stm32*_it.c 提取的外设中断处理函数",
        "it_header2":         "由 STM32 → Arduino 转换工具自动生成",
        "it_header3":         "函数只增不删：it.c 中移除的函数会保留在此文件中，需手动删除",
        "it_new":             "本次新增 {} 个函数",
        "it_restored":        "本次恢复 {} 个函数",
        "hal_hse":            "修改晶振频率（根据实际晶振调整）",
        "hal_detect":         "检测到",
        "hal_no_peri":        "未检测到外设，请根据项目需要手动配置",
        "hal_ref":            "详见",
        "hal_only_note":      "禁用 Arduino 库，仅使用 HAL 库（使用 HAL 库时调用）:",
        "hal_dis_note":       "完全禁用 HAL 模块:",
    },
    "en": {
        "title":              "STM32 → Arduino Converter",
        "label":              "Select STM32 Project Directory",
        "btn_process":        "Select Folder && Process",
        "btn_lang":           "中文",
        "error_title":        "Error",
        "err_no_file":        "main.c or msp.c not found",
        "done_title":         "Done",
        "done_msg":           "Processing completed ✅",
        "done_peri":          "Detected peripherals written to hal_conf_extra.h:",
        "done_hint":          "Edit hal_conf_extra.h manually if needed",
        "dialog_title":       "Select STM32 Project Directory",
        # Generated file comments
        "ino_hal_conf":       "Include HAL configuration",
        "ino_main_c":         "Include main.c",
        "ino_msp_c":          "Include stm32yyxx_hal_msp.c",
        "ino_it_include":     "Include interrupt handlers",
        "ino_setup":          "Execute HAL initialization",
        "ino_note1":          "Callbacks generally need extern \"C\", e.g.:",
        "ino_note2":          "Since we only include main.c and msp.c, not it.c,",
        "ino_note2b":         "interrupt handlers must be extracted from stm32*_it.c",
        "ino_note2c":         "Extracted handlers are in ArduinoIT.h",
        "it_header1":         "Auto-extracted peripheral interrupt handlers from stm32*_it.c",
        "it_header2":         "Auto-generated by STM32 → Arduino Converter",
        "it_header3":         "Add-only: handlers removed from it.c are kept here, delete manually",
        "it_new":             "{} new handler(s) added this run",
        "it_restored":        "{} handler(s) restored this run",
        "hal_hse":            "Adjust crystal frequency to match your board",
        "hal_detect":         "Detected",
        "hal_no_peri":        "No peripherals detected, configure manually",
        "hal_ref":            "See",
        "hal_only_note":      "Disable Arduino wrapper, use HAL directly:",
        "hal_dis_note":       "Completely disable HAL module:",
    },
}

# 生成文件注释：根据当前语言输出
def _b(key: str, *args) -> str:
    return f"// {t(key).format(*args)}"

CONFIG_FILE = Path(__file__).parent / ".stm32_conv_config"


def _load_lang() -> str:
    try:
        with open(CONFIG_FILE, "r", encoding=ENCODING) as f:
            data = json.load(f)
            lang = data.get("language", "zh")
            if lang in ("zh", "en"):
                return lang
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return "zh"


def _save_lang(lang: str):
    try:
        with open(CONFIG_FILE, "w", encoding=ENCODING) as f:
            json.dump({"language": lang}, f)
    except OSError:
        pass


LANG = _load_lang()


def t(key: str) -> str:
    return TEXTS[LANG][key]


def toggle_lang():
    global LANG
    LANG = "en" if LANG == "zh" else "zh"
    _save_lang(LANG)
    _refresh_ui()


def _refresh_ui():
    app.title(t("title"))
    label.config(text=t("label"))
    btn_process.config(text=t("btn_process"))
    btn_lang.config(text=t("btn_lang"))


# ============================================================
# GUI
# ============================================================
app = tk.Tk()
app.title(t("title"))
app.geometry("420x220")

label = tk.Label(app, text=t("label"), font=("Arial", 14))
label.pack(pady=20)

style = ttk.Style()
style.theme_use("vista")  # Win10 风格
style.configure("Big.TButton", padding=8, font=("Segoe UI", 11))

btn_process = ttk.Button(app, text=t("btn_process"), command=select_folder,
                         style="Big.TButton")
btn_process.pack(pady=20)

btn_lang = ttk.Button(app, text=t("btn_lang"), command=toggle_lang, width=6)
btn_lang.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")

app.mainloop()