import os
from PIL import Image
from webui import load_model, predict  # ✅ 直接复用你的模型加载与预测函数

# 指定图片目录
input_dir = os.path.join("data", "poren")

# 1️⃣ 重命名图片
def rename_images(folder):
    images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    images.sort()
    for i, filename in enumerate(images, start=1):
        ext = os.path.splitext(filename)[1]
        new_name = f"{i:03d}{ext.lower()}"
        old_path = os.path.join(folder, filename)
        new_path = os.path.join(folder, new_name)
        os.rename(old_path, new_path)
        print(f"Renamed: {filename} -> {new_name}")

# 2️⃣ 批量识别并写入 .txt
def process_images(folder):
    # 加载模型一次
    load_model()

    images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    images.sort()

    for filename in images:
        path = os.path.join(folder, filename)
        print(f"\n🔍 Processing: {filename}")

        try:
            img = Image.open(path)
            if img.mode != "RGB":
                img = img.convert("RGB")

            tags = predict(img)

            txt_path = os.path.splitext(path)[0] + ".txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(tags)

            print(f"✅ Tags saved to: {txt_path}")

        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")

# 主函数
if __name__ == "__main__":
    # print("=== Step 1: Renaming images ===")
    # rename_images(input_dir)
    print("\n=== Step 2: Generating tags ===")
    process_images(input_dir)
    print("\n🎉 All done!")
