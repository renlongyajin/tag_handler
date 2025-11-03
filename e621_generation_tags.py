import os
import re
import argparse
from PIL import Image
from webui import load_model, predict  # ✅ 复用你的模型函数

# ==============================
# 🧠 过滤规则定义
# ==============================

# 明确色情的标签（始终过滤）
NSFW_TAGS = {
    "sex", "sexual", "intercourse", "genitals", "penis", "vagina", 
    "erection", "cum", "ejaculation", "orgasm", "fellatio", "anal",
    "masturbation", "futanari", "rape", "penetration", "blowjob",
    "pussy", "cock", "balls", "testicles", "explicit", "porn",
    "yiff", "genital_fluids"
}

# 轻度裸露标签（在 strict 模式下过滤，在 loose 模式下保留）
MILD_NUDE_TAGS = {
    "nude", "naked", "unclothed", "bare_body", "bare"
}


def clean_tags(tags, mode="loose"):
    """
    过滤不需要的标签。
    mode = "loose"  -> 保留非性裸露（如 nude, naked）
    mode = "strict" -> 删除所有裸露与性暗示标签
    """
    clean = []
    for t in tags:
        tl = t.lower().strip()

        # 永远过滤明显色情标签
        if tl in NSFW_TAGS:
            continue
        if any(k in tl for k in ["sex", "cum", "ejac", "penis", "vagin", "orgasm", "explicit", "porn", "rape", "masturbat"]):
            continue

        # 严格模式下再过滤裸露类
        if mode == "strict" and (tl in MILD_NUDE_TAGS or any(k in tl for k in ["nude", "naked", "bare"])):
            continue

        clean.append(t)
    return clean


# ==============================
# 🖼️ 文件处理逻辑
# ==============================

def is_already_renamed(filename):
    """
    检查文件名是否符合 001.png / 023.jpg 这样的格式
    """
    return re.fullmatch(r"\d{3}\.(png|jpg|jpeg|webp)", filename.lower()) is not None


def rename_images(folder):
    """如果文件未按标准命名，则重命名为 001.png, 002.png ..."""
    images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    images.sort()

    # 检查是否全部已命名规范
    if all(is_already_renamed(f) for f in images):
        print("✅ 所有图片已按标准命名，无需重命名。")
        return False  # 表示未执行重命名

    for i, filename in enumerate(images, start=1):
        ext = os.path.splitext(filename)[1].lower()
        new_name = f"{i:03d}{ext}"
        old_path = os.path.join(folder, filename)
        new_path = os.path.join(folder, new_name)
        if old_path != new_path:
            os.rename(old_path, new_path)
        print(f"🪶 Renamed: {filename} → {new_name}")

    return True  # 表示已执行重命名


def process_images(folder, filter_mode="loose"):
    """批量识别图片并输出标签"""
    print(f"\n🚀 正在加载模型...")
    load_model()

    images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    images.sort()

    for filename in images:
        path = os.path.join(folder, filename)
        print(f"\n🔍 处理: {filename}")

        try:
            img = Image.open(path)
            if img.mode != "RGB":
                img = img.convert("RGB")

            # 模型预测
            tag_str = predict(img)
            tags = [t.strip() for t in tag_str.split(",") if t.strip()]

            # 标签过滤
            tags = clean_tags(tags, filter_mode)

            # 保存结果
            txt_path = os.path.splitext(path)[0] + ".e621.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(", ".join(tags))

            print(f"✅ 标签已保存 → {txt_path}")
            if filter_mode == "strict":
                print("   (严格模式：nude/naked 等已过滤)")

        except Exception as e:
            print(f"❌ 处理 {filename} 时出错: {e}")


# ==============================
# 🧰 主函数入口
# ==============================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量生成图片标签")
    parser.add_argument("--folder", type=str, default="data/poren", help="图片所在文件夹")
    parser.add_argument("--filter", type=str, default="loose", choices=["loose", "strict"], help="过滤等级：loose=宽松 / strict=严格")
    args = parser.parse_args()

    print("=== Step 1: 检查图片命名 ===")
    renamed = rename_images(args.folder)

    if renamed:
        print("\n✅ 重命名完成！")
    else:
        print("\n⏭️ 跳过重命名。")

    print("\n=== Step 2: 生成标签 ===")
    process_images(args.folder, args.filter)

    print("\n🎉 全部完成！")
