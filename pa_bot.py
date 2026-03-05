import logging
import os
import torch
import cv2
import numpy as np
from PIL import Image
from flask import Flask, request
import telebot
from model import BiSeNet

# ========== ТВОЙ ТОКЕН ==========
TELEGRAM_TOKEN = '8747690008:AAGQVfpp9xUbfyuPObOyt3kJVOUZ1rjnQck'
# ================================

# Секретная строка для безопасности URL
SECRET = "my_super_secret_string_123"

# Инициализация бота (threaded=False - обязательно для бесплатного аккаунта!)
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

# Загружаем модель нейросети
print("🔄 Загрузка модели нейросети...")
n_classes = 19
net = BiSeNet(n_classes=n_classes)
net.load_state_dict(torch.load('/home/Rinatw4fsfsef/my_hair_bot/model.pth', map_location='cpu'))
net.eval()
print("✅ Модель загружена!")

# ===== ВСЕ 8 ЦВЕТОВ =====
COLORS = {
    '🖤 Черный': (0, 0, 0),
    '💛 Золотой': (0, 215, 255),
    '❤️ Красный': (0, 0, 255),
    '🤎 Коричневый': (19, 69, 139),
    '💙 Синий': (255, 0, 0),
    '💚 Зеленый': (0, 255, 0),
    '💜 Фиолетовый': (128, 0, 128),
    '🧡 Рыжий': (0, 165, 255),
}
# ========================

# Словарь для хранения состояния пользователей
user_state = {}


def compress_image(input_path, output_path, max_size=1024, quality=85):
    """Сжимает изображение до указанного максимального размера"""
    try:
        img = Image.open(input_path)
        img.thumbnail((max_size, max_size))
        img.save(output_path, quality=quality)
        return True
    except Exception as e:
        print(f"⚠️ Ошибка сжатия: {e}")
        return False


def change_hair_color(image_path, output_path, color_bgr):
    """Меняет цвет волос используя нейросеть с предварительным сжатием"""

    # ===== 1. СЖАТИЕ ВХОДЯЩЕГО ФОТО =====
    temp_path = image_path + ".temp"
    compress_image(image_path, temp_path, max_size=800, quality=80)
    # Используем сжатое фото для обработки
    img = Image.open(temp_path).convert('RGB')
    original_size = img.size
    # =====================================

    # Ресайзим для нейросети
    img_resized = img.resize((512, 512))
    img_tensor = torch.tensor(np.array(img_resized)).permute(2, 0, 1).unsqueeze(0).float()
    img_tensor = img_tensor / 255.0

    # Получаем маску волос
    with torch.no_grad():
        out = net(img_tensor)[0]
        parsing = out.squeeze(0).argmax(0).numpy()

    # Класс 17 - волосы
    hair_mask = (parsing == 17).astype(np.uint8) * 255

    # Улучшаем маску
    kernel = np.ones((5, 5), np.uint8)
    hair_mask = cv2.morphologyEx(hair_mask, cv2.MORPH_CLOSE, kernel)

    # Ресайзим маску обратно
    hair_mask = cv2.resize(hair_mask, original_size, interpolation=cv2.INTER_LINEAR)

    # Загружаем оригинал и меняем цвет
    img_original = cv2.imread(temp_path)
    result = img_original.copy()

    for c in range(3):
        result[:, :, c] = np.where(
            hair_mask > 0,
            color_bgr[c],
            img_original[:, :, c]
        )

    # Сохраняем результат
    cv2.imwrite(output_path, result)

    # ===== 2. СЖАТИЕ ИСХОДЯЩЕГО ФОТО =====
    final_output = output_path + ".final"
    compress_image(output_path, final_output, max_size=1024, quality=85)
    os.replace(final_output, output_path)  # Заменяем оригинал сжатым
    # ======================================

    # Удаляем временный файл
    try:
        os.remove(temp_path)
    except:
        pass

    # ===== 3. ОЧИСТКА ПАМЯТИ =====
    # Очищаем память PyTorch (если используется GPU)
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    # Принудительная сборка мусора Python
    import gc
    gc.collect()
    # =============================

    return True


@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(
        message.chat.id,
        '👋 Привет! Отправь фото, выбери цвет волос.'
    )


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        # Скачиваем фото
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open('input.jpg', 'wb') as f:
            f.write(downloaded_file)

        user_state[message.chat.id] = {'awaiting_color': True}

        # Клавиатура с цветами
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        for color in COLORS.keys():
            markup.add(color)
        markup.add('❌ Отмена')

        bot.send_message(
            message.chat.id,
            '✅ Выбери цвет:',
            reply_markup=markup
        )

    except Exception as e:
        bot.send_message(message.chat.id, f'❌ Ошибка: {e}')


@bot.message_handler(func=lambda message: True)
def handle_color(message):
    chat_id = message.chat.id

    if chat_id not in user_state or not user_state[chat_id].get('awaiting_color'):
        return

    color_name = message.text

    if color_name == '❌ Отмена':
        user_state[chat_id]['awaiting_color'] = False
        bot.send_message(
            chat_id,
            '❌ Отменено',
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )
        return

    if color_name not in COLORS:
        return

    try:
        bot.send_message(
            chat_id,
            '🎨 Обрабатываю...',
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )

        color_bgr = COLORS[color_name]
        success = change_hair_color('input.jpg', 'output.jpg', color_bgr)

        if success and os.path.exists('output.jpg'):
            with open('output.jpg', 'rb') as f:
                bot.send_photo(chat_id, f, caption=f'✅ Готово! Цвет: {color_name}')

            # ИНСТРУКЦИЯ
            instruction = (
                f'📌 **Как улучшить результат через нейросеть:**\n\n'
                f'1️⃣ Сохрани оба фото:\n'
                f'   • Твое **первоначальное фото** (которое ты отправил)\n'
                f'   • **Фото с наложенным цветом** (которое я только что прислал)\n\n'
                f'2️⃣ Перейди по ссылке:\n'
                f'   👉 https://chat.qwen.ai/c/new-chat\n\n'
                f'3️⃣ Отправь **оба фото** и вставь этот текст:\n\n'
                f'```\n'
                f'Сделай пожалуйста окрас волос, основываясь на моей структуре волос.\n'
                f'Цвет волос должен быть таким же, как на втором фото (референс).\n\n'
                f'Важно: сохрани все детали лица, фон и одежду без изменений.\n'
                f'Волосы должны выглядеть натурально, с сохранением текстуры, бликов и теней.\n\n'
                f'Если хочешь оттенок чуть светлее или темнее - напиши в конце.\n'
                f'```'
            )
            bot.send_message(chat_id, instruction, parse_mode='Markdown')

        # Чистим файлы - ИСПРАВЛЕНО!
        for f in ['input.jpg', 'output.jpg', 'input.jpg.temp', 'output.jpg.final']:
            try:
                os.remove(f)
            except:
                pass

        user_state[chat_id]['awaiting_color'] = False

    except Exception as e:
        bot.send_message(chat_id, f'❌ Ошибка: {e}')
        user_state[chat_id]['awaiting_color'] = False


# ========== ВЕБ-ЧАСТЬ ==========
app = Flask(__name__)


@app.route('/' + SECRET, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    else:
        return 'Forbidden', 403


if __name__ == '__main__':
    print("🚀 Запуск локальной версии...")
    bot.remove_webhook()
    bot.polling(none_stop=True)