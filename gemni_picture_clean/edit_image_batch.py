import os
from google import genai
from google.genai.types import GenerateContentConfig, Modality
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
from tqdm import tqdm  # ✅ 用于显示进度条

# 1️⃣ 载入环境变量
load_dotenv()

# 2️⃣ 从 .env 获取输入与输出路径
INPUT_FOLDER = os.getenv("INPUT_FOLDER")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER")

# 创建输出目录（如果不存在）
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 3️⃣ 初始化 Gemini 客户端
client = genai.Client()

# 4️⃣ 支持的图片格式
valid_extensions = [".jpg", ".jpeg", ".png", ".webp"]

# 5️⃣ 获取所有图片文件列表
image_files = [
    f for f in os.listdir(INPUT_FOLDER)
    if any(f.lower().endswith(ext) for ext in valid_extensions)
]

prompt = """
去除图像中所有水印、logo、文字或标志，特别是右下角的小logo。
背景必须是纯白色（#FFFFFF），不得出现任何形状、阴影、方块或颜色过渡。
不要在右下角或任何地方添加新的形状。
仅保留人物主体及自然柔和的阴影，与白色背景自然融合。
输出为高清、干净、仅保留人物的图像。
"""

total = len(image_files)
if total == 0:
    print(f"❌ 在 {INPUT_FOLDER} 中未找到任何图片文件。")
    exit()

print(f"📂 共找到 {total} 张图片，开始处理……\n")

# 6️⃣ 遍历并处理所有图片（带进度条）
for i, filename in enumerate(tqdm(image_files, desc="处理中", ncols=80), start=1):
    file_path = os.path.join(INPUT_FOLDER, filename)
    try:
        # 打开图片（支持中文路径）
        with Image.open(file_path) as image:
            # 调用 Gemini 进行编辑
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=[image, prompt],
                config=GenerateContentConfig(response_modalities=[Modality.TEXT, Modality.IMAGE]),
            )

            # 解析输出图片
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    edited_image = Image.open(BytesIO(part.inline_data.data))
                    output_path = os.path.join(OUTPUT_FOLDER, f"new_{filename}")
                    edited_image.save(output_path)
                    tqdm.write(f"✅ [{i}/{total}] 已保存：{output_path}")
                    break  # 只保存第一个生成结果

    except Exception as e:
        tqdm.write(f"❌ [{i}/{total}] 处理 {filename} 出错：{e}")

print("\n✨ 所有图片已处理完成！")
print(f"📁 输出目录：{OUTPUT_FOLDER}")
