import polib
from deep_translator import GoogleTranslator, DeeplTranslator
import re
import sys

# --- CẤU HÌNH ---
SOURCE_FILE = 'base.po'
TARGET_FILE = 'base_translated.po'
API_KEY = None  # Thay bằng key của bạn nếu dùng DeepL
TARGET_LANG = 'vi'
MODE = 'google' # Chuyển thành 'deepl' nếu muốn dùng DeepL

def translate_text(text, mode='google', api_key=None):
    if not text.strip():
        return text

    # Bảo vệ placeholders
    placeholders = re.findall(r'(\{[^}]*\}|%s|%d)', text)
    temp_text = text
    for i, ph in enumerate(placeholders):
        temp_text = temp_text.replace(ph, f" PH{i} ")

    try:
        if mode == 'deepl':
            if not api_key:
                raise ValueError("DeepL cần API Key!")
            # Dùng thư viện deep-translator cho đồng bộ
            translated_text = DeeplTranslator(api_key=api_key, source='en', target='vi').translate(temp_text)
        else:
            # Dùng Google qua deep-translator
            translated_text = GoogleTranslator(source='en', target='vi').translate(temp_text)

        # Khôi phục placeholders
        for i, ph in enumerate(placeholders):
            translated_text = re.sub(f"PH{i}", ph, translated_text, flags=re.IGNORECASE)
        
        return translated_text.strip()
    except Exception as e:
        print(f"Lỗi: {e}")
        return None

def main():
    po = polib.pofile(SOURCE_FILE)
    untranslated_entries = [entry for entry in po if not entry.msgstr and entry.msgid]

    print(f"Tìm thấy {len(untranslated_entries)} câu chưa dịch. Bắt đầu xử lý...")

    count = 0
    for entry in untranslated_entries:
        translated = translate_text(entry.msgid, mode=MODE, api_key=API_KEY)
        
        if translated:
            entry.msgstr = translated
            # Đánh dấu fuzzy để mình biết đường mà soát lại
            if 'fuzzy' not in entry.flags:
                entry.flags.append('fuzzy')
            count += 1
            print(f"[{count}] Đã dịch: {entry.msgid[:30]}... -> {translated[:30]}...")
        
        # Lưu định kỳ để tránh mất dữ liệu nếu lỗi mạng
        if count % 10 == 0:
            po.save(TARGET_FILE)

    po.save(TARGET_FILE)
    print(f"\nHoàn thành! Đã dịch {count} câu. File lưu tại: {TARGET_FILE}")

if __name__ == "__main__":
    main()