import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm


# === 基础配置 ===
load_dotenv()

API_KEY = os.environ.get("OPENAI_API_KEY")  
BASE_URL = os.environ.get("OPENAI_BASE_URL") 
MODEL_NAME = "gpt-4o-mini"  # 也可用 gpt-4o / gpt-4-turbo
FOLDER = r"E:\AI\my_project\e621-tagger\data\poren"  # 图片所在文件夹
MAX_RETRIES = 3  # 出错重试次数
DELAY_BETWEEN_CALLS = 1.0  # 每次请求间隔（秒）
LOG_FILE = os.path.join(FOLDER, "merge_log.txt")

client = OpenAI(api_key=API_KEY)

def gpt_merge_tags(e621_tags: str, wd14_tags: str) -> str:
    """
    调用 GPT API 将 e621 + WD14 标签融合为 SD 可识别格式
    """
    prompt = f"""
You are a dataset refinement assistant specialized in tag cleaning for Stable Diffusion LoRA training.

Your task is to merge, clean, and optimize two tag lists (e621 and Kohya/WD14).
Produce a compact, meaningful set of 15–25 tags for each image, suitable for LoRA training.

Rules:
1. Merge both tag lists and remove duplicates or synonyms.
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
4. Merge similar color tags (e.g. "blue scales", "blue fur" → "blue body").
5. Use only lowercase English words, comma-separated.
6. Keep between 15–25 tags total.
7. Output ONLY the final tag list (no explanation).

Example input:
e621 tags: anthropomorphic, dragon, male, wings, tail, scales, armor, yu-gi-oh!, konami, standing, solo, blue body, claws
kohya tags: furry, dragon, armor, sword, wings, solo, blue scales, claws, full body

Example output:
furry, dragon, male, armor, sword, wings, tail, claws, scales, blue body, standing, solo, full body

E621 Tags: {e621_tags}
WD14 Tags: {wd14_tags}
"""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.responses.create(
                model=MODEL_NAME,
                input=prompt,
                temperature=0.2
            )
            result = response.output_text.strip()
            return result
        except Exception as e:
            print(f"⚠️ GPT 调用失败 ({attempt}/{MAX_RETRIES})：{e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
            else:
                raise e

def main():
    files = [f for f in os.listdir(FOLDER) if f.endswith(".e621.txt")]
    if not files:
        print("❌ 未找到任何 .e621.txt 文件。请检查目录路径。")
        return

    with open(LOG_FILE, "w", encoding="utf-8") as log:
        log.write("=== GPT 标签融合日志 ===\n")

    print(f"🚀 共检测到 {len(files)} 张图片，将逐一融合标签...\n")

    for i, file in enumerate(tqdm(files, desc="Processing", ncols=100, dynamic_ncols=True)):
        base = file.replace(".e621.txt", "")
        e621_file = os.path.join(FOLDER, f"{base}.e621.txt")
        wd14_file = os.path.join(FOLDER, f"{base}.txt")
        out_file = os.path.join(FOLDER, f"{base}.final.txt")

        try:
            with open(e621_file, "r", encoding="utf-8") as f:
                e621_tags = f.read().strip()
            with open(wd14_file, "r", encoding="utf-8") as f:
                wd14_tags = f.read().strip()

            merged = gpt_merge_tags(e621_tags, wd14_tags)

            # ✅ tqdm 安全打印（不会被进度条覆盖）
            tqdm.write(f"picture_{i+1}_tags: {merged}\n")

            with open(out_file, "w", encoding="utf-8") as f:
                f.write(merged)

            with open(LOG_FILE, "a", encoding="utf-8", buffering=1) as log:
                log.write(f"[OK] {base}.final.txt ({len(merged.split(','))} tags)\n")
                log.flush()

            time.sleep(DELAY_BETWEEN_CALLS)

        except Exception as e:
            tqdm.write(f"❌ 处理 {base} 出错: {e}")


    print("\n🎉 所有文件处理完成！结果保存在 .final.txt 中。")
    print(f"📝 日志文件：{LOG_FILE}")

if __name__ == "__main__":
    main()
