import os
import cv2
import numpy as np
from PIL import Image
import telebot
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ТВОЙ ТОКЕН ==========
TELEGRAM_TOKEN = '8747690008:AAGQVfpp9xUbfyuPObOyt3kJVOUZ1rjnQck'
# ================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ===== ЦВЕТА =====
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
# =================

user_state = {}

def simple_hair_change(image_path, output_path, color_bgr):
    """Простая замена цвета волос (без нейросети)"""
    
    # Читаем изображение
    img = cv2.imread(image_path)
    if img is None:
        return False
    
    # Конвертируем в HSV для лучшего выделения волос
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Простая маска для темных волос (можно регулировать)
    lower = np.array([0, 0, 0])
    upper = np.array([180, 255, 80])
    mask = cv2.inRange(hsv, lower, upper)
    
    # Улучшаем маску
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    # Размываем края маски
    mask = cv2.GaussianBlur(mask, (5,5), 0)
    mask = mask / 255.0
    
    # Меняем цвет
    result = img.copy()
    for i in range(3):
        result[:,:,i] = (1 - mask) * img[:,:,i] + mask * color_bgr[i]
    
    result = result.astype(np.uint8)
    cv2.imwrite(output_path, result)
    return True

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, '👋 Отправь фото, выбери цвет волос.')

@bot.message_handler(content_types=['photo'])
def photo(message):
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        with open('input.jpg', 'wb') as f:
            f.write(downloaded)
        
        user_state[message.chat.id] = {'awaiting': True}
        
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        for color in COLORS.keys():
            markup.add(color)
        markup.add('❌ Отмена')
        
        bot.send_message(message.chat.id, '✅ Выбери цвет:', reply_markup=markup)
    except Exception as e:
        bot.send_message(message.chat.id, f'❌ Ошибка: {e}')

@bot.message_handler(func=lambda m: True)
def color(m):
    cid = m.chat.id
    
    if cid not in user_state or not user_state[cid].get('awaiting'):
        return
    
    if m.text == '❌ Отмена':
        user_state[cid]['awaiting'] = False
        bot.send_message(cid, '❌ Отменено', reply_markup=telebot.types.ReplyKeyboardRemove())
        return
    
    if m.text not in COLORS:
        bot.send_message(cid, '❌ Выбери цвет кнопками')
        return
    
    try:
        bot.send_message(cid, '🎨 Обрабатываю...', reply_markup=telebot.types.ReplyKeyboardRemove())
        
        success = simple_hair_change('input.jpg', 'output.jpg', COLORS[m.text])
        
        if success and os.path.exists('output.jpg'):
            with open('output.jpg', 'rb') as f:
                bot.send_photo(cid, f, caption=f'✅ Готово! Цвет: {m.text}')
        
        # Чистка
        for f in ['input.jpg', 'output.jpg']:
            try: os.remove(f)
            except: pass
        
        user_state[cid]['awaiting'] = False
    except Exception as e:
        bot.send_message(cid, f'❌ Ошибка: {e}')
        user_state[cid]['awaiting'] = False

if __name__ == '__main__':
    print("🚀 Бот запущен")
    bot.polling(none_stop=True)