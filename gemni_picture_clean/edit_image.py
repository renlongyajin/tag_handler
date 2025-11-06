from google import genai
from google.genai.types import GenerateContentConfig, Modality
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

load_dotenv("gemni_picture_clean\.env")

client = genai.Client()  # ✅ 不传 api_key，SDK 自动读取 .env 的凭证

# 打开一张本地图片，例如 test_image.png
image = Image.open("gemni_picture_clean\A9296EF25431FAF66DC56E0CD30FAF83.jpg")

prompt = """
去除图像中所有水印、logo、文字或标志，特别是右下角的小logo。
背景必须是纯白色（#FFFFFF），不得出现任何形状、阴影、方块或颜色过渡。
不要在右下角或任何地方添加新的形状。
仅保留人物主体及自然柔和的阴影，与白色背景自然融合。
输出为高清、干净、仅保留人物的图像。
"""

# 调用 Gemini 2.5 Flash Image 模型进行编辑
response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[image, prompt],  # 你可以修改提示词
    config=GenerateContentConfig(response_modalities=[Modality.TEXT, Modality.IMAGE]),
)

# 解析并保存结果
for part in response.candidates[0].content.parts:
    if part.text:
        print("模型说明：", part.text)
    elif part.inline_data:
        edited_image = Image.open(BytesIO(part.inline_data.data))
        edited_image.save("gemni_picture_clean\output_image.png")
        print("已保存编辑后的图片：output_image.png")
