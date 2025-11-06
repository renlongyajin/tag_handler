import argparse
import os
import time
from typing import List, Sequence

from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm


# === 基础配置 ===
load_dotenv()

API_KEY = os.environ.get("OPENAI_API_KEY")
BASE_URL = os.environ.get("OPENAI_BASE_URL")

DEFAULT_MODEL_NAME = os.environ.get("E621_TAGGER_MODEL", "gpt-4o-mini")
DEFAULT_INPUT_DIR = os.environ.get(
    "E621_TAGGER_INPUT_DIR", r"E:\AI\my_project\e621-tagger\data\poren"
)
DEFAULT_MAX_RETRIES = 3
DEFAULT_DELAY_BETWEEN_CALLS = 1.0
DEFAULT_OUTPUT_SUFFIX = ".final.txt"
DEFAULT_TAG_SOURCES: List[str] = [".e621.txt", ".txt"]

DEFAULT_PROMPT_TEMPLATE = """You are a dataset refinement assistant specialized in tag cleaning for Stable Diffusion LoRA training.

Your task is to merge, clean, and optimize the provided tag lists.
Produce a compact, meaningful set of 15-25 tags for each image, suitable for LoRA training.

Rules:
1. Merge all tag lists and remove duplicates or synonyms.
2. Keep only visually or semantically meaningful tags:
   - species (e.g., dragon, furry, wolf)
   - anatomy (horns, wings, tail, scales)
   - gender or body shape (male, female, muscular)
   - clothing / armor / accessories
   - colors and materials (blue body, silver armor)
   - pose and composition (standing, solo, full body)
3. Remove the following:
   - background or environment tags (simple background, white background)
   - camera/view tags (looking at viewer, perspective)
   - redundant or generic terms (clothing, bottomwear, creature)
   - brand or franchise tags (e.g., yu-gi-oh!, konami, pokemon, digimon, disney, sega, nintendo)
   - specific character names unless the dataset is focused on that OC
4. Merge similar color tags (e.g. "blue scales", "blue fur" -> "blue body").
5. Use only lowercase English words, comma-separated.
6. Keep between 15-25 tags total.
7. Output ONLY the final tag list (no explanation).

{tag_sections}
"""


# === 参数解析 ===
def parse_tag_source(value: str) -> str:
    """只接收后缀名"""
    suffix = value.strip()
    if not suffix:
        raise argparse.ArgumentTypeError("Tag source suffix cannot be empty")
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    return suffix


def normalize_suffix(suffix: str) -> str:
    suffix = suffix.strip()
    if not suffix:
        raise argparse.ArgumentTypeError("Suffix cannot be empty")
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    return suffix


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge tag files with GPT assistance")
    parser.add_argument(
        "-i",
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help="Directory containing tag files (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Directory to save merged tag files (default: same as input)",
    )
    parser.add_argument(
        "--tag-source",
        dest="tag_sources",
        action="append",
        type=parse_tag_source,
        help="Tag source suffix (e.g., .e621.txt). Repeat for multiple sources.",
    )
    parser.add_argument(
        "--output-suffix",
        default=DEFAULT_OUTPUT_SUFFIX,
        help="Suffix for merged output files (default: %(default)s)",
    )
    parser.add_argument(
        "--prompt-file",
        help="Path to a custom prompt template file. Use {tag_sections} as placeholder for inputs.",
    )
    parser.add_argument(
        "--prompt-extra",
        action="append",
        dest="prompt_extra",
        help="Additional instruction line appended to the prompt. Repeat to add more.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
        help="OpenAI model name (default: %(default)s)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Maximum retry attempts on API failure (default: %(default)s)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_BETWEEN_CALLS,
        help="Delay in seconds between successful API calls (default: %(default)s)",
    )
    parser.add_argument(
        "--log-file",
        help="Path to log file (default: <output-dir>/merge_log.txt)",
    )
    parser.add_argument(
        "--api-key",
        default=API_KEY,
        help="OpenAI API key (default: value from OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="Custom OpenAI API base URL (default: value from OPENAI_BASE_URL)",
    )

    args = parser.parse_args()
    args.output_suffix = normalize_suffix(args.output_suffix)
    return args


# === 工具函数 ===
def load_prompt_template(path: str | None, extra_lines: Sequence[str] | None) -> str:
    if path:
        with open(path, "r", encoding="utf-8") as file:
            template = file.read()
    else:
        template = DEFAULT_PROMPT_TEMPLATE

    if extra_lines:
        template = f"{template.rstrip()}\n\n" + "\n".join(extra_lines)

    return template


