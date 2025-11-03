import os

def convert_to_utf8(root_dir):
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith(('.py', '.txt', '.html', '.js', '.css', '.json', '.md')):  # 可自行修改类型
                path = os.path.join(root, file)
                try:
                    with open(path, 'rb') as f:
                        raw = f.read()

                    # 跳过二进制文件
                    if b'\x00' in raw:
                        continue

                    # 自动检测原始编码（常见为 utf-8 或 gbk）
                    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'cp936', 'ansi']
                    for enc in encodings:
                        try:
                            text = raw.decode(enc)
                            break
                        except UnicodeDecodeError:
                            text = None
                            continue

                    if text is None:
                        print(f"⚠️ Skipped {path}: unknown encoding")
                        continue

                    # ✅ 统一换行符，防止出现多空行
                    text = text.replace('\r\n', '\n').replace('\r', '\n')

                    # 再保存为 UTF-8（不 BOM）
                    with open(path, 'w', encoding='utf-8', newline='\n') as f:
                        f.write(text)

                    print(f"✅ Converted: {path}")
                except Exception as e:
                    print(f"⚠️ Skipped {path}: {e}")

if __name__ == "__main__":
    convert_to_utf8(".")