def build_prompt(tag_lists: Sequence[str], template: str) -> str:
    tag_sections = "\n".join(f"Tags: {tags}" for tags in tag_lists if tags.strip())
    if "{tag_sections}" in template:
        return template.replace("{tag_sections}", tag_sections)
    return f"{template.rstrip()}\n\n{tag_sections}"


def create_client(api_key: str | None, base_url: str | None) -> OpenAI:
    client_kwargs = {}
    if api_key:
        client_kwargs["api_key"] = api_key
    if base_url:
        client_kwargs["base_url"] = base_url
    return OpenAI(**client_kwargs)


def gpt_merge_tags(client: OpenAI, model: str, prompt: str, max_retries: int) -> str:
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.responses.create(model=model, input=prompt, temperature=0.2)
            return response.output_text.strip()
        except Exception as exc:
            last_error = exc
            print(f"⚠️ GPT 调用失败 ({attempt}/{max_retries})：{exc}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
    if last_error:
        raise last_error
    raise RuntimeError("Unable to call GPT and no error captured")


# === 主逻辑 ===
def main() -> None:
    args = parse_arguments()

    if not args.api_key and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("缺少 OpenAI API key，请通过 --api-key 或环境变量 OPENAI_API_KEY 提供")

    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir) if args.output_dir else input_dir

    tag_sources = args.tag_sources or list(DEFAULT_TAG_SOURCES)
    if not tag_sources:
        raise RuntimeError("至少需要一个标签来源 (--tag-source)")

    os.makedirs(output_dir, exist_ok=True)

    log_file = (
        os.path.abspath(args.log_file)
        if args.log_file
        else os.path.join(output_dir, "merge_log.txt")
    )

    client = create_client(args.api_key, args.base_url)
    prompt_template = load_prompt_template(args.prompt_file, args.prompt_extra)

    # === 只保留唯一 base_name，防止重复处理 ===
    suffixes = tuple(tag_sources)
    all_files = [f for f in os.listdir(input_dir) if f.endswith(suffixes)]

    base_names = set()
    for f in all_files:
        for suffix in suffixes:
            if f.endswith(suffix):
                base_names.add(f[:-len(suffix)])
                break
    base_names = sorted(base_names)

    if not base_names:
        print(f"⚠️ 未找到任何以 {suffixes} 结尾的文件。请检查目录路径：{input_dir}")
        return

    with open(log_file, "w", encoding="utf-8") as log:
        log.write("=== GPT 标签融合日志 ===\n")
        log.write(f"输入目录：{input_dir}\n")
        log.write(f"输出目录：{output_dir}\n")
        log.write(f"使用模型：{args.model}\n")
        log.write("标签来源：" + ", ".join(tag_sources) + "\n\n")

    print(f"🗂 输入文件夹：{input_dir}")
    print(f"🗃 输出文件夹：{output_dir}")
    print(f"🔖 标签来源后缀：{', '.join(tag_sources)}")
    print(f"🚀 共检测到 {len(base_names)} 个基础文件，将逐一融合标签...\n")

    for index, base_name in enumerate(
        tqdm(base_names, desc="Processing", ncols=100, dynamic_ncols=True), start=1
    ):
        tag_lists: List[str] = []
        missing_sources: List[str] = []

        for suffix in tag_sources:
            source_path = os.path.join(input_dir, f"{base_name}{suffix}")
            if not os.path.exists(source_path):
                missing_sources.append(source_path)
                continue
            with open(source_path, "r", encoding="utf-8") as source_file:
                tags = source_file.read().strip()
            tag_lists.append(tags)

        if missing_sources:
            tqdm.write(f"⚠️ {base_name} 缺少文件：{', '.join(missing_sources)}，已跳过")
            continue

        try:
            prompt = build_prompt(tag_lists, prompt_template)
            merged_tags = gpt_merge_tags(client, args.model, prompt, args.max_retries)
            tqdm.write(f"{base_name}_tags: {merged_tags}\n")

            output_path = os.path.join(output_dir, f"{base_name}{args.output_suffix}")
            with open(output_path, "w", encoding="utf-8") as out_file:
                out_file.write(merged_tags)

            tag_count = len([tag for tag in (t.strip() for t in merged_tags.split(",")) if tag])
            with open(log_file, "a", encoding="utf-8", buffering=1) as log:
                log.write(f"[OK] {base_name}{args.output_suffix} ({tag_count} tags)\n")
                log.flush()

            time.sleep(max(args.delay, 0.0))

        except Exception as exc:
            tqdm.write(f"⚠️ 处理 {base_name} 出错: {exc}")

    print("\n🎉 所有文件处理完成！结果已保存至输出目录。")
    print(f"📝 日志文件：{log_file}")


if __name__ == "__main__":
    main()
